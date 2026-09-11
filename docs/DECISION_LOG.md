# Decision Log

Significant engineering decisions with rationale. Newest last. Dates are
2026-09 (project build-out).

## D1 — Modular monolith first, not microservices
The mission allows service extraction "only when justified" (§32, §64). The
enforcement path is one in-process engine; latency and atomicity matter more
than independent scaling at MVP. Extraction seams exist (store protocol, tool
adapters, event bus).

## D2 — Python 3.11+/FastAPI/SQLAlchemy/Pydantic v2
FastAPI is explicitly suggested by the mission; Pydantic v2 gives strict
boundary validation (`extra=forbid`) with discriminated unions for the
constraint vocabulary. SQLAlchemy Core keeps SQLite-dev/Postgres-prod on one
schema without ORM overhead.

## D3 — Deterministic rule-based intent compiler for v1
An LLM compiler would be a dependency and a trust question at the heart of the
authorization story. v1 is rule-based, offline, and testable; it records
ambiguity rather than guessing, and the firewall treats missing constraints on
high-impact operations as ESCALATE — so compiler imprecision can only make
IntentGuard stricter, never looser. An LLM compiler can be added behind the
same interface (its output passes identical validation + firewall).

## D4 — Capabilities are the enforcement artifact
The firewall checks against the minted capability (derived from intent ∩
policy), not the mutable intent text. Versions of both are recorded on every
decision (§70), so historical decisions remain explainable.

## D5 — Policy can only narrow
Deny rules block; limit rules take the minimum across layers; there are no
permissive rules at all (§69: "more permissive policies must never silently
override stronger restrictions"). Implemented in PolicyEngine; unit-tested.

## D6 — Storage: TEXT-typed timestamps/decimals for dialect portability
ISO-8601 UTC strings sort chronologically and Decimal-as-string survives
SQLite/PostgreSQL without dialect-specific types. Trade-off (less type
enforcement in the DB layer) documented; Alembic migrations are the roadmap
path for schema hardening.

## D7 — Trajectory analysis runs even on hard-failed actions
Early versions gated taint/trajectory analysis behind "no prior failure",
which made session degradation inert against block-retry loops (an attacker
probing constraints repeatedly would never degrade). Now runs always; the
degradation defense and taint explanations depend on it. Found by the test
suite, not by assumption.

## D8 — Replay detection binds to executions, not authorizations
An allowed-but-unexecuted action may legitimately be retried (transient
failures). Replay-blocking now keys off the execution ledger (idempotent
execution recorded per decision), keeping double-execution impossible while
not breaking retries. Engine still refuses to execute any decision twice.

## D9 — Approvals are digest-bound, single-use, expiring
The digest covers session, tool, operation, and full parameters. A grant
cannot be replayed for another action (tested), and consumption is recorded
in the audit chain. Approval dedupe is scoped (session+digest) — the O(n²)
full-scan version was a measured p50 75ms → 8.5ms fix.

## D10 — Trusted observations for taint analysis
Web/document/A2A-inbox adapters build `Observation` objects themselves;
agent-supplied context is accepted only as additional (best-effort) signal.
Hard constraint enforcement never depends on agent-supplied context.

## D11 — Frontend: no-build ES-module SPA instead of Next.js for v1
Decision criteria from §19/§64: every dependency needs a reason. A zero-build
dashboard ships with the repo, serves from FastAPI, and avoids a Node
toolchain for a Python-first product. Design language is specified in
docs/DESIGN_RESEARCH.md (tokens verified for WCAG AA). Migration path to
Next.js/React is straightforward (same REST/SSE contract) and documented as
the productionization step.

## D12 — AttackBench families are distinct parameterizations, not padded counts
The mission asks for thousands of scenarios; we shipped 208 meaningful ones
and say so honestly (REQUIREMENTS R8.4 ◐). Padding grids with duplicates
would inflate detection metrics without new coverage — anti-goal per §10
("Never fabricate benchmark results" — padded counts are results-inflation
by another name).

## D13 — MIT license
Permissive, startup-friendly; THIRD_PARTY_NOTICES kept as dependencies.md
entry (all current deps are MIT/BSD/Apache — see DEPENDENCIES).

## D14 — Demo attacks use sandbox-only content
All malicious pages/documents live behind pseudo-schemes and `*.example`
hosts inside seeded content (§9 "Do not provide operational instructions for
real-world abuse"). The narrative shows the *defense*, not an exploit recipe.
