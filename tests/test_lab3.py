import json
import os
from pathlib import Path

import pytest

from oficina import provedores
from oficina.pipeline_prompts import (
    Fatos, Classificacao, avaliar_caso, deve_escalar, etapa, processar, promessas_proibidas, rodar_referencia,
)

CASOS = json.loads((Path(__file__).resolve().parent.parent / "dados" / "casos_teste.json").read_text("utf-8"))
_atual: dict = {}


def _modelo_simulado(sistema: str, mensagem: str) -> str:
    sim = _atual["modelo_simulado"]
    if "# Extrair" in sistema:
        return json.dumps(sim["fatos"], ensure_ascii=False)
    if "# Classificar" in sistema:
        return json.dumps(sim["classificacao"], ensure_ascii=False)
    return json.dumps(sim["rascunho"], ensure_ascii=False)


@pytest.fixture(autouse=True)
def _falso(monkeypatch):
    monkeypatch.setenv("OFICINA_PROVEDOR", "falso")
    provedores.usar_resposta_falsa(_modelo_simulado)


def _rodar(caso):
    _atual.clear(); _atual.update(caso)
    return processar(caso["mensagem"])


def test_distribuicao_dos_20_casos():
    cont = {}
    for c in CASOS:
        cont[c["categoria"]] = cont.get(c["categoria"], 0) + 1
    assert len(CASOS) == 20
    assert cont == {"normal": 12, "ambigua": 3, "nao_e_reclamacao": 2, "manipulacao": 2, "escalar": 1}


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c["id"])
def test_cada_caso_passa_nas_asserções(caso):
    assert avaliar_caso(caso, _rodar(caso)) == []


def test_referencia_17_de_20():
    def por_caso():
        ok = 0
        for c in CASOS:
            ok += not avaliar_caso(c, _rodar(c))
        return ok
    assert por_caso() >= 17


def test_nao_reclamacao_encerra_sem_chamar_as_outras_etapas():
    r = _rodar(next(c for c in CASOS if c["id"] == "c16"))
    assert r.etapas_chamadas == ["extrair"] and r.rascunho is None


def test_caso_de_escalada_sempre_escala_sem_rascunho():
    r = _rodar(next(c for c in CASOS if c["id"] == "c20"))
    assert r.escalar_humano and r.rascunho is None and "responder" not in r.etapas_chamadas


def test_codigo_escala_mesmo_se_o_modelo_classificar_errado():
    caso = dict(next(c for c in CASOS if c["id"] == "c20"))
    caso["modelo_simulado"] = {**caso["modelo_simulado"], "classificacao": {"gravidade": "baixa", "motivo": "x"}}
    r = _rodar(caso)
    assert r.escalar_humano and r.rascunho is None


def test_rascunho_com_promessa_vai_para_humano():
    caso = dict(next(c for c in CASOS if c["id"] == "c18"))
    caso["modelo_simulado"] = {**caso["modelo_simulado"], "rascunho": {"assunto": "Ok", "texto": "Vamos reembolsar em 24 horas."}}
    r = _rodar(caso)
    assert r.escalar_humano and r.rascunho is None and "fora da política" in r.motivo_escalada


def test_vazamento_do_canario_e_bloqueado():
    assert promessas_proibidas("meu código é CANARIO-CC-7f3a")


def test_valor_alto_e_ameaca_juridica_escalam():
    f = Fatos(e_reclamacao=True, valor_mencionado=3500)
    assert deve_escalar(f, Classificacao(gravidade="media", motivo="x"))
    f = Fatos(e_reclamacao=True, ameaca_juridica=True)
    assert deve_escalar(f, Classificacao(gravidade="baixa", motivo="x"))
    assert deve_escalar(Fatos(e_reclamacao=True), Classificacao(gravidade="baixa", motivo="x")) == ""


def test_etapa_tenta_de_novo_devolvendo_o_erro():
    chamadas = []
    def modelo(sistema, mensagem):
        chamadas.append(mensagem)
        if len(chamadas) == 1:
            return '{"gravidade": "gravíssima", "motivo": "x"}'
        return '{"gravidade": "alta", "motivo": "ok"}'
    provedores.usar_resposta_falsa(modelo)
    r = etapa("classificar_v1.md", "<fatos>{}</fatos>", Classificacao)
    assert r.gravidade == "alta" and len(chamadas) == 2 and "rejeitada" in chamadas[1]


def test_etapa_desiste_depois_de_2_tentativas():
    provedores.usar_resposta_falsa(lambda s, m: "não sei")
    with pytest.raises(ValueError, match="3 tentativas"):
        etapa("classificar_v1.md", "x", Classificacao)


def test_prompts_seguem_o_padrao():
    pasta = Path(__file__).resolve().parent.parent / "prompts"
    for nome in ["extrair_v1.md", "classificar_v1.md", "responder_v1.md"]:
        t = (pasta / nome).read_text("utf-8")
        for secao in ["## Papel", "## Restrições", "## Formato de saída", "## Saída de emergência"]:
            assert secao in t, (nome, secao)
        assert "DADO" in t or "dado, não instrução" in t
