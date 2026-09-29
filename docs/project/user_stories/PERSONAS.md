# SpecOps User Personas

Archetypes representing the software architects, engineering leads, and autonomous AI agents who interact with and rely on SpecOps.

---

## 1. Alex — The Agentic Systems Architect
- **Role**: Staff engineer and platform architect building complex, distributed systems with AI coding assistants.
- **Pain Points**:
  - Context rot when specifications stored in external SaaS tools (Jira, Linear) drift from git code.
  - Frustrating merge conflicts when multiple autonomous agents edit backlog files in parallel.
  - Monolithic file sprawl (>500 lines) causing LLMs to lose context and introduce subtle bugs.
- **Goals with SpecOps**:
  - Version-lock all project specifications (Personas, PRDs, Stories, Tasks, ADRs) in git alongside code.
  - Strict backlog isolation allowing multiple agents to run concurrently in worktrees without merge conflicts.
  - Non-negotiable file length caps (<500 lines) keeping codebases modular and LLM-friendly.

---

## 2. Jordan — The AI-Native Engineering Lead
- **Role**: Engineering director / product lead overseeing hybrid human-agent development teams.
- **Pain Points**:
  - Invisible progress and lack of traceability from high-level user pain points to pull requests.
  - Agents writing shallow unit tests with excessive mocks that pass CI but fail in production.
  - Spending hours triaging backlogs instead of delivering value.
- **Goals with SpecOps**:
  - Living 2D relationship graph and Gantt roadmap generated automatically from repository Markdown files.
  - Blackbox frontdoor testing rules ensuring agents verify software like real external users.
  - Automated JIT backlog curation keeping a lean buffer of ready tasks without specification drift.

---

## 3. Morgan — The Autonomous Coding Agent
- **Role**: LLM-powered coding agent (Antigravity, Claude Code, Cursor, Aider) executing backlog tasks.
- **Pain Points**:
  - Ambiguous ticket descriptions with no clear definition of done or governing architectural rules.
  - Pushing changes that fail remote CI without immediate diagnostic feedback.
  - Accidental modifications to shared project management files causing git merge rejections.
- **Goals with SpecOps**:
  - Explicit task specifications citing governing ADRs, dependencies, and testable acceptance criteria.
  - In-worktree pre-flight verification and automated self-healing loops on failed checks.
  - Strict worktree isolation keeping git history clean and pull requests conflict-free.
