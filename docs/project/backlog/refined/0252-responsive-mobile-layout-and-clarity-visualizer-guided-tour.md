---
id: '0252'
title: Mobile Responsive Layout and Background Clarity for Visualizer Guided Tour
status: Refined
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
governing_prds:
- PRD-0005
governing_stories:
- US-0107
- US-0129
target_bc: visualizer
persona: Taylor
---

# TASK-0252: Mobile Responsive Layout and Background Clarity for Visualizer Guided Tour

## Summary
Resolve critical usability issues on mobile viewports within the living visualizer's guided tour and welcome modal:
1. Eliminate the `backdrop-filter: blur(...)` rule on `.tour-overlay`, ensuring visualizer tabs, navigation, and graph controls behind the tour modal remain sharp and clearly visible rather than obfuscated.
2. Prevent document and layout viewport blowout (`docScrollWidth > 1600px`) on narrow screens by applying responsive wrapping, horizontal overflow constraints, and mobile styling across `header`, `stats-bar`, `search-box`, and navigation bars.
3. Fix modal containment so the tour modal and welcome modal render cleanly within the visible mobile viewport without requiring users to zoom out.
4. Correct unclosed modal wrapper tags in `template.py` to ensure proper DOM encapsulation.

## Problem Statement & Context
Stakeholders attempting to view the living visualizer on mobile devices or narrow browser viewports report that:
- The guided tour modal renders far off-screen due to the visualizer header expanding the document width beyond 1600px. Users are forced to pinch and zoom out to locate the modal.
- The guided tour overlay applies `backdrop-filter: blur(4px)` with an opaque scrim, completely blurring and darkening the very interface elements the tour is guiding them through.
- Button text in the modal footer overflows or clips on small screens.

## Detailed Objectives & Remediation Plan
1. **Remove Background Blur**:
   - In `src/spec_ops/visualizer/tour_script.py`, remove `backdrop-filter: blur(4px)` from `.tour-overlay`.
   - Update overlay background to a subtle transparent scrim (`rgba(15, 23, 42, 0.45)`), keeping target elements crisp and legible.
2. **Mobile Viewport & Layout Containment**:
   - In `src/spec_ops/visualizer/styles.py`, add `max-width: 100vw; overflow-x: hidden;` to `html` and `body`.
   - Implement `@media (max-width: 768px)` styles for `header`, `.header-left`, `.header-center`, `.stats-bar`, and `.nav-tabs-bar` to wrap and scroll within screen bounds rather than expanding document width.
3. **Responsive Modal Layout**:
   - In `src/spec_ops/visualizer/tour_script.py`, ensure `.tour-overlay` and `.tour-modal` have responsive sizing (`max-width: 520px; width: 92%; max-height: 85vh; overflow-y: auto;`).
   - Add `@media (max-width: 768px)` overrides for `.tour-modal` and `.tour-footer` with `flex-wrap: wrap` and touch-friendly paddings.
   - Update `applyTourHighlight` in `TOUR_JS` to scroll target elements into view on small screens.
4. **HTML DOM Integrity**:
   - In `src/spec_ops/visualizer/template.py`, add missing closing tags for `tour-modal` and `tour-overlay` before `drift-audit-modal`.
5. **Quality & Invariants**:
   - Keep `styles.py` and `tour_script.py` strictly below 400 lines (ADR-0002).
   - Add blackbox frontdoor tests verifying absence of blur, proper tag closure, and responsive dimensions.

## Definition of Done
1. Zero `backdrop-filter: blur` in `.tour-overlay`.
2. Document scroll width on <=768px viewports does not exceed viewport width (`docScrollWidth <= windowWidth`).
3. Guided tour and welcome modals remain completely inside visible viewport bounding boxes on mobile screens.
4. `uv run spec-ops health` passes with 0 file limit violations and 0 warnings.
5. All automated tests pass with 100% pass rate.
