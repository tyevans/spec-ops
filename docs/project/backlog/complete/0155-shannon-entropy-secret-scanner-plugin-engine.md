---
id: '0155'
title: Shannon Entropy Secret Scanner Rule Plugin Engine and Custom Token Defenses
status: Complete
dependencies:
- TASK-0053
- TASK-0130
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0019
governing_prds:
- PRD-0002
governing_stories:
- US-0053
- US-0054
target_bc: security
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T18:25:44.720342+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0155: Shannon Entropy Secret Scanner Rule Plugin Engine and Custom Token Defenses

## Summary
Implement the extensible Shannon entropy secret scanner rule plugin engine (`src/spec_ops/security/entropy_plugins.py`). Fulfilling ADR-0019 and PRD-0002, this engine provides project-configurable secret detection rules, dynamic Shannon entropy calculation over base64/hex token candidates, and custom token allowlisting loaded from `.specops/security.yaml` without hardcoding credentials in source code.

## Problem Statement & Context
Hardcoded regexes for secret detection catch known tokens (e.g. AWS keys, GitHub tokens) but miss custom high-entropy credentials, internal HMAC signing secrets, or private API keys used by enterprise organizations. Conversely, strict entropy scanners produce false positives on UUIDs or SHA hashes unless tuned. Teams require an extensible plugin architecture that computes Shannon entropy and applies project-specific allowlists and rules.

## Key Requirements & Scope
1. **Shannon Entropy & Rule Plugin Engine (`src/spec_ops/security/entropy_plugins.py`)**:
   - Calculates mathematical Shannon entropy $H(X) = -\sum p(x) \log_2 p(x)$ across arbitrary string tokens.
   - Loads custom rule plugins and entropy threshold definitions from `.specops/security.yaml` or project config.
   - Supports contextual ignore markers (`# pragma: allowlist secret`, SHA hashes, UUIDs).
2. **Scanner CLI Integration**:
   - Integrated into `spec-ops health --security` and git pre-commit hooks.
   - Provides `spec-ops security scan --entropy [--threshold <float>]` for ad-hoc inspection.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Entropy plugin module in `src/spec_ops/security/entropy_plugins.py` must stay strictly under 400 lines (ADR-0002).
- **Zero Hardcoded Secrets Invariant (ADR-0019)**: Tests and implementation must never contain live or fake high-entropy credentials without allowlist pragmas.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/security/entropy_plugins.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Detecting high-entropy tokens exceeding custom threshold
```gherkin
Given a staged source file containing an unannotated 48-character high-entropy secret token
When the security scanner evaluates the file using Shannon entropy analysis
Then the token is flagged as a credential leak risk
And the security check exits with code 1
```

### Scenario 2: Respecting custom project allowlists and pragma annotations
```gherkin
Given a test fixture token annotated with "# pragma: allowlist secret"
When the security scanner runs in strict entropy mode
Then the annotated token is safely ignored
And the security check passes with exit code 0
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary input string, computed Shannon entropy is mathematically non-negative, finite, and bounded strictly by $\log_2(\text{len}(\text{alphabet}))$.
