---
id: '0257'
title: Prevent Task ID Digit Collisions in normalize_task_id
status: Proposed
dependencies: []
governing_prds:
- PRD-0001
governing_stories:
- US-0001
target_bc: queue
---

## Summary
`normalize_task_id()` extracts the first sequence of digits `(\d+)` from any candidate task string or filename. When proposed refactoring task filenames include numbers (e.g. `TASK-REFACTOR-tests-unit-application-migration-test_phase2_integration.md`), the regex extracts `2` and normalizes the task to `TASK-0002`, colliding with existing numerical tasks such as `0002-delta-compress-stored-event-payloads.md`.

## Problem Statement
Task normalization must prioritize canonical ID patterns (`TASK-\d+` or leading `^\d{4}-`) before attempting broad regex digit matches, and ignore numbers embedded in test or module names.

## Acceptance Criteria
```gherkin
Given a proposed task with a descriptive name containing digits like "test_phase2_integration"
When normalize_task_id is evaluated
Then it does not collide with TASK-0002 or coerce the task to an unintended numerical sequence.
```
