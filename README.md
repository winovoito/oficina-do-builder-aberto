# Oficina do Builder · material aberto

Material aberto da **Oficina do Builder**, da Winovoito: a escola de IA feita por IAs que treina você para ser melhor com IA.

A pergunta que guia tudo: **este problema pede uma regra, um modelo de machine learning, um modelo de linguagem ou um agente?**

## O que tem aqui

| Pasta | O que é |
|---|---|
| `notebooks/01_decisor.ipynb` | Lab 1 completo: a Ficha de decisão vira código, é testada em 6 casos e um modelo de linguagem preenche a ficha a partir de texto livre |
| `notebooks/02a_demanda.ipynb` | Lab 2a: previsão de demanda de uma rede de padarias fictícia, com teste automático de vazamento |
| `notebooks/02b_churn.ipynb` | Lab 2b: churn com limiar escolhido pelo custo, explicação por cliente e modelo salvo com hash |
| `notebooks/02c_fraude.ipynb` | Lab 2c: fraude rara (0,1%), curva de precisão e recall, regras + modelo + fila humana |
| `notebooks/02d_api.ipynb` | Lab 2d: o modelo de churn vira uma API com FastAPI, validação de entrada e testes |
| `notebooks/03_pipeline_prompts.ipynb` | Lab 3: cadeia de 3 prompts (extrair, classificar, responder) com saída validada, 20 casos de teste e regras de segurança em código |
| `notebooks/04_rag.ipynb` | Lab 4: RAG em 3 acervos fictícios, com busca híbrida, permissão por papel, citações conferidas, recusa e defesa contra instrução escondida |
| `notebooks/05_agente.ipynb` | Lab 5: agente com 5 ferramentas, aprovação humana obrigatória em código, 8 cenários |
| `notebooks/06_prontidao.ipynb` | Lab 6: harness com casos repetidos, custo, bateria de 15 ataques e Relatório de prontidão |
| `notebooks/final_guia.ipynb` | Guia do projeto final, em 5 seções com testes prontos |
| `fichas/` | Ficha de decisão "Regra, ML, LLM ou agente?" para imprimir ou copiar |
| `revisor/` | Revisor dos 7 erros, em versão curta e versão completa: revisa sistemas com IA contra 7 padrões de falha |
| `oficina/` | Código de apoio: o Decisor, a extração de critérios, o adaptador de provedores, os geradores de dados sintéticos as soluções de referência da Bancada 2, o RAG, o agente e o harness |
| `prompts/` | Prompts versionados como arquivos |
| `dados/` | Casos do Lab 1, 20 reclamações do Lab 3, 3 acervos do Lab 4 e políticas do Lab 5, todos fictícios, com gabarito |
| `scripts/` | Gerador dos acervos fictícios |
| `tests/` | Testes automáticos |

## Como usar

**No Colab:** abra `notebooks/01_decisor.ipynb` e rode as células. As partes 1 e 2 não precisam de chave nenhuma. Os labs da Bancada 2 não usam modelo de linguagem: rodam sem chave, com dados sintéticos gerados no próprio notebook.

**No seu computador:**

```bash
pip install -r requirements.txt
python -m pytest
```

### Rodar sem modelo de linguagem (modo simulado)
Os labs 3 a 6 funcionam sem chave: se nenhum provedor estiver configurado, usam um **modelo simulado** com respostas prontas. Isso valida a *encanação* (esquemas, regras em código, citações, aprovação humana, ataques), que é o que os testes automáticos conferem. **Não mede a qualidade de um modelo de verdade.** Para isso, configure um provedor (abaixo) e rode de novo: os relatórios avisam em que modo foram gerados.

### Modelo de linguagem: sem fornecedor preferido
O adaptador `oficina/provedores.py` usa o formato de chat compatível, oferecido por vários provedores e por servidores de modelos abertos que rodam localmente. Configure por variáveis de ambiente ou pelo cofre de segredos do Colab:

| Variável | Para quê |
|---|---|
| `OFICINA_PROVEDOR` | `remoto` (padrão), `local` ou `falso` (testes sem rede) |
| `OFICINA_BASE_URL` | Endereço do provedor ou do servidor local |
| `OFICINA_MODELO` | Nome do modelo |
| `OFICINA_API_KEY` | A sua chave. **Nunca escreva a chave no código.** |

Defina um limite de gasto mensal na sua conta antes de usar um provedor pago.

## Como conferimos
Os testes rodam automaticamente a cada mudança. O material é escrito e revisado por IAs, e um humano executa os notebooks antes de publicar. Achou um erro? Abra uma *issue*: ele vira um caso de teste.

## Licenças
- Código: [Apache-2.0](LICENSE)
- Textos, fichas e o Revisor: [CC BY 4.0](LICENSE-CONTEUDO). Pode usar e adaptar, citando a Winovoito.

Empresas, pessoas e dados dos exemplos são fictícios.

---
*Feito e revisado por IAs. Orquestrado por humanos.*
