# Contributing to Handoff

Thanks for wanting to help. This project is a hackathon submission, so the
maintainer's time is limited; keep changes small and focused.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
```

## Running tests

```bash
python -m pytest tests/ -v
```

The suite skips the live cloud test unless `HANDOFF_DB_URL` is set. That test
hits the real CockroachDB cluster and Bedrock, so only run it when you intend
to.

## What to work on

Look at open issues, or the `docs/roadmap.md` file. If you want to add a new
storage adapter or embedding provider, the interfaces are:

- `src/handoff/storage/base.py` — storage contract
- `src/handoff/embeddings.py` — embedding provider contract

## Pull request rules

- One logical change per PR.
- No unrelated reformatting.
- New logic ships with a matching test (assert-based, no framework needed).
- Never commit credentials, tokens, or connection strings. Use env vars.