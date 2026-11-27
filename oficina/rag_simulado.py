"""Modelo SIMULADO para o Lab 4: um "leitor perfeito" que obedece ao prompt.

Ele conhece a resposta de cada pergunta da coleção, mas só responde se o trecho certo estiver entre
os recebidos; caso contrário, recusa com a frase fixa. Assim os testes medem a ENCANAÇÃO (busca,
filtro de permissão, citações, recusa), sem rede e sem custo.
Não mede a qualidade de um modelo de verdade: para isso, rode o notebook com um provedor real.
"""
import json
import re
from typing import Callable

from oficina.rag import FRASE_RECUSA


def criar_modelo_simulado(colecao: dict) -> Callable[[str, str], str]:
    docs = {d["id"]: d for d in colecao["documentos"]}
    perguntas = {q["pergunta"]: q for q in colecao["perguntas"]}

    def modelo(sistema: str, mensagem: str) -> str:
        pergunta = re.search(r"<pergunta>(.*?)</pergunta>", mensagem, re.S).group(1)
        q = perguntas.get(pergunta)
        recusa = json.dumps({"resposta": FRASE_RECUSA, "citacoes": [], "recusou": True}, ensure_ascii=False)
        if not q or q["tipo"] != "resposta":
            return recusa
        for tid, texto in re.findall(r"^\[([A-Z]+-\d+#\d+)\] (.*)$", mensagem, re.M):
            if tid.startswith(q["doc_esperado"] + "#") and q["contem"] in texto:
                frase = next(f for f in re.split(r"(?<=\.)\s+", texto) if q["contem"] in f)
                return json.dumps({"resposta": frase, "citacoes": [tid], "recusou": False}, ensure_ascii=False)
        return recusa

    return modelo
