# How-To: Index Failure Memory and Generate Autonomous Healing Playbooks

This guide demonstrates how to index historical failure post-mortems, retrieve targeted remediation advice for recurring errors, and generate autonomous healing playbooks for AI coding workers.

---

## Inspecting Available Healing Strategies

To list all indexed failure remediation strategies ranked by relevance and historical frequency:

```bash
spec-ops rescue playbooks
```

Output:

```text
=== Autonomous Failure Healing Playbook ===
Indexed Strategies: 7 (Total Indexed: 7)

1. [strat-adr0002-file-length] ADR-0002: File length limit violation (>500 lines) (Rank: 10.0)
   Category: file_length
   Summary:  Decompose monolithic module into single-responsibility submodules.
   Remedy:   Run 'spec-ops decompose --suggest <file>' to analyze AST seams and extract cohesive logic.
   Prompt:   "Keep all source files strictly under 400 lines by decomposing into focused helper modules."
   Example:  uv run spec-ops decompose --suggest src/spec_ops/monolith.py
...
```

---

## Querying Targeted Strategies for Specific Errors

When an autonomous worker or preflight gate encounters an error signature (e.g., `ADR-0002` or `mock`):

```bash
spec-ops rescue playbooks --query ADR-0002
```

Output:

```text
=== Autonomous Failure Healing Playbook ===
Indexed Strategies: 1 (Total Indexed: 7)
Query Filter: 'ADR-0002'

1. [strat-adr0002-file-length] ADR-0002: File length limit violation (>500 lines) (Rank: 10.0)
   Category: file_length
   Summary:  Decompose monolithic module into single-responsibility submodules.
   Remedy:   Run 'spec-ops decompose --suggest <file>' to analyze AST seams and extract cohesive logic.
   Prompt:   "Keep all source files strictly under 400 lines by decomposing into focused helper modules."
   Example:  uv run spec-ops decompose --suggest src/spec_ops/monolith.py
```

---

## Machine-Readable JSON Playbooks

For agent prompt injection and automated anti-loop constraints, request JSON output:

```bash
spec-ops rescue playbooks --query ADR-0003 --json
```

Output:

```json
{
  "version": "1.0",
  "query": "ADR-0003",
  "total_matched": 1,
  "strategies": [
    {
      "strategy_id": "strat-adr0003-mock-backdoors",
      "category": "mock_backdoor",
      "failure_signature": "ADR-0003: Prohibited mock backdoor or private internal monkeypatching",
      "ranking_score": 10.0,
      "summary": "Replace private internal mocks with public frontdoor CLI or model entrypoints.",
      "actionable_remedy": "Test observable outcomes through public interfaces without private mock backdoors.",
      "code_snippet": "result = subprocess.run([sys.executable, '-m', 'spec_ops.cli.main', '...'])",
      "prompt_instruction": "Never use unittest.mock or monkeypatch. Verify contracts solely through public interfaces."
    }
  ]
}
```

---

## Exporting Playbooks to Disk

To generate standalone documentation or Markdown playbooks:

```bash
spec-ops rescue playbooks --export dist/rescue/playbook.md
```

Or as JSON:

```bash
spec-ops rescue playbooks --export dist/rescue/playbook.json
```
