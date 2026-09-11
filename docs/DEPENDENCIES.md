# THIRD_PARTY_NOTICES / Dependencies

All runtime dependencies and their licenses (checked 2026-09-12 against
PyPI metadata; re-verify on upgrade).

## Backend runtime

| Package | Version constraint | License | Copyright |
|---|---|---|---|
| fastapi | >=0.115 | MIT | © Sebastián Ramírez |
| starlette (transitive) | — | BSD-3-Clause | © SentinelOne, Inc. |
| uvicorn[standard] | >=0.30 | BSD-3-Clause | © Jordi Boggiano relayed by encode |
| pydantic | >=2.9 | MIT | © Pydantic Services Inc. |
| SQLAlchemy | >=2.0 | MIT | © SQLAlchemy authors |
| PyYAML | >=6.0 | MIT | © Ingy döt Net, Kirill Simonov |
| httpx | >=0.27 | BSD-3-Clause | © Encode OSS Ltd. |
| cryptography | >=43.0 | Apache-2.0 OR BSD-3-Clause | © cryptography developers |

## Backend dev

pytest (MIT), ruff (MIT).

## Frontend

Zero bundled packages. Google Fonts (Inter, JetBrains Mono) are loaded via
`<link>` at runtime under the SIL Open Font License; the UI degrades to
system font stacks without network.

## This project

MIT — see LICENSE. All first-party code is original to this repository except
where third-party snippets would appear (none currently).
