"""Lab 2a · Previsão de demanda (Pão da Esquina).

Funções de referência do lab. O notebook mostra cada passo; aqui fica a
versão que os testes automáticos conferem.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

CARACTERISTICAS = [
    "loja", "dia_semana", "mes", "dia_ano", "feriado", "chuva_prevista",
    "lag_1", "lag_7", "lag_14", "media_7", "media_28", "media_dow_4",
]


def dividir_no_tempo(df: pd.DataFrame, inicio: str | None = None):
    """Treino até o mês 30, validação 31–33, teste 34–36 (contados do início)."""
    inicio = pd.Timestamp(inicio or df["data"].min())
    mes_n = (df["data"].dt.year - inicio.year) * 12 + (df["data"].dt.month - inicio.month) + 1
    return df[mes_n <= 30], df[(mes_n > 30) & (mes_n <= 33)], df[mes_n > 33]


def criar_caracteristicas(df: pd.DataFrame) -> pd.DataFrame:
    """Calendário + defasagens que olham SÓ para o passado.

    Regra contra vazamento: `shift` antes de `rolling`. A linha do dia t só
    pode usar vendas até t-1.
    """
    df = df.sort_values(["loja", "data"]).copy()
    g = df.groupby("loja")["vendas"]
    df["dia_semana"] = df["data"].dt.dayofweek
    df["mes"] = df["data"].dt.month
    df["dia_ano"] = df["data"].dt.dayofyear
    df["lag_1"] = g.shift(1)
    df["lag_7"] = g.shift(7)
    df["lag_14"] = g.shift(14)
    df["media_7"] = g.transform(lambda s: s.shift(1).rolling(7).mean())
    df["media_28"] = g.transform(lambda s: s.shift(1).rolling(28).mean())
    # média das últimas 4 ocorrências do mesmo dia da semana
    df["media_dow_4"] = (df.groupby(["loja", "dia_semana"])["vendas"]
                           .transform(lambda s: s.shift(1).rolling(4).mean()))
    return df


def checar_vazamento(df: pd.DataFrame, funcao=criar_caracteristicas,
                     colunas=CARACTERISTICAS, n_datas: int = 5, semente: int = 0) -> list[str]:
    """Confere se alguma característica do dia t usa venda do dia t ou do futuro.

    Como: calcula as características, depois troca por lixo todas as vendas
    a partir de uma data t e recalcula. Se o valor de alguma característica
    na data t mudar, ela olhou para o presente ou para o futuro.
    Devolve a lista de colunas com vazamento (vazia = passou).
    """
    rng = np.random.default_rng(semente)
    datas = df["data"].drop_duplicates().sort_values().iloc[60:-5]
    colunas = [c for c in colunas if c != "loja"]
    suspeitas: set[str] = set()
    base = funcao(df).set_index(["loja", "data"])
    for t in rng.choice(datas.to_numpy(), size=n_datas, replace=False):
        sujo = df.copy()
        futuro = sujo["data"] >= t
        sujo.loc[futuro, "vendas"] = rng.integers(0, 10_000, size=futuro.sum())
        refeito = funcao(sujo).set_index(["loja", "data"])
        a = base.xs(t, level="data")[colunas]
        b = refeito.xs(t, level="data")[colunas]
        for c in colunas:
            if not np.allclose(a[c].astype(float), b[c].astype(float), equal_nan=True):
                suspeitas.add(c)
    return sorted(suspeitas)


def baseline_sazonal(df_feat: pd.DataFrame) -> pd.Series:
    """Amanhã vende o mesmo que no mesmo dia da semana passada."""
    return df_feat["lag_7"]


def criar_pipeline() -> Pipeline:
    pre = ColumnTransformer([
        ("loja", OrdinalEncoder(), ["loja"]),
    ], remainder="passthrough")
    modelo = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                           categorical_features=[0], random_state=0)
    return Pipeline([("pre", pre), ("modelo", modelo)])


def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def mape(y, p) -> float:
    y = np.asarray(y, dtype=float)
    return float(np.mean(np.abs(y - np.asarray(p)) / np.where(y == 0, np.nan, y)) * 100)


def sobra_semanal(y, p, custo_unitario: float = 0.6) -> dict:
    """Traduz erro em negócio: pão que sobra (produção acima da venda).

    Hipótese simples do lab: a loja produz exatamente o previsto. Excesso vira
    sobra; falta vira venda perdida.
    """
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    semanas = len(y) / 7 / 5  # 5 lojas
    sobra = np.clip(p - y, 0, None).sum() / semanas
    falta = np.clip(y - p, 0, None).sum() / semanas
    return {"sobra_pães_semana": int(round(sobra)), "falta_pães_semana": int(round(falta)),
            "custo_sobra_semana": float(round(sobra * custo_unitario, 2))}


def rodar_referencia(df: pd.DataFrame) -> dict:
    """A solução de referência completa: devolve as métricas no teste."""
    f = criar_caracteristicas(df).dropna(subset=CARACTERISTICAS)
    treino, valid, teste = dividir_no_tempo(f, inicio=str(df["data"].min().date()))
    treino = pd.concat([treino, valid])  # na referência, treina com treino + validação
    pipe = criar_pipeline().fit(treino[CARACTERISTICAS], treino["vendas"])
    prev = pipe.predict(teste[CARACTERISTICAS])
    base = baseline_sazonal(teste)
    return {
        "mae_baseline": mae(teste["vendas"], base),
        "mae_modelo": mae(teste["vendas"], prev),
        "pipeline": pipe, "teste": teste.assign(previsto=prev, baseline=base),
    }
