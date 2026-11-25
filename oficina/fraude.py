"""Lab 2c · Fraude e dados desbalanceados (Carteira).

Classe rara (~0,1%), métrica certa (curva de precisão e recall), ajuste para
a classe rara, limiar pela capacidade da equipe e o sistema completo:
regras + modelo + fila de revisão humana.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score

CARACTERISTICAS = ["hora", "valor", "pais_diferente", "dispositivo_novo",
                   "transacoes_1h", "idade_conta_dias"]
ALVO = "fraude"
CAPACIDADE_DIARIA = 200  # casos que a equipe consegue revisar por dia


def dividir(df: pd.DataFrame, ultimo_dia_treino: int = 39):
    """Treino até o dia 39, teste do dia 40 em diante."""
    return df[df["dia"] <= ultimo_dia_treino], df[df["dia"] > ultimo_dia_treino]


def _modelo(**kw) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, random_state=0, **kw)


def treinar_sem_ajuste(treino: pd.DataFrame):
    return _modelo().fit(treino[CARACTERISTICAS], treino[ALVO])


def treinar_com_peso(treino: pd.DataFrame):
    """Pesos maiores para a classe rara (class_weight='balanced')."""
    return _modelo(class_weight="balanced").fit(treino[CARACTERISTICAS], treino[ALVO])


def treinar_subamostrado(treino: pd.DataFrame, proporcao: int = 50, semente: int = 0):
    """Mantém todas as fraudes e só `proporcao` legítimas para cada fraude."""
    fraudes = treino[treino[ALVO] == 1]
    legit = treino[treino[ALVO] == 0].sample(n=min(len(fraudes) * proporcao,
                                                   (treino[ALVO] == 0).sum()), random_state=semente)
    amostra = pd.concat([fraudes, legit])
    return _modelo().fit(amostra[CARACTERISTICAS], amostra[ALVO])


def pr_auc(modelo, teste: pd.DataFrame) -> float:
    return float(average_precision_score(teste[ALVO], modelo.predict_proba(teste[CARACTERISTICAS])[:, 1]))


# --------------------------------------------------------------------------- fila de revisão
def regra_golpe_novo(df: pd.DataFrame, teto: float = 2_000.0) -> pd.Series:
    """Regra da equipe: valor acima do teto em dispositivo novo vai direto para revisão."""
    return (df["valor"] > teto) & df["dispositivo_novo"]


def fila_do_dia(dia_df: pd.DataFrame, score: np.ndarray, capacidade: int = CAPACIDADE_DIARIA,
                usar_regras: bool = False) -> pd.Index:
    """Índices das transações que a equipe revisa no dia.

    Sem regras: as `capacidade` maiores notas do modelo.
    Com regras: primeiro os casos da regra; o modelo preenche o resto da fila.
    """
    s = pd.Series(score, index=dia_df.index)
    if not usar_regras:
        return s.nlargest(capacidade).index
    pela_regra = dia_df.index[regra_golpe_novo(dia_df).to_numpy()][:capacidade]
    resto = s.drop(pela_regra).nlargest(capacidade - len(pela_regra)).index
    return pela_regra.append(resto)


def avaliar_fila(modelo, teste: pd.DataFrame, capacidade: int = CAPACIDADE_DIARIA,
                 usar_regras: bool = False) -> dict:
    """Mede o sistema: fraudes pegas, casos revisados e fraudes por caso revisado."""
    score = modelo.predict_proba(teste[CARACTERISTICAS])[:, 1]
    score = pd.Series(score, index=teste.index)
    revisados = pd.Index([])
    for _, dia_df in teste.groupby("dia"):
        revisados = revisados.append(fila_do_dia(dia_df, score.loc[dia_df.index].to_numpy(),
                                                 capacidade, usar_regras))
    pegas = int(teste.loc[revisados, ALVO].sum())
    total = int(teste[ALVO].sum())
    por_tipo = teste.loc[revisados].query("fraude == 1")["tipo_fraude"].value_counts().to_dict()
    return {"revisados": len(revisados), "fraudes_pegas": pegas, "fraudes_total": total,
            "recall": round(pegas / total, 3) if total else 0.0,
            "fraudes_por_caso": round(pegas / len(revisados), 4) if len(revisados) else 0.0,
            "pegas_por_tipo": por_tipo}


def rodar_referencia(df: pd.DataFrame) -> dict:
    treino, teste = dividir(df)
    sem = treinar_sem_ajuste(treino)
    peso = treinar_com_peso(treino)
    sub = treinar_subamostrado(treino)
    pr = {"sem_ajuste": pr_auc(sem, teste), "com_peso": pr_auc(peso, teste),
          "subamostrado": pr_auc(sub, teste)}
    melhor = {"com_peso": peso, "subamostrado": sub}[max(["com_peso", "subamostrado"], key=pr.get)]
    return {"pr_auc": pr, "modelo": melhor,
            "fila_modelo": avaliar_fila(melhor, teste),
            "fila_sistema": avaliar_fila(melhor, teste, usar_regras=True),
            "acuracia_nunca_fraude": float(1 - teste[ALVO].mean())}
