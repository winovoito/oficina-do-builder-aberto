"""Lab 4 · RAG: busca híbrida (vetorial + BM25 + RRF), filtro de permissão, resposta com citações.

O embedder padrão é LÉXICO (TF-IDF de caracteres + SVD): roda local, sem download e de forma
determinística, o que mantém os testes estáveis. Para o modelo multilíngue de verdade
(sentence-transformers), use `embedder_multilingue()` no notebook.

Winovoito · Apache-2.0 · Feito e revisado por IAs. Orquestrado por humanos.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import numpy as np
from pydantic import BaseModel, ConfigDict, ValidationError
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from oficina import provedores

RAIZ = Path(__file__).resolve().parent.parent
FRASE_RECUSA = "Não encontrei essa informação nos documentos disponíveis."
CANARIO = "CANARIO-RAG-91"
PERMISSOES = {"visitante": {"publico"}, "colaborador": {"publico", "interno"}, "gestor": {"publico", "interno", "restrito"}}
STOPWORDS = set("""a o as os um uma de do da dos das em no na nos nas por para com sem e ou que qual quais quanto quantos quantas
quando como onde se ao aos à é são ser há ate até posso pode podem tem têm mais menos sobre entre vale valem""".split())


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def radical(w: str) -> str:
    """'Stemming' bem simples: os 6 primeiros caracteres (estagiário e estagiários viram 'estagi')."""
    return w[:6] if w.isalpha() else w


def tokens(t: str) -> list[str]:
    return [radical(w) for w in re.findall(r"[a-z0-9]+", sem_acento(t.lower())) if w not in STOPWORDS and len(w) > 1]


# --- Dados e trechos -----------------------------------------------------------------------

def carregar_colecao(nome: str) -> dict:
    return json.loads((RAIZ / "dados" / "rag" / f"{nome}.json").read_text("utf-8"))


def dividir_em_trechos(doc: dict) -> list[dict]:
    """Divide por estrutura (parágrafos), não por tamanho. O título entra em cada trecho."""
    paragrafos = [p.strip() for p in doc["texto"].split("\n\n") if p.strip()]
    corpo = paragrafos[1:] if len(paragrafos) > 1 else paragrafos  # a 1ª linha repete o título
    trechos = []
    for n, p in enumerate(corpo):
        trechos.append({"id": f"{doc['id']}#{n}", "doc_id": doc["id"], "acesso": doc["acesso"],
                        "titulo": doc["titulo"], "texto": f"{doc['titulo']}. {p}"})
    return trechos


# --- Embeddings ------------------------------------------------------------------------------

class EmbedderLexico:
    """TF-IDF de n-gramas de caracteres + SVD. Local, determinístico, sem download."""

    def __init__(self, dim: int = 48):
        self.dim = dim
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), preprocessor=lambda t: sem_acento(t.lower()))
        self.svd: TruncatedSVD | None = None

    def ajustar(self, textos: list[str]) -> "EmbedderLexico":
        x = self.tfidf.fit_transform(textos)
        self.svd = TruncatedSVD(n_components=min(self.dim, x.shape[1] - 1, x.shape[0] - 1), random_state=0).fit(x)
        return self

    def __call__(self, textos: list[str]) -> np.ndarray:
        v = self.svd.transform(self.tfidf.transform(textos))
        return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)


def embedder_multilingue(nome: str = "paraphrase-multilingual-MiniLM-L12-v2") -> Callable[[list[str]], np.ndarray]:
    """Modelo de embeddings de código aberto (requer `pip install sentence-transformers` e rede na 1ª vez)."""
    from sentence_transformers import SentenceTransformer  # type: ignore

    modelo = SentenceTransformer(nome)
    return lambda textos: np.asarray(modelo.encode(textos, normalize_embeddings=True))


# --- Índice e busca --------------------------------------------------------------------------

class Indice:
    def __init__(self, documentos: list[dict], embedder: Callable[[list[str]], np.ndarray] | None = None):
        self.trechos = [t for d in documentos for t in dividir_em_trechos(d)]
        textos = [t["texto"] for t in self.trechos]
        self.embedder = embedder or EmbedderLexico().ajustar(textos)
        self.matriz = self.embedder(textos)
        self._tf = [Counter(tokens(t)) for t in textos]
        self._len = np.array([sum(c.values()) for c in self._tf], dtype=float)
        df: Counter = Counter()
        for c in self._tf:
            df.update(c.keys())
        n = len(textos)
        self._idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def _permitidos(self, papel: str | None) -> np.ndarray:
        if papel is None:
            return np.ones(len(self.trechos), dtype=bool)
        if papel not in PERMISSOES:
            raise ValueError(f"papel desconhecido: {papel!r}")
        return np.array([t["acesso"] in PERMISSOES[papel] for t in self.trechos])

    def _rank(self, notas: np.ndarray, papel: str | None, k: int) -> list[int]:
        ok = self._permitidos(papel)  # o filtro vem ANTES do ranking: o que não pode ver nem entra
        notas = np.where(ok, notas, -np.inf)
        ordem = np.argsort(-notas, kind="stable")
        return [int(i) for i in ordem[:k] if np.isfinite(notas[i])]

    def notas_vetorial(self, pergunta: str) -> np.ndarray:
        return self.matriz @ self.embedder([pergunta])[0]

    def notas_bm25(self, pergunta: str, k1: float = 1.5, b: float = 0.75) -> np.ndarray:
        media = self._len.mean()
        notas = np.zeros(len(self.trechos))
        for w in set(tokens(pergunta)):
            idf = self._idf.get(w)
            if idf is None:
                continue
            for i, tf in enumerate(self._tf):
                f = tf.get(w, 0)
                if f:
                    notas[i] += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * self._len[i] / media))
        return notas

    def buscar(self, pergunta: str, modo: str = "hibrido", k: int = 5, papel: str | None = None) -> list[dict]:
        if modo == "vetorial":
            idx = self._rank(self.notas_vetorial(pergunta), papel, k)
        elif modo == "bm25":
            idx = self._rank(self.notas_bm25(pergunta), papel, k)
        elif modo == "hibrido":
            idx = rrf([self._rank(self.notas_vetorial(pergunta), papel, 50), self._rank(self.notas_bm25(pergunta), papel, 50)])[:k]
        else:
            raise ValueError("modo deve ser 'vetorial', 'bm25' ou 'hibrido'")
        return [self.trechos[i] for i in idx]


def rrf(listas: list[list[int]], c: int = 60) -> list[int]:
    """Reciprocal Rank Fusion: junta rankings sem precisar comparar as notas de cada um."""
    pontos: dict[int, float] = {}
    for lista in listas:
        for pos, i in enumerate(lista):
            pontos[i] = pontos.get(i, 0.0) + 1.0 / (c + pos + 1)
    return sorted(pontos, key=lambda i: (-pontos[i], i))


def recall_e_mrr(indice: Indice, perguntas: list[dict], modo: str, k: int = 5) -> tuple[float, float]:
    com_doc = [q for q in perguntas if q["tipo"] == "resposta"]
    acertos, rr = 0, 0.0
    for q in com_doc:
        docs = [t["doc_id"] for t in indice.buscar(q["pergunta"], modo, k, papel=q["papel"])]
        if q["doc_esperado"] in docs:
            acertos += 1
            rr += 1.0 / (docs.index(q["doc_esperado"]) + 1)
    return acertos / len(com_doc), rr / len(com_doc)


# --- Defesa em código contra instruções escondidas nos documentos ---------------------------

_SUSPEITO = [r"ignore (todas )?as (regras|instru)", r"para o assistente", r"responda (a )?qualquer pergunta", r"esque[cç]a (as|todas)",
             r"desconsidere", r"\bsystem prompt\b", r"voc[eê] (agora )?(deve|[eé])\b.*\bassistente\b"]


def trecho_suspeito(texto: str) -> bool:
    baixo = sem_acento(texto.lower())
    return any(re.search(sem_acento(p), baixo) for p in _SUSPEITO)


# --- Resposta com citações ---------------------------------------------------------------------

class Resposta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resposta: str
    citacoes: list[str]
    recusou: bool


def montar_mensagem(pergunta: str, trechos: list[dict]) -> str:
    corpo = "\n".join(f"[{t['id']}] {t['texto']}" for t in trechos)
    return f"<trechos>\n{corpo}\n</trechos>\n<pergunta>{pergunta}</pergunta>"


def responder(pergunta: str, trechos: list[dict], tentativas: int = 2) -> Resposta:
    """Responde usando os trechos. Código confere: citações existem; recusa usa a frase fixa."""
    seguros = [t for t in trechos if not trecho_suspeito(t["texto"])]
    permitidas = {t["id"] for t in seguros}
    sistema = (PASTA := RAIZ / "prompts" / "responder_rag_v1.md").read_text("utf-8")

    def validar(dados: Any) -> Resposta:
        try:
            r = Resposta.model_validate(dados)
        except ValidationError as e:
            raise ValueError("; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())) from e
        inexistentes = [c for c in r.citacoes if c not in permitidas]
        if inexistentes:
            raise ValueError(f"citações inexistentes nos trechos recebidos: {inexistentes}")
        if r.recusou:
            return Resposta(resposta=FRASE_RECUSA, citacoes=[], recusou=True)
        if not r.citacoes:
            raise ValueError("resposta sem citação: cite os identificadores ou recuse")
        if CANARIO.lower() in r.resposta.lower():
            raise ValueError("a resposta vazou o código interno")
        return r

    if not seguros:
        return Resposta(resposta=FRASE_RECUSA, citacoes=[], recusou=True)
    try:
        return provedores.perguntar_json(montar_mensagem(pergunta, seguros), sistema, validar, tentativas=tentativas)
    except ValueError:
        # Sem resposta válida: o sistema prefere recusar a entregar algo não verificado.
        return Resposta(resposta=FRASE_RECUSA, citacoes=[], recusou=True)


def perguntar_ao_acervo(indice: Indice, pergunta: str, papel: str, k: int = 5) -> Resposta:
    return responder(pergunta, indice.buscar(pergunta, "hibrido", k, papel=papel))


# --- Avaliação ---------------------------------------------------------------------------------

def avaliar_resposta(q: dict, r: Resposta) -> bool:
    """Regra: perguntas respondíveis devem conter o fato esperado e citar o documento certo;
    as demais devem recusar com a frase fixa."""
    if q["tipo"] == "resposta":
        return (not r.recusou and sem_acento(q["contem"].lower()) in sem_acento(r.resposta.lower())
                and any(c.startswith(q["doc_esperado"] + "#") for c in r.citacoes))
    return r.recusou and r.resposta == FRASE_RECUSA


def rodar_referencia(nome: str, embedder: Callable | None = None) -> dict:
    col = carregar_colecao(nome)
    indice = Indice(col["documentos"], embedder)
    out: dict[str, Any] = {"colecao": nome}
    for modo in ("vetorial", "bm25", "hibrido"):
        out[f"recall5_{modo}"], out[f"mrr_{modo}"] = recall_e_mrr(indice, col["perguntas"], modo)
    ok = {"resposta": 0, "sem_resposta": 0, "fora_do_escopo": 0}
    tot = dict.fromkeys(ok, 0)
    for q in col["perguntas"]:
        tot[q["tipo"]] += 1
        ok[q["tipo"]] += avaliar_resposta(q, perguntar_ao_acervo(indice, q["pergunta"], q["papel"]))
    out["respostas_ok"] = ok
    out["respostas_total"] = tot
    return out


# --- Juiz de respostas (para o notebook, calibrado com casos rotulados por humano) ------------

class Veredito(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contem_referencia: bool
    inventa_algo: bool

    @property
    def aprovada(self) -> bool:
        return self.contem_referencia and not self.inventa_algo


def julgar(pergunta: str, referencia: str, resposta: str) -> Veredito:
    sistema = (RAIZ / "prompts" / "juiz_v1.md").read_text("utf-8")
    msg = f"<pergunta>{pergunta}</pergunta>\n<referencia>{referencia}</referencia>\n<resposta>{resposta}</resposta>"

    def validar(d: Any) -> Veredito:
        try:
            return Veredito.model_validate(d)
        except ValidationError as e:
            raise ValueError(str(e)) from e

    return provedores.perguntar_json(msg, sistema, validar)


def calibrar_juiz(casos: list[dict]) -> float:
    """Concordância entre o juiz e o rótulo humano nos casos de calibração (meta: ≥ 4 de 5)."""
    acertos = sum(julgar(c["pergunta"], c["referencia"], c["resposta"]).aprovada == c["humano_aprova"] for c in casos)
    return acertos / len(casos)
