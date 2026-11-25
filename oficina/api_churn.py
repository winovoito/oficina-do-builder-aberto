"""Lab 2d · O modelo de churn como API (FastAPI + Pydantic).

    POST /prever_churn  -> probabilidade, decisão pelo limiar, 3 fatores, versão
    GET  /saude         -> versão e data do modelo

Rodar no computador:
    OFICINA_MODELO_PASTA=modelos/churn uvicorn oficina.api_churn:app
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from . import churn


class Plano(str, Enum):
    basico = "basico"
    padrao = "padrao"
    premium = "premium"


class Cliente(BaseModel):
    """Formato esperado. Campo faltando, tipo errado ou valor fora da faixa: erro 422."""
    model_config = ConfigDict(extra="forbid")

    plano: Plano
    mensalidade: float = Field(gt=0, le=10_000)
    tempo_casa_meses: int = Field(ge=0, le=600)
    chamados_90d: int = Field(ge=0, le=500)
    uso_semanal_horas: float = Field(ge=0, le=168)
    dias_atraso_pagamento: int = Field(ge=0, le=3650)
    nps: int | None = Field(default=None, ge=0, le=10, description="Pode faltar")


class Fator(BaseModel):
    caracteristica: str
    nome: str
    valor: float | str | None
    tipico: float | str | None
    efeito: float


class Previsao(BaseModel):
    probabilidade: float
    acionar_retencao: bool
    limiar: float
    fatores: list[Fator]
    versao_modelo: str


def criar_app(pasta_modelo: str | Path, referencia: pd.DataFrame | None = None) -> FastAPI:
    """Cria a API a partir da pasta com o modelo e os metadados (hash conferido)."""
    modelo, meta = churn.carregar(pasta_modelo)
    if referencia is None:
        # sem base de referência, os valores típicos vêm da base sintética
        from .sinteticos import gerar_fluxo
        referencia = gerar_fluxo()
    app = FastAPI(title="Fluxo · churn", version=meta["versao"])

    @app.get("/saude")
    def saude():
        return {"status": "ok", "versao_modelo": meta["versao"], "data_treino": meta["data_treino"]}

    @app.post("/prever_churn", response_model=Previsao)
    def prever(cliente: Cliente):
        linha = pd.DataFrame([cliente.model_dump(mode="json")])
        linha["nps"] = linha["nps"].astype(float)
        p = float(modelo.predict_proba(linha[churn.CARACTERISTICAS])[0, 1])
        return Previsao(probabilidade=round(p, 4), acionar_retencao=p >= meta["limiar"],
                        limiar=meta["limiar"],
                        fatores=churn.fatores_locais(modelo, linha, referencia),
                        versao_modelo=meta["versao"])

    return app


# para `uvicorn oficina.api_churn:app`
_pasta = os.environ.get("OFICINA_MODELO_PASTA")
app = criar_app(_pasta) if _pasta else None
