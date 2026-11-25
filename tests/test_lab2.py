"""Critérios de aceite da Bancada 2 (labs 2a, 2b, 2c e 2d).

Rodam sobre os dados sintéticos e as soluções de referência, sem chave de API.
"""
import pytest
from fastapi.testclient import TestClient

from oficina import churn, demanda, fraude
from oficina.api_churn import criar_app
from oficina.sinteticos import COLUNA_VAZAMENTO, gerar_carteira, gerar_fluxo, gerar_padaria


# ------------------------------------------------------------------ Lab 2a · demanda
@pytest.fixture(scope="module")
def padaria():
    return gerar_padaria()


def test_2a_modelo_vence_baseline_por_15_por_cento(padaria):
    r = demanda.rodar_referencia(padaria)
    assert r["mae_modelo"] <= 0.85 * r["mae_baseline"]


def test_2a_caracteristicas_sem_vazamento(padaria):
    assert demanda.checar_vazamento(padaria) == []


def test_2a_detector_pega_media_movel_sem_shift(padaria):
    def com_vazamento(df):
        f = demanda.criar_caracteristicas(df)
        f["media_7"] = f.groupby("loja")["vendas"].transform(lambda s: s.rolling(7).mean())
        return f
    assert "media_7" in demanda.checar_vazamento(padaria, com_vazamento)


# ------------------------------------------------------------------ Lab 2b · churn
@pytest.fixture(scope="module")
def fluxo():
    return gerar_fluxo()


@pytest.fixture(scope="module")
def ref_churn(fluxo, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("modelo")
    r = churn.rodar_referencia(fluxo, pasta)
    r["pasta"] = pasta
    return r


def test_2b_coluna_com_vazamento_detectada(fluxo):
    assert churn.detectar_vazamento(fluxo) == [COLUNA_VAZAMENTO]


def test_2b_auc_minima(ref_churn):
    assert max(ref_churn["auc_logistica"], ref_churn["auc_boosting"]) >= 0.80


def test_2b_limiar_por_custo_bate_limiar_0_5(ref_churn):
    assert ref_churn["custo"] < ref_churn["custo_0_5"]


def test_2b_fatores_explicam_cliente_de_risco(ref_churn):
    t = ref_churn["teste"].sort_values("prob").iloc[[-1]]
    fatores = churn.fatores_locais(ref_churn["modelo"], t, ref_churn["treino"])
    assert 1 <= len(fatores) <= 3
    assert all(f["efeito"] > 0 for f in fatores)


def test_2b_carregar_recusa_arquivo_alterado(ref_churn, tmp_path):
    import shutil
    copia = tmp_path / "m"
    shutil.copytree(ref_churn["pasta"], copia)
    with open(copia / "modelo_churn.joblib", "ab") as f:
        f.write(b"alterado")
    with pytest.raises(ValueError):
        churn.carregar(copia)


# ------------------------------------------------------------------ Lab 2c · fraude
@pytest.fixture(scope="module")
def ref_fraude():
    return fraude.rodar_referencia(gerar_carteira())


def test_2c_ajuste_melhora_pr_auc(ref_fraude):
    pr = ref_fraude["pr_auc"]
    assert max(pr["com_peso"], pr["subamostrado"]) > pr["sem_ajuste"]


def test_2c_sistema_combinado_pega_mais_por_caso(ref_fraude):
    assert ref_fraude["fila_sistema"]["fraudes_por_caso"] > ref_fraude["fila_modelo"]["fraudes_por_caso"]


def test_2c_fila_respeita_capacidade(ref_fraude):
    dias = 60 - 40
    assert ref_fraude["fila_sistema"]["revisados"] <= fraude.CAPACIDADE_DIARIA * dias


# ------------------------------------------------------------------ Lab 2d · API
@pytest.fixture(scope="module")
def cliente_api(ref_churn):
    return TestClient(criar_app(ref_churn["pasta"], referencia=ref_churn["treino"]))


VALIDO = {"plano": "basico", "mensalidade": 49, "tempo_casa_meses": 4, "chamados_90d": 5,
          "uso_semanal_horas": 2, "dias_atraso_pagamento": 30, "nps": 4}


def test_2d_cliente_valido(cliente_api):
    r = cliente_api.post("/prever_churn", json=VALIDO)
    assert r.status_code == 200
    corpo = r.json()
    assert 0 <= corpo["probabilidade"] <= 1
    assert corpo["versao_modelo"] == "churn-1.0.0"
    assert len(corpo["fatores"]) <= 3


@pytest.mark.parametrize("ruim", [
    {"tempo_casa_meses": -3}, {"plano": "ouro"}, {"mensalidade": "caro"}, {"extra": 1},
])
def test_2d_entrada_invalida_devolve_422(cliente_api, ruim):
    assert cliente_api.post("/prever_churn", json={**VALIDO, **ruim}).status_code == 422


def test_2d_campo_faltando_devolve_422(cliente_api):
    sem_plano = {k: v for k, v in VALIDO.items() if k != "plano"}
    assert cliente_api.post("/prever_churn", json=sem_plano).status_code == 422


def test_2d_cliente_no_limite(cliente_api):
    r = cliente_api.post("/prever_churn", json={**VALIDO, "tempo_casa_meses": 0, "chamados_90d": 0,
                                                "dias_atraso_pagamento": 0, "nps": None})
    assert r.status_code == 200


def test_2d_saude(cliente_api):
    assert cliente_api.get("/saude").json()["versao_modelo"] == "churn-1.0.0"
