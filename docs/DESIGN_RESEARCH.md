# IntentGuard — Design Research & Design-Token Specification

**Document:** DESIGN_RESEARCH.md
**Owner:** Design Research specialist, IntentGuard engineering
**Access date:** 2026-09-12
**Scope:** Publicly visible design analysis of acmvit.in plus control-plane / developer-platform references, distilled into design principles and a concrete design-token specification for IntentGuard's dark enterprise security console.
**Rules honored:** No proprietary assets, code, or copy were copied. All extracted values below are either factual token-level observations from publicly served CSS/HTML or design principles restated in our own words. Reference-site findings are principles only.

---

## 1. Methodology

What was actually observable on 2026-09-12 (stated honestly):

| Target | Method | What was observable | What was not |
| --- | --- | --- | --- |
| `acmvit.in` homepage | Direct HTML download via `curl` (557 KB document) | Full DOM: information architecture, nav structure, section order, card anatomies, copy registers, duplicated responsive blocks, inline color values, Google Fonts payload | Rendered imagery, final composed motion |
| `acmvit.in` stylesheet `/_astro/index.B4qmX8U6.css` | Direct CSS download (118 KB, Astro build) | Font families, Tailwind-style size/tracking/radius tokens in use, concrete hex colors, transition timings, 11 `@keyframes` | One additional CloudFront-hosted CSS asset (`index.cETkkPhm.css`) returned `AccessDenied` — noted, not used |
| `stripe.com` | Text-extraction fetcher | Section rhythm, mega-menu IA, stats-band grids, card anatomy, CTA pairing, marquee evidence (duplicated logo rows), trust signals | Exact hex values, typefaces, rendered gradients — colors below are inferred from structure and are labeled as such |
| `vercel.com` | Text-extraction fetcher | Headline architecture, CTA pairing, repeated social-proof template, "Recently shipped" card cadence, developer-console copy voice | Rendered palette/typography (widely known dark geometric aesthetic treated as context, not as observation) |
| `tailscale.com` | Text-extraction fetcher | Utility bar + mega-menu, persona tabs, dual-funnel CTAs, metric-forward cards, security-buyer vocabulary density | Exact colors, illustration style |
| `github.com/features/security` | Text-extraction fetcher | Product tab bar, benefit trio, pricing-card pairing, resource-card format labels, single-column marketing rhythm | Exact colors and screenshot presentation |

Because reference-site colors could not be verified pixel-for-pixel, the reference analysis is deliberately framed at the level of structure, density, and interaction patterns. All exact numbers in this document (hex values, ms durations, px radii) come from the ACM VIT source or from our own proposed token set — clearly separated.

---

## 2. ACM VIT analysis (acmvit.in)

An Astro-built single-page student-chapter site with a deliberately "retro terminal / cassette" aesthetic. It is a student club site — playful, self-aware, high-energy — so the value for IntentGuard is not its look, but the *mechanics* underneath it, plus a few things to consciously avoid.

### 2.1 Information architecture & navigation
- Single-page anchor IA: primary nav (`ABOUT / DOMAINS / EVENTS / PROJECTS / ACM-W / MORE`) mostly points to in-page sections; only blogs, GitHub, and socials leave the page.
- Two-tier model: five primary sections + a `MORE` dropdown absorbing secondary destinations (Blogs, Partners, Contact, Community, Team). Footer mirrors the IA in link columns.
- Award-announcement banner sits above the nav — persistent announcement chrome is the first element on the page.
- Lowercase duplicate of the nav exists in the DOM (mobile/responsive variant rendered separately).

### 2.2 Landing-page structure
Observed section order: award banner → nav → hero (video background, lowercase identity statement, founding-year framing, single CTA to a CLI-themed `/grep` route) → About triptych (three entity blurbs) → outreach/SDG blocks → award repeat → numbered Code of Conduct (4 numbered subsections) → two Distinguished Speaker blocks → Domains statement → Events list (11 items with hash IDs like `#2gqy-0000/11`) → Projects grid (7 cards) → ACM-W bento section → Team roster (16) → blog grid (~17) → keyword marquee → photo gallery (20 tiles) → contact form → large footer ending with an "All systems online" status line.

### 2.3 Typography (extracted from served CSS/HTML)
- Display family: **PolySans** (Bold / Bulky Wide / Slim / Medium / Trial variants). Body/UI fallback: **Inter** (loaded weights 400/700/900 only). A `--font-mono` variable exists and is used for the CLI/ID texture.
- Tailwind-style size tokens (`--text-xs` … `--text-8xl`) plus extreme fluid display sizes: `clamp(1.5rem, 6vw, 5rem)` up to `clamp(7rem, 30vw, 36rem)` — oversized numerals and display words as focal points.
- Line-heights: **1.05** for display, **0.85–0.9** for the tightest display, **1.4 / 1.45 / 1.55** for body.
- Letter-spacing: tight display at `-.02em`; wide-tracked uppercase eyebrows at `.04em–.15em`, with one extreme `.5em` (the "E V E N T S" treatment).
- Register mixing: playful lowercase hero vs ALL-CAPS section titles vs full-caps body paragraphs in event recaps. Hash-indexed IDs and CLI-named projects give a terminal/monospace flavor.

### 2.4 Color (extracted from served CSS/HTML)
- Canvas: near-black with a faint blue cast — `#020308`, `#030303`, `#050505`, `#0d0e0d`, `#060606d9`.
- Primary text: warm cream `#fefcd9` / `#fffdd0` (94 inline occurrences — the single dominant ink).
- Accents: dominant coral `#f95f4a` / `#ff5f4a` (45 occurrences), hot pink `#ff007a` (ACM-W sub-brand), purple `#7100ff` / `#8710db`, blue `#2664e4`, plus semantic green `#16a34a` and red `#eb5757`.
- Separation: white-alpha borders (`#ffffff1a`, `#ffffff0d`) and black-alpha shadows — hairline separation rather than hard borders.

### 2.5 Cards, sections, density
- One repeated card skeleton across projects, team, gallery: eyebrow/label → title → 1–2 sentence blurb → paired action links (e.g., "VISIT WEBSITE" + GitHub icon; role + LinkedIn/GitHub pair). Consistent anatomy across ~50 cards.
- Cards are framed in a "cassette" template — a themed but consistent card chrome.
- Density is high: long uniform lists (17 blogs, 20 gallery tiles, 16 team members) with short blurbs and no long-form prose.
- Entire blocks (projects, gallery, about) are duplicated verbatim in the DOM for desktop/mobile renders — the page weighs 557 KB partly because of this.

### 2.6 Motion & interaction
- Transitions cluster at `.3s ease` with fine-grained outliers at `.16s`, `.18s`, `.24s`, `.26s` — durations scale with element size.
- 11 keyframe animations: `fadeIn`, `fadeInUp`, `float` (50s infinite), `marquee` (×2 variants), `pulse`, `rotate`, `shimmer`, `slideInUp`, `spin`, `footer-starfield-breathe` — mostly ambient/decorative loops.
- Repeated text runs ("technology" ×4, doubled event-name strip) confirm marquee usage.
- Radii: `10px` dominant, large soft values (`25px`, `32px`, `41px`) for feature cards, `9999px` pills, small `2–3px` for tiny controls.

### 2.7 Trust signals worth stealing
- "All systems online" status line — system-health visibility.
- Numbered Code of Conduct — governance seriousness through stable numbering.
- Eyebrow labels ("OUTREACH EVENT", "SDG", "COMMUNITY RECOGNITION") preceding every section — cheap wayfinding.

---

## 3. Reference-site analysis (control-plane / dev-platform language)

*All observations are structural/copy-level (see methodology); colors are not claimed.*

### 3.1 Stripe
- **Stats as typography:** a 4-column stats band ("135+", "99.999%", "US$1.9tn") — oversized numerals function as the focal point; the uptime figure links to the public status page. Trust = quantified, linked proof.
- **Product-UI-as-content:** a live-looking billing widget embedded in the marketing page — the product interface itself is the sales evidence. For IntentGuard: show the real decision card / policy editor in the landing hero.
- **Restrained CTA system:** one filled primary ("Start now") + quiet text-link secondary, repeated identically page-wide; verb-led, 1–3 word labels.
- **Dense footer, spacious body:** marketing sections are airy; the footer is a compressed 7-column sitemap — density is placed where scanning (not persuasion) happens.

### 3.2 Vercel
- **One H1, one line, dual CTA:** "Agentic Infrastructure" + one positioning sentence; "Deploy now" (self-serve) paired with "Talk to sales" (enterprise). Bookend CTA blocks close the page.
- **Terse, spec-sheet copy rhythm:** noun-phrase feature labels that read like console nav items ("Fluid Compute", "Web Application Firewall") — no marketing adjectives. Density of *product vocabulary* replaces decoration.
- **Machine-native affordance:** pointing agents at a `/get-started.md` file — the design language serves tools as much as humans; plain, semantic, low-chrome.
- Widely visible dark-canvas, geometric-sans, hairline-border aesthetic treated as context (not verifiable in our fetch).

### 3.3 Tailscale
- **Utility bar over mega-menu:** Blog/Docs/Download/Contact-sales strip above the primary nav — utility is separated from marketing nav.
- **Persona tabs** (IT / Security / DevOps / Engineering): same content re-framed per audience — a pattern IntentGuard can use for Admin / Security engineer / Developer views.
- **Dual funnel everywhere:** self-serve ("Start connecting devices") beside enterprise ("Contact sales") at hero, mid-page, and footer — consistent pairing, never a lone CTA.
- **Security-buyer vocabulary density:** Zero Trust, least privilege, PAM, SASE — terminology does the trust work; plus ~13 attributed testimonials, status-page link, and complete legal footer as legitimacy signals.

### 3.4 GitHub Security
- **Product-level tab bar** under the main nav (Advanced Security / Secret Protection / Code Security / Supply Chain Security / Pricing) — sub-site wayfinding without leaving the chrome.
- **Benefit trio + resource cards labeled by format** (DEMO / REPORT / VIDEOS) with format-specific action verbs ("Read the report", "Watch the videos").
- **Mirrored pricing cards** with transparent per-unit pricing ("$19 per active committer/month") — procurement ambiguity removed.
- **Trust stack:** logo strip, attributed testimonial, Forrester link, Trust center, public docs pre-purchase.

### 3.5 Cross-reference synthesis for a security console
1. Separation is done with **hairline borders on flat surfaces**, not shadows (shadow reserved for floating layers).
2. **One accent + semantic colors only**; everything else is neutral tiers.
3. **Typography carries hierarchy** (size/weight/tracking), not decoration.
4. **Quantified, linked proof** (uptime, volume) is a first-class UI element.
5. **Density is a feature** where experts work (footers, tables) and a liability where persuasion happens.
6. **Motion is transitional, not ambient** — crossfades and carousels on marketing pages, near-instant feedback inside products.

---

## 4. Observation → Principle → Adaptation chains

Each chain follows the exact four-step format: **ACM VIT observation → design principle → IntentGuard adaptation → why it improves UX.**

**Chain 1 — Canvas discipline**
ACM VIT renders everything on one near-black, faintly blue-tinted canvas family (`#020308`–`#0d0e0d`) with a single dominant ink (cream `#fefcd9`) and one accent (`#f95f4a`) → design principle: a single dark canvas plus one scarce accent makes hierarchy automatic — color earns attention by rarity → IntentGuard adapts this as a deep blue-black canvas `#0B0F17` with neutral text tiers and exactly one interactive accent (`#5B9BFF`), while `ALLOW/BLOCK/ESCALATE` are the only other saturated hues on screen → why it improves UX: in an authorization console every colored pixel must mean something; accent scarcity makes decision states the loudest elements on screen, cutting triage scan time.

**Chain 2 — Monospace as trust texture**
ACM VIT gives events hash IDs (`#2gqy-0000/11`), names projects like CLI commands, routes its CTA to `/grep`, and loads a `--font-mono` variable → design principle: monospace/terminal texture signals verifiability and machine-generation to technical audiences → IntentGuard adapts this by setting every agent ID, decision hash, policy rule name, timestamp, and latency figure in JetBrains Mono with tabular numerals → why it improves UX: agent actions are machine artifacts; mono guarantees copy-paste fidelity (fixed-width, unambiguous glyphs) and reads as security infrastructure rather than a marketing site.

**Chain 3 — Eyebrow wayfinding**
ACM VIT precedes every section with a small uppercase eyebrow ("OUTREACH EVENT", "SDG") tracked at `.04em–.15em`, with one extreme `.5em` display tracking → design principle: uppercase micro-labels provide wayfinding without adding visual chrome → IntentGuard adapts a single standardized eyebrow spec — 11px, 500 weight, +0.08em tracking, uppercase, `text-tertiary` — on every section, table group, and card cluster → why it improves UX: consoles are dense; consistent eyebrows let auditors locate sections while scanning at speed, and survive 150% zoom without layout breakage.

**Chain 4 — Motion budget, inverted**
ACM VIT spends its motion budget on ambient decoration — 50s `float`, dual marquees, `shimmer`, `footer-starfield-breathe`, `spin` — while keeping feedback transitions tight (.16–.3s) → design principle: ambient motion is entertainment; transitional motion is information — a working tool must invert the ratio → IntentGuard bans marquees/ambient loops inside the console and tokenizes only transition durations (80/120/180/240/320 ms), spending motion on state changes: row insert flash, decision badge swap, drawer entry → why it improves UX: operators watch live event streams for hours; decorative loops cause fatigue and mask real changes, whereas state-attached motion directly answers "what just happened?".

**Chain 5 — One card anatomy**
ACM VIT repeats one card skeleton ~50 times (label → title → blurb → paired action links) across projects, team, and gallery → design principle: repeated identical anatomy converts reading into pattern recognition → IntentGuard adapts this into exactly two card species — an EventCard (decision badge, agent, action, rule, timestamp, expand) and a PolicyCard (ID, scope, effect, last-modified) — with fixed field order and fixed action slots → why it improves UX: the 50th decision is processed as fast as the first; fixed anatomy also makes anomalies (missing field, odd state) visually pop, which is precisely an auditor's job.

**Chain 6 — Shallow two-tier navigation**
ACM VIT keeps five primary nav items and absorbs six secondary destinations under `MORE`, with the footer mirroring the full IA → design principle: shallow primary nav with an overflow tier keeps chrome calm while preserving reachability → IntentGuard adapts a 5-item primary rail (Overview, Events, Policies, Agents, Settings) plus a utility cluster (environment switcher, status, account) with secondary pages in an overflow menu → why it improves UX: the nav maps to the audit mental model ("what happened / what's the rule / who acted"); five destinations mean zero misroutes during incidents.

**Chain 7 — Perpetual system status**
ACM VIT closes every page with an "All systems online" line backed by semantic green `#16a34a` → design principle: visible system-health signaling builds trust at near-zero UI cost → IntentGuard adapts a persistent ControlPlane status pill in the top bar (Connected / Degraded / Disconnected) using the semantic palette plus a 2s pulse on the dot → why it improves UX: an authorization plane that silently goes down is an outage nobody sees; perpetual status converts "is it the app or the policy?" into a one-glance answer.

**Chain 8 — Numbered governance**
ACM VIT renders its Code of Conduct as four numbered subsections and uses role-then-name patterns in rosters → design principle: stable numbering signals governance seriousness and makes items citable → IntentGuard adapts stable human-readable identifiers for policies (`POL-001.2`), displayed adjacent to every rule row and in escalation steps → why it improves UX: security review is citation-driven; stable IDs let policies be referenced in tickets, commit messages, and audit findings without ambiguity.

**Chain 9 — No duplicated responsive DOM**
ACM VIT duplicates entire project/gallery/about blocks verbatim for desktop and mobile, inflating the page to 557 KB → design principle: responsiveness achieved by DOM duplication causes drift and weight → IntentGuard adapts single responsive components with two density variants (`comfortable`/`compact`) and container queries instead of duplicated renders → why it improves UX: identical state across viewports means the mobile console never disagrees with the desktop audit view, and the bundle stays small enough for fast first paint on restricted corporate networks.

**Chain 10 — Display voice vs workhorse body**
ACM VIT pairs an expressive display family (PolySans Bulky Wide/Slim, fluid `clamp()` up to 36rem, line-height 0.85–1.05) with plain Inter for body → design principle: personality lives in display type; the workhorse text stays neutral — but the split must be scoped → IntentGuard confines expressive display treatment to the landing/marketing layer (Inter 600, tighter tracking, up to 48px) and keeps the console strictly Inter + JetBrains Mono at functional sizes (11–20px) → why it improves UX: decorative typefaces in dense operational UI slow character-level parsing of IDs and rules; calm type where work happens, personality where persuasion happens.

**Chain 11 — Scannable density over prose**
ACM VIT presents 17 blogs, 20 gallery tiles, and 16 team members as short uniform entries with no long-form prose → design principle: for repeated item types, scannable density beats editorial narrative → IntentGuard adapts data tables at 40px comfortable / 32px compact rows and an event stream at a 28px line pitch, zebra-free with 1px separators and truncate-plus-tooltip for long values → why it improves UX: maximum rows per viewport is a triage feature; uniform short entries keep the scan path vertical and predictable.

**Chain 12 — Repeated proof with linked numbers**
Reference observation paired with ACM VIT: Stripe repeats one stat-band template with figures linked to a public status page; ACM VIT repeats its award banner twice and its CTA pairing consistently → design principle: trust accumulates through repeated, verifiable, quantified proof placed at regular intervals → IntentGuard adapts a repeating "proof band" pattern: decisions today, blocks prevented, mean decision latency, policy coverage — each figure linked to its underlying filtered event view → why it improves UX: an enterprise buyer/admin can verify every headline number in one click, which is the console-native equivalent of Stripe's status-page link.

---

## 5. Recommended design tokens — IntentGuard dark enterprise security console

### 5.1 Color palette

| Token | Value | Role |
| --- | --- | --- |
| `bg-canvas` | `#0B0F17` | App background (deep blue-black) |
| `bg-inset` | `#0E131D` | Wells: code blocks, log gutters, search inputs |
| `surface-1` | `#121826` | Cards, table containers, side panel |
| `surface-2` | `#182031` | Hover states, sticky headers, secondary panels |
| `surface-3` | `#1F2940` | Active/selected rows, popovers, tooltips |
| `border-subtle` | `#232D42` | Default 1px separators, card outlines |
| `border-strong` | `#33405C` | Interactive boundaries (inputs, hovered cards) |
| `text-primary` | `#E8EDF6` | Headings, primary values, decision text |
| `text-secondary` | `#A9B4C7` | Body copy, table cells, descriptions |
| `text-tertiary` | `#7C889D` | Eyebrows, timestamps, meta labels |
| `text-faint` | `#5A6577` | Disabled, placeholder, decorative only — **not body text** |
| `accent` (INFO) | `#5B9BFF` | Primary buttons, links, selection, focus ring |
| `accent-hover` | `#77ACFF` | Accent hover state |
| `state-allow` | `#3ECF8E` | ALLOW decision text/icon/badge |
| `state-allow-bg` | `rgba(62,207,142,0.12)` | ALLOW badge tint (over surface) |
| `state-block` | `#FF6B5E` | BLOCK decision text/icon/badge |
| `state-block-bg` | `rgba(255,107,94,0.12)` | BLOCK badge tint |
| `state-escalate` | `#E8B75A` | ESCALATE decision text/icon/badge |
| `state-escalate-bg` | `rgba(232,183,90,0.12)` | ESCALATE badge tint |
| `btn-dark-label` | `#0B0F17` | Label color on solid accent/semantic buttons |

Design intent: the canvas family is a blue-shifted near-black (calm, "control room", not pitch black); one accent hue total; three semantic hues that never appear decoratively.

### 5.2 Contrast verification (WCAG, computed 2026-09-12)

Body text requires **≥ 4.5:1**; large text (≥18.66px bold / 24px) and non-text UI require **≥ 3:1**.

| Pair | Ratio | Verdict |
| --- | --- | --- |
| `text-primary` `#E8EDF6` on `bg-canvas` `#0B0F17` | **16.33** | AAA |
| `text-primary` on `surface-1` `#121826` | **15.09** | AAA |
| `text-primary` on `surface-2` `#182031` | **13.86** | AAA |
| `text-primary` on `surface-3` `#1F2940` | **12.33** | AAA |
| `text-secondary` `#A9B4C7` on `bg-canvas` | **9.17** | AAA |
| `text-secondary` on `surface-1` | **8.48** | AAA |
| `text-secondary` on `surface-2` | **7.78** | AAA |
| `text-secondary` on `surface-3` | **6.93** | AA |
| `text-tertiary` `#7C889D` on `bg-canvas` | **5.36** | AA body |
| `text-tertiary` on `surface-1` | **4.95** | AA body |
| `text-tertiary` on `surface-2` | **4.55** | AA body |
| `text-tertiary` on `surface-3` | **4.05** | Large/meta only (≥3:1) — do not use for body on surface-3 |
| `text-faint` `#5A6577` on `bg-canvas` | **3.25** | Disabled/large only — never body text |
| `accent` `#5B9BFF` on `bg-canvas` | **6.92** | AA body / link text |
| `accent` on `surface-1` | **6.40** | AA body |
| `accent` on `surface-2` | **5.87** | AA body |
| `state-allow` `#3ECF8E` on `bg-canvas` | **9.61** | AAA |
| `state-allow` on `surface-1` | **8.88** / 8.16 on surface-2 | AAA |
| `state-block` `#FF6B5E` on `bg-canvas` | **6.87** | AA body |
| `state-block` on `surface-1` | **6.35** / 5.83 on surface-2 | AA body |
| `state-escalate` `#E8B75A` on `bg-canvas` | **10.37** | AAA |
| `state-escalate` on `surface-1` | **9.59** / 8.80 on surface-2 | AAA |
| `btn-dark-label` `#0B0F17` on `accent` `#5B9BFF` | **6.92** | AA button label |
| `btn-dark-label` on `state-allow` solid | **9.61** | AAA |
| `btn-dark-label` on `state-block` solid | **6.87** | AA |
| `btn-dark-label` on `state-escalate` solid | **10.37** | AAA |
| `accent` focus ring vs `border-subtle` `#232D42` | **4.97** | Meets 3:1 non-text UI |
| Semantic text on own 12% tint badge (over surface-1) | ALLOW **7.14** / BLOCK **5.44** / ESCALATE **7.62** | All AA body |

Every body-text pairing used in the console meets AA 4.5:1; the two deliberate exceptions (`text-faint`, tertiary-on-surface-3) are restricted to disabled, decorative, or large-type contexts by token usage rules.

### 5.3 Type scale

**Font stacks**
- Sans (UI + display): `"Inter", -apple-system, "Segoe UI", system-ui, "Helvetica Neue", sans-serif` — load weights 400/500/600 only in the console (700 reserved for dashboard metrics).
- Mono (data/IDs): `"JetBrains Mono", ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace` — weights 400/500.
- Rule: `font-variant-numeric: tabular-nums` on all data columns, metrics, and timestamps. All identifiers, hashes, rule names, JSON, and logs render in mono.

| Token | Size / line-height | Weight | Tracking | Usage |
| --- | --- | --- | --- | --- |
| `display-xl` | 48px / 1.1 | 600 | -0.02em | Landing hero only |
| `display-lg` | 40px / 1.15 | 600 | -0.02em | Landing sections |
| `metric` | 32px / 1.2 | 600 | -0.015em | Dashboard KPI numbers (mono allowed) |
| `title-lg` | 24px / 1.3 | 600 | -0.01em | Page titles |
| `title-md` | 20px / 1.35 | 600 | normal | Panel/section titles |
| `title-sm` | 18px / 1.4 | 600 | normal | Card titles |
| `body-lg` | 16px / 1.6 | 400 | normal | Section intros, empty states |
| `body` | 14px / 1.55 | 400 | normal | Descriptions, form help |
| `ui` | 13px / 1.5 | 400/500 | normal | Default UI text, table cells (comfortable) |
| `mono-data` | 12px / 1.45 | 400 | normal | IDs, timestamps, log lines, compact cells |
| `label` | 11px / 1.4 | 500 | +0.08em uppercase | Eyebrows, table headers, badges |

### 5.4 Spacing scale (4px base)

`2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80` (px).
Application rules: card padding 16 (compact) / 20 (comfortable); table cell padding 8×12 (compact) / 10×16 (comfortable); panel gaps 24; page gutters 24 desktop / 16 mobile; section rhythm 48–64; icon-to-label gap 8.

### 5.5 Radii scale

| Token | Value | Usage |
| --- | --- | --- |
| `radius-xs` | 4px | Checkboxes, small inputs, kbd chips |
| `radius-sm` | 6px | Buttons, dropdown items, inputs |
| `radius-md` | 8px | Cards, panels, table container |
| `radius-lg` | 12px | Modals, popovers, command palette |
| `radius-pill` | 999px | Status pills, decision badges, tags |

Maximum non-pill radius is 12px — crisp geometry, no "pill cards".

### 5.6 Border & shadow system

- Separation is **1px borders first**: `border-subtle` by default, `border-strong` on interactive hover/focus boundaries.
- One inset highlight allowed on raised surfaces: `inset 0 1px 0 rgba(255,255,255,0.04)`.
- Shadows are reserved for floating layers only (never static cards):
  - `shadow-sm`: `0 1px 2px rgba(0,0,0,0.40)` — tooltips
  - `shadow-md`: `0 4px 12px rgba(0,0,0,0.45)` — popovers, dropdowns
  - `shadow-lg`: `0 12px 32px rgba(0,0,0,0.50)` — modals, command palette
- Focus ring: `0 0 0 2px #0B0F17, 0 0 0 4px #5B9BFF` (2px offset ring, verified 4.97:1 against adjacent chrome).

### 5.7 Iconography

- Grid: 16px for inline/table icons, 20px for nav. Stroke 1.5px, rounded caps/joins, outline style (Lucide-class geometry) for consistency with dev-platform conventions.
- Semantic state icons (check = ALLOW, octagon/slash = BLOCK, shield-alert = ESCALATE, info = accent) may be filled; everything else stays outline.
- Icons inherit text color; they never introduce a new hue.
- **Never color-only state:** every ALLOW/BLOCK/ESCALATE is icon + text label (also required for color-blind users; red/green distinction must not be load-bearing).

### 5.8 Motion guidance

- Durations: `instant 80ms` (opacity), `fast 120ms` (row insert, badge swap), `base 180ms` (hover, panel), `enter 240ms` (drawer, popover), `large 320ms` (page-level transitions). Exits run at half their enter duration with `cubic-bezier(0.4, 0, 1, 1)`.
- Easing: standard `cubic-bezier(0.2, 0, 0, 1)`. No springs, bounce, or elastic curves — security UI never overshoots.
- Live event stream: new rows fade + slide 8px over 120ms; auto-scroll pauses on hover; a 2s opacity pulse is permitted only on the status dot.
- `prefers-reduced-motion: reduce`: disable all transforms, loops, and pulses; transitions collapse to ≤120ms opacity; new stream rows appear instantly with a background-tint fade instead.
- Banned in console: marquees, ambient floats, shimmer, parallax, starfields (all observed on ACM VIT's marketing layer — kept out of operational surfaces).

### 5.9 Density guidance

**Data tables**
- Row heights: 40px comfortable / 32px compact (user-toggleable); header row 32px with 11px uppercase mono labels.
- Cells: 13px sans for names/labels, 12px mono for IDs/values; single-line truncate + tooltip; right-align numerals with tabular-nums.
- No zebra striping — 1px `border-subtle` row separators; hover = `surface-2`; selected row = `surface-3` + 2px accent left rail.
- Sticky header; column sort affordances on header hover; virtualize above ~200 rows.

**Live event stream**
- 28px line pitch, 12px mono; fixed column order: `timestamp | decision | agent | action | resource | rule | latency`.
- Decision badge: 20px pill, semantic text on 12% semantic tint, icon + label.
- New-row emphasis: semantic tint at 8% fading over 2s (suppressed under reduced motion).
- Auto-follow with pause-on-hover and a "jump to live" affordance after user scroll-back; virtualized rendering mandatory.

---

## 6. Anti-patterns to avoid

1. **Cyberpunk/neon gaming aesthetics** — no glowing text, scanlines, gradient meshes, or ACM VIT-style hot-pink/purple energy (`#ff007a`, `#7100ff`) inside the console; they read as entertainment, not control.
2. **Ambient decorative motion in operational views** — marquees, infinite floats, shimmer, starfield breathes (observed extensively on acmvit.in) mask real state changes and fatigue operators.
3. **Chatbot aesthetics** — no chat bubbles, avatars-first layouts, or conversational framing; IntentGuard is a control plane, decisions are records, not messages.
4. **Color-only state encoding** — a red dot alone is not a BLOCK; always icon + text (accessibility and auditability both demand it).
5. **Shadow-heavy card design** — glowing or deep shadows on static dark cards; separation belongs to hairline borders, shadows only lift floating layers.
6. **Duplicated responsive DOM** — verbatim desktop/mobile block duplication (observed on acmvit.in, 557 KB page) causes state drift and slow loads.
7. **Display-typeface noise in dense UI** — bulky display fonts (e.g., PolySans Bulky Wide) above 13px data text slow parsing; expressive type is landing-layer only.
8. **Wall-of-caps body text** — full-caps paragraphs (observed in ACM VIT event recaps) destroy reading speed; caps are for 11px eyebrows only.
9. **More than one competing accent** — a rainbow of brand hues (coral + pink + purple + blue on one page) competes with ALLOW/BLOCK/ESCALATE semantics; one accent, three semantics, everything else neutral.
10. **Radius inflation** — 25–41px feature-card radii (observed on acmvit.in) read consumer-toy; 4–12px keeps infrastructure crisp.
11. **Marketing CTAs inside the console** — "Talk to sales" energy does not belong next to a BLOCK decision; console actions are verbs on objects (Approve, Escalate, Disable rule).
12. **Unverifiable proof** — dashboard metrics without a link to the underlying evidence (violating the Stripe status-link pattern) erode the trust the numbers are meant to build.

---

*End of document. All contrast ratios computed against the WCAG 2.x relative-luminance formula on 2026-09-12; ACM VIT source values extracted from publicly served HTML/CSS on the same date.*
