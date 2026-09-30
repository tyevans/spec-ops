# How-To: Author PRDs and User Stories with the Web Studio

This guide explains how to launch and use the zero-dependency Web PRD Studio and Low-Code Gherkin BDD Story Assistant.

---

## Launching the Web PRD Studio

To start the local visualizer web server focused directly on the PRD Studio view:

```bash
spec-ops prd studio
```

Options:
- `--open`: Automatically opens your default web browser to the studio view (`http://127.0.0.1:8787/studio`).
- `--port PORT`: Specifies custom local port (default: `8787`).
- `--host HOST`: Specifies custom network interface (default: `127.0.0.1`).

Example:

```bash
spec-ops prd studio --open --port 8787
```

---

## Authoring PRDs with Real-Time Validation

The **PRD Studio** view provides an interactive form-based authoring interface:

1. **Title & Target Persona**: Select a target persona from `docs/project/user_stories/PERSONAS.md` or define a new persona.
2. **Component & Bounded Context**: Assign the architectural component governing the PRD.
3. **Problem Statement & Anti-Goals**: Explicitly capture user frictions, value metrics, and out-of-scope anti-goals.
4. **Falsifiable Checkable Outcomes**: Write testable outcome statements. The live structural linter validates outcome statements against falsifiability heuristics and highlights vague or non-testable prose in real time.
5. **Split-Pane Markdown Preview**: Live preview shows formatted Diataxis markdown with synchronized YAML frontmatter.
6. **Direct Save**: Click **Save PRD** to write the document directly to `docs/project/product/idea/` or `shaped/` with git version-locking.

---

## Authoring BDD User Stories in the Story Studio

The **Story Studio** view provides a low-code Gherkin scenario editor:

1. **Select Parent PRD**: Choose the accepted PRD that this story implements.
2. **Gherkin Step Autocompletion**: When typing `Given`, `When`, or `Then`, the assistant suggests public frontdoor fixture steps extracted from existing test suites.
3. **Active Backdoor Detection**: The assistant checks step definitions against ADR-0003 anti-patterns. If a step attempts private internal state tampering or mock backdoors, an architectural warning is displayed with guidance to test observable frontdoor contracts instead.
4. **Accept & Save**: Once valid Gherkin scenarios are defined, saving writes the user story directly to `docs/project/user_stories/accepted/us-XXXX-*.md`.
