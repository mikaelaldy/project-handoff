# Security Policy

## Reporting a vulnerability

If you find a security issue, please do **not** open a public GitHub issue.
Email the maintainer directly at mikaelaldy56@gmail.com with:

- Affected component and version
- Steps to reproduce
- Impact assessment

## Secrets handling

This project processes context packets that may contain credentials. Two rules:

1. **Redaction happens at the write boundary.** `handoff.envelope.redact()`
   scrubs common secret shapes (API keys, tokens, private keys, passwords)
   before anything is persisted to storage. If you store raw secrets, that is
   a bug — report it.
2. **Never commit credentials.** Connection strings and keys belong in
   environment variables (`HANDOFF_DB_URL`, `HANDOFF_DATABASE_URL`, etc.).
   The live test reads `HANDOFF_DB_URL` from env and skips if unset.

## Rotation policy

If a credential is ever exposed in git history, rewriting history is not
sufficient — GitHub may retain unreachable objects and forks may exist.
Rotate the credential. See the git history of `tests/test_live_cloud.py` for a
prior incident and how it was handled.