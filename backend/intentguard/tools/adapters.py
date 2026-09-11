"""Deterministic mock tools (§11). Each supports legitimate operation, malicious
input, boundary conditions, failure, and timeout via a harness-configured
fault profile — never via agent-controlled parameters.

State is in-memory per adapter instance: enough for demos and AttackBench;
the real integrations phase replaces adapters, not the firewall.
"""
from __future__ import annotations

import random
from decimal import Decimal
from typing import Any

from intentguard.core.enums import SideEffectClass
from intentguard.core.errors import ValidationError
from intentguard.tools.base import ExecutionContext, OperationSpec, ToolAdapter, ToolResult
from intentguard.tools.content import (
    AGENT_MESSAGES,
    DOCUMENTS,
    WEB_PAGES,
    observation_from,
)


class ShoppingAPI(ToolAdapter):
    name = "shopping_api"
    description = "Mock e-commerce API: product search, details, comparison, purchase."
    specs = {
        "search_products": OperationSpec("search_products", SideEffectClass.SEARCH, ("query",)),
        "get_product": OperationSpec("get_product", SideEffectClass.READ, ("product_id",)),
        "compare": OperationSpec("compare", SideEffectClass.ANALYZE, ("product_ids",)),
        "purchase": OperationSpec(
            "purchase",
            SideEffectClass.PURCHASE,
            ("item", "brand", "unit_price", "quantity", "currency", "destination"),
        ),
    }
    param_map = {
        "brand": "brand",
        "destination": "destination",
        "quantity": "quantity",
        "amount": "unit_price",
        "currency": "currency",
        "item": "item",
    }

    def __init__(self) -> None:
        super().__init__()
        self.catalog: dict[str, dict[str, Any]] = {
            "lenovo-thinkpad-e14": {"product_id": "lenovo-thinkpad-e14", "brand": "Lenovo", "item": "laptop", "unit_price": "62000.00", "currency": "INR"},
            "lenovo-v15-g4": {"product_id": "lenovo-v15-g4", "brand": "Lenovo", "item": "laptop", "unit_price": "41500.00", "currency": "INR"},
            "macbook-pro-16": {"product_id": "macbook-pro-16", "brand": "Apple", "item": "laptop", "unit_price": "249900.00", "currency": "INR"},
        }
        self.orders: list[dict[str, Any]] = []

    def execute(self, operation: str, params: dict[str, Any], ctx: ExecutionContext) -> ToolResult:
        self._maybe_fault(operation)
        if operation == "search_products":
            query = str(params["query"]).lower()
            hits = [p for p in self.catalog.values() if query in p["item"] or query in p["brand"].lower()]
            return ToolResult(ok=True, data={"results": hits})
        if operation == "get_product":
            product = self.catalog.get(str(params["product_id"]))
            if product is None:
                return ToolResult(ok=False, error="product not found")
            return ToolResult(ok=True, data={"product": product})
        if operation == "compare":
            ids = list(params["product_ids"])
            return ToolResult(ok=True, data={"comparison": [self.catalog.get(i) for i in ids if i in self.catalog]})
        if operation == "purchase":
            order = {
                "order_id": f"ord_{len(self.orders) + 1:04d}",
                "org_id": ctx.org_id,
                "session_id": ctx.session_id,
                "agent_id": ctx.agent_id,
                **params,
            }
            self.orders.append(order)
            return ToolResult(ok=True, data={"order": order, "status": "confirmed (MOCK)"})
        raise ValidationError(f"unsupported operation '{operation}'")

    def _maybe_fault(self, operation: str) -> None:
        profile = self.fault_profile
        if profile.get("fail_ops") and operation in profile["fail_ops"]:
            raise ValidationError(f"mock tool failure injected for '{operation}'")
        if profile.get("timeout_ops") and operation in profile["timeout_ops"]:
            raise TimeoutError(f"mock timeout injected for '{operation}'")
        rate = float(profile.get("fail_rate", 0.0))
        if rate > 0 and random.random() < rate:
            raise ValidationError("mock transient failure injected")


class BankingAPI(ToolAdapter):
    name = "banking_api"
    description = "Mock banking API: balance reads and fund transfers."
    specs = {
        "get_balance": OperationSpec("get_balance", SideEffectClass.READ, ("account_id",)),
        "transfer": OperationSpec(
            "transfer", SideEffectClass.TRANSFER,
            ("amount", "currency", "recipient", "destination_account"),
            ("note",),
        ),
    }
    param_map = {"amount": "amount", "currency": "currency", "recipient": "recipient"}

    def __init__(self, balance: str = "2500000.00") -> None:
        super().__init__()
        self.balances: dict[str, str] = {"acc_main": balance}
        self.transfers: list[dict[str, Any]] = []

    def execute(self, operation: str, params: dict[str, Any], ctx: ExecutionContext) -> ToolResult:
        if operation == "get_balance":
            account = str(params["account_id"])
            if account not in self.balances:
                return ToolResult(ok=False, error="account not found")
            return ToolResult(ok=True, data={"account_id": account, "balance": self.balances[account]})
        if operation == "transfer":
            record = {"transfer_id": f"trf_{len(self.transfers) + 1:04d}", "org_id": ctx.org_id, "session_id": ctx.session_id, **params}
            self.transfers.append(record)
            return ToolResult(ok=True, data={"transfer": record, "status": "executed (MOCK)"})
        raise ValidationError(f"unsupported operation '{operation}'")


class EmailAPI(ToolAdapter):
    name = "email_api"
    description = "Mock email API. Common exfiltration channel in attack scenarios."
    specs = {
        "send_email": OperationSpec(
            "send_email", SideEffectClass.SEND, ("to", "subject", "body")
        ),
    }
    param_map = {"recipient": "to"}

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[dict[str, Any]] = []

    def execute(self, operation: str, params: dict[str, Any], ctx: ExecutionContext) -> ToolResult:
        record = {"email_id": f"eml_{len(self.sent) + 1:04d}", "org_id": ctx.org_id, "session_id": ctx.session_id, **params}
        self.sent.append(record)
        return ToolResult(ok=True, data={"email": record, "status": "sent (MOCK)"})


class WebBrowser(ToolAdapter):
    name = "web_browser"
    description = "Mock browser restricted to sandbox pages. Read operations produce trusted observations."

    specs = {
        "fetch_page": OperationSpec("fetch_page", SideEffectClass.READ, ("uri",)),
    }
    param_map = {}

    def execute(self, operation: str, params: dict[str, Any], ctx: ExecutionContext) -> ToolResult:
        uri = str(params["uri"])
        page = WEB_PAGES.get(uri)
        if page is None:
            return ToolResult(ok=False, error=f"page not found in sandbox: {uri}")
        return ToolResult(
            ok=True,
            data={"title": page.title, "content": page.content, "uri": page.uri},
            observation=observation_from(page),
        )


class FileStore(ToolAdapter):
    name = "file_store"
    description = "Mock document store. Reads produce trusted observations; writes are WRITE-class."
    specs = {
        "read_document": OperationSpec("read_document", SideEffectClass.READ, ("path",)),
        "write_document": OperationSpec("write_document", SideEffectClass.WRITE, ("path", "content")),
    }
    param_map = {}

    def __init__(self) -> None:
        super().__init__()
        self.files: dict[str, str] = {}

    def execute(self, operation: str, params: dict[str, Any], ctx: ExecutionContext) -> ToolResult:
        path = str(params["path"])
        if operation == "read_document":
            seeded = DOCUMENTS.get(path)
            if seeded is not None:
                return ToolResult(
                    ok=True,
                    data={"path": path, "content": seeded.content, "title": seeded.title},
                    observation=observation_from(seeded),
                )
            if path in self.files:
                return ToolResult(ok=True, data={"path": path, "content": self.files[path]})
            return ToolResult(ok=False, error="document not found")
        if operation == "write_document":
            self.files[path] = str(params["content"])
            return ToolResult(ok=True, data={"path": path, "status": "written (MOCK)"})
        raise ValidationError(f"unsupported operation '{operation}'")


class AgentInbox(ToolAdapter):
    """Mock agent-to-agent channel (§9 agent-to-agent manipulation). Reads
    deliver seeded peer messages as trusted observations."""

    name = "agent_inbox"
    description = "Mock A2A message channel for sandboxed agent-to-agent scenarios."
    specs = {
        "read_message": OperationSpec("read_message", SideEffectClass.READ, ("uri",)),
    }
    param_map = {}

    def execute(self, operation: str, params: dict[str, Any], ctx: ExecutionContext) -> ToolResult:
        uri = str(params["uri"])
        message = AGENT_MESSAGES.get(uri)
        if message is None:
            return ToolResult(ok=False, error=f"message not found: {uri}")
        return ToolResult(
            ok=True,
            data={"title": message.title, "content": message.content, "uri": message.uri},
            observation=observation_from(message),
        )
