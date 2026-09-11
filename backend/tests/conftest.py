"""Shared fixtures: in-memory store + fully wired engine + standard tenant."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from intentguard.config import Settings
from intentguard.engine import IntentGuardEngine
from intentguard.storage.sql import SqlStore

PURCHASE_OK = {
    "item": "laptop",
    "brand": "Lenovo",
    "unit_price": "9500",
    "quantity": 100,
    "currency": "INR",
    "destination": "Chennai",
}

INTENT_TEXT = (
    "Buy 100 Lenovo laptops with a total budget of 10,00,000 INR and deliver them to Chennai"
)


@pytest.fixture()
def store():
    s = SqlStore("sqlite://")
    yield s
    s.close()


@pytest.fixture()
def engine(store):
    return IntentGuardEngine(store, settings=Settings(store_kind="memory"))


@pytest.fixture()
def org_ctx(engine):
    org = engine.create_organization("Test Org")
    principal = engine.create_principal(org.org_id, "Owner")
    agent = engine.register_agent(org.org_id, principal.principal_id, "procurement-agent")
    intent = engine.compile_intent(org.org_id, principal.principal_id, INTENT_TEXT)
    session = engine.start_session(org.org_id, agent.agent_id, intent.intent_id)
    return SimpleNamespace(
        engine=engine,
        org=org,
        principal=principal,
        agent=agent,
        intent=intent,
        session=session,
        purchase_params=dict(PURCHASE_OK),
    )
