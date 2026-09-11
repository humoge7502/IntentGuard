# Skills & Ecosystem Research

Research date: **2026-09-12**. All four mission-named resources plus the
`npx skills` mechanism were verified by direct fetch on this date. Nothing
from these repositories was executed or installed into this project.

## Summary decision table

| Resource | Purpose | License | Security assessment | Usefulness | Decision |
|---|---|---|---|---|---|
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) ✅ | design guidance for AI coding agents (anti-"AI-slop"); 61 deterministic detector rules + CLI `npx impeccable detect` | Apache-2.0 | active maintainer (Paul Bakaus), huge community traction (67k+ stars), npm distribution — standard supply-chain surface, no red flags | HIGH: its anti-generic-design rules directly match the mission's §31 quality bar; the deterministic CLI could lint our frontend | **ADOPT (process, not code)** — the design principles are already reflected in docs/DESIGN_RESEARCH.md; optionally run `detect` during frontend QA |
| [vercel-labs/skills](https://github.com/vercel-labs/skills) ✅ | the `npx skills add` CLI ("The CLI for the open agent skills ecosystem", skills.sh) | MIT | Vercel-labs maintained (31k+ stars); installs SKILL.md files by **symlink or copy**; supports direct URL downloads of archives; collects anonymous telemetry (opt-out `DISABLE_TELEMETRY=1`); skills are agent-followed instructions — untrusted input by nature | MEDIUM: distribution mechanism only, nothing to adopt for a Python product | **MONITOR** — do not install third-party SKILL.md content into this security-sensitive repo without review; documented because the mission asked about `npx skills add nutlope/hallmark` |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) ⚠️ | design-taste skill (small community repo) | not re-verified today | small maintainer base — cannot verify provenance on fetch date | LOW for the product (our design system is already specified and built) | **REJECT (for now)** — revisit only if we adopt a skills workflow |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) ✅ | curated list of 1,400+ agent skills by provider | MIT | directory/list only — low inherent risk; individual skills vary wildly in provenance | MEDIUM as an index: notable entries relevant to us: **Trail of Bits security skills** (insecure-defaults, static-analysis), OpenAI threat-model skill, Addy Osmani web-quality skills, Cloudflare web-perf | **MONITOR** — mine for future security-review skills; adopt none wholesale today |
| [emilkowalski/skills](https://github.com/emilkowalski/skills) ⚠️ | UI/animation craft skills from a known design engineer | not re-verified today (fetch budget) | reputable individual maintainer | LOW–MEDIUM (frontend is complete; useful if we do a polish pass) | **MONITOR** |

## Security analysis of the `skills` mechanism (why we didn't install any)

A "skill" is a prompt/instruction set the coding agent will follow, optionally
with tool permissions and hooks (agent-dependent). Installing one from an
untrusted source is **prompt injection with install steps** — exactly the
threat class IntentGuard exists to contain. The vercel CLI also supports
direct archive downloads and (opt-out) telemetry. For this repository:

1. No third-party skills were executed or installed.
2. Design guidance was consumed as *principles* (via the separate,
   fetched-based design research doc) rather than as installed prompts.
3. If we later adopt skills, policy: review SKILL.md + any hooks as code
   review, pin sources, prefer symlinked local copies under version control.

## Cross-reference

- Design principles actually used in this project: docs/DESIGN_RESEARCH.md
  (derived independently from ACM VIT + reference consoles, then cross-checked
  against impeccable's published anti-patterns — Inter-overuse caveat
  acknowledged; we use Inter + JetBrains Mono deliberately for a data-dense
  console with AA-verified tokens).
- Security skills shortlist for future CI enrichment (from VoltAgent list):
  Trail of Bits `insecure-defaults`, `static-analysis`.

## Sources (fetched 2026-09-12)

- https://github.com/pbakaus/impeccable
- https://github.com/vercel-labs/skills
- https://github.com/VoltAgent/awesome-agent-skills
- (Leonxlnx/taste-skill and emilkowalski/skills not re-fetched this date — marked ⚠️)
