# Deployment

## Docker (verified)

```bash
docker compose up -d
# logs show the one-time bootstrap admin key:
docker compose logs intentguard | grep "Admin API key"
# dashboard: http://localhost:8400/app/   health: http://localhost:8400/health
```

The SQLite file persists in the `intentguard-data` volume. A PostgreSQL
service is included under the `postgres` profile:

```bash
INTENTGUARD_STORE=postgres \
INTENTGUARD_DATABASE_URL=postgresql+psycopg://intentguard:intentguard@db:5432/intentguard \
docker compose --profile postgres up -d
```

(The psycopg driver must be added to dependencies for Postgres use; SQLite is
the verified default. Change the compose password for anything real.)

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `INTENTGUARD_STORE` | `sqlite` | `sqlite` \| `postgres` \| `memory` |
| `INTENTGUARD_SQLITE_PATH` | `./data/intentguard.db` | SQLite file path |
| `INTENTGUARD_DATABASE_URL` | — | SQLAlchemy URL for postgres |
| `INTENTGUARD_HOST` / `INTENTGUARD_PORT` | 127.0.0.1 / 8400 | bind address |
| `INTENTGUARD_CORS_ORIGINS` | local | comma-separated allowed origins |
| `INTENTGUARD_RATE_LIMIT_PER_MIN` | 600 | per-key sliding window |
| `INTENTGUARD_AUDIT_SIGNING_KEY` | — | base64 Ed25519 private key (optional) |
| `INTENTGUARD_BOOTSTRAP_ADMIN` | `1` | seed first org + admin key on empty store |

## Production checklist (honest state)

Done in-repo:
- [x] Container image + compose + healthcheck
- [x] Key hashing, role model, tenant scoping, rate limiting, security headers
- [x] Audit chain with optional Ed25519 signing

Required before real production use (not automated here):
- [ ] TLS termination (reverse proxy: Caddy/Traefik/nginx) — the app serves plain HTTP
- [ ] `INTENTGUARD_BOOTSTRAP_ADMIN=0` after the first boot; store the bootstrap key in a secret manager
- [ ] PostgreSQL + Alembic-managed migrations (currently `create_all`)
- [ ] Redis-backed rate limiting if running replicas
- [ ] Log aggregation; structured logs are plain today
- [ ] Audit-log retention/archival job (retention policy: decisions and audit
      events are security records — define before deleting anything)
- [ ] Dependency & container scanning in the deploy pipeline (CI runs pip-audit on push)
- [ ] Backups: the SQLite/PG file is the entire authorization state — schedule and test restores

## Scaling notes

The engine is in-process and stateless besides the store; horizontal scaling
needs (a) shared Postgres, (b) shared rate-limit store, (c) the event bus
fanned out via Redis pub/sub if multiple replicas serve SSE. The firewall
decision path is pure computation + a few indexed queries — benchmark before
optimizing (docs/BENCHMARKS.md).
