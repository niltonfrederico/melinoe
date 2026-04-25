# Melinoe — Bot de Identificação de Livros

Melinoe é um bot para Telegram que analisa fotos de capas de livros e retorna metadados bibliográficos detalhados: título, autor, ISBN, editora, sinopse, gêneros, prêmios e avaliações. Opcionalmente aceita também a folha de rosto para aumentar a precisão.

---

## Como funciona

```
Usuário envia capa → Hecate (valida) → CoverAnalyzer (analisa visualmente)
  → [opcional] TitlePageAnalyzer (lê folha de rosto)
  → LoadRelevantMemory (consulta memórias anteriores)
  → BookLookup (busca em Open Library, Google Books, Estante Virtual, Skoob)
  → WriteMemory (salva resultado para uso futuro)
  → Resposta formatada ao usuário
```

Cada etapa é uma **skill** independente, orquestrada pelo `BookwormWorkflow`. As skills de visão usam **Gemini Flash**; a síntese de memória usa **GPT-4o** (via GitHub Copilot); Claude Sonnet/Opus está disponível como alternativa.

---

## Pré-requisitos

- Python **3.13**
- [Poetry](https://python-poetry.org/) para gerenciamento de dependências
- Chaves de API:
  - `GEMINI_API_KEY` — Google AI Studio
  - `ANTHROPIC_API_KEY` — Anthropic (opcional, para modelos Claude)
  - `GITHUB_COPILOT_API_KEY` — GitHub Models / Azure Inference
  - `TELEGRAM_BOT_TOKEN` — [@BotFather](https://t.me/BotFather)

---

## Configuração

1. Clone o repositório e instale as dependências:

```bash
git clone <url-do-repositório>
cd hallm9000
poetry install
```

2. Crie o arquivo `.env` na raiz do projeto com as variáveis abaixo:

```env
DEBUG=False
TELEGRAM_BOT_TOKEN=<token do @BotFather>
GEMINI_API_KEY=<chave do Google AI Studio>
ANTHROPIC_API_KEY=<chave da Anthropic>
GITHUB_COPILOT_API_KEY=<chave do GitHub Models>
```

---

## Como executar

### Bot Telegram

```bash
poetry run python -m melinoe.bot
```

Inicie uma conversa com o bot e envie uma foto da capa do livro. O bot pedirá a folha de rosto em seguida — você pode pular essa etapa clicando no botão exibido.

### Script CLI (processamento avulso)

```bash
poetry run python scripts/cover_analyzer.py caminho/para/capa.jpg
```

O resultado é impresso no terminal e salvo em `output/<timestamp>-<autor>-<titulo>/result.json`.

---

## Estrutura do projeto

```
hallm9000/
├── melinoe/
│   ├── bot.py               # Handlers do Telegram (máquina de estados)
│   ├── client.py            # Abstração de LLM (litellm), modelos pré-configurados
│   ├── logger.py            # Loggers coloridos por camada
│   ├── settings.py          # Variáveis de ambiente
│   └── workflows/
│       ├── base.py          # Classes abstratas Step e Workflow
│       ├── bookworm.py      # Orquestrador principal
│       ├── agents/          # Definições de agentes (.md)
│       ├── memories/        # Base de conhecimento persistida (.md por livro)
│       ├── skills/          # Skills individuais (Python + prompt .md)
│       └── souls/           # Personas / system prompts (.md)
├── scripts/
│   └── cover_analyzer.py    # CLI de uso avulso
├── input/                   # Imagens de entrada (uso manual)
├── output/                  # Resultados gerados (JSON + imagens)
└── pyproject.toml
```

### Skills disponíveis

| Skill | Modelo | Responsabilidade |
|---|---|---|
| `HecateSkill` | Gemini Flash | Valida se a imagem é uma capa legível |
| `CoverAnalyzerSkill` | Gemini Flash | Extrai título, autor, gênero, design e paleta de cores |
| `TitlePageAnalyzerSkill` | Gemini Flash | Transcreve ISBN, edição, dados CIP da folha de rosto |
| `LoadRelevantMemorySkill` | GPT-4o | Filtra memórias anteriores relevantes ao livro atual |
| `BookLookupSkill` | Gemini Flash | Agrega dados de múltiplas fontes e sintetiza os metadados |
| `WriteMemorySkill` | GPT-4o | Persiste o resultado como entrada Markdown na base de memória |

---

## Desenvolvimento

```bash
# Verificação de tipos
poetry run ty check melinoe/

# Linting
poetry run ruff check melinoe/

# Formatação
poetry run ruff format melinoe/
```

Os hooks de pre-commit (ruff) são instalados automaticamente via:

```bash
poetry run pre-commit install
```

---

## Licença

Uso interno — sem licença open-source definida.
