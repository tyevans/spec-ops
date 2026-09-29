# SpecOps ⚡

> **Opinionated Project Management as Code (PMaC) and Autonomous Delivery Engine for AI-Agentic Software Engineering.**

SpecOps extracts the hard-won engineering disciplines, guardrails, and autonomous workflows proven in large-scale agentic codebases into a turnkey, reusable platform.

Rather than isolating requirements, tickets, and roadmaps in external SaaS silos (Jira, Linear, Notion), SpecOps treats project management as **machine-readable, version-controlled code** living directly within git alongside production source code.

📖 **Architectural Treatise**: [Delivering Real Integrated Value: How SpecOps Eliminates Functional Silos and the "Mocked Perfection" Trap](docs/delivering-real-value.md)

---

## Why SpecOps? (The Core Philosophy)

Autonomous coding agents (e.g. Antigravity, Claude Code, Cursor, Aider) fail or produce architectural decay when working against traditional project management tools. SpecOps solves the three foundational failure modes of agentic software development:

1. **Context Rot & Specification Drift**:
   External tickets diverge from code within weeks. In SpecOps, specifications (Personas, PRDs, User Stories, Backlog Tasks, and ADRs) live as structured Markdown with YAML frontmatter. Specifications branch, review, and merge directly with code, ensuring **version-locked synchronization**.

2. **The Multi-Agent Concurrency & Merge Conflict Problem**:
   When parallel agents work on concurrent tasks, modifying shared planning files causes merge conflicts upon PR integration. SpecOps enforces **Strict Backlog Isolation**: feature branches in isolated git worktrees are forbidden from touching the backlog directory, allowing $N$ parallel worker streams to merge cleanly into `main` under an atomic merge lock.

3. **Mock Rot & Backdoor Test Masking**:
   Agents frequently write unit tests with excessive mocking or backdoor database hacking (`INSERT INTO...`) that pass tests while failing in production. SpecOps enforces **Hard Invariant: Blackbox Frontdoor Testing**: tests must interact exclusively through public APIs, user interfaces, or standard CloudEvents with zero private backdoors.

4. **The Monolithic Decay Problem**:
   Large monolithic files (>500 lines) cause context loss, broken diffs, and catastrophic regressions in LLMs. SpecOps enforces **Hard Invariant: <500 Lines per Source File**: codebases must proactively decompose into focused, single-responsibility modules.

---

## Architectural Profiles & Baseline ADRs

SpecOps introduces **Architectural Profiles**: composable bundles of foundational Architectural Decision Records (ADRs) that install the "laws of physics" into a project from Day 1:

| Profile | Focus | Installed Baseline ADRs |
|---|---|---|
| **`core`** | Universal SDLC Invariants | • **ADR-0001**: Specification as Code & Project Management Substrate<br>• **ADR-0002**: Modular File Length Limit (<500 Lines Anti-Rot Rule)<br>• **ADR-0003**: Blackbox Frontdoor Verification & Zero Backdoor Testing<br>• **ADR-0004**: Continuous Pre-flight & In-Worktree Self-Healing CI<br>• **ADR-0005**: Git Worktree Concurrency & Strict Backlog Isolation |
| **`bdd`** | Living Executable User Journeys | • **ADR-0006**: Behavior-Driven Development (BDD) with Gherkin User Stories & Playwright |
| **`ddd`** | Cohesive Domain Boundaries | • **ADR-0007**: Domain-Driven Design (DDD) Layering & Explicit Bounded Contexts |

List available profiles at any time:
```bash
spec-ops profiles list
```

---

## Quickstart

### 1. Installation

Install SpecOps via `uv` or `pip`:

```bash
uv pip install -e .
# or run directly:
uv run spec-ops --help
```

### 2. Initialize a Project

Bootstrap the SpecOps directory structure, baseline ADRs, starter personas, and `specops.toml` config:

```bash
spec-ops init --name "MyPlatform" --profile core,bdd,ddd
```

This scaffolds:
```
docs/project/
├── adrs/             # Baseline ADRs (ADR-0001 to ADR-0007) and REGISTRY.md
├── product/          # PRD lifecycle (idea/, shaped/, accepted/, shipped/)
├── user_stories/     # Persona definitions and Gherkin user stories
└── backlog/          # proposed/, refined/, complete/, PRIORITY.md, ROADMAP.md
```

### 3. Verify Codebase Invariants & Buffer Health

```bash
spec-ops health
```
Scans for files exceeding 500 lines, verifies that `PRIORITY.md` matches filesystem states, and reports on the lean ready buffer.

---

## The Three-Tier Autonomous Delivery Loop

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 1: PRD Decomposition Pipeline                         │
│ spec-ops prd create --title "..."                           │
│ spec-ops prd decompose PRD-0001                             │
│ PRD → Architectural Spikes + Thin Vertical Slices in proposed│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Tier 2: JIT Backlog Curation                                │
│ spec-ops curate                                             │
│ Maintains a lean ready buffer of ~10 tasks in refined/      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Tier 3: Autonomous Multi-Worker Engine                      │
│ spec-ops worker                                             │
│ Isolated git worktrees → Preflight gates → Merge lock       │
└─────────────────────────────────────────────────────────────┘
```

### Commands

- **Scaffold New PRD**:
  ```bash
  spec-ops prd create --title "User Authentication" --persona "Developer" --component "core"
  ```
- **Audit PRD Health**:
  ```bash
  spec-ops prd audit
  ```
- **Decompose PRD into Spikes & Slices**:
  ```bash
  spec-ops prd decompose PRD-0001
  ```
- **JIT Backlog Curation**:
  ```bash
  spec-ops curate
  ```
- **Inspect Graph Metrics**:
  ```bash
  spec-ops stats
  ```

---

## Living 2D Graph Visualizer

Launch the interactive relationship graph, Gantt timeline, and Kanban board in your browser:

```bash
spec-ops visualizer --serve --port 8787
```

Or export a zero-dependency, single-file HTML bundle for offline distribution, documentation sites, or GitHub Pages:

```bash
spec-ops visualizer --build dist/visualizer.html
```

---

## Configuration (`specops.toml`)

Configure project boundaries, quality gates, and agent execution parameters:

```toml
[project]
name = "MyPlatform"
docs_dir = "docs/project"

[architecture]
file_length_limit = 500     # Anti-rot file size cap
buffer_target = 10         # Lean JIT ready buffer
components = [
  { id = "core", name = "Core Engine", path = "src" }
]

[quality]
testing_style = "blackbox-frontdoor"
require_bdd = true
preflight = ["pytest"]

[execution]
agent_command = "agy -p '{prompt}'"
agent_max_attempts = 3
git_branch_prefix = "feat/"
backlog_isolation = true
```

---

## License

MIT
