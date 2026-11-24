"""Parte 3 do Lab 1: o LLM lê a descrição e preenche os critérios; a regra decide.

Winovoito · Apache-2.0 · Feito e revisado por IAs. Orquestrado por humanos.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any

from .decisor import Criterios
from .provedores import perguntar_json

PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "extrair_criterios_v1.md"

_BOOLEANOS = {
    "logica_escrevivel", "estruturado", "rotulado", "varios_passos",
    "caminho_varia", "precisa_explicar", "precisa_documentos",
}
_INTEIROS = {"volume_exemplos", "decisoes_mes"}


def validar_criterios(dados: Any) -> Criterios:
    """Confere tipos e valores; levanta ValueError com mensagem útil para o modelo."""
    if not isinstance(dados, dict):
        raise ValueError("a resposta deve ser um objeto JSON")
    nomes = {f.name for f in fields(Criterios)}
    faltando = sorted(nomes - dados.keys())
    if faltando:
        raise ValueError(f"campos faltando: {', '.join(faltando)}")
    for nome in _BOOLEANOS:
        if not isinstance(dados[nome], bool):
            raise ValueError(f"o campo {nome} deve ser true ou false")
    for nome in _INTEIROS:
        if isinstance(dados[nome], bool) or not isinstance(dados[nome], int) or dados[nome] < 0:
            raise ValueError(f"o campo {nome} deve ser um inteiro maior ou igual a zero")
    if dados["custo_erro"] not in ("baixo", "medio", "alto"):
        raise ValueError("o campo custo_erro só aceita baixo, medio ou alto")
    return Criterios(**{n: dados[n] for n in nomes})


def extrair_criterios(descricao: str) -> Criterios:
    sistema = PROMPT.read_text(encoding="utf-8")
    mensagem = f"<descricao>\n{descricao}\n</descricao>"
    return perguntar_json(mensagem, sistema, validar_criterios)
