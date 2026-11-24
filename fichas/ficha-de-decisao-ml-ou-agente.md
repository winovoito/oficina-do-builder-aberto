# Ficha de decisão · Regra, ML, LLM ou agente?

**Oficina do Builder · Winovoito** · CC BY 4.0

Preencha antes de escrever qualquer código. Decisão registrada é decisão revisável.

| | |
|---|---|
| **Problema em uma frase** | |
| **Data** | |
| **Autor** | |

## 1. Dados
- A entrada é estruturada (tabela) ou não estruturada (texto, áudio, imagem)? ☐ estruturada ☐ não estruturada
- Existe histórico com a resposta certa (dados rotulados)? ☐ sim ☐ não
- Quantos exemplos rotulados? ☐ nenhum ☐ dezenas ☐ milhares ☐ milhões
- Dá para escrever a lógica completa como regra? ☐ sim ☐ não

## 2. Custo
- Decisões por mês: ______
- Custo aceitável por decisão: ______
- Tempo de resposta aceitável: ______

## 3. Risco
- Custo de um erro: ☐ baixo ☐ médio ☐ alto
- A ação é reversível? ☐ sim ☐ não
- A tarefa tem várias etapas? ☐ sim ☐ não · O caminho muda de caso para caso? ☐ sim ☐ não

## 4. Explicabilidade
- Quem vai pedir explicação das decisões? ______
- A explicação precisa ser auditável? ☐ sim ☐ não
- A resposta depende de documentos privados? ☐ sim ☐ não

## Leitura rápida

| Se... | Considere |
|---|---|
| A lógica cabe numa frase | **Regra** |
| Tabela + histórico rotulado (milhares de exemplos) | **ML clássico** + regras ao redor |
| Texto livre, julgamento, poucos exemplos | **LLM** (com RAG se depender de documentos) |
| Várias etapas, caminho conhecido | **Cadeia** de prompts e código |
| Várias etapas, caminho que varia, resultado verificável | **Agente** |
| Custo do erro alto | + aprovação ou revisão humana |
| Volume alto com LLM ou agente | + conta de custo por decisão antes de seguir |

## Minha decisão
- **Abordagem escolhida:**
- **Por quê:**
- **Salvaguardas:**
- **O que me faria mudar de ideia:**

---
Winovoito · *Feito e revisado por IAs. Orquestrado por humanos.*
