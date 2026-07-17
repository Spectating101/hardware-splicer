# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `v1.1.0` / `v1.1.0-alpha.*` on `main` | Yes |
| Older alphas / untagged trees | Best-effort only |

## What this software is (trust boundary)

Hardware-Splicer assists **compile, DRC, packaging, and bench gate workflows**. It does **not**:

- Certify electrical safety, UL/CE, or production readiness
- Authorize power-on — the human operator does
- Guarantee fab-ready copper (default preview ≠ autorouted)

See [`docs/COLD_INTERNAL_EXIT.md`](docs/COLD_INTERNAL_EXIT.md) and [`docs/SUPPORT_AND_LIABILITY_v1.md`](docs/SUPPORT_AND_LIABILITY_v1.md).

## Reporting a vulnerability

Please **do not** open a public issue for security-sensitive reports.

1. Email the maintainer via the contact on your GitHub profile / release notes, **or**
2. Open a **private** security advisory on the GitHub repo if enabled.

Include: affected version/tag, reproduction steps, impact, and any logs (redact secrets).

## API / self-host notes

- Treat `HARDWARE_SPLICER_*` secrets and API bind addresses as sensitive.
- Do not expose `/v1` to the public internet without auth, TLS, and an allowlist.
- See [`docs/BUILD_FILES_API_SECURITY.md`](docs/BUILD_FILES_API_SECURITY.md) when present.

We aim to acknowledge valid reports within 14 days.
