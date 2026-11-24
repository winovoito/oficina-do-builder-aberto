"""Adaptador de provedores da Oficina do Builder.

Uma função, `perguntar`, que funciona com qualquer provedor que ofereça o formato de
chat compatível (oferecido por vários provedores comerciais e por servidores de modelos
abertos rodando localmente). Para trocar de provedor, mude a configuração, não o código.

Configuração por variáveis de ambiente (ou pelo cofre de segredos do Colab):
    OFICINA_PROVEDOR   "remoto" (padrão), "local" ou "falso" (testes sem rede)
    OFICINA_BASE_URL   endereço do provedor, ex.: http://localhost:11434/v1 para um servidor local
    OFICINA_MODELO     nome do modelo
    OFICINA_API_KEY    a sua chave. NUNCA escreva a chave no código.

Winovoito · Apache-2.0 · Feito e revisado por IAs. Orquestrado por humanos.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

TEMPO_MAXIMO_S = 60


def _segredo(nome: str) -> str | None:
    """Lê do ambiente; no Colab, tenta o cofre de segredos."""
    valor = os.environ.get(nome)
    if valor:
        return valor
    try:  # pragma: no cover - só existe no Colab
        from google.colab import userdata  # type: ignore

        return userdata.get(nome)
    except Exception:
        return None


def _config() -> dict[str, str | None]:
    provedor = (_segredo("OFICINA_PROVEDOR") or "remoto").lower()
    base_padrao = "http://localhost:11434/v1" if provedor == "local" else None
    return {
        "provedor": provedor,
        "base_url": _segredo("OFICINA_BASE_URL") or base_padrao,
        "modelo": _segredo("OFICINA_MODELO"),
        "api_key": _segredo("OFICINA_API_KEY"),
    }


# Provedor "falso": permite rodar os testes automáticos sem rede e sem custo.
_resposta_falsa: Callable[[str, str], str] | None = None


def usar_resposta_falsa(funcao: Callable[[str, str], str]) -> None:
    """Define a função que responde no modo 'falso': recebe (sistema, mensagem)."""
    global _resposta_falsa
    _resposta_falsa = funcao


def perguntar(mensagem: str, sistema: str = "", temperatura: float = 0.0) -> str:
    """Envia uma mensagem ao modelo configurado e devolve o texto da resposta."""
    cfg = _config()
    if cfg["provedor"] == "falso":
        if _resposta_falsa is None:
            raise RuntimeError("Modo 'falso' sem função de resposta. Use usar_resposta_falsa().")
        return _resposta_falsa(sistema, mensagem)

    if not cfg["base_url"] or not cfg["modelo"]:
        raise RuntimeError(
            "Configure OFICINA_BASE_URL e OFICINA_MODELO (veja o Guia de setup da aula 0.2)."
        )
    if cfg["provedor"] == "remoto" and not cfg["api_key"]:
        raise RuntimeError("Chave não encontrada. Guarde OFICINA_API_KEY no cofre de segredos.")

    import requests

    mensagens: list[dict[str, str]] = []
    if sistema:
        mensagens.append({"role": "system", "content": sistema})
    mensagens.append({"role": "user", "content": mensagem})
    cabecalhos = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        cabecalhos["Authorization"] = f"Bearer {cfg['api_key']}"

    r = requests.post(
        f"{cfg['base_url'].rstrip('/')}/chat/completions",
        headers=cabecalhos,
        json={"model": cfg["modelo"], "messages": mensagens, "temperature": temperatura},
        timeout=TEMPO_MAXIMO_S,
    )
    if r.status_code != 200:
        # Não repete o corpo inteiro: pode conter dados da requisição.
        raise RuntimeError(f"O provedor respondeu {r.status_code}. Confira URL, modelo e chave.")
    return r.json()["choices"][0]["message"]["content"]


def extrair_json(texto: str) -> Any:
    """Extrai o primeiro objeto JSON de um texto (aceita bloco de código markdown)."""
    bloco = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.S)
    candidato = bloco.group(1) if bloco else texto[texto.find("{") : texto.rfind("}") + 1]
    if not candidato:
        raise ValueError("Nenhum JSON encontrado na resposta.")
    return json.loads(candidato)


def perguntar_json(
    mensagem: str,
    sistema: str,
    validar: Callable[[Any], Any],
    tentativas: int = 2,
) -> Any:
    """Pede uma resposta em JSON, valida e tenta de novo devolvendo o erro ao modelo."""
    ultimo_erro = ""
    for _ in range(tentativas + 1):
        texto = mensagem if not ultimo_erro else (
            f"{mensagem}\n\nSua resposta anterior foi rejeitada: {ultimo_erro}\n"
            "Responda apenas com o JSON corrigido."
        )
        try:
            return validar(extrair_json(perguntar(texto, sistema)))
        except (ValueError, KeyError, TypeError) as e:
            ultimo_erro = str(e)
    raise ValueError(f"Resposta inválida após {tentativas + 1} tentativas: {ultimo_erro}")
