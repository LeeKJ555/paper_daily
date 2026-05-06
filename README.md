# Paper Daily

Paper Daily fetches OS/System, tiered-memory, and OS-kernel papers each week, then writes Chinese Markdown summaries. It is designed to run locally with `uv` and later run unattended in GitHub Actions.

## Features

- Sources: arXiv, OpenAlex, DBLP, and USENIX proceedings.
- Default topics: systems, tiered memory, and OS kernel.
- Weekly run by default: look back 7 days and summarize at most 20 new papers.
- Legal PDF policy: download only arXiv, USENIX, OpenAlex OA PDFs, or PDFs explicitly marked as open access by enrichment metadata.
- DBLP is treated as a discovery source. DBLP records are enriched through OpenAlex; title-only DBLP records are cached but not summarized.
- LLM providers: OpenAI Responses API and OpenAI-compatible Chat Completions APIs such as DeepSeek.

## Local Setup

```powershell
uv sync --extra dev
Copy-Item .env.example .env
```

OpenAI example:

```text
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4o-mini
```

DeepSeek example:

```text
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek-chat
```

Then choose the provider in `config.yaml`:

```yaml
summary:
  provider: openai-compatible
  model: ${DEEPSEEK_MODEL:deepseek-chat}
  api_key_env: DEEPSEEK_API_KEY
  base_url: https://api.deepseek.com
  max_input_chars: 42000
```

## Commands

Check sources:

```powershell
uv run paper-daily sources-check
```

Fetch and rank only, without writing files or spending LLM tokens:

```powershell
uv run paper-daily dry-run
```

Generate summaries:

```powershell
uv run paper-daily run
```

Bootstrap USENIX history into the source cache:

```powershell
uv run paper-daily bootstrap --source usenix
```

## Source Tuning

USENIX is fetched per event so a single proceedings page cannot fill the whole weekly candidate list:

```yaml
sources:
  usenix:
    max_results_per_event: 30
    include_unpublished: false
```

`include_unpublished: false` means title-only papers such as early OSDI listings are written to `data/source_cache.jsonl` but skipped for summarization until a PDF or useful public content appears.

OpenAlex uses multiple broad queries, then local keyword ranking filters the results:

```yaml
sources:
  openalex:
    queries:
      - operating system
      - kernel
      - tiered memory
```

DBLP uses short `venue + year` queries, then tries to enrich matching records with OpenAlex:

```yaml
sources:
  dblp:
    enrich_with_openalex: true
    require_public_content: true
    enrichment_max_queries: 40
```

When `require_public_content` is true, DBLP records without an abstract or OA PDF are cached but do not enter `run` or `dry-run` selected candidates.

## Outputs

```text
summaries/
  YYYY-MM-DD/
    index.md
    doi-...-paper-title.md
data/
  papers.jsonl
  source_cache.jsonl
```

Each paper summary includes:

- What problem the paper addresses
- What solution it proposes
- How the solution works
- What results it reports
- Limitations from an observer's perspective
- Follow-up points worth tracking
- Metadata and links

## GitHub Actions

After pushing to GitHub, add the secrets required by your selected provider:

```text
OPENAI_API_KEY
DEEPSEEK_API_KEY
```

The workflow runs at Beijing time Thursday 07:00 by default and can also be triggered manually. It commits:

```text
summaries/**/*.md
data/papers.jsonl
data/source_cache.jsonl
```

PDF cache files are not committed.

## Future Extensions

- IEEE Xplore API metadata and OA discovery.
- Crossref and Unpaywall enrichment for DOI-based OA PDF discovery.
- Local PDF inbox for manually downloaded ACM/IEEE PDFs.
- Weekly or monthly digest generation from saved summaries.
