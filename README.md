# research-radar

Vibe-coded Python CLI tool to query public research databases and generate reports.
Designed to give weekly literature alerts for a configured research scope.

`research-radar` reads a YAML registry of topics and watched authors, searches public scholarly databases, deduplicates results, labels relevance, and writes a Markdown report.
Reports are written to `reports/YYYY-MM-DD.md`, and run state is stored in `state/litreview.sqlite`.

## Features

- Search OpenAlex, Europe PMC, bioRxiv, medRxiv, and arXiv.
- Configure topics, synonyms, watched authors, ORCIDs, and source preferences in
  `registry.yaml`.
- Classify records as:
  - `high`: matched both a watched author and a registry topic
  - `medium`: matched a watched author only
  - `low`: matched a registry topic only
- Deduplicate by DOI, preprint ID, then exact cleaned-title match.
- Render Markdown reports grouped by relevance and category.
- Include citation metadata as copyable BibTeX entries.
- Persist successful report windows in SQLite and skip duplicate runs unless
  `--overwrite` is used.
- Support optional OpenAlex API keys through local environment files.
- Generate a macOS `launchd` plist for scheduled runs.

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)
- macOS only if you want to use the built-in `launchd` scheduler helper

No API credentials are required for the default sources.
An OpenAlex API key is optional.

## Quickstart

Install dependencies:

```bash
uv sync --extra dev
```

Create a working registry:

```bash
cp registry.example.yaml registry.yaml
```

Edit `registry.yaml` to define the topics and authors you want to track, then
validate it:

```bash
uv run litreview validate-registry
```

Generate a report:

```bash
uv run litreview run
```

The report will be written to `reports/YYYY-MM-DD.md`.

## Configuration

`registry.yaml` is the main runtime configuration file. A neutral template is
provided in `registry.example.yaml`.

The registry contains:

- `metadata`: registry name and description
- `categories`: report categories and subcategories
- `topics`: topic search terms, synonyms, include/exclude notes, and source rules
- `watchlist`: authors/PIs/labs to track
- `sources`: enabled source adapters and per-source options
- `relevance_rules`: labels used in report output
- `change_log`: human-readable registry history

IDs should use lowercase snake case, for example `single_cell_genomics`.

### Topics

Each topic belongs to a category and subcategory and defines `search_terms` and
optional `synonyms`. These terms are used to query the enabled sources.

```yaml
topics:
  - id: neural_operators
    name: Neural operators
    category: machine_learning
    subcategory: scientific_ml
    priority: medium
    search_terms: ["neural operator"]
    synonyms: ["Fourier neural operator", "operator learning"]
    include_when:
      - The work develops or applies neural operators for scientific modeling.
    exclude_when: []
    notes: ""
    sources: {include: [], exclude: []}
```

Use `sources.include` or `sources.exclude` when a topic should only run against
particular databases.

### Watched Authors

Watched authors are queried separately from topic searches. ORCID and source IDs
improve matching when available, but can be left blank.

```yaml
watchlist:
  - id: example_author
    name: Example Author
    type: author
    affiliation: Example University
    orcid: ""
    profile_urls: []
    source_ids: {}
    aliases: []
    related_topics: [neural_operators]
    priority: medium
    notes: Replace this item with someone you want to track.
```

For OpenAlex author searches, `source_ids.openalex` can be either an OpenAlex
author URL such as `https://openalex.org/A123456789` or the bare OpenAlex ID.

## Running

Run the default date window:

```bash
uv run litreview run
```

Run an explicit inclusive date window:

```bash
uv run litreview run --from 2026-08-24 --to 2026-08-31
```

Regenerate an existing successful report window:

```bash
uv run litreview run --from 2026-08-24 --to 2026-08-31 --overwrite
```

Search only watched authors and skip topic queries:

```bash
uv run litreview run --author-only
```

Generate a report without advancing the stored last-run date:

```bash
uv run litreview run --no-date-update
```

Preview output in the terminal without writing run state:

```bash
uv run litreview test
uv run litreview test --author-only
```

Render the registry as Markdown:

```bash
uv run litreview render-registry
```

## Reports

Reports include:

- title
- authors
- publication or online availability date
- source
- DOI link when available
- abstract when available
- category and subcategory
- relevance label
- BibTeX citation metadata
- source diagnostics

Source failures are reported in diagnostics and do not stop the full run unless
all useful sources fail to return relevant results.

## State And Overwrites

Run state is stored in SQLite at `state/litreview.sqlite` by default.

When a successful run already exists for a date window, `research-radar` skips
the run and prints a message explaining that `--overwrite` is required. With
`--overwrite`, the old report file is replaced and the existing run record is
updated.

The first initialization sets the stored last-run date to seven days before the
first scheduled run, so the first automatic report covers the preceding week.

## Optional API Keys

OpenAlex supports an optional API key. To use one, copy `.env.example` to
`.env.local` and fill in the value:

```bash
cp .env.example .env.local
```

```bash
OPENALEX_API_KEY=your-key-here
```

The CLI loads `.env` and `.env.local` automatically without overriding existing
environment variables. If `OPENALEX_API_KEY` is missing, OpenAlex requests use
the normal unauthenticated API path. If OpenAlex rejects the key with `401` or
`403`, the adapter retries that request once without the key and records
`fallback_unauthenticated` in source diagnostics.

Do not commit `.env` or `.env.local`.

## Scheduling On macOS

The built-in scheduler helper targets macOS `launchd`.

Preview the plist:

```bash
uv run litreview install-launchd --dry-run
```

Install it:

```bash
uv run litreview install-launchd
```

The generated plist runs hourly and invokes:

```bash
uv run litreview scheduled-run
```

`scheduled-run` only performs the review when the current `Europe/London` time
is Friday 08:00. This keeps the intended schedule independent of the Mac's local
timezone and daylight-saving changes.

Logs are written to:

- `logs/litreview.out.log`
- `logs/litreview.err.log`

`launchd` is macOS-specific. The same CLI can be scheduled with `cron`, GitHub
Actions, or another scheduler by running `uv run litreview run` or
`uv run litreview scheduled-run`.

## Development

Run tests:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check .
```

Validate both the working registry and the public example:

```bash
uv run litreview validate-registry
uv run litreview validate-registry --registry registry.example.yaml
```

Useful repository paths:

- `src/litreview/`: application code
- `src/litreview/sources/`: source adapters
- `tests/`: unit tests
- `reports/`: generated Markdown reports, ignored except `.gitkeep`
- `state/`: SQLite runtime state, ignored except `.gitkeep`
- `logs/`: scheduler logs, ignored except `.gitkeep`

## Limitations

- This is a metadata and abstract alerting tool; it does not retrieve or analyze
  full text.
- Email, notifications, and feedback-derived ranking are out of scope for the
  current version.
- Crossref, Semantic Scholar, and PubMed are not implemented yet.
- Topic matching is rule based and intentionally simple.
- arXiv requests are throttled to avoid excessive API traffic.

## License

MIT License. See `LICENSE`.
