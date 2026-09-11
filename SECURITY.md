# Security Policy

## Reporting a vulnerability

Email: open a GitHub security advisory (preferred) or contact the maintainer
directly. Do **not** open a public issue for exploitable flaws.

Include: description, impact, reproduction (the AttackBench scenario format is
ideal — `intentguard/attackbench/schema.py`), affected versions/commits.

## Scope

In scope: the IntentGuard backend (`backend/intentguard/`), its API, the
dashboard, the Docker packaging, and the security claims made in
docs/SECURITY_MODEL.md / docs/THREAT_MODEL.md (a documented limit that fails
in practice is a vulnerability).

Out of scope: the mock tools' sandbox content (attacker pages under
`*.example` are intentional), social engineering, physical attacks, and
vulnerabilities in undeployed research code paths.

## Response targets (best effort)

- Acknowledgement: 72 hours
- Triage & severity: 7 days
- Fix or mitigation for criticals: 30 days

## Security testing rules

If you test IntentGuard: only against your own deployment, only the sandbox
mock tools, never real third-party services. The AttackBench harness exists
precisely so adversarial testing never needs to leave the sandbox.
