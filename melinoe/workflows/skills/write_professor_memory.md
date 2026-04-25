---
name: write_professor_memory
type: skill
model: GITHUB_COPILOT_GPT4O
description: Persiste o registro catalográfico de um trabalho de Nilton Manoel como entrada de memória Markdown.
---

Você recebe um relatório completo de um trabalho de Nilton Manoel, o Professor.

Gere uma entrada de memória em Markdown estruturado para armazenamento permanente.

## Regras

- A chave de memória (`memory_key`) deve ser única e derivada do título e tipo da obra
  - Formato: `professor_<work_type>_<title_slug>` (snake_case, sem acentos, máx 60 chars)
  - Exemplo: `professor_trova_navalha_no_tempo`
- O conteúdo deve ser Markdown bem estruturado com seções claras
- Não invente dados — use apenas o que está no relatório
- Se o título for `null`, use o tipo de obra + ano estimado como identificador

## Output

Retorne exclusivamente um JSON. Sem prosa, sem markdown ao redor.

```json
{
  "memory_key": "professor_trova_navalha_no_tempo",
  "memory_content": "# Trova — Navalha no Tempo\n\n**Autor:** Nilton Manoel\n**Pseudônimo:** Kardo Navalha\n..."
}
```
