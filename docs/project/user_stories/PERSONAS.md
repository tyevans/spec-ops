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

---

## 4. Riley — The Human IC Developer
- **Role**: Senior, mid, or junior software engineer working in a hybrid human-agent development environment.
- **Pain Points**:
  - Agent PR fatigue and the overwhelming cognitive load of reviewing massive AI-generated diffs without architectural context.
  - Being locked out of worktrees when an agent's automated self-healing loop stalls after repeated failures.
  - Lack of ergonomic editor tools, pre-commit validations, and IDE-native feedback loops.
- **Goals with SpecOps**:
  - Seamless worktree takeover capabilities to unblock failed autonomous tasks.
  - Clear provenance and diff legibility separating human-written and agent-generated changes.
  - Fast, localized preflight verification hooks directly within the local developer environment.

---

## 5. Taylor — The Product Manager
- **Role**: Product manager, business analyst, or domain expert owning product outcomes and customer discovery.
- **Pain Points**:
  - High friction and terminal-command intimidation when collaborating on git-based specifications.
  - Disconnect between green CI test runs and actual customer-ready business value.
  - Double-entry overhead translating between git repositories and executive roadmaps.
- **Goals with SpecOps**:
  - Clear user acceptance testing (UAT) workflows and visual PRD lifecycle tracking.
  - Direct traceability from business outcomes to executable Gherkin scenarios without writing raw code.
  - Living visualizer reports and milestone roadmap exports for non-technical stakeholders.

---

## 6. Sasha — The Trust & Security Officer
- **Role**: Security engineer, DevSecOps lead, or compliance auditor ensuring safe autonomous agent execution.
- **Pain Points**:
  - Unsandboxed agents running arbitrary shell commands, installing hallucinated packages (slopsquatting), or leaking credentials.
  - Lack of verifiable, tamper-evident audit trails showing human sign-offs for SOC2 and ISO compliance.
- **Goals with SpecOps**:
  - Hard sandboxing boundaries and dependency lockfile invariants for all autonomous worker sessions.
  - Cryptographic provenance and human sign-off verification for production-bound specification changes.
