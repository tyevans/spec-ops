# How to Generate Customer Release Notes and Business Value Changelogs

SpecOps provides automated, customer-facing release notes and business value changelog generation (`spec-ops release notes`). It extracts shipped PRD capabilities, passed Gherkin user scenarios, and persona impacts while strictly excluding internal engineering chores and technical spikes.

---

## 1. Generating Customer Release Notes in Markdown

To generate a customer-facing Markdown release notes document for a completed milestone:

```bash
uv run spec-ops release notes --milestone M1 --format markdown
```

This compiles specifications and writes the output to `docs/reference/release-notes-m1.md` (or a custom path via `-o / --output`).

The generated notes categorize outcomes into three customer-visible sections:
- **New Capabilities**: Shipped PRD outcomes from the "What good looks like" sections.
- **User Scenarios Added**: Passed executable Gherkin user story summaries and scenarios.
- **Persona Impacts**: Customer benefits and goals mapped from `PERSONAS.md`.

Internal developer refactors, technical debt chores, and invisible architectural spike experiments are strictly omitted from customer communications.

---

## 2. Exporting Styled HTML for Stakeholder Newsletters

To generate a standalone, styled HTML email template for distribution to non-technical stakeholders, customers, or executive newsletters:

```bash
uv run spec-ops release notes --milestone M1 --format html --branded
```

This outputs a responsive, email-friendly HTML document with SpecOps branding and saves it to `docs/reference/release-notes-m1.html` (or a custom path via `-o / --output`).

The HTML template provides:
- Standalone CSS styling compatible with email clients and web views.
- Deep links connecting each new capability directly to the live GitHub Pages documentation.
- Visualizer permalinks allowing stakeholders to explore the capability in the interactive 2D graph visualizer.

---

## 3. Generating Release Notes from a Shipped PRD

To compile customer-facing release notes directly from a shipped or accepted PRD:

```bash
uv run spec-ops release notes PRD-0001 --format markdown
```

This groups benefits by target persona (`Taylor`, `Alex`, `Jordan`, `Riley`) and formats checkable outcomes as verifiable customer UAT checkmarks without internal git commit jargon.

### Publishing to Project Changelog

To update the living project changelog at `docs/explanation/changelog.md` and save dedicated release notes under `docs/releases/`:

```bash
uv run spec-ops release notes PRD-0001 --publish
```

### Exporting Multi-Format Output

Release notes can be exported in GitHub Markdown, self-contained HTML, or structured JSON:

```bash
uv run spec-ops release notes PRD-0001 --format html
uv run spec-ops release notes PRD-0001 --format json
```
