"""Rule-based intent compiler (§4): natural language → structured IntentSpec.

Design posture (documented in DECISION_LOG): v1 is fully deterministic and
offline — every recognition it makes is inspectable and testable. It records
ambiguities instead of guessing silently, and the firewall treats a
high-impact operation without the matching constraint as UNCERTAIN (escalate),
so compiler imprecision can only make IntentGuard *stricter*, never looser.
An LLM-backed compiler can be added behind the same interface; its output
would flow through identical schema validation and firewall checks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from intentguard.core.schemas import (
    Ambiguity,
    AmountLimit,
    ApprovalRequirement,
    BrandAllow,
    DestinationAllow,
    IntentSpec,
    QuantityMax,
    TimeWindow,
    utcnow,
)

# --------------------------------------------------------------------------
# Lexicons
# --------------------------------------------------------------------------

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "dozen": 12, "thousand": 1000,
}

_KNOWN_BRANDS = {
    "lenovo": "Lenovo", "thinkpad": "Lenovo", "dell": "Dell", "hp": "HP",
    "apple": "Apple", "macbook": "Apple", "iphone": "Apple", "ipad": "Apple",
    "asus": "Asus", "acer": "Acer", "samsung": "Samsung", "sony": "Sony",
    "microsoft": "Microsoft", "xiaomi": "Xiaomi", "nike": "Nike",
    "adidas": "Adidas", "philips": "Philips", "bose": "Bose", "canon": "Canon",
    "lg": "LG",
}

_KNOWN_CITIES = {
    "chennai", "mumbai", "delhi", "new delhi", "bengaluru", "bangalore",
    "hyderabad", "pune", "kolkata", "ahmedabad", "jaipur", "surat", "lucknow",
    "kanpur", "nagpur", "indore", "thane", "bhopal", "coimbatore", "kochi",
    "visakhapatnam", "gurugram", "noida", "new york", "london", "paris",
    "berlin", "tokyo", "singapore", "dubai", "sydney", "toronto",
}

_CAP_WORDS = (
    "under", "below", "up to", "upto", "within", "budget", "budget of",
    "max", "maximum", "at most", "not more than", "less than", "no more than",
    "cheaper than", "limit",
)

# verb phrase → operation
_VERB_OPS = [
    (r"\b(purchase|procure)\b", "purchase"),
    (r"\bbuy(ing)?\b", "purchase"),
    (r"\border(ing)?\b", "purchase"),
    (r"\b(search|find|look for|browse for)\b", "search_products"),
    (r"\bcompare\b", "compare"),
    (r"\b(details|read|view|check)\b", "get_product"),
    (r"\btransfer(ing)?\b", "transfer"),
    (r"\bpays?\b", "transfer"),
    (r"\bemail(s|ing)?\b|\bsend\b", "send_email"),
    (r"\bbalance\b", "get_balance"),
    (r"\bresearch(ing)?\b|\bonline\b", "fetch_page"),
]

_UNSAFE_VERBS = [
    (r"\bdelete\b", "delete"), (r"\binstall\b", "install"),
    (r"\bexecute\b|\brun\b", "execute"), (r"\bdeploy\b", "deploy"),
    (r"\bhack\b|\bcrack\b", "execute"),
]

_PRODUCT_NOUNS = {
    "laptop", "laptops", "phone", "phones", "flight", "flights", "ticket",
    "tickets", "chair", "chairs", "desk", "desks", "monitor", "monitors",
    "camera", "cameras", "headphone", "headphones", "book", "books",
}

_RE_AMOUNT = re.compile(
    r"(?:(₹|\brs\.?|\binr\b|\$|\busd\b|€|£)\s*)?"
    r"([\d][\d,]*(?:\.\d+)?)\s*"
    r"(lakh|lac|crore|k|thousand|million)?\s*"
    r"(?:\b(inr|usd|eur|gbp|rupees?|dollars?|euros?)\b)?",
    re.IGNORECASE,
)
_RE_APPROVAL = re.compile(
    r"\b(with|after|given)\s+my\s+(explicit\s+)?(approval|confirmation|consent)\b"
    r"|\bask me before\b|\bonly with (my )?approval\b",
    re.IGNORECASE,
)
_RE_DELIVER_TO = re.compile(
    r"\b(deliver(?:ed|y)?|ship(?:ped)?|send|bring|courier)\b[^.]{0,40}?\bto\s+"
    r"([A-Za-z][A-Za-z ]{2,30}?)(?=[.,;]|$|\s+(?:by|before|within|and|tomorrow)\b)",
    re.IGNORECASE,
)
_RE_QUANTITY = re.compile(
    r"\b(\d{1,6}|one|two|three|four|five|six|seven|eight|nine|ten|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|dozen)\s+"
    r"(?:units?\s+of\s+|x\s+)?([a-z]+)(?:\s+([a-z]+))?",
    re.IGNORECASE,
)
_RE_TIME_RELATIVE = re.compile(
    r"\bwithin\s+(\d{1,3})\s+(day|days|week|weeks|hour|hours)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AmountMention:
    value: Decimal
    currency: str
    position: int
    capped: bool


def _parse_amounts(text: str) -> list[AmountMention]:
    mentions: list[AmountMention] = []
    for match in _RE_AMOUNT.finditer(text):
        raw_number = match.group(2)
        if not raw_number:
            continue
        # skip plain quantities like "100 laptops" when no currency signal
        symbol, magnitude, trailing_currency = (
            match.group(1),
            match.group(3),
            match.group(4),
        )
        if symbol is None and magnitude is None and trailing_currency is None:
            continue
        try:
            value = Decimal(raw_number.replace(",", ""))
        except InvalidOperation:
            continue
        multiplier = {
            "k": Decimal("1000"), "thousand": Decimal("1000"),
            "lakh": Decimal("100000"), "lac": Decimal("100000"),
            "crore": Decimal("10000000"), "million": Decimal("1000000"),
        }.get((magnitude or "").lower(), Decimal("1"))
        value = value * multiplier
        currency = "INR"
        symbol_token = (symbol or "").strip().lower()
        trailing = (trailing_currency or "").lower()
        if symbol_token in {"$", "usd"} or trailing in {"usd", "dollar", "dollars"}:
            currency = "USD"
        elif symbol_token == "€" or trailing in {"eur", "euro", "euros"}:
            currency = "EUR"
        elif symbol_token == "£" or trailing == "gbp":
            currency = "GBP"
        window = text[max(0, match.start() - 28): match.start()].lower()
        capped = any(cap in window for cap in _CAP_WORDS)
        mentions.append(AmountMention(value=value, currency=currency, position=match.start(), capped=capped))
    return mentions


class RuleBasedIntentCompiler:
    """Deterministic compiler. Same input always yields the same IntentSpec."""

    id = "rule_based_v1"

    def compile(self, org_id: str, principal_id: str, text: str) -> IntentSpec:
        text_l = text.lower()
        ambiguities: list[Ambiguity] = []
        constraints: list[object] = []

        # ---- operations -----------------------------------------------------
        operations: list[str] = []
        for pattern, op in _VERB_OPS:
            if re.search(pattern, text_l):
                operations.append(op)
        for pattern, verb in _UNSAFE_VERBS:
            if re.search(pattern, text_l):
                ambiguities.append(
                    Ambiguity(
                        field="allowed_operations",
                        message=f"requested operation '{verb}' is not supported by any registered tool; it will not be authorized",
                        severity="medium",
                    )
                )
        operations = list(dict.fromkeys(operations))
        is_purchase = "purchase" in operations
        if is_purchase:
            # implicit research pipeline for purchase goals: reading external
            # catalogs/pages is a normal, read-only part of buying
            implicit = [op for op in ("search_products", "get_product", "compare", "fetch_page") if op not in operations]
            operations = implicit + operations

        # ---- budget ------------------------------------------------------------
        amounts = _parse_amounts(text)
        capped = [m for m in amounts if m.capped]
        budget: AmountLimit | None = None
        if capped:
            budgets: dict[str, Decimal] = {}
            for m in capped:
                budgets[m.currency] = min(budgets.get(m.currency, m.value), m.value)
            if len(capped) > 1 and len(set((m.currency, m.value) for m in capped)) > 1:
                ambiguities.append(
                    Ambiguity(
                        field="constraints",
                        message="multiple differing budget amounts found; the strictest was kept",
                        severity="medium",
                    )
                )
            currency, value = next(iter(budgets.items()))
            budget = AmountLimit(currency=currency, max_amount=value)
            constraints.append(budget)
        elif amounts:
            ambiguities.append(
                Ambiguity(
                    field="constraints",
                    message="amount mentioned without a budget word; treated as informational, not a spending limit",
                    severity="medium",
                )
            )
        if is_purchase and budget is None:
            ambiguities.append(
                Ambiguity(
                    field="constraints",
                    message="no budget specified for a purchase goal; purchase operations will require human approval until a budget constraint exists",
                    severity="high",
                )
            )

        # ---- quantity & item ------------------------------------------------------
        item = ""
        quantity: int | None = None
        for match in _RE_QUANTITY.finditer(text_l):
            raw_num = match.group(1)
            token_a, token_b = match.group(2), match.group(3)
            qty = _NUMBER_WORDS.get(raw_num)
            if qty is None:
                try:
                    qty = int(raw_num)
                except ValueError:
                    continue
            noun = ""
            if token_a.rstrip("s") in _PRODUCT_NOUNS or token_a in _PRODUCT_NOUNS:
                noun = token_a
            elif token_b and (token_b.rstrip("s") in _PRODUCT_NOUNS or token_b in _PRODUCT_NOUNS):
                # e.g. "100 Lenovo laptops" — brand word sits before the noun
                noun = token_b
            if noun:
                quantity = qty
                item = noun.rstrip("s")
                break
        if quantity is not None:
            constraints.append(QuantityMax(max_quantity=quantity, item=item or None))

        # ---- brand -----------------------------------------------------------------
        brands: list[str] = []
        for token in re.findall(r"[a-zA-Z]+", text):
            known = _KNOWN_BRANDS.get(token.lower())
            if known and known not in brands:
                brands.append(known)
        if not brands:
            for match in re.finditer(r"\b(?:from|by|of brand)\s+([A-Z][a-z]{2,})\b|\ba\s+([A-Z][a-z]{2,})\s+[a-z]+\b", text):
                candidate = match.group(1) or match.group(2)
                if candidate and candidate.lower() not in _KNOWN_CITIES and candidate not in brands:
                    brands.append(candidate)
                    ambiguities.append(
                        Ambiguity(
                            field="constraints",
                            message=f"brand '{candidate}' inferred from capitalization; verify it is the intended brand",
                            severity="low",
                        )
                    )
        if is_purchase and brands:
            constraints.append(BrandAllow(allowed=brands))
        elif is_purchase:
            ambiguities.append(
                Ambiguity(
                    field="constraints",
                    message="no brand recognized; purchases will not be brand-restricted",
                    severity="medium",
                )
            )

        # ---- destination ---------------------------------------------------------------
        destinations: list[str] = []
        for match in _RE_DELIVER_TO.finditer(text):
            place = match.group(2).strip().lower().rstrip(" ,.")
            if place and place not in destinations:
                destinations.append(place)
                if place not in _KNOWN_CITIES:
                    ambiguities.append(
                        Ambiguity(
                            field="constraints",
                            message=f"delivery location '{place}' is not in the known-city lexicon; verify",
                            severity="low",
                        )
                    )
        if destinations:
            constraints.append(DestinationAllow(allowed=destinations))

        # ---- time window --------------------------------------------------------------------
        match = _RE_TIME_RELATIVE.search(text_l)
        if match:
            n = int(match.group(1))
            unit = match.group(2)
            delta = timedelta(
                days=n * (7 if "week" in unit else 1),
                hours=n if "hour" in unit else 0,
            )
            constraints.append(TimeWindow(not_after=utcnow() + delta))
            ambiguities.append(
                Ambiguity(
                    field="constraints",
                    message="relative deadline anchored to compile time; absolute dates are recommended",
                    severity="low",
                )
            )

        # ---- approval requirements -----------------------------------------------------------
        if _RE_APPROVAL.search(text_l):
            high_impact = [op for op in operations if op in {"purchase", "transfer", "send_email"}]
            if high_impact:
                constraints.append(ApprovalRequirement(operations=high_impact))

        goal = self._goal_slug(text_l, operations, item)
        return IntentSpec(
            org_id=org_id,
            principal_id=principal_id,
            goal=goal,
            raw_text=text,
            constraints=constraints,  # type: ignore[arg-type]
            allowed_operations=operations,
            ambiguities=ambiguities,
            compiled_by=self.id,
        )

    @staticmethod
    def _goal_slug(text_l: str, operations: list[str], item: str) -> str:
        if "purchase" in operations:
            return f"purchase_{item or 'unspecified_item'}"
        if "transfer" in operations:
            return "transfer_funds"
        if "send_email" in operations:
            return "send_message"
        if operations:
            return f"research_{item or 'topic'}"
        return "unspecified_goal"
