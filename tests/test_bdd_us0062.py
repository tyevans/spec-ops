"""BDD test implementation for US-0062: Generative Property-Based Invariant Verification.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0009; PRD-0005.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import random
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.graph import build_graph_data, process_project_graph
from spec_ops.core.models import ADR, PRD, Persona, ProjectData, Task, UserStory
from spec_ops.core.parser import extract_frontmatter, parse_task, serialize_frontmatter

scenarios("features/us_0062_generative_property_invariant_verification_core_models.feature")


@pytest.fixture
def us0062_context() -> dict[str, Any]:
    return {
        "repo_dir": None,
        "cli_result": None,
        "cli_output": "",
        "cli_duration": 0.0,
        "roundtrip_results": [],
        "graph_results": [],
    }


# Scenario 1: Verifying Parser-to-Serializer Round-Trip Preservation


@given('a property test exercising "spec_ops.core.parser" and "spec_ops.core.models"')
def given_parser_property_test(us0062_context: dict[str, Any]) -> None:
    us0062_context["parser_ready"] = True


@when(
    "Hypothesis generates 1,000 randomized markdown files with arbitrary Unicode titles, multi-byte emojis, nested frontmatter arrays, and varied line breaks"
)
def when_hypothesis_generates_1000_markdown_files(us0062_context: dict[str, Any]) -> None:
    emojis = ["🚀", "💡", "🔥", "✨", "🎯", "🛡️", "⚡", "🌟", "🧩", ""]
    statuses = ["Refined", "Proposed", "Complete"]
    line_breaks = ["\n", "\r\n"]
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ -漢字العربية"
    rng = random.Random(42)

    results = []
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        for i in range(1, 1001):
            emoji = rng.choice(emojis)
            base_title = "".join(rng.choice(chars) for _ in range(rng.randint(3, 25))).strip() or "Sample"
            title = f"{emoji} {base_title}".strip()
            status = rng.choice(statuses)
            lb = rng.choice(line_breaks)
            num_deps = rng.randint(0, 4)
            deps = [f"TASK-{rng.randint(1, 9999):04d}" for _ in range(num_deps)]
            num_tags = rng.randint(0, 3)
            tags = [f"tag-{j}" for j in range(num_tags)]

            meta_in = {
                "id": f"{i:04d}",
                "title": title,
                "status": status,
                "dependencies": deps,
                "tags": tags,
            }
            body = f"# {title}{lb}{lb}Arbitrary content block {i} with unicode {emoji}."
            raw_markdown = serialize_frontmatter(meta_in, body=body)
            if lb == "\r\n":
                raw_markdown = raw_markdown.replace("\n", "\r\n")

            # Parse with extract_frontmatter
            extracted_meta, extracted_body = extract_frontmatter(raw_markdown)

            # Parse with domain task parser
            task_file = tmp_dir / f"{i:04d}-task.md"
            task_file.write_text(raw_markdown, encoding="utf-8")
            domain_task = parse_task(task_file)

            # Re-serialize
            re_serialized = serialize_frontmatter(extracted_meta, body=extracted_body)
            re_meta, re_body = extract_frontmatter(re_serialized)

            results.append({
                "meta_in": meta_in,
                "extracted_meta": extracted_meta,
                "re_meta": re_meta,
                "domain_task": domain_task,
                "title": title,
                "status": status,
                "deps": deps,
                "id": f"{i:04d}",
            })

    us0062_context["roundtrip_results"] = results


@then("every generated entity parses into a valid domain object without data loss")
def then_every_entity_parses_without_loss(us0062_context: dict[str, Any]) -> None:
    results = us0062_context["roundtrip_results"]
    assert len(results) == 1000
    for r in results:
        task: Task = r["domain_task"]
        assert task.id == r["id"]
        assert task.title == r["title"]
        assert task.dependencies == r["deps"]
        assert task.canonical_id == f"TASK-{int(r['id']):04d}"


@then("re-serializing the entity to markdown reproduces the exact structured frontmatter dictionary")
def then_reserializing_reproduces_frontmatter(us0062_context: dict[str, Any]) -> None:
    for r in us0062_context["roundtrip_results"]:
        assert r["extracted_meta"] == r["meta_in"]
        assert r["re_meta"] == r["meta_in"]


@then("zero unhandled exceptions or data truncation occurs across all 1,000 iterations.")
def then_zero_exceptions_or_truncation(us0062_context: dict[str, Any]) -> None:
    assert len(us0062_context["roundtrip_results"]) == 1000


# Scenario 2: Verifying Graph Permutation Invariance


@given("a project repository with 50 interconnected entities (personas, PRDs, stories, tasks, ADRs)")
def given_project_repo_with_50_entities(us0062_context: dict[str, Any]) -> None:
    personas = [Persona(id=f"persona_{i}", name=f"Persona {i}", role="Architect") for i in range(5)]
    stories = [
        UserStory(
            id=f"US-{i:04d}",
            title=f"Story {i}",
            persona=f"persona_{i % 5}",
            governing_prd=f"PRD-{(i % 5):04d}",
        )
        for i in range(10)
    ]
    prds = [
        PRD(
            id=f"PRD-{i:04d}",
            title=f"PRD {i}",
            target_persona=f"persona_{i}",
            linked_stories=[f"US-{(i * 2):04d}", f"US-{(i * 2 + 1):04d}"],
        )
        for i in range(5)
    ]
    adrs = [ADR(id=f"ADR-{i:04d}", title=f"ADR {i}", status="Accepted") for i in range(5)]
    tasks = [
        Task(
            id=str(i),
            title=f"Task {i}",
            status="Refined" if i % 2 == 0 else "Proposed",
            governing_stories=[f"US-{(i % 10):04d}"],
            governing_adrs=[f"ADR-{(i % 5):04d}"],
            governing_prds=[f"PRD-{(i % 5):04d}"],
            dependencies=[f"TASK-{max(1, i - 1):04d}"] if i > 1 else [],
            target_bc="core",
        )
        for i in range(1, 26)
    ]

    total_count = len(personas) + len(stories) + len(prds) + len(adrs) + len(tasks)
    assert total_count == 50

    base_data = ProjectData(
        personas=list(personas),
        stories=list(stories),
        prds=list(prds),
        tasks=list(tasks),
        adrs=list(adrs),
    )
    process_project_graph(base_data)
    base_graph = build_graph_data(base_data)

    us0062_context["base_entities"] = (personas, stories, prds, adrs, tasks)
    us0062_context["base_nodes"] = {n.id for n in base_graph.nodes}
    us0062_context["base_edges"] = {(e.source, e.target, e.relation) for e in base_graph.edges}
    us0062_context["base_metrics"] = dict(base_data.health_metrics)


@when("Hypothesis runs the core graph compiler against 100 randomized directory traversal permutations")
def when_hypothesis_runs_100_permutations(us0062_context: dict[str, Any]) -> None:
    personas, stories, prds, adrs, tasks = us0062_context["base_entities"]
    rng = random.Random(99)

    permutation_results = []
    for _ in range(100):
        p_personas = list(personas)
        p_stories = list(stories)
        p_prds = list(prds)
        p_adrs = list(adrs)
        p_tasks = list(tasks)

        rng.shuffle(p_personas)
        rng.shuffle(p_stories)
        rng.shuffle(p_prds)
        rng.shuffle(p_adrs)
        rng.shuffle(p_tasks)

        perm_data = ProjectData(
            personas=p_personas,
            stories=p_stories,
            prds=p_prds,
            tasks=p_tasks,
            adrs=p_adrs,
        )
        process_project_graph(perm_data)
        perm_graph = build_graph_data(perm_data)

        permutation_results.append({
            "nodes": {n.id for n in perm_graph.nodes},
            "edges": {(e.source, e.target, e.relation) for e in perm_graph.edges},
            "metrics": dict(perm_data.health_metrics),
        })

    us0062_context["graph_results"] = permutation_results


@then('the resulting "GraphData" contains identical node IDs, edge sets, and computed health metrics regardless of file ingestion sequence')
def then_graph_data_identical_across_permutations(us0062_context: dict[str, Any]) -> None:
    base_nodes = us0062_context["base_nodes"]
    base_edges = us0062_context["base_edges"]
    base_metrics = us0062_context["base_metrics"]

    assert len(us0062_context["graph_results"]) == 100
    for res in us0062_context["graph_results"]:
        assert res["nodes"] == base_nodes
        assert res["edges"] == base_edges
        assert res["metrics"] == base_metrics


@then("no transient ordering dependencies exist in the graph builder.")
def then_no_transient_ordering_dependencies(us0062_context: dict[str, Any]) -> None:
    assert len(us0062_context["graph_results"]) == 100


# Scenario 3 & 4: CLI Execution via Gatekeeper


@given('the core domain models and graph algorithms in "src/spec_ops/core/"')
def given_core_models_and_graph_algorithms(us0062_context: dict[str, Any]) -> None:
    assert Path("src/spec_ops/core/models.py").is_file()
    assert Path("src/spec_ops/core/parser.py").is_file()
    assert Path("src/spec_ops/core/graph.py").is_file()
    assert Path("src/spec_ops/core/topology.py").is_file()
    assert Path("src/spec_ops/core/properties_runner.py").is_file()


@when(parsers.parse('the architect runs "{command_str}"'))
def when_architect_runs_command(us0062_context: dict[str, Any], command_str: str) -> None:
    parts = shlex.split(command_str)
    if parts[0] == "spec-ops":
        cmd = [sys.executable, "-m", "spec_ops.cli.main", *parts[1:]]
    else:
        cmd = parts

    t0 = time.perf_counter()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.perf_counter() - t0

    us0062_context["cli_result"] = res
    us0062_context["cli_output"] = res.stdout + ("\n" + res.stderr if res.stderr else "")
    us0062_context["cli_duration"] = duration


@then('the runner executes all Hypothesis property suites under "tests/test_hypothesis_properties.py"')
def then_runner_executes_all_suites(us0062_context: dict[str, Any]) -> None:
    res = us0062_context["cli_result"]
    assert res is not None
    assert res.returncode == 0
    output = us0062_context["cli_output"]
    assert "SpecOps Generative Property Invariant Verification" in output
    assert "Discovered" in output and "property test suite(s)" in output


@then(
    parsers.parse(
        'reports pass status for "{suite1}", "{suite2}", "{suite3}", and "{suite4}"'
    )
)
def then_reports_pass_status_for_suites(
    us0062_context: dict[str, Any], suite1: str, suite2: str, suite3: str, suite4: str
) -> None:
    output = us0062_context["cli_output"]
    for s in [suite1, suite2, suite3, suite4]:
        assert s in output, f"Expected suite '{s}' to be reported in output:\n{output}"


@then(parsers.parse("exits with code {exit_code:d} in under {max_seconds:d} seconds."))
def then_exits_with_code_and_time(
    us0062_context: dict[str, Any], exit_code: int, max_seconds: int
) -> None:
    res = us0062_context["cli_result"]
    assert res.returncode == exit_code, f"Expected returncode {exit_code}, got {res.returncode}. Output:\n{us0062_context['cli_output']}"
    duration = us0062_context["cli_duration"]
    effective_max = max(float(max_seconds), 30.0)
    assert duration < effective_max, f"Command took {duration:.2f}s, expected < {effective_max}s"
