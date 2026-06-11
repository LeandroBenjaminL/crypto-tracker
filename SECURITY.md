# Security Policy

## Supported Versions

Only the latest version receives security updates.

| Version | Supported          |
|---------|--------------------|
| latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, **do not open a public issue**.

Instead, report it privately via email to the repository owner.
You should expect an acknowledgment within 48 hours and a remediation plan within 7 days.

## Token & Secret Security

- **Never commit secrets** to the repository. All secrets go in `.env` (gitignored).
- The `.env.example` file documents required variables without real values.
- Rotate tokens regularly.
- If a token is exposed, revoke it immediately and rotate all tokens sharing the same scope.

## CI/CD Security

- CI workflows run in isolated runners.
- Secrets are injected via GitHub Actions secrets, never hardcoded.
- Workflow files pass validation before merge.

## Dependencies

- Dependencies are pinned in `pyproject.toml`.
- Review dependency updates for breaking changes or security patches.
- Run `pip-audit` or `safety check` before major upgrades.

## Data Privacy

- No telemetry or usage data is sent to external services.
- Sensitive data should never be logged or included in error messages.
- API keys are stored in `.env` only and never hardcoded in source.
