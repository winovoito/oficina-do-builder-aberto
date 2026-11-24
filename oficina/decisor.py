"""Decisor da Oficina do Builder: regra, ML, LLM, cadeia ou agente?

Transforma a Ficha de decisão em uma regra explícita. É de propósito uma regra
e não um modelo: a lógica cabe numa descrição, então uma regra é a ferramenta certa.

Winovoito · Apache-2.0 · Feito e revisado por IAs. Orquestrado por humanos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CustoErro = Literal["baixo", "medio", "alto"]
Abordagem = Literal["regra", "ml", "llm", "cadeia", "agente"]

MIN_EXEMPLOS_ML = 1_000
VOLUME_ALTO = 100_000  # decisões por mês a partir das quais custo por chamada pesa


@dataclass
class Criterios:
    """Os critérios da Ficha de decisão."""

    logica_escrevivel: bool  # dá para escrever a lógica completa como regra?
    estruturado: bool  # a entrada é uma tabela (linhas e colunas)?
    rotulado: bool  # existe histórico com a resposta certa?
    volume_exemplos: int  # quantos exemplos rotulados existem
    decisoes_mes: int  # quantas decisões o sistema toma por mês
    custo_erro: CustoErro  # quanto custa um erro
    varios_passos: bool  # a tarefa tem várias etapas com ferramentas?
    caminho_varia: bool  # a sequência de etapas muda de caso para caso?
    precisa_explicar: bool  # alguém vai pedir a explicação de cada decisão?
    precisa_documentos: bool = False  # a resposta depende de documentos privados?


@dataclass
class Decisao:
    abordagem: Abordagem
    justificativa: str
    salvaguardas: list[str] = field(default_factory=list)


def decidir(c: Criterios) -> Decisao:
    """Sugere uma abordagem e as salvaguardas a partir dos critérios."""
    if c.custo_erro not in ("baixo", "medio", "alto"):
        raise ValueError(f"custo_erro inválido: {c.custo_erro!r}")
    if c.volume_exemplos < 0 or c.decisoes_mes < 0:
        raise ValueError("volumes não podem ser negativos")

    if c.varios_passos and c.caminho_varia:
        abordagem: Abordagem = "agente"
        motivo = "a tarefa tem várias etapas e o caminho muda de caso para caso"
    elif c.varios_passos:
        abordagem = "cadeia"
        motivo = "a tarefa tem várias etapas, mas o caminho é conhecido: uma cadeia fixa é mais previsível"
    elif c.logica_escrevivel:
        abordagem = "regra"
        motivo = "a lógica cabe numa descrição: uma regra é rápida, barata e auditável"
    elif c.estruturado and c.rotulado and c.volume_exemplos >= MIN_EXEMPLOS_ML:
        abordagem = "ml"
        motivo = "dados tabulares com histórico rotulado suficiente"
    elif not c.estruturado:
        abordagem = "llm"
        motivo = "a entrada é texto ou outro dado não estruturado e pede julgamento"
    else:
        abordagem = "regra"
        motivo = (
            "dados tabulares sem histórico rotulado suficiente: comece com uma regra simples "
            "e colete rótulos para treinar um modelo depois"
        )

    salvaguardas: list[str] = []
    if c.precisa_documentos and abordagem in ("llm", "cadeia", "agente"):
        salvaguardas.append("rag: responder só com base nos documentos, citando a fonte e sabendo dizer 'não sei'")
    if c.custo_erro == "alto":
        if abordagem in ("llm", "cadeia", "agente"):
            salvaguardas.append("aprovação humana antes de qualquer ação externa ou irreversível")
        else:
            salvaguardas.append("revisão humana dos casos na zona cinzenta")
    if abordagem == "ml":
        salvaguardas.append("regras fixas ao redor do modelo para os casos óbvios")
    if c.decisoes_mes >= VOLUME_ALTO and abordagem in ("llm", "agente"):
        salvaguardas.append("custo: volume alto, calcule o custo por decisão antes de seguir")
    if c.precisa_explicar and abordagem in ("llm", "agente"):
        salvaguardas.append("explicabilidade: registre fontes e passos, a justificativa em texto não basta")

    return Decisao(abordagem=abordagem, justificativa=motivo, salvaguardas=salvaguardas)
