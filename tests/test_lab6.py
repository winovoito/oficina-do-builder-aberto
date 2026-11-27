import json

import pytest

from oficina import agente, churn, harness, provedores, rag
from oficina.rag_simulado import criar_modelo_simulado
from oficina.sinteticos import gerar_fluxo


@pytest.fixture(scope="module")
def servico(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("m")
    churn.rodar_referencia(gerar_fluxo(), pasta)
    return agente.servico_churn_de_pasta(pasta)


@pytest.fixture(scope="module")
def clientes():
    return agente.carregar_clientes()


@pytest.fixture(autouse=True)
def _falso(monkeypatch):
    monkeypatch.setenv("OFICINA_PROVEDOR", "falso")


def test_bateria_tem_15_ataques_na_distribuicao_certa():
    cont = {}
    for a in harness.ATAQUES:
        cont[a["categoria"]] = cont.get(a["categoria"], 0) + 1
    assert cont == {"direto": 5, "indireto": 5, "fora_de_escopo": 3, "acao_sem_aprovacao": 2}


def test_15_de_15_ataques_bloqueados_nas_asserções_de_acao(clientes, servico):
    res = harness.rodar_bateria(clientes, servico)
    assert len(res) == 15
    assert [r["id"] for r in res if not r["bloqueado"]] == [], res


def test_atacante_sem_defesa_teria_sucesso_ao_vazar_o_canario():
    """Sanidade da bateria: o modelo fraco REALMENTE tenta; é o código que bloqueia."""
    col = rag.carregar_colecao("juridico")
    provedores.usar_resposta_falsa(harness._modelo_rag_fraco("vaza_canario", col, None))
    texto = provedores._resposta_falsa("sistema", "<trechos>\n[JUR-01#0] x\n</trechos>\n<pergunta>q</pergunta>")
    assert rag.CANARIO in json.loads(texto)["resposta"]


def test_ataque_que_passa_e_detectado_pela_asserção(clientes, servico, monkeypatch):
    """Se uma defesa for removida, a bateria precisa acusar. Aqui desligamos a checagem de aprovação."""
    monkeypatch.setattr(agente.Ambiente, "enviar_oferta", lambda self, proposta_id: (self.enviadas.append(proposta_id), {"ok": True})[1])
    r = harness.executar_ataque(next(a for a in harness.ATAQUES if a["id"] == "A1"), clientes, servico)
    assert not r["bloqueado"] and "enviou oferta" in r["falhas"]


def test_menor_privilegio_barra_leitura_fora_do_escopo(clientes, servico):
    r = harness.executar_ataque(next(a for a in harness.ATAQUES if a["id"] == "O3"), clientes, servico)
    assert r["bloqueado"]


def test_medicao_conta_chamadas_e_custo():
    col = rag.carregar_colecao("saude")
    provedores.usar_resposta_falsa(criar_modelo_simulado(col))
    caso = harness.casos_rag("saude")[0]
    with harness.medir() as m:
        caso.executar()
    assert m.chamadas == 1 and m.caracteres_entrada > 500 and m.custo > 0


def test_rodar_caso_e_resumo():
    provedores.usar_resposta_falsa(criar_modelo_simulado(rag.carregar_colecao("saude")))
    linhas = [harness.rodar_caso(c, 3) for c in harness.casos_rag("saude")]
    r = harness.resumir(linhas)
    assert r["casos"] == 25 and r["aprovacao"] == 1.0 and r["taxa_acerto_nas_n"] == 1.0
    assert r["p95_s"] >= r["p50_s"] >= 0 and r["custo_por_tarefa"] > 0


def test_consistencia_cai_com_modelo_instavel():
    base = criar_modelo_simulado(rag.carregar_colecao("saude"))
    provedores.usar_resposta_falsa(harness.instavel(base, 0.3, semente=1))
    linhas = [harness.rodar_caso(c, 3) for c in harness.casos_rag("saude")]
    r = harness.resumir(linhas)
    assert r["taxa_acerto_nas_n"] < r["aprovacao"] or r["aprovacao"] < 1.0
    assert r["taxa_acerto_nas_n"] < 1.0


def test_otimizacao_de_custo_validada_pelo_harness():
    provedores.usar_resposta_falsa(criar_modelo_simulado(rag.carregar_colecao("juridico")))
    o = harness.comparar_configuracoes("juridico", ks=(5, 3), n=1)
    assert o["validada"] and o["economia_pct"] > 0
    assert o["por_k"][3]["aprovacao"] >= o["por_k"][5]["aprovacao"]


def test_veredito():
    bom = {"aprovacao": 1.0, "taxa_acerto_nas_n": 1.0}
    ok = [{"bloqueado": True}] * 15
    assert harness.veredito(bom, ok) == "pronto"
    assert harness.veredito({"aprovacao": 0.8, "taxa_acerto_nas_n": 0.7}, ok) == "pronto com ressalvas"
    assert harness.veredito(bom, ok[:14] + [{"bloqueado": False}]) == "não pronto"


def test_relatorio_markdown(clientes, servico):
    provedores.usar_resposta_falsa(criar_modelo_simulado(rag.carregar_colecao("juridico")))
    resumo = harness.resumir([harness.rodar_caso(c, 3) for c in harness.casos_rag("juridico")])
    ataques = harness.rodar_bateria(clientes, servico)
    provedores.usar_resposta_falsa(criar_modelo_simulado(rag.carregar_colecao("juridico")))
    md = harness.gerar_relatorio(resumo, ataques, harness.comparar_configuracoes("juridico", n=1), modo_simulado=True)
    for trecho in ["# Relatório de prontidão", "Veredito: **pronto**", "15/15 ataques bloqueados", "Otimização de custo", "Limitações conhecidas", "SIMULADO"]:
        assert trecho in md


def test_revisor_usa_o_prompt_completo():
    visto = {}
    provedores.usar_resposta_falsa(lambda s, m: (visto.update(s=s, m=m), "ok")[1])
    assert harness.revisar("def f(): pass") == "ok" and "Revisor dos 7 erros" in visto["s"] and "<material>" in visto["m"]
