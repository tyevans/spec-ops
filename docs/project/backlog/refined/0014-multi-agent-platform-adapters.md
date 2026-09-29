---
id: '0014'
title: Multi-Agent Platform Adapters (Claude, Cursor, Antigravity)
status: Refined
dependencies:
- TASK-0010
- TASK-0011
governing_adrs:
- ADR-0001
- ADR-0005
governing_prds:
- PRD-0001
governing_stories:
- US-0007
target_bc: core
---

# TASK-0014: Multi-Agent Platform Adapters (Claude, Cursor, Antigravity)

## Summary
Build multi-agent platform integrations and configuration generators for Claude Code (`CLAUDE.md`), Cursor (`.cursorrules`), and Antigravity slash commands and skills.

## Definition of Done
1. Generators for Claude Code, Cursor, and Antigravity rule sets.
2. Slash command definitions for Antigravity (`/curate`, `/health`, `/worker`).
3. CLI flags in `spec-ops init --agent antigravity,claude,cursor` to configure target agents.
