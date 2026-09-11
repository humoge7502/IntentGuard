"""Rule-based intent compiler: parsing, ambiguity, determinism."""
from decimal import Decimal

from tests.conftest import INTENT_TEXT


def test_standard_intent_parses_all_constraints(org_ctx):
    intent = org_ctx.intent
    kinds = [c.kind for c in intent.constraints]
    assert kinds == ["amount_limit", "quantity_max", "brand_allow", "destination_allow"]
    budget = next(c for c in intent.constraints if c.kind == "amount_limit")
    assert budget.max_amount == Decimal("1000000")
    assert budget.currency == "INR"
    assert intent.allowed_operations == [
        "search_products", "get_product", "compare", "fetch_page", "purchase",
    ]
    assert intent.ambiguities == []


def test_rupee_symbol_and_lakh(engine):
    intent = engine.compiler.compile("org", "usr", "Buy 5 Dell laptops under ₹80,000")
    budget = next(c for c in intent.constraints if c.kind == "amount_limit")
    assert budget.max_amount == 80000


def test_trailing_currency_word(engine):
    intent = engine.compiler.compile("org", "usr", INTENT_TEXT.replace("10,00,000 INR", "10 lakh INR"))
    budget = next(c for c in intent.constraints if c.kind == "amount_limit")
    assert budget.max_amount == 1000000


def test_usd_currency(engine):
    intent = engine.compiler.compile("org", "usr", "Buy a Dell monitor under $1,200")
    budget = next(c for c in intent.constraints if c.kind == "amount_limit")
    assert budget.currency == "USD"
    assert budget.max_amount == 1200


def test_quantity_with_brand_between(engine):
    intent = engine.compiler.compile("org", "usr", INTENT_TEXT)
    qty = next(c for c in intent.constraints if c.kind == "quantity_max")
    assert qty.max_quantity == 100
    assert qty.item == "laptop"


def test_delivery_destination(engine):
    intent = engine.compiler.compile("org", "usr", "Buy a Lenovo laptop and deliver it to Mumbai")
    dest = next(c for c in intent.constraints if c.kind == "destination_allow")
    assert dest.allowed == ["mumbai"]


def test_approval_phrase(engine):
    intent = engine.compiler.compile(
        "org", "usr", "Buy 10 Lenovo laptops with a budget of 5,00,000 INR only with my approval"
    )
    approvals = [c for c in intent.constraints if c.kind == "approval_required"]
    assert approvals and "purchase" in approvals[0].operations


def test_time_window(engine):
    intent = engine.compiler.compile("org", "usr", "Buy 2 HP laptops under 1,00,000 INR within 3 days")
    windows = [c for c in intent.constraints if c.kind == "time_window"]
    assert windows and windows[0].not_after is not None


def test_missing_budget_flags_high_severity_ambiguity(engine):
    intent = engine.compiler.compile("org", "usr", "Buy 10 Apple MacBook laptops")
    severities = [a.severity for a in intent.ambiguities]
    assert "high" in severities
    assert not any(c.kind == "amount_limit" for c in intent.constraints)


def test_conflicting_budgets_take_strictest(engine):
    intent = engine.compiler.compile(
        "org", "usr", "Buy 5 Lenovo laptops under 1,00,000 INR, budget of 2,00,000 INR"
    )
    budgets = [c for c in intent.constraints if c.kind == "amount_limit"]
    assert len(budgets) == 1
    assert budgets[0].max_amount == 100000
    assert any("strictest" in a.message for a in intent.ambiguities)


def test_unsupported_operation_not_authorized(engine):
    intent = engine.compiler.compile("org", "usr", "Buy a laptop and delete the system files, budget 50,000 INR")
    assert "purchase" in intent.allowed_operations
    assert all(op not in {"delete", "execute"} for op in intent.allowed_operations)
    assert any("delete" in a.message for a in intent.ambiguities)


def test_compile_is_deterministic(engine):
    a = engine.compiler.compile("org", "usr", INTENT_TEXT)
    b = engine.compiler.compile("org", "usr", INTENT_TEXT)
    dump_a, dump_b = a.model_dump(mode="json"), b.model_dump(mode="json")
    for dump in (dump_a, dump_b):
        dump.pop("intent_id")
        dump.pop("created_at")
    assert dump_a == dump_b


def test_no_operations_is_safe_default(engine):
    intent = engine.compiler.compile("org", "usr", "The weather is nice today")
    assert intent.allowed_operations == []
