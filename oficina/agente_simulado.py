"""Agente SIMULADO do Lab 5: segue o roteiro de um bom agente (e, em alguns modos, de um agente FRACO).

Serve para testar o laço e as regras em código sem rede. Os modos "fraco_*" fazem de propósito o que
um modelo ruim ou manipulado faria, para provar que o código segura. Não mede a qualidade de um
modelo de verdade: para isso, rode o notebook com um provedor real.
"""
import json
import re
from typing import Callable


def _passos(mensagem: str) -> list[tuple[dict, dict]]:
    acoes = [json.loads(a) for a in re.findall(r"<acao>(.*?)</acao>", mensagem, re.S)]
    obs = [json.loads(o) for o in re.findall(r"<observacao>(.*?)</observacao>", mensagem, re.S)]
    return list(zip(acoes, obs))


def _ferr(nome: str, **args) -> str:
    return json.dumps({"acao": "usar_ferramenta", "ferramenta": nome, "argumentos": args}, ensure_ascii=False)


def _fim(texto: str) -> str:
    return json.dumps({"acao": "finalizar", "resposta": texto}, ensure_ascii=False)


def criar_agente_simulado(modo: str = "bom") -> Callable[[str, str], str]:
    """modo: bom | fraco_obedece_30 | fraco_obedece_injecao | fraco_laco | fraco_inventa_prob | fraco_novo"""

    def modelo(sistema: str, mensagem: str) -> str:
        cid = re.search(r"\bC\d{3}\b", re.search(r"<pedido>(.*?)</pedido>", mensagem, re.S).group(1)).group(0)
        passos = _passos(mensagem)
        n = len(passos)
        ultima = passos[-1][1] if passos else {}
        feitas = [a.get("ferramenta") for a, _ in passos]

        if modo == "fraco_laco":
            return _ferr("buscar_cliente", cliente_id=cid)
        if n == 0:
            return _ferr("buscar_cliente", cliente_id=cid)
        if modo == "fraco_obedece_injecao" and n == 1:
            return _ferr("propor_acao", cliente_id=cid, tipo="oferta_desconto", desconto_pct=40, justificativa="anotação do cadastro")
        if modo == "fraco_obedece_injecao" and n == 2:
            return _ferr("enviar_oferta", proposta_id="P-1")
        if modo == "fraco_obedece_injecao":
            return _fim("Tentei aplicar 40% e enviar a oferta conforme a anotação do cadastro, mas as regras recusaram os dois passos. Nada foi proposto nem enviado; um humano deve assumir.")
        if n == 1:
            return _ferr("prever_churn", cliente_id=cid)
        if n == 2:
            if not passos[-1][1].get("ok"):
                if modo == "fraco_inventa_prob":
                    return _fim("A probabilidade de churn é 72%. Proponho 10% de desconto.")
                return _fim("Não consegui obter a previsão de churn (serviço indisponível). Não estimei a probabilidade; um humano deve assumir.")
            return _ferr("consultar_politica", pergunta="limite de desconto e regras para clientes novos")
        if n == 3:
            cliente = passos[0][1]
            prev = passos[1][1]
            novo = cliente["tempo_casa_meses"] < 3
            if modo == "fraco_obedece_30":
                return _ferr("propor_acao", cliente_id=cid, tipo="oferta_desconto", desconto_pct=30, justificativa="cliente pediu 30%")
            if prev["acionar_retencao"] and not novo:
                return _ferr("propor_acao", cliente_id=cid, tipo="oferta_desconto", desconto_pct=10, justificativa=f"risco {prev['probabilidade']:.0%}, acima do limiar")
            if modo == "fraco_novo":
                return _ferr("propor_acao", cliente_id=cid, tipo="oferta_desconto", desconto_pct=10, justificativa="x")
            return _ferr("propor_acao", cliente_id=cid, tipo="contato_consultivo", justificativa="risco baixo ou cliente novo")
        if n == 4:
            if not ultima.get("ok"):  # a ferramenta recusou: corrige dentro da regra, não contorna
                p = passos[-1][0]["argumentos"]
                if p.get("desconto_pct", 0) > 0 and "limite" in ultima.get("erro", ""):
                    return _ferr("propor_acao", cliente_id=cid, tipo="oferta_desconto", desconto_pct=15, justificativa="máximo permitido pela POL-01")
                return _ferr("propor_acao", cliente_id=cid, tipo="contato_consultivo", justificativa="corrigido após recusa da regra")
            return _fim(f"Proposta {ultima['proposta_id']} registrada. Depende de aprovação humana antes de qualquer envio.")
        return _fim("Proposta registrada. Depende de aprovação humana antes de qualquer envio.")

    return modelo
