# Explanation: Project Management as Code (PMaC)

Why version-lock project management in git instead of using external issue trackers like Jira or Linear?

---

## 1. The Specification Drift Problem

When requirements, user stories, and acceptance criteria live in external SaaS tools, they inevitably drift from the code repository. Branches are merged without updating ticket descriptions. Acceptance criteria change in discussions without updating tickets. Coding agents lack access to true project context and rely on outdated or truncated instructions.

---

## 2. Git as the Single Source of Truth

With Project Management as Code (PMaC):
- Requirements and source code share the exact same commit hash.
- Changes to user stories or tasks are reviewed via standard pull requests.
- Autonomous coding agents have instant, offline access to full project context directly in the workspace.
- There are zero external API dependencies or synchronization bottlenecks.

---

## 3. The Multi-Disciplinary Team in PMaC

PMaC does not replace humans with an isolated agent; it aligns a hybrid human-agent workforce:

| Persona | Role in PMaC | Key Interaction |
|---|---|---|
| **Alex** (Systems Architect) | Establishes baseline ADRs and architectural profiles | Defines non-negotiable quality invariants and boundaries |
| **Jordan** (Engineering Lead) | Guides velocity and backlog health | Monitors the living 2D graph and JIT curation buffer |
| **Morgan** (Coding Agent) | Executes vertical slices in isolated worktrees | Validates against Gherkin scenarios via frontdoor-only tests |
| **Riley** (Human IC Developer) | Pairs with agents and steps in when needed | Takes over stalled worktrees and authors nuanced logic |
| **Taylor** (Product Manager) | Governs customer outcomes and PRD lifecycles | Validates business value and signs off on UAT readiness |
| **Sasha** (Security & Trust Officer) | Enforces execution safety and compliance | Audits dependency provenance and ensures sandbox boundaries |

---

## 4. The Two Tiers of Personas: Meta vs. Domain

When adopting PMaC, teams must distinguish between two conceptual tiers of personas:

1. **Meta-Personas (The Toolchain Operators)**:
   - These are the humans and autonomous agents who build and maintain the codebase (Alex, Jordan, Morgan, Riley, Taylor, Sasha).
   - They govern how work is organized, reviewed, and merged.
2. **Domain Personas (The Downstream End-Users)**:
   - These are the external users, customers, or actors for whom the application is built (e.g. "Dr. Patel the Clinician", "Marcus the Logistics Manager").
   - These personas anchor PRD outcomes and Gherkin scenarios (`As a <Domain Persona>, I want <Action> so that <Outcome>`), ensuring tests prove real end-user value rather than engineering technicalities.
