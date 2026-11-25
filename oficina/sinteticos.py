"""Dados sintéticos dos labs da Bancada 2.

Todos os dados são gerados aqui, com semente fixa e padrões conhecidos.
Nenhum dado real, nenhuma pessoa real: as empresas (Pão da Esquina, Fluxo,
Carteira) são fictícias. Como sabemos qual padrão colocamos, os testes
automáticos sabem qual resultado é alcançável.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Lab 2a · Pão da Esquina: vendas diárias de pão por loja
# ---------------------------------------------------------------------------

LOJAS = ["Centro", "Bairro Alto", "Praia", "Estação", "Shopping"]

# Feriados fixos fictícios (mês, dia). Datas móveis ficam de fora de propósito:
# o modelo não precisa conhecer o calendário brasileiro inteiro para o lab.
FERIADOS_FIXOS = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)]


def _e_feriado(datas: pd.DatetimeIndex) -> np.ndarray:
    md = list(zip(datas.month, datas.day))
    return np.array([x in FERIADOS_FIXOS for x in md])


def gerar_padaria(semente: int = 7, inicio: str = "2023-01-01", meses: int = 36) -> pd.DataFrame:
    """Vendas diárias (unidades de pão) de 5 lojas por `meses` meses.

    Padrões embutidos: nível por loja, efeito do dia da semana diferente por
    loja (a Praia vende mais no fim de semana, a Estação nos dias úteis),
    sazonalidade anual, feriados, chuva prevista e ruído.
    Colunas: data, loja, feriado, chuva_prevista, vendas.
    """
    rng = np.random.default_rng(semente)
    fim = pd.Timestamp(inicio) + pd.DateOffset(months=meses) - pd.Timedelta(days=1)
    datas = pd.date_range(inicio, fim, freq="D")
    feriado = _e_feriado(datas)

    nivel = {"Centro": 420, "Bairro Alto": 260, "Praia": 300, "Estação": 380, "Shopping": 220}
    # fator por dia da semana (seg=0 ... dom=6)
    semana = {
        "Centro": [1.05, 1.0, 1.0, 1.0, 1.1, 0.9, 0.6],
        "Bairro Alto": [0.9, 0.9, 0.95, 0.95, 1.0, 1.25, 1.3],
        "Praia": [0.7, 0.7, 0.75, 0.8, 0.95, 1.5, 1.6],
        "Estação": [1.2, 1.15, 1.15, 1.15, 1.1, 0.6, 0.45],
        "Shopping": [0.85, 0.85, 0.9, 0.95, 1.1, 1.3, 1.15],
    }
    # a Praia sente muito mais o verão
    amplitude_anual = {"Centro": 0.06, "Bairro Alto": 0.08, "Praia": 0.35, "Estação": 0.05, "Shopping": 0.1}
    efeito_chuva = {"Centro": -0.08, "Bairro Alto": 0.05, "Praia": -0.3, "Estação": -0.05, "Shopping": 0.12}

    # chuva prevista: mais comum no verão
    dia_ano = datas.dayofyear.to_numpy()
    p_chuva = 0.25 + 0.15 * np.cos(2 * np.pi * (dia_ano - 15) / 365.25)

    linhas = []
    for loja in LOJAS:
        chuva = rng.random(len(datas)) < p_chuva
        sazonal = 1 + amplitude_anual[loja] * np.cos(2 * np.pi * (dia_ano - 20) / 365.25)
        fator_semana = np.array(semana[loja])[datas.dayofweek]
        tendencia = 1 + 0.04 * np.arange(len(datas)) / 365.25
        # feriado: a Estação despenca, a Praia sobe
        f_feriado = np.where(feriado, {"Estação": 0.4, "Praia": 1.4}.get(loja, 0.75), 1.0)
        f_chuva = np.where(chuva, 1 + efeito_chuva[loja], 1.0)
        media = nivel[loja] * fator_semana * sazonal * tendencia * f_feriado * f_chuva
        vendas = rng.normal(media, 0.07 * media)
        linhas.append(pd.DataFrame({
            "data": datas, "loja": loja, "feriado": feriado,
            "chuva_prevista": chuva, "vendas": np.clip(np.round(vendas), 0, None).astype(int),
        }))
    return pd.concat(linhas, ignore_index=True).sort_values(["loja", "data"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Lab 2b · Fluxo: churn de clientes de software por assinatura
# ---------------------------------------------------------------------------

PLANOS = {"basico": 49.0, "padrao": 99.0, "premium": 199.0}
COLUNA_VAZAMENTO = "dias_ultimo_acesso_pos_corte"


def gerar_fluxo(n: int = 20_000, semente: int = 11) -> pd.DataFrame:
    """Clientes da Fluxo, um por linha, com o mês de referência da foto.

    `cancelou` = 1 se o cliente cancelou nos 60 dias seguintes ao mês de
    referência (~10%). A coluna `dias_ultimo_acesso_pos_corte` tem VAZAMENTO
    de propósito: foi medida depois do corte e entrega a resposta.
    """
    rng = np.random.default_rng(semente)
    plano = rng.choice(list(PLANOS), size=n, p=[0.45, 0.4, 0.15])
    mensalidade = np.array([PLANOS[p] for p in plano]) * rng.choice([1.0, 0.9, 0.8], size=n, p=[0.7, 0.2, 0.1])
    tempo_casa = np.round(rng.gamma(2.0, 9.0, size=n)).astype(int)  # meses
    chamados = rng.poisson(0.8 + 0.6 * (plano == "basico"), size=n)
    uso = np.clip(rng.normal(6, 3, size=n), 0, None).round(1)  # horas por semana
    atraso = np.where(rng.random(n) < 0.15, rng.integers(1, 45, size=n), 0)
    nps = np.clip(np.round(rng.normal(7.5, 2, size=n)), 0, 10).astype(int)
    mes = rng.integers(1, 13, size=n)

    # relação verdadeira, conhecida (escala log-odds)
    logit = (-0.65
             - 0.05 * np.minimum(tempo_casa, 36)
             + 0.45 * chamados
             - 0.35 * uso
             + 0.05 * atraso
             - 0.25 * (nps - 7)
             + 0.6 * (plano == "basico")
             - 0.4 * (plano == "premium")
             + 0.006 * (mensalidade - 99))
    p = 1 / (1 + np.exp(-logit))
    cancelou = (rng.random(n) < p).astype(int)

    # a coluna com vazamento: clientes que cancelaram param de acessar
    vaz = np.where(cancelou == 1, rng.integers(25, 60, size=n), rng.integers(0, 6, size=n))

    df = pd.DataFrame({
        "cliente_id": np.arange(100_000, 100_000 + n),
        "mes_referencia": mes,
        "plano": plano,
        "mensalidade": mensalidade.round(2),
        "tempo_casa_meses": tempo_casa,
        "chamados_90d": chamados,
        "uso_semanal_horas": uso,
        "dias_atraso_pagamento": atraso,
        "nps": nps,
        COLUNA_VAZAMENTO: vaz,
        "cancelou": cancelou,
    })
    # um pouco de dado faltando, como na vida real
    faltando = rng.random(n) < 0.04
    df.loc[faltando, "nps"] = np.nan
    return df


# ---------------------------------------------------------------------------
# Lab 2c · Carteira: transações com fraude rara
# ---------------------------------------------------------------------------

def gerar_carteira(n: int = 500_000, dias: int = 60, semente: int = 23,
                   dia_golpe_novo: int = 45) -> pd.DataFrame:
    """Transações da Carteira em `dias` dias, ~0,1% de fraude.

    Dois tipos de fraude:
    - golpe conhecido (o tempo todo): madrugada, país diferente, rajada de transações;
    - golpe novo (a partir de `dia_golpe_novo`): valor alto em dispositivo novo,
      em horário comercial e no país do cadastro. O modelo treinado antes dele
      quase não o conhece; a equipe de fraude criou uma regra para ele.
    """
    rng = np.random.default_rng(semente)
    dia = np.sort(rng.integers(0, dias, size=n))
    hora = rng.choice(24, size=n, p=_perfil_horario())
    valor = np.round(rng.lognormal(4.2, 1.0, size=n), 2)
    pais_diferente = rng.random(n) < 0.02
    dispositivo_novo = rng.random(n) < 0.05
    transacoes_1h = rng.poisson(0.6, size=n)
    idade_conta = rng.integers(1, 2000, size=n)

    fraude = np.zeros(n, dtype=int)
    tipo = np.array([""] * n, dtype=object)

    # golpe conhecido: ~0,08%
    alvo = rng.random(n) < 0.0008
    k = alvo.sum()
    hora[alvo] = rng.choice([0, 1, 2, 3, 4, 23], size=k)
    pais_diferente[alvo] = rng.random(k) < 0.7
    transacoes_1h[alvo] = rng.poisson(4, size=k)
    valor[alvo] = np.round(rng.lognormal(5.0, 0.8, size=k), 2)
    idade_conta[alvo] = rng.integers(1, 400, size=k)
    fraude[alvo] = 1
    tipo[alvo] = "conhecido"

    # golpe novo: ~0,05% das transações depois do dia do golpe
    depois = dia >= dia_golpe_novo
    alvo2 = depois & (rng.random(n) < 0.0005) & (fraude == 0)
    k2 = alvo2.sum()
    valor[alvo2] = np.round(rng.uniform(2_500, 6_000, size=k2), 2)
    dispositivo_novo[alvo2] = True
    hora[alvo2] = rng.integers(9, 18, size=k2)
    pais_diferente[alvo2] = False
    fraude[alvo2] = 1
    tipo[alvo2] = "novo"

    df = pd.DataFrame({
        "dia": dia, "hora": hora, "valor": valor,
        "pais_diferente": pais_diferente, "dispositivo_novo": dispositivo_novo,
        "transacoes_1h": transacoes_1h, "idade_conta_dias": idade_conta,
        "fraude": fraude, "tipo_fraude": tipo,
    })
    return df


def _perfil_horario() -> np.ndarray:
    base = np.array([1, 0.6, 0.4, 0.3, 0.3, 0.5, 1.5, 3, 5, 6, 6.5, 7, 8, 7.5, 6.5, 6, 6, 6.5,
                     7, 7, 6, 4.5, 3, 2], dtype=float)
    return base / base.sum()
