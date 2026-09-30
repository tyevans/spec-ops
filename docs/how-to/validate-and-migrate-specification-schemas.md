# How-To: Validate and Migrate Specification Schemas

This guide explains how to audit YAML frontmatter across `docs/project/` against active Pydantic schema models and perform automated, safe in-place migrations.

---

## 1. Audit Specification Frontmatter

To audit all specification documents (`backlog/`, `product/`, `user_stories/`) against schema v2.0:

```bash
uv run spec-ops schema check
```

Or target a specific directory or file:

```bash
uv run spec-ops schema check docs/project/backlog/refined/0076-sample.md
```

If all documents conform, the command reports:

```text
Schema Check Passed: All specification documents conform to schema v2.0
```

If any document contains malformed YAML syntax or missing required fields, compiler-grade diagnostic pointers indicating the exact file, line, and column will be displayed with exit code `1`.

---

## 2. Preview Schema Migrations (Dry-Run)

When specifications use legacy fields (such as `governing_adr: 0001` instead of `governing_adrs: ['ADR-0001']`), preview the projected transformations with `--dry-run`:

```bash
uv run spec-ops schema migrate --dry-run
```

This command outputs a unified diff of all projected frontmatter transformations without modifying files on disk.

---

## 3. Execute In-Place Schema Migrations

To automatically upgrade legacy frontmatter fields in-place while preserving non-frontmatter bodies, headings, tables, and fenced code blocks byte-for-byte:

```bash
uv run spec-ops schema migrate --in-place
```

SpecOps will rewrite only the YAML frontmatter block, guaranteeing zero byte alteration to the technical specification body below the frontmatter fence.
