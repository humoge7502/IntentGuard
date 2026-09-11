# Prior Art & Landscape Research

Research date: **2026-09-12**. Verification legend: ✅ verified by direct
fetch of the cited page on this date · ⚠️ known work, page not re-fetched
today (details from prior knowledge — re-verify before relying on specifics).
**No legal advice, no patentability claims.** This is technical landscape
research for qualified counsel.

## 1. Classification summary

| Landscape entry | Class | Overlap notes |
|---|---|---|
| PDP/PEP model (XACML heritage) | implementation precedent | IntentGuard = PEP; firewall = PDP pattern is classic authZ architecture |
| Capability-based security (object-capability model) | implementation precedent | scoped, unforgeable grants are textbook capability security |
| NVIDIA NeMo Guardrails ✅ | adjacent | programmable rails around LLM I/O (input/dialog/retrieval/execution/output); Colang flows; mitigates jailbreak/injection at the *conversation* layer — not intent-scoped, digest-bound authorization of consequential actions |
| OWASP GenAI Top 10 (2025) ✅ | conceptually related | codifies Excessive Agency (LLM06) + Prompt Injection (LLM01) as risks IntentGuard directly mitigates |
| MCP authorization spec ✅ | adjacent | OAuth 2.1 resource-server model: *authentication/transport authZ*, not intent-scoped action authorization |
| Invariant Labs / agent-security scanners ⚠️ | adjacent | analyzer-class tools (trace inspection, injection detection); detection vs enforcement emphasis |
| Guardrails AI ⚠️ | adjacent | output/input validation rails (structured, retryable) — data-shape focus, not authorization |
| Progent (⚠️ arXiv 2025, programmable privilege control for LLM agents) | directly overlapping (research) | policy-based permission control over agent tool calls; closest academic neighbor — verify exact claims at https://arxiv.org before any counsel discussion |
| Conseca (⚠️ contextual integrity for agent permissions, research) | directly overlapping (research) | NL-derived contextual-integrity policies for agent communication |
| LLM patent landscape ⚠️ | partially overlapping | multiple filings exist around "policy enforcement for AI agent actions"; specific numbers NOT verified — counsel should run a fresh professional search |
| OS hardening / admission controllers | conceptually related | deny-by-default + least privilege applied to a new subject (agents) |

## 2. Known technology vs combination vs potentially distinct

**Known technology (established):**
- PDP/PEP enforcement architecture; policy engines (OPA/XACML lineage).
- Capability tokens, scoping, revocation, expiry (object capabilities; OAuth
  scopes; macaroons/caveats lineage).
- Hash-chained tamper-evident logs (certificate transparency lineage);
  Ed25519 signatures.
- Prompt-injection threat modeling (OWASP LLM01; indirect injection
  literature).
- Trajectory/behavior analysis of agent runs (scanner/analyzer products).

**Combinations of known techniques (where IntentGuard mostly sits):**
- NL intent → *structured, versioned authorization artifact* (compiler) —
  combination of semantic parsing + authZ artifacts.
- Digest-bound, single-use human approval bound to the canonical action —
  combination of capability caveats + approval workflows.
- Trajectory rules that *degrade standing* (capability narrowing over time) —
  combination of behavioral detection + dynamic capability narrowing.
- Taint tracking from external content into authorization decisions —
  combination of DFW-style taint analysis + authZ.

**Potentially distinct (uncertain, for counsel — not claims):**
- The specific composition: independent deterministic firewall whose decision
  inputs are (compiled intent ∩ policy) capabilities + trusted-observation
  taint + trajectory degradation, with enforcement *before first side effect*
  and execution idempotency keyed to decisions. Whether this composition is
  novel as a matter of patent law requires professional search; as a matter
  of engineering literature we found no identical open system on fetch date.

## 3. Nearest neighbors — what to study

1. **NeMo Guardrails** ✅ (https://github.com/NVIDIA/NeMo-Guardrails, Apache-2.0):
   five rail types incl. *execution rails* — closest industry mechanism to
   "check before tool runs". Differentiator: rails are developer-scripted
   conversational policies; IntentGuard derives constraints from a specific
   human intent statement and binds approval to an action digest.
2. **Progent** ⚠️ (arXiv 2025): programmable privilege policies over tool
   calls — read before any novelty discussion.
3. **Conseca / contextual-integrity permission research** ⚠️: deriving
   permissions from contextual-integrity norms (very close in spirit to
   intent-derived constraints).
4. **Invariant Labs** ⚠️ and commercial agent-security platforms (scanning/
   prevention): classify per deployment as detection vs enforcement.
5. **MCP authorization** ✅: transport authZ IntentGuard should *reuse*
   (RFC 9728/8707) rather than reinvent.

## 4. Limitations of this research

- Patent databases (USPTO/EPO/WIPO/Google Patents) were **not** systematically
  searched in this pass (earlier attempt was blocked by fetch infrastructure);
  any patent-facing work requires a professional prior-art search.
- Academic coverage is partial; Progent/Conseca details from prior knowledge
  (⚠️) — verify titles/claims on arXiv before citing externally.
- Commercial products change quickly; the industry row is a snapshot.

## Sources fetched 2026-09-12

- https://github.com/NVIDIA/NeMo-Guardrails (guardrail types, Colang, license)
- https://genai.owasp.org/llm-top-10/ (2025 categories, Excessive Agency LLM06)
- https://modelcontextprotocol.io/specification/latest (+authorization page)
- https://github.com/a2aproject/A2A (governance, transport, concepts)
