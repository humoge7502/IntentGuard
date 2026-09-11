"""Reference SQL store (SQLAlchemy Core). SQLite by default; PostgreSQL works
by passing ``INTENTGUARD_DATABASE_URL``.

MVP storage note (documented in DECISION_LOG): datetime and decimal values are
stored as ISO/numeric strings in TEXT columns so one schema runs on both
dialects. All timestamps are timezone-aware UTC, which keeps ISO-8601 string
ordering equivalent to chronological ordering.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    insert,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from intentguard.core.enums import ApprovalStatus
from intentguard.core.schemas import (
    DecisionRecord,
    AgentIdentity,
    AgentSession,
    ApiKeyRecord,
    ApprovalRequest,
    AuditEvent,
    Capability,
    IntentSpec,
    Observation,
    Organization,
    PolicyRule,
    Principal,
    TrajectoryStep,
    utcnow,
)
from intentguard.storage.store import IntentGuardStore

meta = MetaData()

_t_orgs = Table(
    "organizations", meta,
    Column("org_id", String, primary_key=True),
    Column("name", String),
    Column("created_at", String),
)
_t_principals = Table(
    "principals", meta,
    Column("principal_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("display_name", String),
    Column("kind", String),
    Column("created_at", String),
)
_t_agents = Table(
    "agents", meta,
    Column("agent_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("name", String),
    Column("owner_principal_id", String),
    Column("framework", String),
    Column("trust_score", Float),
    Column("created_at", String),
)
_t_api_keys = Table(
    "api_keys", meta,
    Column("key_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("principal_id", String),
    Column("role", String),
    Column("key_hash", String, index=True),
    Column("name", String),
    Column("revoked", Integer),
    Column("created_at", String),
)
_t_intents = Table(
    "intents", meta,
    Column("intent_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("principal_id", String),
    Column("version", Integer),
    Column("goal", String),
    Column("raw_text", String),
    Column("constraints_json", String),
    Column("allowed_operations_json", String),
    Column("ambiguities_json", String),
    Column("compiled_by", String),
    Column("created_at", String),
)
_t_capabilities = Table(
    "capabilities", meta,
    Column("capability_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("intent_id", String),
    Column("agent_id", String),
    Column("version", Integer),
    Column("status", String),
    Column("scopes_json", String),
    Column("budget_json", String),
    Column("expires_at", String),
    Column("revoked_reason", String),
    Column("created_at", String),
)
_t_sessions = Table(
    "sessions", meta,
    Column("session_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("agent_id", String),
    Column("intent_id", String),
    Column("capability_id", String),
    Column("status", String),
    Column("degraded", Integer),
    Column("created_at", String),
)
_t_policy_rules = Table(
    "policy_rules", meta,
    Column("rule_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("layer", String),
    Column("name", String),
    Column("effect", String),
    Column("tool", String),
    Column("operation", String),
    Column("max_amount", String),
    Column("currency", String),
    Column("reason_code", String),
    Column("description", String),
    Column("created_at", String),
)
_t_decisions = Table(
    "decisions", meta,
    Column("decision_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("action_id", String),
    Column("action_digest", String, index=True),
    Column("session_id", String, index=True),
    Column("agent_id", String),
    Column("intent_id", String),
    Column("capability_id", String),
    Column("decision", String),
    Column("reasons_json", String),
    Column("checks_json", String),
    Column("risk_json", String),
    Column("versions_json", String),
    Column("approval_id", String),
    Column("latency_ms", Float),
    Column("created_at", String),
)
_t_approvals = Table(
    "approvals", meta,
    Column("approval_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("session_id", String, index=True),
    Column("intent_id", String),
    Column("action_digest", String, index=True),
    Column("action_summary_json", String),
    Column("reasons_json", String),
    Column("status", String),
    Column("granted_by", String),
    Column("requested_at", String),
    Column("expires_at", String),
    Column("resolved_at", String),
)
_t_trajectory = Table(
    "trajectory_steps", meta,
    Column("rowid_seq", Integer, primary_key=True, autoincrement=True),
    Column("org_id", String, index=True),
    Column("session_id", String, index=True),
    Column("seq", Integer),
    Column("action_id", String),
    Column("tool", String),
    Column("operation", String),
    Column("side_effect_class", String),
    Column("decision", String),
    Column("reasons_json", String),
    Column("risk_score", Integer),
    Column("taint", Integer),
    Column("created_at", String),
)
_t_observations = Table(
    "session_observations", meta,
    Column("rowid_seq", Integer, primary_key=True, autoincrement=True),
    Column("org_id", String, index=True),
    Column("session_id", String, index=True),
    Column("obs_json", String),
    Column("created_at", String),
)
_t_audit = Table(
    "audit_events", meta,
    Column("rowid_seq", Integer, primary_key=True, autoincrement=True),
    Column("org_id", String),
    Column("seq", Integer),
    Column("event_type", String),
    Column("payload_json", String),
    Column("prev_hash", String),
    Column("hash", String),
    Column("signature", String),
    Column("created_at", String),
)
_t_executions = Table(
    "executions", meta,
    Column("decision_id", String, primary_key=True),
    Column("org_id", String, index=True),
    Column("session_id", String, index=True),
    Column("action_digest", String, index=True),
    Column("summary_json", String),
    Column("created_at", String),
)
Index("ix_audit_org_seq", _t_audit.c.org_id, _t_audit.c.seq, unique=True)

# table -> (primary-key column key, [(column, json_source_field_or_None)])
_SCHEMA: dict[Table, tuple[str, list[tuple[Column, str | None]]]] = {
    _t_orgs: ("org_id", [(c, None) for c in _t_orgs.columns]),
    _t_principals: ("principal_id", [(c, None) for c in _t_principals.columns]),
    _t_agents: ("agent_id", [(c, None) for c in _t_agents.columns]),
    _t_api_keys: ("key_id", [(c, None) for c in _t_api_keys.columns]),
    _t_intents: (
        "intent_id",
        [
            (_t_intents.c.intent_id, None),
            (_t_intents.c.org_id, None),
            (_t_intents.c.principal_id, None),
            (_t_intents.c.version, None),
            (_t_intents.c.goal, None),
            (_t_intents.c.raw_text, None),
            (_t_intents.c.constraints_json, "constraints"),
            (_t_intents.c.allowed_operations_json, "allowed_operations"),
            (_t_intents.c.ambiguities_json, "ambiguities"),
            (_t_intents.c.compiled_by, None),
            (_t_intents.c.created_at, None),
        ],
    ),
    _t_capabilities: (
        "capability_id",
        [
            (_t_capabilities.c.capability_id, None),
            (_t_capabilities.c.org_id, None),
            (_t_capabilities.c.intent_id, None),
            (_t_capabilities.c.agent_id, None),
            (_t_capabilities.c.version, None),
            (_t_capabilities.c.status, None),
            (_t_capabilities.c.scopes_json, "scopes"),
            (_t_capabilities.c.budget_json, "budget"),
            (_t_capabilities.c.expires_at, None),
            (_t_capabilities.c.revoked_reason, None),
            (_t_capabilities.c.created_at, None),
        ],
    ),
    _t_sessions: ("session_id", [(c, None) for c in _t_sessions.columns]),
    _t_policy_rules: ("rule_id", [(c, None) for c in _t_policy_rules.columns]),
    _t_decisions: (
        "decision_id",
        [
            (_t_decisions.c.decision_id, None),
            (_t_decisions.c.org_id, None),
            (_t_decisions.c.action_id, None),
            (_t_decisions.c.action_digest, None),
            (_t_decisions.c.session_id, None),
            (_t_decisions.c.agent_id, None),
            (_t_decisions.c.intent_id, None),
            (_t_decisions.c.capability_id, None),
            (_t_decisions.c.decision, None),
            (_t_decisions.c.reasons_json, "reasons"),
            (_t_decisions.c.checks_json, "checks"),
            (_t_decisions.c.risk_json, "risk"),
            (_t_decisions.c.versions_json, "versions"),
            (_t_decisions.c.approval_id, None),
            (_t_decisions.c.latency_ms, None),
            (_t_decisions.c.created_at, None),
        ],
    ),
    _t_approvals: (
        "approval_id",
        [
            (_t_approvals.c.approval_id, None),
            (_t_approvals.c.org_id, None),
            (_t_approvals.c.session_id, None),
            (_t_approvals.c.intent_id, None),
            (_t_approvals.c.action_digest, None),
            (_t_approvals.c.action_summary_json, "action_summary"),
            (_t_approvals.c.reasons_json, "reasons"),
            (_t_approvals.c.status, None),
            (_t_approvals.c.granted_by, None),
            (_t_approvals.c.requested_at, None),
            (_t_approvals.c.expires_at, None),
            (_t_approvals.c.resolved_at, None),
        ],
    ),
    _t_trajectory: (
        "rowid_seq",
        [
            (_t_trajectory.c.org_id, None),
            (_t_trajectory.c.session_id, None),
            (_t_trajectory.c.seq, None),
            (_t_trajectory.c.action_id, None),
            (_t_trajectory.c.tool, None),
            (_t_trajectory.c.operation, None),
            (_t_trajectory.c.side_effect_class, None),
            (_t_trajectory.c.decision, None),
            (_t_trajectory.c.reasons_json, "reasons"),
            (_t_trajectory.c.risk_score, None),
            (_t_trajectory.c.taint, None),
            (_t_trajectory.c.created_at, None),
        ],
    ),
    _t_observations: (
        "rowid_seq",
        [
            (_t_observations.c.org_id, None),
            (_t_observations.c.session_id, None),
            (_t_observations.c.obs_json, "__whole__"),
            (_t_observations.c.created_at, None),
        ],
    ),
    _t_audit: (
        "rowid_seq",
        [
            (_t_audit.c.org_id, None),
            (_t_audit.c.seq, None),
            (_t_audit.c.event_type, None),
            (_t_audit.c.payload_json, "payload"),
            (_t_audit.c.prev_hash, None),
            (_t_audit.c.hash, None),
            (_t_audit.c.signature, None),
            (_t_audit.c.created_at, None),
        ],
    ),
}

_BOOL_KEYS = {"revoked", "degraded", "taint"}


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class SqlStore(IntentGuardStore):
    def __init__(self, url: str = "sqlite:///./data/intentguard.db") -> None:
        kwargs: dict[str, Any] = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if url in ("sqlite://", "sqlite:///:memory:"):
                kwargs["poolclass"] = StaticPool
        self.engine: Engine = create_engine(url, **kwargs)
        meta.create_all(self.engine)

    # -- serialization helpers ---------------------------------------------

    def _upsert(self, conn: Any, table: Table, row: dict[str, Any]) -> None:
        pk, _ = _SCHEMA[table]
        conn.execute(delete(table).where(getattr(table.c, pk) == row[pk]))
        conn.execute(insert(table).values(**row))

    @staticmethod
    def _row_from_model(
        model: Any, columns: list[tuple[Column, str | None]]
    ) -> dict[str, Any]:
        data = model.model_dump(mode="json")
        row: dict[str, Any] = {}
        for col, json_field in columns:
            if json_field == "__whole__":
                row[col.key] = _dumps(data)
            elif json_field is not None:
                row[col.key] = _dumps(data[json_field])
            else:
                row[col.key] = data.get(col.key)
        return row

    @staticmethod
    def _model_from_row(
        model_cls: type, row: Any, columns: list[tuple[Column, str | None]]
    ) -> Any:
        data: dict[str, Any] = {}
        for col, json_field in columns:
            raw = getattr(row, col.key)
            if raw is None:
                continue
            if json_field == "__whole__":
                data.update(json.loads(raw))
            elif json_field is not None:
                data[json_field] = json.loads(raw)
            else:
                data[col.key] = raw
        for key in _BOOL_KEYS:
            if key in data and isinstance(data[key], int):
                data[key] = bool(data[key])
        return model_cls.model_validate(data)

    def _save(self, model: Any, table: Table) -> None:
        _, columns = _SCHEMA[table]
        row = self._row_from_model(model, columns)
        with self.engine.begin() as conn:
            self._upsert(conn, table, row)

    def _get(
        self,
        model_cls: type,
        table: Table,
        pk_col: Any,
        pk: str,
        org_col: Any | None,
        org_id: str,
    ) -> Any:
        stmt = select(table).where(pk_col == pk)
        if org_col is not None:
            stmt = stmt.where(org_col == org_id)
        with self.engine.connect() as conn:
            row = conn.execute(stmt).first()
        if row is None:
            return None
        _, columns = _SCHEMA[table]
        return self._model_from_row(model_cls, row, columns)

    def _list(
        self,
        model_cls: type,
        table: Table,
        org_col: Any,
        org_id: str,
        order_col: Any | None = None,
    ) -> list[Any]:
        stmt = select(table).where(org_col == org_id)
        if order_col is not None:
            stmt = stmt.order_by(order_col)
        _, columns = _SCHEMA[table]
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [self._model_from_row(model_cls, r, columns) for r in rows]

    # -- organizations -------------------------------------------------------
    def save_organization(self, org: Organization) -> None:
        self._save(org, _t_orgs)

    def get_organization(self, org_id: str) -> Organization | None:
        return self._get(Organization, _t_orgs, _t_orgs.c.org_id, org_id, None, "")

    # -- principals & agents ---------------------------------------------------
    def save_principal(self, principal: Principal) -> None:
        self._save(principal, _t_principals)

    def get_principal(self, org_id: str, principal_id: str) -> Principal | None:
        return self._get(
            Principal, _t_principals, _t_principals.c.principal_id, principal_id,
            _t_principals.c.org_id, org_id,
        )

    def save_agent(self, agent: AgentIdentity) -> None:
        self._save(agent, _t_agents)

    def get_agent(self, org_id: str, agent_id: str) -> AgentIdentity | None:
        return self._get(
            AgentIdentity, _t_agents, _t_agents.c.agent_id, agent_id,
            _t_agents.c.org_id, org_id,
        )

    def list_agents(self, org_id: str) -> list[AgentIdentity]:
        return self._list(AgentIdentity, _t_agents, _t_agents.c.org_id, org_id, _t_agents.c.created_at)

    # -- api keys -----------------------------------------------------------------
    def save_api_key(self, record: ApiKeyRecord) -> None:
        self._save(record, _t_api_keys)

    def get_api_key_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(_t_api_keys).where(_t_api_keys.c.key_hash == key_hash)
            ).first()
        if row is None:
            return None
        _, columns = _SCHEMA[_t_api_keys]
        return self._model_from_row(ApiKeyRecord, row, columns)

    def list_api_keys(self, org_id: str) -> list[ApiKeyRecord]:
        return self._list(ApiKeyRecord, _t_api_keys, _t_api_keys.c.org_id, org_id)

    # -- intents --------------------------------------------------------------------
    def save_intent(self, intent: IntentSpec) -> None:
        self._save(intent, _t_intents)

    def get_intent(self, org_id: str, intent_id: str) -> IntentSpec | None:
        return self._get(
            IntentSpec, _t_intents, _t_intents.c.intent_id, intent_id,
            _t_intents.c.org_id, org_id,
        )

    def list_intents(self, org_id: str) -> list[IntentSpec]:
        return self._list(IntentSpec, _t_intents, _t_intents.c.org_id, org_id, _t_intents.c.created_at)

    # -- capabilities ------------------------------------------------------------------
    def save_capability(self, capability: Capability) -> None:
        self._save(capability, _t_capabilities)

    def get_capability(self, org_id: str, capability_id: str) -> Capability | None:
        return self._get(
            Capability, _t_capabilities, _t_capabilities.c.capability_id, capability_id,
            _t_capabilities.c.org_id, org_id,
        )

    def list_capabilities(self, org_id: str) -> list[Capability]:
        return self._list(Capability, _t_capabilities, _t_capabilities.c.org_id, org_id, _t_capabilities.c.created_at)

    # -- sessions -------------------------------------------------------------------------
    def save_session(self, session: AgentSession) -> None:
        self._save(session, _t_sessions)

    def get_session(self, org_id: str, session_id: str) -> AgentSession | None:
        return self._get(
            AgentSession, _t_sessions, _t_sessions.c.session_id, session_id,
            _t_sessions.c.org_id, org_id,
        )

    def list_sessions(self, org_id: str) -> list[AgentSession]:
        return self._list(AgentSession, _t_sessions, _t_sessions.c.org_id, org_id, _t_sessions.c.created_at)

    # -- policy ----------------------------------------------------------------------------
    def save_policy_rule(self, rule: PolicyRule) -> None:
        self._save(rule, _t_policy_rules)

    def list_policy_rules(self, org_id: str) -> list[PolicyRule]:
        return self._list(PolicyRule, _t_policy_rules, _t_policy_rules.c.org_id, org_id)

    def delete_policy_rule(self, org_id: str, rule_id: str) -> bool:
        with self.engine.begin() as conn:
            res = conn.execute(
                delete(_t_policy_rules)
                .where(_t_policy_rules.c.rule_id == rule_id)
                .where(_t_policy_rules.c.org_id == org_id)
            )
        return bool(res.rowcount and res.rowcount > 0)

    # -- decisions ---------------------------------------------------------------------------
    def save_decision(self, decision: DecisionRecord) -> None:
        self._save(decision, _t_decisions)

    def get_decision(self, org_id: str, decision_id: str) -> DecisionRecord | None:
        return self._get(
            DecisionRecord, _t_decisions, _t_decisions.c.decision_id, decision_id,
            _t_decisions.c.org_id, org_id,
        )

    def list_decisions(self, org_id: str, session_id: str | None = None, limit: int = 200) -> list[DecisionRecord]:
        stmt = select(_t_decisions).where(_t_decisions.c.org_id == org_id)
        if session_id:
            stmt = stmt.where(_t_decisions.c.session_id == session_id)
        stmt = stmt.order_by(_t_decisions.c.created_at.desc()).limit(limit)
        _, columns = _SCHEMA[_t_decisions]
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [self._model_from_row(DecisionRecord, r, columns) for r in rows]

    def find_allowed_digest(self, org_id: str, session_id: str, action_digest: str) -> bool:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(_t_decisions.c.decision_id)
                .where(_t_decisions.c.org_id == org_id)
                .where(_t_decisions.c.session_id == session_id)
                .where(_t_decisions.c.action_digest == action_digest)
                .where(_t_decisions.c.decision == "allow")
                .limit(1)
            ).first()
        return row is not None

    # -- approvals ------------------------------------------------------------------------------
    def save_approval(self, approval: ApprovalRequest) -> None:
        self._save(approval, _t_approvals)

    def get_approval(self, org_id: str, approval_id: str) -> ApprovalRequest | None:
        return self._get(
            ApprovalRequest, _t_approvals, _t_approvals.c.approval_id, approval_id,
            _t_approvals.c.org_id, org_id,
        )

    def list_approvals(self, org_id: str, status: ApprovalStatus | None = None) -> list[ApprovalRequest]:
        stmt = select(_t_approvals).where(_t_approvals.c.org_id == org_id)
        if status is not None:
            stmt = stmt.where(_t_approvals.c.status == status.value)
        stmt = stmt.order_by(_t_approvals.c.requested_at.desc())
        _, columns = _SCHEMA[_t_approvals]
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [self._model_from_row(ApprovalRequest, r, columns) for r in rows]

    def find_granted_for_digest(self, org_id: str, session_id: str, action_digest: str) -> ApprovalRequest | None:
        stmt = (
            select(_t_approvals)
            .where(_t_approvals.c.org_id == org_id)
            .where(_t_approvals.c.session_id == session_id)
            .where(_t_approvals.c.action_digest == action_digest)
            .where(_t_approvals.c.status == ApprovalStatus.GRANTED.value)
            .order_by(_t_approvals.c.requested_at.desc())
        )
        _, columns = _SCHEMA[_t_approvals]
        with self.engine.connect() as conn:
            row = conn.execute(stmt).first()
        return self._model_from_row(ApprovalRequest, row, columns) if row else None

    # -- trajectory --------------------------------------------------------------------------------
    def append_trajectory_step(self, step: TrajectoryStep) -> None:
        _, columns = _SCHEMA[_t_trajectory]
        row = self._row_from_model(step, columns)
        row.pop("rowid_seq", None)
        with self.engine.begin() as conn:
            conn.execute(insert(_t_trajectory).values(**row))

    def list_trajectory(self, org_id: str, session_id: str) -> list[TrajectoryStep]:
        stmt = (
            select(_t_trajectory)
            .where(_t_trajectory.c.org_id == org_id)
            .where(_t_trajectory.c.session_id == session_id)
            .order_by(_t_trajectory.c.seq)
        )
        _, columns = _SCHEMA[_t_trajectory]
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [self._model_from_row(TrajectoryStep, r, columns) for r in rows]

    # -- observations ----------------------------------------------------------------------------------
    def append_observation(self, org_id: str, session_id: str, observation: Observation) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(_t_observations).values(
                    org_id=org_id,
                    session_id=session_id,
                    obs_json=_dumps(observation.model_dump(mode="json")),
                    created_at=utcnow().isoformat(),
                )
            )

    def list_observations(self, org_id: str, session_id: str) -> list[Observation]:
        stmt = (
            select(_t_observations)
            .where(_t_observations.c.org_id == org_id)
            .where(_t_observations.c.session_id == session_id)
            .order_by(_t_observations.c.rowid_seq)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [Observation.model_validate(json.loads(r.obs_json)) for r in rows]

    def session_observation_count(self, org_id: str, session_id: str) -> int:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(_t_observations.c.rowid_seq)
                .where(_t_observations.c.org_id == org_id)
                .where(_t_observations.c.session_id == session_id)
            ).all()
        return len(rows)

    # -- audit chain -------------------------------------------------------------------------------------
    def append_audit_event(self, event: AuditEvent) -> None:
        _, columns = _SCHEMA[_t_audit]
        row = self._row_from_model(event, columns)
        row.pop("rowid_seq", None)
        with self.engine.begin() as conn:
            conn.execute(insert(_t_audit).values(**row))

    def get_audit_head(self, org_id: str) -> AuditEvent | None:
        stmt = (
            select(_t_audit)
            .where(_t_audit.c.org_id == org_id)
            .order_by(_t_audit.c.seq.desc())
            .limit(1)
        )
        _, columns = _SCHEMA[_t_audit]
        with self.engine.connect() as conn:
            row = conn.execute(stmt).first()
        return self._model_from_row(AuditEvent, row, columns) if row else None

    def list_audit_events(self, org_id: str, limit: int = 500) -> list[AuditEvent]:
        stmt = (
            select(_t_audit)
            .where(_t_audit.c.org_id == org_id)
            .order_by(_t_audit.c.seq)
            .limit(limit)
        )
        _, columns = _SCHEMA[_t_audit]
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [self._model_from_row(AuditEvent, row, columns) for row in rows]

    # -- executions ----------------------------------------------------------------------------------
    def record_execution(self, org_id: str, decision_id: str, action_digest: str, summary: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                delete(_t_executions).where(_t_executions.c.decision_id == decision_id)
            )
            conn.execute(
                insert(_t_executions).values(
                    decision_id=decision_id,
                    org_id=org_id,
                    session_id=str(summary.get("session_id", "")),
                    action_digest=action_digest,
                    summary_json=_dumps(summary),
                    created_at=utcnow().isoformat(),
                )
            )

    def get_execution(self, org_id: str, decision_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(_t_executions)
                .where(_t_executions.c.decision_id == decision_id)
                .where(_t_executions.c.org_id == org_id)
            ).first()
        if row is None:
            return None
        return json.loads(row.summary_json)

    def find_executed_digest(self, org_id: str, session_id: str, action_digest: str) -> bool:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(_t_executions.c.decision_id)
                .where(_t_executions.c.org_id == org_id)
                .where(_t_executions.c.session_id == session_id)
                .where(_t_executions.c.action_digest == action_digest)
                .limit(1)
            ).first()
        return row is not None

    # -- metrics ------------------------------------------------------------------------------------------
    def decision_counts(self, org_id: str) -> dict[str, int]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(_t_decisions.c.decision).where(_t_decisions.c.org_id == org_id)
            ).all()
        counts = {"allow": 0, "block": 0, "escalate": 0}
        for (decision,) in rows:
            counts[decision] = counts.get(decision, 0) + 1
        return counts

    def count(self, table: str, org_id: str) -> int:
        tables = {
            "agents": _t_agents,
            "intents": _t_intents,
            "sessions": _t_sessions,
            "capabilities": _t_capabilities,
            "decisions": _t_decisions,
        }
        t = tables.get(table)
        if t is None:
            return 0
        with self.engine.connect() as conn:
            rows = conn.execute(select(t.c.org_id).where(t.c.org_id == org_id)).all()
        return len(rows)

    def close(self) -> None:
        self.engine.dispose()
