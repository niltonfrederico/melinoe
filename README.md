# Melinoe — Bot de Identificação de Livros

Melinoe é um bot para Telegram que analisa fotos de capas de livros e retorna metadados bibliográficos detalhados: título, autor, ISBN, editora, sinopse, gêneros, prêmios e avaliações. Opcionalmente aceita também a folha de rosto para aumentar a precisão.

Melinoe também possui dois agentes especializados para catalogar e rastrear a obra literária de **Nilton Manoel de Andrade Teixeira** (O Professor), escritor underground de Ribeirão Preto, SP.

______________________________________________________________________

## Como funciona

### Fluxo principal — livros gerais

```
Usuário envia capa
  → ProfessorDetector (é obra do Professor?)
      ↓ sim (high/medium confidence)         ↓ não
  Confirmação do usuário              Hecate (valida capa)
      ↓ confirmado                           ↓
  KardoNavalhaWorkflow          CoverAnalyzer (analisa visualmente)
      ↓                           → [opcional] TitlePageAnalyzer
  Resultado catalográfico         → LoadRelevantMemory
  + Meilisearch nilton_works      → BookLookup
  + Enfileira Senhor scraping     → WriteMemory
                                  → Resposta formatada
```

### Agente Kardo Navalha — catálogo do Professor

```
ProfessorDetector → ProfessorClassifier → CoverAnalyzer
  → ProfessorCataloger → WriteProfessorMemory
  → Índice Meilisearch (nilton_works)
  → Enfileira scraping via ARQ
```

### Agente Senhor das Horas Mortas — rastreador autônomo

Executa diariamente às 03:00 UTC (e sob demanda após cada nova catalogação):

```
LoadScrapingState → PlanScraping → ExecuteWebMentions
  → EnrichProfessorProfile → SaveScrapingState
```

O agente acumula estado entre sessões (`professor_scraping_state.json`) e enriquece progressivamente o perfil do Professor (`professor_profile.md`), que por sua vez alimenta o `ProfessorDetector` com novos marcadores de identidade descobertos.

Cada etapa é uma **skill** independente, orquestrada pelo workflow correspondente. As skills de visão usam **Gemini Flash**; a síntese de memória usa **GPT-4o** (via GitHub Copilot); Claude Sonnet/Opus está disponível como alternativa.

______________________________________________________________________

## Pré-requisitos

- Python **3.13**
- [Poetry](https://python-poetry.org/) para gerenciamento de dependências
- **Redis** — para a fila ARQ do worker assíncrono
- Chaves de API:
  - `GEMINI_API_KEY` — Google AI Studio
  - `ANTHROPIC_API_KEY` — Anthropic (opcional, para modelos Claude)
  - `GITHUB_COPILOT_API_KEY` — GitHub Models / Azure Inference
  - `TELEGRAM_BOT_TOKEN` — [@BotFather](https://t.me/BotFather)

______________________________________________________________________

## Configuração

1. Clone o repositório e instale as dependências:

```bash
git clone <url-do-repositório>
cd hallm9000
poetry install
```

1. Crie o arquivo `.env` na raiz do projeto com as variáveis abaixo:

```env
DEBUG=False
TELEGRAM_BOT_TOKEN=<token do @BotFather>
GEMINI_API_KEY=<chave do Google AI Studio>
ANTHROPIC_API_KEY=<chave da Anthropic>
GITHUB_COPILOT_API_KEY=<chave do GitHub Models>
REDIS_URL=redis://localhost:6379
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_API_KEY=dev-master-key
```

______________________________________________________________________

## Como executar

### Docker Compose (recomendado)

Sobe todos os serviços — bot, worker ARQ, Meilisearch, SeaweedFS e Redis:

```bash
docker compose up
```

### Bot Telegram (local)

```bash
poetry run python -m melinoe.bot
```

### Worker ARQ (local — necessário para o Senhor das Horas Mortas)

```bash
poetry run python -m arq melinoe.worker.WorkerSettings
```

O worker roda a cron diária às 03:00 UTC e também processa tarefas enfileiradas pelo Kardo Navalha após cada nova catalogação.

### Script CLI (processamento avulso)

```bash
poetry run python scripts/cover_analyzer.py caminho/para/capa.jpg
```

O resultado é impresso no terminal e salvo em `output/<timestamp>-<autor>-<titulo>/result.json`.

______________________________________________________________________

## Estrutura do projeto

```
hallm9000/
├── melinoe/
│   ├── bot.py               # Handlers do Telegram (máquina de estados)
│   ├── logger.py            # Loggers coloridos por camada
│   ├── settings.py          # Variáveis de ambiente
│   ├── worker.py            # ARQ WorkerSettings + tarefas assíncronas
│   ├── clients/
│   │   ├── ai.py            # Abstração de LLM (litellm)
│   │   ├── meilisearch.py   # Índices books + nilton_works
│   │   ├── redis.py         # Pool ARQ
│   │   └── seaweedfs.py     # Armazenamento de arquivos
│   └── workflows/
│       ├── base.py               # Classes abstratas Step e Workflow
│       ├── bookworm.py           # Orquestrador — livros gerais
│       ├── kardo_navalha.py      # Orquestrador — obras do Professor
│       ├── senhor_das_horas_mortas.py  # Orquestrador — scraper autônomo
│       ├── agents/               # Definições de agentes (.md)
│       ├── memories/             # Base de conhecimento persistida (.md por livro/perfil)
│       ├── skills/               # Skills individuais (Python + prompt .md)
│       └── souls/                # Personas / system prompts (.md)
├── icarus/                  # CLI Typer (icarus entry point)
├── input/                   # Imagens de entrada (uso manual)
├── output/                  # Resultados gerados (JSON + imagens)
└── pyproject.toml
```

### Skills disponíveis

#### Fluxo BookwormWorkflow

| Skill | Modelo | Responsabilidade |
|---|---|---|
| `HecateSkill` | Gemini Flash | Valida se a imagem é uma capa legível |
| `CoverAnalyzerSkill` | Gemini Flash | Extrai título, autor, gênero, design e paleta de cores |
| `TitlePageAnalyzerSkill` | Gemini Flash | Transcreve ISBN, edição, dados CIP da folha de rosto |
| `LoadRelevantMemorySkill` | GPT-4o | Filtra memórias anteriores relevantes ao livro atual |
| `BookLookupSkill` | Gemini Flash | Agrega dados de múltiplas fontes e sintetiza os metadados |
| `WriteMemorySkill` | GPT-4o | Persiste o resultado como entrada Markdown na base de memória |

#### KardoNavalhaWorkflow — obras de Nilton Manoel

| Skill | Modelo | Responsabilidade |
|---|---|---|
| `ProfessorDetectorSkill` | Gemini Flash | Detecta se a imagem é obra de Nilton Manoel |
| `ProfessorClassifierSkill` | Gemini Flash | Classifica o tipo literário (trova, haicai, soneto…) |
| `ProfessorCatalogerSkill` | GPT-4o | Produz o registro catalográfico completo |
| `WriteProfessorMemorySkill` | GPT-4o | Persiste o registro como memória |

#### SenhorDasHorasMortasWorkflow — rastreador autônomo

| Skill | Modelo | Responsabilidade |
|---|---|---|
| `LoadScrapingStateSkill` | — | Carrega estado persistido da sessão anterior |
| `PlanScrapingSkill` | GPT-4o | Planeja próximas URLs e queries de busca |
| `ExecuteWebMentionsSkill` | Gemini Flash | Visita URLs e extrai menções confirmadas |
| `EnrichProfessorProfileSkill` | GPT-4o | Atualiza `professor_profile.md` com novas descobertas |
| `SaveScrapingStateSkill` | — | Persiste estado atualizado para a próxima sessão |

______________________________________________________________________

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

______________________________________________________________________

## Licença

Distribuído sob a [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0).

______________________________________________________________________

## Aviso sobre uso de IA

Este projeto é inteiramente assistido por IA. Veja [AI_DISCLAIMER.md](AI_DISCLAIMER.md) para o contexto completo — por que essa escolha foi feita e como você pode ajudar se quiser.
