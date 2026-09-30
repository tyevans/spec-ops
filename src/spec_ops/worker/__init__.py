"""Worker bounded context for multi-worker execution, claiming, and merge locking."""

from .claimer import (
    TaskClaimer,
    hydrate_task_prompt,
    initialize_worktree,
    validate_definition_of_ready,
)
from .guardrails import (
    detect_backlog_modifications,
    prepare_guardrailed_commit,
    sanitize_backlog_modifications,
    stage_legitimate_files,
)
from .hooks import (
    HookEvaluationResult,
    PreCommitHookEvaluator,
    install_pre_commit_hook,
    run_spec_ops_health_hook,
)
from .integration import (
    determine_rebase_command,
    is_rebase_in_progress,
    rebase_with_inference_healing,
    squash_merge_and_commit,
)
from .merge_lock import MergeLockManager
from .orchestrator import BatchCycleOrchestrator, BatchCycleReport
from .preflight import (
    PipelineResult,
    PreflightPipeline,
    PreflightStage,
    StageResult,
    run_worktree_preflight,
)
from .runners import (
    AgentRunner,
    build_agent_cmd,
    interpolate_runner_template,
    prepare_runner_environment,
)
from .worktree import cleanup_worktree, create_worktree

__all__ = [
    "AgentRunner",
    "BatchCycleOrchestrator",
    "BatchCycleReport",
    "HookEvaluationResult",
    "MergeLockManager",
    "PipelineResult",
    "PreCommitHookEvaluator",
    "PreflightPipeline",
    "PreflightStage",
    "StageResult",
    "TaskClaimer",
    "build_agent_cmd",
    "cleanup_worktree",
    "create_worktree",
    "detect_backlog_modifications",
    "determine_rebase_command",
    "hydrate_task_prompt",
    "initialize_worktree",
    "install_pre_commit_hook",
    "interpolate_runner_template",
    "is_rebase_in_progress",
    "prepare_guardrailed_commit",
    "prepare_runner_environment",
    "rebase_with_inference_healing",
    "run_spec_ops_health_hook",
    "run_worktree_preflight",
    "sanitize_backlog_modifications",
    "squash_merge_and_commit",
    "stage_legitimate_files",
    "validate_definition_of_ready",
]
