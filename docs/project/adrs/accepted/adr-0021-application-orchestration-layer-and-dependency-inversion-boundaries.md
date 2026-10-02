# ADR-0021: Application Orchestration Layer and Dependency Inversion Boundaries

## Status
Accepted

## Context
As SpecOps expanded its autonomous Project Management as Code (PMaC) capabilities, the living architectural review radar identified 15 prohibited boundary import violations violating ADR-0007 (Domain-Driven Design and Layered Architecture). Specifically:
1. Lower-layer domain contexts (`backlog`, `security`, `spike`) illegally imported from execution infrastructure (`worker`, `rescue`, `scaffold`).
2. Foundational layers (`core`, `docs`, `security`) illegally imported presentation/visualization modules (`visualizer.generator`, `visualizer.burndown_deck`).
3. Domain layers (`docs`, `prd`) reached upward to import CLI argument parsing (`cli.parser.build_parser`) for drift inspection.
4. Core event storage (`core.event_store`) directly imported `backlog` deciders and file writers to project read models.

These backward dependencies were temporarily suppressed in `pyproject.toml` under `ignore_imports`, but surfaced on the living relationship graph as flashing red alert lines, highlighting significant architectural seam erosion.

The root cause was the absence of an explicit **Application / Use-Case Orchestration Layer** (`spec_ops.app`) positioned between presentation (`cli`, `tui`) and domain/execution layers, combined with misplaced foundational primitives and lack of dependency inversion for projections and introspection.

## Decision
We establish **ADR-0021: Application Orchestration Layer and Dependency Inversion Boundaries** through four architectural pillars:

### 1. New Bounded Context: `spec_ops.app` (Layer 4)
We introduce an explicit application orchestration bounded context `spec_ops.app` at Layer 4 (co-located with presentation services):
- **Role**: Coordinates multi-context workflows, transactional use cases, and cross-cutting pipelines.
- **Components**:
  - `app.task_lifecycle`: Coordinates task claiming, preflight gating, dual-custody verification (`security`), git squash-merging and merge-locking (`worker`), and queue status transitions (`backlog`).
  - `app.rescue_lifecycle`: Coordinates human worktree rescue, patch salvaging (`rescue`), handover artifact cleanup, and failure post-mortem recording (`backlog`).
  - `app.site_bundler`: Orchestrates documentation static site compilation (`docs`), embedding interactive visualizer bundles (`visualizer`), and exporting roadmap diagrams (`prd`).
- **Layer Rule**: `app` is permitted to import downward into Layer 3 (`worker`, `rescue`, `scaffold`, `release`), Layer 2 (`backlog`, `prd`, `adrs`, `graph`, `profiles`, `spike`), and Layer 1 (`core`, `security`, `docs`, `config`). Lower layers are strictly forbidden from importing `app`.

### 2. Downward Relocation of Foundational Primitives (Layers 0 & 1)
Low-level primitives mistakenly implemented in higher-level contexts are relocated downward to foundational packages:
- **Git Worktree Primitives**: Move `create_worktree` and `cleanup_worktree` from `spec_ops.worker.worktree` into `spec_ops.core.git_worktree`. Both `spike` and `worker` depend downward on `core`.
- **Environment Sanitization**: Move `sanitize_environment` from `spec_ops.worker.sandbox_env` into `spec_ops.security.sandbox`. Execution sandboxes depend downward on `security`.
- **Git Tree Hashing**: Move `compute_git_tree_digest` from `spec_ops.prd.manifest` into `spec_ops.security.digest`. Both `security` and `prd` consume the foundational digest service.
- **Roadmap Milestone Parser**: Move `parse_roadmap_milestones` from `spec_ops.visualizer.burndown_deck` into `spec_ops.core.roadmap`. `visualizer` and `backlog` both consume `core`.

### 3. Dependency Inversion for Domain Event Projections (`core` → `backlog`)
- `spec_ops.core.event_store` must remain a pure domain event substrate without importing `spec_ops.backlog`.
- State projection occurs via an in-memory event publisher/subscriber pattern or projection port. Read-model projection logic resides in `spec_ops.backlog`, which subscribes to core events or is invoked via dependency inversion.

### 4. Dependency Injection for Presentation Introspection (`docs` / `prd` → `cli`)
- `spec_ops.docs.checker` and `spec_ops.prd.persona_friction` are strictly forbidden from importing `spec_ops.cli.parser`.
- Command trees, CLI schema specifications, or argument parser instances must be passed into inspection functions via dependency injection from the CLI entrypoint (composition root).

### 5. Architectural Contract and Waiver Retirement
- `pyproject.toml` [tool.importlinter] contracts are updated to include `spec_ops.app` in Layer 4.
- All temporary `ignore_imports` entries corresponding to these 15 violations are scheduled for sequential elimination as the remediation tasks integrate into `main`.

## Consequences
- **Positive**:
  - Restores strict acyclic layering under ADR-0007.
  - Eliminates flashing red warning lines on the living relationship graph and review radar.
  - Provides a natural home (`spec_ops.app`) for complex end-to-end workflows without polluting domain models.
  - Unblocks clean, isolated testing of domain logic without spinning up execution infrastructure.
- **Negative**:
  - Requires decomposing existing multi-context utility files and updating import paths across the codebase.
  - Requires maintaining the `spec_ops.app` module and enforcing its boundary rules in `spec-ops health`.
