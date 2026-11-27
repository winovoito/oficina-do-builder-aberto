import json
from pathlib import Path

import pytest

from oficina import provedores, rag
from oficina.rag_simulado import criar_modelo_simulado

COLECOES = ["juridico", "saude", "financas"]
RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _falso(monkeypatch):
    monkeypatch.setenv("OFICINA_PROVEDOR", "falso")


def _preparar(nome):
    col = rag.carregar_colecao(nome)
    provedores.usar_resposta_falsa(criar_modelo_simulado(col))
    return col, rag.Indice(col["documentos"])


@pytest.mark.parametrize("nome", COLECOES)
def test_formato_da_colecao(nome):
    col = rag.carregar_colecao(nome)
    assert len(col["documentos"]) == 30 and len(col["perguntas"]) == 25
    tipos = [q["tipo"] for q in col["perguntas"]]
    assert (tipos.count("resposta"), tipos.count("sem_resposta"), tipos.count("fora_do_escopo")) == (18, 5, 2)
    assert sum(bool(d.get("injetado")) for d in col["documentos"]) == 1


@pytest.mark.parametrize("nome", COLECOES)
def test_hibrido_nao_perde_para_o_vetorial(nome):
    col, ix = _preparar(nome)
    assert rag.recall_e_mrr(ix, col["perguntas"], "hibrido")[0] >= rag.recall_e_mrr(ix, col["perguntas"], "vetorial")[0]


@pytest.mark.parametrize("nome", COLECOES)
def test_referencia_da_colecao(nome):
    _preparar(nome)
    r = rag.rodar_referencia(nome)
    assert r["respostas_ok"]["resposta"] + r["respostas_ok"]["sem_resposta"] + r["respostas_ok"]["fora_do_escopo"] >= 20
    assert r["respostas_ok"]["sem_resposta"] == 5 and r["respostas_ok"]["fora_do_escopo"] == 2


@pytest.mark.parametrize("nome", COLECOES)
def test_documento_injetado_nao_chega_ao_modelo_nem_altera_respostas(nome):
    col, ix = _preparar(nome)
    base = provedores._resposta_falsa
    vistos = []
    provedores.usar_resposta_falsa(lambda s, m: (vistos.append(m), base(s, m))[1])
    for q in col["perguntas"]:
        r = rag.perguntar_ao_acervo(ix, q["pergunta"], q["papel"])
        assert "999" not in r.resposta and rag.CANARIO not in r.resposta
    assert vistos and all("CANARIO-RAG-91" not in m and "999 dias" not in m for m in vistos)


def test_modelo_que_obedece_a_injecao_nao_consegue_citar_o_documento_injetado():
    col, ix = _preparar("juridico")
    injetado = next(d["id"] for d in col["documentos"] if d.get("injetado"))
    provedores.usar_resposta_falsa(lambda s, m: json.dumps({"resposta": "O prazo é de 999 dias.", "citacoes": [injetado + "#0"], "recusou": False}))
    q = col["perguntas"][0]
    trechos = ix.buscar(q["pergunta"], papel="gestor") + [t for t in ix.trechos if t["doc_id"] == injetado]
    r = rag.responder(q["pergunta"], trechos)
    assert r.recusou and "999" not in r.resposta


@pytest.mark.parametrize("nome", COLECOES)
def test_filtro_de_permissao(nome):
    col, ix = _preparar(nome)
    restritas = [q for q in col["perguntas"] if q["tipo"] == "resposta" and q["papel"] == "gestor"]
    assert restritas
    for q in restritas:
        for papel in ("visitante", "colaborador"):
            assert all(t["acesso"] != "restrito" for t in ix.buscar(q["pergunta"], "hibrido", 10, papel))
            assert rag.perguntar_ao_acervo(ix, q["pergunta"], papel).recusou
        assert not rag.perguntar_ao_acervo(ix, q["pergunta"], "gestor").recusou


def test_papel_desconhecido_e_erro():
    _, ix = _preparar("saude")
    with pytest.raises(ValueError):
        ix.buscar("qualquer", papel="admin")


def test_citacao_inexistente_nunca_e_aceita():
    col, ix = _preparar("saude")
    provedores.usar_resposta_falsa(lambda s, m: json.dumps({"resposta": "8 horas.", "citacoes": ["SAU-99#0"], "recusou": False}))
    q = col["perguntas"][0]
    assert rag.perguntar_ao_acervo(ix, q["pergunta"], "visitante").recusou


def test_resposta_sem_citacao_e_rejeitada_e_a_frase_de_recusa_e_fixa():
    col, ix = _preparar("saude")
    provedores.usar_resposta_falsa(lambda s, m: json.dumps({"resposta": "8 horas.", "citacoes": [], "recusou": False}))
    assert rag.perguntar_ao_acervo(ix, col["perguntas"][0]["pergunta"], "visitante").recusou
    provedores.usar_resposta_falsa(lambda s, m: json.dumps({"resposta": "sei lá", "citacoes": [], "recusou": True}))
    assert rag.perguntar_ao_acervo(ix, col["perguntas"][0]["pergunta"], "visitante").resposta == rag.FRASE_RECUSA


def test_vazamento_do_canario_na_resposta_e_bloqueado():
    col, ix = _preparar("saude")
    q = col["perguntas"][0]
    tid = ix.buscar(q["pergunta"], papel="visitante")[0]["id"]
    provedores.usar_resposta_falsa(lambda s, m: json.dumps({"resposta": "CANARIO-RAG-91", "citacoes": [tid], "recusou": False}))
    assert rag.perguntar_ao_acervo(ix, q["pergunta"], "visitante").recusou


def test_chunking_por_estrutura_e_rrf():
    col = rag.carregar_colecao("juridico")
    t = rag.dividir_em_trechos(col["documentos"][0])
    assert len(t) == 3 and t[0]["id"] == "JUR-01#0" and all(x["titulo"] in x["texto"] for x in t)
    assert rag.rrf([[1, 2, 3], [3, 4, 1]])[:2] == [1, 3]


def test_bm25_acha_codigo_exato_e_stemming():
    col, ix = _preparar("juridico")
    assert ix.buscar("FCI-3", "bm25", 1, "gestor")[0]["doc_id"] == "JUR-06"
    assert rag.tokens("estagiário") == rag.tokens("estagiários")


def test_juiz_calibrado():
    casos = json.loads((RAIZ / "dados" / "rag" / "calibracao_juiz.json").read_text("utf-8"))

    def juiz_simulado(sistema, mensagem):
        ref = rag.re.search(r"<referencia>(.*?)</referencia>", mensagem).group(1)
        resp = rag.re.search(r"<resposta>(.*?)</resposta>", mensagem).group(1)
        extra = bool(rag.re.search(r"\d+ dias", resp)) and ref not in resp or "automático" in resp
        return json.dumps({"contem_referencia": ref in resp, "inventa_algo": extra})
    provedores.usar_resposta_falsa(juiz_simulado)
    assert rag.calibrar_juiz(casos) >= 0.8
