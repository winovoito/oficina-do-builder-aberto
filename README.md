# Oficina do Builder · material aberto

Material aberto da **Oficina do Builder**, da Winovoito: a escola de IA feita por IAs que treina você para ser melhor com IA.

A pergunta que guia tudo: **este problema pede uma regra, um modelo de machine learning, um modelo de linguagem ou um agente?**

## O que tem aqui

| Pasta | O que é |
|---|---|
| `notebooks/01_decisor.ipynb` | Lab 1 completo: a Ficha de decisão vira código, é testada em 6 casos e um modelo de linguagem preenche a ficha a partir de texto livre |
| `fichas/` | Ficha de decisão "Regra, ML, LLM ou agente?" para imprimir ou copiar |
| `revisor/revisor-7-erros.md` | Revisor dos 7 erros, versão curta: revisa sistemas com IA contra 7 padrões de falha |
| `oficina/` | Código de apoio: o Decisor, a extração de critérios e um adaptador de provedores |
| `prompts/` | Prompts versionados como arquivos |
| `dados/casos.json` | Os 6 casos fictícios do lab, com gabarito |
| `tests/` | Testes automáticos |

## Como usar

**No Colab:** abra `notebooks/01_decisor.ipynb` e rode as células. As partes 1 e 2 não precisam de chave nenhuma.

**No seu computador:**

```bash
pip install -r requirements.txt
python -m pytest
```

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
