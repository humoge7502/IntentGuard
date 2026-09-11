# IntentGuard API Reference (v1)

Base URL: `http://127.0.0.1:8400/api/v1` · OpenAPI: `GET /docs` (Swagger UI) ·
`GET /openapi.json`.

## Authentication

All `/api/v1` routes require an API key:

```
X-API-Key: ig_…            (or)
Authorization: Bearer ig_…
```

Keys are created by an admin (bootstrap prints the first one once) and stored
hashed. Roles: **viewer** (read-only) < **agent** (evaluate/execute/sessions)
< **admin** (policies, approvals, revocation, keys, audit verify, benchmarks,
demos).

Errors use a stable envelope: `{"error": CODE, "message": "…"}` with status
400/403/404/409/422/429.

## Endpoints

### Identity & meta
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/me` | any | key identity: org, principal, role, key id |
| GET | `/tools` | any | registered sandbox tools + operation classes |

### Intents
| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/intents` | agent+ | `{text}` → compile → IntentSpec (with ambiguities) |
| GET | `/intents` | any | list |
| GET | `/intents/{id}` | any | one intent |
| GET | `/intents/{id}/graph` | any | nodes/edges for the intent graph UI |

### Agents & sessions
| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/agents` | admin | `{name, framework}` register an agent identity |
| GET | `/agents` | any | list |
| POST | `/sessions` | agent+ | `{agent_id, intent_id, ttl_seconds?}` → session (mints capability) |
| GET | `/sessions/{id}` | any | full view: session, intent, capability, trajectory, decisions |

### Firewall
| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/firewall/evaluate` | agent+ | propose an action → Decision (before execution) |
| POST | `/firewall/execute` | agent+ | `{decision_id}` → run an ALLOW decision once (idempotent) |
| GET | `/decisions?session_id&limit` | any | decision history |

`evaluate` body:
```json
{
  "session_id": "ses_…", "agent_id": "agt_…",
  "tool": "shopping_api", "operation": "purchase",
  "params": {"item": "laptop", "brand": "Lenovo", "unit_price": "9500",
             "quantity": 100, "currency": "INR", "destination": "Chennai"},
  "context": []
}
```

Decision response (abridged):
```json
{
  "decision": "block",
  "reasons": ["AMOUNT_LIMIT_EXCEEDED", "INTENT_DIVERGENCE"],
  "checks": [{"check": "intent_alignment", "status": "fail", "detail": "authorized 1000000 INR, requested 7500000 INR"}],
  "risk": {"score": 65, "band": "high", "categories": ["INTEGRITY"], "signals": []},
  "versions": {"intent": 1, "capability": 1, "policy_rules": [], "compiler": "rule_based_v1", "proposal": {}},
  "action_digest": "9f2c…", "latency_ms": 6.1
}
```

### Approvals & capabilities
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/approvals?status=` | any | approval requests |
| POST | `/approvals/{id}/grant` | admin | `{approver}` → grant (single-use, digest-bound) |
| POST | `/approvals/{id}/deny` | admin | `{approver}` |
| GET | `/capabilities` | any | list |
| POST | `/capabilities/{id}/revoke` | admin | `{reason}` — effective immediately |

### Policies
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/policies` | any | list rules |
| POST | `/policies` | admin | `{layer, name, effect: deny|limit, tool?, operation?, max_amount?, currency?, reason_code}` |

### Audit & metrics
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/audit?limit` | any | hash-chained events |
| POST | `/audit/verify` | admin | recompute chain → `{valid, events, broken_at_seq}` |
| GET | `/metrics/summary` | any | dashboard counters |

### Benchmarks & demos
| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/benchmarks/run` | admin | `{max_per_family}` → full AttackBench report |
| POST | `/demo/{name}/run` | admin | `intent_divergence` · `trajectory_credential_harvest` → transcript |

### Live stream
| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/events/stream` | any | SSE; key via header or `?api_key=` (EventSource limitation). Emits `decision`, `approval`, `execution` events; keepalive comments every 15s. |

## Versioning

`/api/v1/` prefix; breaking changes would ship as `/api/v2`. Enums and reason
codes are stable wire identifiers (see `core/enums.py`, firewall reasons).
