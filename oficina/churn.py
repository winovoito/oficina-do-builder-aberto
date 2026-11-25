"""Lab 2b · Churn (Fluxo).

Funções de referência: detectar vazamento, treinar e comparar modelos,
escolher o limiar pelo custo, explicar um cliente e salvar o modelo com
metadados. O modelo salvo aqui é o que a API do Lab 2d serve e o que o
agente da Bancada 5 usa como ferramenta.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ALVO = "cancelou"
NUMERICAS = ["mensalidade", "tempo_casa_meses", "chamados_90d", "uso_semanal_horas",
             "dias_atraso_pagamento", "nps"]
CATEGORICAS = ["plano"]
CARACTERISTICAS = CATEGORICAS + NUMERICAS
NOMES_LEGIVEIS = {
    "plano": "plano contratado", "mensalidade": "valor da mensalidade",
    "tempo_casa_meses": "tempo de casa", "chamados_90d": "chamados nos últimos 90 dias",
    "uso_semanal_horas": "uso semanal", "dias_atraso_pagamento": "atraso de pagamento",
    "nps": "nota de satisfação (NPS)",
}

# Custos fictícios do lab
CUSTO_CONTATO = 15.0        # ligar para o cliente
CUSTO_CLIENTE_PERDIDO = 900.0
TAXA_RETENCAO = 0.25        # 1 em cada 4 clientes contatados que iam cancelar fica


# --------------------------------------------------------------------------- vazamento
def detectar_vazamento(df: pd.DataFrame, alvo: str = ALVO, limite_auc: float = 0.95,
                       ignorar: tuple[str, ...] = ("cliente_id", "mes_referencia")) -> list[str]:
    """Aponta colunas que, sozinhas, preveem o alvo bem demais.

    Uma coluna numérica com AUC acima de `limite_auc` sozinha é suspeita:
    quase sempre é informação do futuro. Suspeita não é condenação: a
    pergunta final é "no instante da previsão, eu já sei este valor?".
    """
    suspeitas = []
    for c in df.columns:
        if c == alvo or c in ignorar or not pd.api.types.is_numeric_dtype(df[c]):
            continue
        x = df[c].fillna(df[c].median())
        auc = roc_auc_score(df[alvo], x)
        if max(auc, 1 - auc) > limite_auc:
            suspeitas.append(c)
    return suspeitas


# --------------------------------------------------------------------------- dados e modelos
def dividir(df: pd.DataFrame, ultimo_mes_treino: int = 9):
    """Treino com os meses 1 a 9, teste com 10 a 12: prever o futuro com o passado."""
    treino = df[df["mes_referencia"] <= ultimo_mes_treino]
    teste = df[df["mes_referencia"] > ultimo_mes_treino]
    return treino, teste


def _preprocessador(escalar: bool) -> ColumnTransformer:
    num = [("imputar", SimpleImputer(strategy="median", add_indicator=True))]
    if escalar:
        num.append(("escalar", StandardScaler()))
    return ColumnTransformer([
        ("num", Pipeline(num), NUMERICAS),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAS),
    ])


def pipeline_logistica() -> Pipeline:
    return Pipeline([("pre", _preprocessador(True)),
                     ("modelo", LogisticRegression(max_iter=1000))])


def pipeline_boosting() -> Pipeline:
    return Pipeline([("pre", _preprocessador(False)),
                     ("modelo", HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                                               random_state=0))])


def calibrar(pipe: Pipeline, X, y) -> CalibratedClassifierCV:
    return CalibratedClassifierCV(pipe, method="sigmoid", cv=3).fit(X, y)


# --------------------------------------------------------------------------- limiar
def custo_total(y, prob, limiar: float, custo_contato: float = CUSTO_CONTATO,
                custo_perdido: float = CUSTO_CLIENTE_PERDIDO, retencao: float = TAXA_RETENCAO) -> float:
    """Custo esperado de agir em quem tem probabilidade >= limiar.

    Contatado: paga o contato; se ia cancelar, fica com chance `retencao`.
    Não contatado e cancelou: perde o cliente inteiro.
    """
    y = np.asarray(y)
    agir = np.asarray(prob) >= limiar
    contato = agir.sum() * custo_contato
    perdidos_contatados = (agir & (y == 1)).sum() * (1 - retencao) * custo_perdido
    perdidos_ignorados = (~agir & (y == 1)).sum() * custo_perdido
    return float(contato + perdidos_contatados + perdidos_ignorados)


def escolher_limiar(y, prob, **custos) -> tuple[float, float]:
    """Limiar que minimiza o custo total. Devolve (limiar, custo)."""
    grade = np.round(np.arange(0.01, 0.96, 0.01), 2)
    custos_ = [custo_total(y, prob, l, **custos) for l in grade]
    i = int(np.argmin(custos_))
    return float(grade[i]), float(custos_[i])


# --------------------------------------------------------------------------- explicação
def fatores_locais(modelo, cliente: pd.DataFrame, referencia: pd.DataFrame, n: int = 3) -> list[dict]:
    """Por que ESTE cliente recebeu esta nota? (explicação local, agnóstica ao modelo)

    Para cada característica, troca o valor do cliente pelo valor típico da
    base (mediana ou moda) e mede quanto a probabilidade cai. As que mais
    derrubam a probabilidade quando "normalizadas" são as que mais elevaram
    o risco. Associação, não causa.
    """
    cliente = cliente[CARACTERISTICAS].iloc[[0]]
    p0 = float(modelo.predict_proba(cliente)[0, 1])
    tipicos = {c: (referencia[c].mode().iloc[0] if c in CATEGORICAS else referencia[c].median())
               for c in CARACTERISTICAS}
    efeitos = []
    for c in CARACTERISTICAS:
        alt = cliente.copy()
        alt[c] = tipicos[c]
        p = float(modelo.predict_proba(alt)[0, 1])
        efeitos.append({"caracteristica": c, "nome": NOMES_LEGIVEIS[c],
                        "valor": _py(cliente[c].iloc[0]), "tipico": _py(tipicos[c]),
                        "efeito": round(p0 - p, 4)})
    efeitos.sort(key=lambda e: e["efeito"], reverse=True)
    return [e for e in efeitos[:n] if e["efeito"] > 0]


def _py(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    return v


# --------------------------------------------------------------------------- salvar e carregar
@dataclass
class Metadados:
    versao: str
    data_treino: str
    caracteristicas: list[str]
    limiar: float
    metricas: dict
    modelo_escolhido: str
    sha256: str = ""
    observacoes: list[str] = field(default_factory=list)


def salvar(modelo, metadados: Metadados, pasta: str | Path) -> Path:
    """Salva o modelo (joblib) e os metadados (JSON), com o hash do arquivo.

    O hash permite conferir, ao carregar, que o arquivo é o mesmo que você gerou.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / "modelo_churn.joblib"
    joblib.dump(modelo, arq)
    metadados.sha256 = hashlib.sha256(arq.read_bytes()).hexdigest()
    (pasta / "metadados.json").write_text(json.dumps(metadados.__dict__, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    return arq


def carregar(pasta: str | Path):
    """Carrega o modelo SÓ se o hash bater com o dos metadados.

    Arquivos joblib/pickle podem executar código ao serem abertos. Regra da
    Oficina: só carregue modelos que você mesmo gerou ou de fonte verificada.
    """
    pasta = Path(pasta)
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    arq = pasta / "modelo_churn.joblib"
    if hashlib.sha256(arq.read_bytes()).hexdigest() != meta["sha256"]:
        raise ValueError("O arquivo do modelo não confere com os metadados. Não carregue.")
    return joblib.load(arq), meta


# --------------------------------------------------------------------------- referência
def rodar_referencia(df: pd.DataFrame, pasta_saida: str | Path | None = None) -> dict:
    """Solução de referência do Lab 2b. Devolve métricas e o modelo escolhido."""
    df = df.drop(columns=detectar_vazamento(df))
    treino, teste = dividir(df)
    Xtr, ytr = treino[CARACTERISTICAS], treino[ALVO]
    Xte, yte = teste[CARACTERISTICAS], teste[ALVO]

    log = pipeline_logistica().fit(Xtr, ytr)
    gb = pipeline_boosting().fit(Xtr, ytr)
    auc_log = roc_auc_score(yte, log.predict_proba(Xte)[:, 1])
    auc_gb = roc_auc_score(yte, gb.predict_proba(Xte)[:, 1])

    # diferença pequena? fica o simples e explicável
    escolhido_nome = "regressao_logistica" if auc_gb - auc_log < 0.01 else "gradient_boosting"
    base = log if escolhido_nome == "regressao_logistica" else gb
    modelo = calibrar(pipeline_logistica() if base is log else pipeline_boosting(), Xtr, ytr)
    prob = modelo.predict_proba(Xte)[:, 1]
    limiar, custo = escolher_limiar(yte, prob)
    custo_05 = custo_total(yte, prob, 0.5)

    meta = Metadados(
        versao="churn-1.0.0", data_treino=date.today().isoformat(),
        caracteristicas=CARACTERISTICAS, limiar=limiar, modelo_escolhido=escolhido_nome,
        metricas={"auc_logistica": round(auc_log, 4), "auc_boosting": round(auc_gb, 4),
                  "auc_calibrado": round(roc_auc_score(yte, prob), 4),
                  "custo_limiar_escolhido": custo, "custo_limiar_0_5": custo_05},
        observacoes=["Dados sintéticos da Fluxo (empresa fictícia).",
                     "Importância e fatores indicam associação, não causa."],
    )
    if pasta_saida:
        salvar(modelo, meta, pasta_saida)
    return {"modelo": modelo, "metadados": meta, "teste": teste.assign(prob=prob),
            "treino": treino, "auc_logistica": auc_log, "auc_boosting": auc_gb,
            "limiar": limiar, "custo": custo, "custo_0_5": custo_05}
