"""Worker bounded context for multi-worker execution, claiming, and merge locking."""

from .claimer import (
    TaskClaimer,
    hydrate_task_prompt,
    initialize_worktree,
    validate_definition_of_ready,
)
from .commits import (
    build_commit_subject,
    build_commit_trailers,
    derive_conventional_type,
    format_task_commit_message,
    parse_commit_trailers,
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
from .review import (
    ChangedFileInfo,
    CommitProvenanceInfo,
    ReviewBrief,
    generate_review_brief,
    render_review_brief,
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
    "ChangedFileInfo",
    "CommitProvenanceInfo",
    "HookEvaluationResult",
    "MergeLockManager",
    "PipelineResult",
    "PreCommitHookEvaluator",
    "PreflightPipeline",
    "PreflightStage",
    "ReviewBrief",
    "StageResult",
    "TaskClaimer",
    "build_agent_cmd",
    "build_commit_subject",
    "build_commit_trailers",
    "cleanup_worktree",
    "create_worktree",
    "derive_conventional_type",
    "detect_backlog_modifications",
    "determine_rebase_command",
    "format_task_commit_message",
    "generate_review_brief",
    "hydrate_task_prompt",
    "initialize_worktree",
    "install_pre_commit_hook",
    "interpolate_runner_template",
    "is_rebase_in_progress",
    "parse_commit_trailers",
    "prepare_guardrailed_commit",
    "prepare_runner_environment",
    "rebase_with_inference_healing",
    "render_review_brief",
    "run_spec_ops_health_hook",
    "run_worktree_preflight",
    "sanitize_backlog_modifications",
    "squash_merge_and_commit",
    "stage_legitimate_files",
    "validate_definition_of_ready",
]
