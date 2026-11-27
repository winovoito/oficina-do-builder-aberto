"""Lab 3 · Pipeline de 3 prompts (extrair → classificar → responder) com regras em código.

Cada etapa é um prompt versionado em `prompts/` e devolve um objeto validado (Pydantic).
O que NÃO pode falhar (escalar casos graves, bloquear promessas fora da política) fica em
código, não no prompt.

Winovoito · Apache-2.0 · Feito e revisado por IAs. Orquestrado por humanos.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from oficina import provedores

PASTA_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
CANARIO = "CANARIO-CC-7f3a"
LIMITE_VALOR_ALTO = 3000.0

TipoProblema = Literal[
    "defeito", "entrega", "cobranca", "produto_errado_ou_incompleto", "atendimento", "informacao", "outro"
]


class Fatos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    e_reclamacao: bool
    produto: str | None = None
    problema: str = Field(default="", max_length=200)
    tipo_problema: TipoProblema = "outro"
    valor_mencionado: float | None = Field(default=None, ge=0)
    dano_fisico: bool = False
    reincidencia: bool = False
    ameaca_juridica: bool = False


class Classificacao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gravidade: Literal["baixa", "media", "alta"]
    motivo: str = Field(max_length=160)


class Rascunho(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assunto: str = Field(max_length=80)
    texto: str = Field(min_length=1, max_length=600)


class Resultado(BaseModel):
    encerrado_em: Literal["nao_e_reclamacao", "escalado", "rascunho"]
    fatos: Fatos
    classificacao: Classificacao | None = None
    rascunho: Rascunho | None = None
    escalar_humano: bool = False
    motivo_escalada: str = ""
    etapas_chamadas: list[str] = Field(default_factory=list)


def carregar_prompt(arquivo: str) -> str:
    return (PASTA_PROMPTS / arquivo).read_text(encoding="utf-8")


def etapa(prompt_arquivo: str, entrada: str, esquema: type[BaseModel], tentativas: int = 2) -> BaseModel:
    """Chama um prompt e valida a saída. Se falhar, devolve o erro ao modelo (até `tentativas`)."""
    sistema = carregar_prompt(prompt_arquivo)

    def validar(dados: Any) -> BaseModel:
        try:
            return esquema.model_validate(dados)
        except ValidationError as e:
            # ValueError é o que `perguntar_json` sabe tentar de novo, com a mensagem do erro.
            raise ValueError("; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())) from e

    return provedores.perguntar_json(entrada, sistema, validar, tentativas=tentativas)


# --- Regras em código -------------------------------------------------------------------

# Promessas que a política reserva a um humano (aplicadas ao rascunho, depois do modelo).
_PROMESSAS = [
    r"\breembols", r"\bdevolveremos\b", r"\bestorn", r"\btroca(remos|mos)\b", r"\bsubstitu(iremos|ição gratuita)",
    r"\bconsert(aremos|o gratuito)\b", r"\bdesconto", r"\bindeniza", r"\bgarantimos\b",
    r"\b(em|dentro de|até)\s+\d+\s*(dias|horas|h|úteis)", r"\bamanhã\b", r"\bem até\b",
]
_DADOS_SENSIVEIS = [r"\bcpf\b", r"\bsenha\b", r"número do cart", r"\bcvv\b"]


def promessas_proibidas(texto: str) -> list[str]:
    """Devolve os trechos do texto que prometem algo que só um humano pode prometer."""
    achados = []
    baixo = texto.lower()
    for padrao in _PROMESSAS + _DADOS_SENSIVEIS:
        m = re.search(padrao, baixo)
        if m:
            achados.append(m.group(0))
    if CANARIO.lower() in baixo:
        achados.append("vazamento do código interno")
    return achados


def deve_escalar(fatos: Fatos, classe: Classificacao) -> str:
    """Regra de segurança em código: não depende de o modelo 'lembrar' de escalar."""
    if fatos.dano_fisico:
        return "relato de risco à segurança ou dano físico"
    if classe.gravidade == "alta":
        return "gravidade alta"
    if fatos.valor_mencionado is not None and fatos.valor_mencionado >= LIMITE_VALOR_ALTO:
        return "valor igual ou acima do limite"
    if fatos.ameaca_juridica:
        return "ameaça jurídica"
    return ""


def processar(mensagem: str) -> Resultado:
    chamadas: list[str] = []
    entrada = f"<reclamacao>\n{mensagem.strip()}\n</reclamacao>"
    fatos = etapa("extrair_v1.md", entrada, Fatos)
    chamadas.append("extrair")
    if not fatos.e_reclamacao:
        return Resultado(encerrado_em="nao_e_reclamacao", fatos=fatos, etapas_chamadas=chamadas)

    classe = etapa("classificar_v1.md", f"<fatos>\n{fatos.model_dump_json()}\n</fatos>", Classificacao)
    chamadas.append("classificar")

    motivo = deve_escalar(fatos, classe)
    if motivo:
        return Resultado(
            encerrado_em="escalado", fatos=fatos, classificacao=classe,
            escalar_humano=True, motivo_escalada=motivo, etapas_chamadas=chamadas,
        )

    pacote = json.dumps({"fatos": fatos.model_dump(), "gravidade": classe.gravidade}, ensure_ascii=False)
    rascunho = etapa("responder_v1.md", f"<fatos>\n{pacote}\n</fatos>", Rascunho)
    chamadas.append("responder")

    achados = promessas_proibidas(rascunho.assunto + " " + rascunho.texto)
    if achados:  # nunca entrega rascunho fora da política: manda para um humano
        return Resultado(
            encerrado_em="escalado", fatos=fatos, classificacao=classe, escalar_humano=True,
            motivo_escalada="rascunho fora da política: " + ", ".join(achados), etapas_chamadas=chamadas,
        )
    return Resultado(
        encerrado_em="rascunho", fatos=fatos, classificacao=classe, rascunho=rascunho, etapas_chamadas=chamadas
    )


def avaliar_caso(caso: dict, resultado: Resultado) -> list[str]:
    """Asserções por regra (sem 'juiz' de IA). Devolve a lista de falhas; vazia = passou."""
    falhas = []
    esp = caso["esperado"]
    if resultado.encerrado_em != esp["encerra_em"]:
        falhas.append(f"encerrou em {resultado.encerrado_em}, esperado {esp['encerra_em']}")
    for campo, valor in esp.get("fatos", {}).items():
        if getattr(resultado.fatos, campo) != valor:
            falhas.append(f"fatos.{campo}={getattr(resultado.fatos, campo)!r}, esperado {valor!r}")
    if "gravidade" in esp:
        g = resultado.classificacao.gravidade if resultado.classificacao else None
        if g != esp["gravidade"]:
            falhas.append(f"gravidade {g}, esperado {esp['gravidade']}")
    if resultado.escalar_humano != esp["escala"]:
        falhas.append(f"escalar_humano={resultado.escalar_humano}, esperado {esp['escala']}")
    if resultado.rascunho:
        falhas += [f"promessa proibida: {a}" for a in promessas_proibidas(resultado.rascunho.texto)]
    return falhas


def rodar_referencia(casos: list[dict]) -> dict:
    """Roda todos os casos; devolve aprovados, falhas e se algum caso de segurança quebrou."""
    aprovados, falhas = 0, {}
    for caso in casos:
        try:
            f = avaliar_caso(caso, processar(caso["mensagem"]))
        except ValueError as e:
            f = [f"erro: {e}"]
        if f:
            falhas[caso["id"]] = f
        else:
            aprovados += 1
    return {"aprovados": aprovados, "total": len(casos), "falhas": falhas}
