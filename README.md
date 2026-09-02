# Paper Alert Bot

Weekly literature alerts for a configured research scope.

## Setup

```bash
uv sync --extra dev
```

## Common commands

```bash
uv run litreview validate-registry
uv run litreview run
uv run litreview run --from 2026-08-24 --to 2026-08-31
uv run litreview run --from 2026-08-24 --to 2026-08-31 --overwrite
uv run litreview run --no-date-update
uv run litreview scheduled-run
uv run litreview test
uv run litreview render-registry
uv run litreview install-launchd --dry-run
uv run pytest
```

Reports are written to `reports/YYYY-MM-DD.md`. State is stored in `state/litreview.sqlite`.

## Optional API keys

OpenAlex can use an optional API key. Put it in `.env.local`:

```bash
OPENALEX_API_KEY=your-key-here
```

The CLI loads `.env` and `.env.local` automatically without overriding existing
environment variables. If `OPENALEX_API_KEY` is missing, requests fall back to the
current unauthenticated OpenAlex API behavior. If OpenAlex rejects the key with
`401` or `403`, the adapter retries that request once without the key and records
`fallback_unauthenticated` in source diagnostics.

The v1 scheduler target is macOS `launchd`. The generated plist runs hourly and invokes `uv run litreview scheduled-run`; the CLI only runs the review when the current `Europe/London` time is Friday 08:00. This keeps London-time behavior independent of the Mac's local timezone and daylight-saving changes. The scheduler can be replaced by `cron`, GitHub Actions, or a hosted scheduled job later.
