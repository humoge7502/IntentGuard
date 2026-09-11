# Independent Audit — Round 2

Date: 2026-09-12, after the initial build. Mandate: "if this were released to
real users today, what could still fail?" Method: fresh adversarial review of
the shipped code with grep-level evidence for every finding, no reliance on
earlier build reports. Every finding below was confirmed against the code
before fixing.

## Confirmed defects (all fixed, all with regression tests)

### BUG-001 — Audit chain append crashes under concurrent writers
- Severity: HIGH (reliability of the security-critical path) · Priority: P1
- Affected: `intentguard/audit/chain.py`, storage unique index `(org_id, seq)`
- Evidence: no IntegrityError/retry handling existed (grep: zero matches)
- Reproduction: two threads append to one org; both read the same head, both
  compute seq N+1; the loser's INSERT violates the unique index → unhandled
  exception → 500 from `firewall/evaluate`.
- Fix: bounded retry (4 attempts, backoff) recomputing seq from the refreshed
  head on `IntegrityError`.
- Regression tests: `test_audit_append_survives_seq_collision` (deterministic
  stale-head monkeypatch), `test_audit_concurrent_appends_keep_chain_valid`
  (8 threads × 5 appends on a file-backed WAL store → chain verifies, 41
  events). Status: VERIFIED.

### BUG-002 — Double side effect possible via racing executions
- Severity: HIGH (security/integrity — the exact failure class IntentGuard
  exists to prevent) · Priority: P0
- Affected: `intentguard/engine.py::execute` (check-then-act:
  `get_execution is None` at line 223 vs `record_execution` at line 238)
- Reproduction: two concurrent `execute(decision_id)` calls both pass the
  existence check → both run the tool → order placed twice.
- Fix: claim-then-complete. `store.claim_execution` is an atomic INSERT keyed
  on decision_id (PK); the loser gets ConflictError. A claimed-but-failed
  execution stays consumed (re-propose, never blind retry). Claim rows carry
  the action digest, so replay protection already covers in-flight claims.
- Regression test: `test_concurrent_execution_has_exactly_one_side_effect`
  (4 racing threads → exactly 1 order, 3 conflicts). Status: VERIFIED.

### BUG-003 — `pending_approvals` metric counted all approvals
- Severity: MEDIUM (operational correctness) · Priority: P2
- Evidence: `metrics_summary` used `list_approvals(org_id, None)`.
- Impact: dashboard showed granted/denied/consumed requests as "pending".
- Fix: count `ApprovalStatus.PENDING` only.
- Regression test: `test_pending_approvals_metric_counts_only_pending`.
  Status: VERIFIED.

### BUG-004 — SQLite file store lacked WAL and busy timeout
- Severity: MEDIUM (reliability under realistic load) · Priority: P1
- Evidence: no journal_mode/busy_timeout pragmas.
- Impact: while AttackBench or demos wrote continuously (~9s bursts), a
  concurrent dashboard request could hit `database is locked` → 500.
- Fix: WAL journal mode + `busy_timeout=30000` + `synchronous=NORMAL` on every
  file-backed SQLite connection (event-listener); readers now proceed during
  write bursts.
- Regression test: `test_sqlite_file_store_uses_wal`. Status: VERIFIED.

### BUG-005 — API keys leaked into access logs via SSE query parameter
- Severity: MEDIUM (credential exposure; CVSS ~5.3 information disclosure to
  log readers) · Priority: P1
- Evidence: `GET /events/stream?api_key=…`; uvicorn access logs (and any
  reverse-proxy logs) capture full URLs including query strings.
- Fix: single-use, 60-second **stream tokens** (`POST /api/v1/events/token`,
  header-authenticated; `StreamTokenBroker`). EventSource connects with the
  worthless one-shot token; the API key never appears in a URL. The frontend
  was updated to the token flow. The access-log line itself now logs path
  only — never the query string.
- Regression tests: `test_stream_token_flow` (403 paths + broker single-use +
  expiry + unauthenticated token issuance), plus **live browser verification**
  of the new flow delivering events. Status: VERIFIED (browser) / PARTIALLY
  VERIFIED over HTTP (see environment note below).

### BUG-006 — Rate limiter key map grew without bound
- Severity: LOW-MEDIUM (memory availability) · Priority: P2
- Evidence: `_hits` defaultdict with no cap; anonymous garbage headers create
  unbounded entries.
- Fix: 10,000-key cap with oldest-entry eviction.
- Regression test: `test_rate_limiter_map_is_capped`. Status: VERIFIED.

## Environment constraint discovered (not an IntentGuard bug)

The installed starlette 1.6.0 TestClient **deadlocks on any infinite
streaming response** — reproduced with a 10-line bare FastAPI app; installing
httpx2 (the starlette-recommended client) does not help. Consequences:
- SSE over HTTP is verified live (browser, real uvicorn server) and at the
  unit level (broker + guard paths), but NOT through the TestClient transport.
  Labeled PARTIALLY VERIFIED for that transport only.
- The old `@app.middleware("http")` (BaseHTTPMiddleware) was replaced with
  pure ASGI `RequestContextMiddleware` while investigating — kept because pure
  ASGI never wraps response bodies and is the correct shape for a streaming
  API (also removes a class of starlette BaseHTTPMiddleware bugs).

## Improvements shipped with the fixes

- `X-Request-ID` on every response + structured access log lines
  (`request_id, method, path, status, duration_ms`) with query strings
  excluded — privacy-preserving by construction.
- SSE stream is now tenant-scoped (events for other orgs are filtered by the
  stream token's org).
- Tool-adapter exceptions during execution are recorded (decision consumed,
  error stored) instead of leaving orphan claims.
- Mobile (≤480px) topbar wrap fix; 390px viewport visually verified.

## Post-fix verification

- Full suite: **76 passed** (68 prior + 8 new round-2 regression tests + gate).
- Lint: `ruff check` clean.
- Latency benchmark n=500 post-fix: p99 15.0ms (no regression).
- Live server: demos run 200; stream token issuance 200; browser-verified
  event delivery through the new token flow.
