# Tutorial 02: Product Manager & Domain Expert Onboarding to PMaC

Welcome to SpecOps! This tutorial guides product managers, business analysts, and domain experts through Project Management as Code (PMaC) using business-friendly terms and browser-based workflows—with zero terminal commands required.

---

## 1. What is Project Management as Code (PMaC)?

In traditional software development, product requirements live in wikis or ticketing systems, while code lives in git repositories. Over time, requirements and code inevitably drift apart, leading to missed expectations, out-of-date documentation, and frustrating sprint reviews.

**Project Management as Code (PMaC)** solves this by storing specifications, user personas, user stories, and acceptance criteria directly inside the version-controlled project repository alongside the code.

### Core Principles for Product Managers
- **Single Source of Truth**: Requirements and code evolve atomically in the same change history.
- **Traceability**: Every feature connects back to a persona, a product requirement document (PRD), and executable user stories.
- **Falsifiable Acceptance**: Requirements are written as concrete, testable outcomes rather than ambiguous wish lists.
- **Audit-Ready Evidence**: Test results and user acceptance verification produce tamper-evident proof of delivery.

---

## 2. Navigating and Reading PRDs

Product Requirement Documents (PRDs) define the *why* and *what* of a customer-facing capability. In SpecOps, PRDs progress through a clear four-stage lifecycle:

| Stage | Meaning | Product Manager Action |
|---|---|---|
| **Idea** | Initial proposal or customer problem hypothesis | Author problem statement and initial target outcomes |
| **Shaped** | Refined scope with bounded contexts and personas | Define user journeys, architectural seams, and constraints |
| **Accepted** | Formal commitment ready for active delivery | Decompose into vertical slices and executable Gherkin stories |
| **Shipped** | Verified live in production | Review acceptance criteria and sign off on UAT receipts |

### Anatomy of a PMaC PRD
Each PRD is written in structured Markdown and contains:
1. **Target Persona**: Who we are solving this problem for (e.g., Alex the Architect, Taylor the PM).
2. **Problem Statement**: The customer pain point, expressed clearly without technical jargon.
3. **Checkable Outcomes**: A bulleted list of verifiable results that prove the problem is solved.

To explore existing PRDs, open the SpecOps Web Visualizer and navigate to the **PRDs & Features** tab.

---

## 3. Authoring Executable Gherkin Stories

Rather than writing vague acceptance bullet points, PMaC uses **Gherkin syntax** (`Given`, `When`, `Then`) to write executable user stories. These stories describe observable customer behavior through the system's "frontdoor":

```gherkin
Scenario: Self-service notification preference update
  Given a customer is logged into their account settings portal
  When the customer toggles off "Weekly marketing digest" and clicks "Save"
  Then the preference update is confirmed with a green checkmark
  And marketing emails are silenced for that customer account.
```

### Frontdoor vs. Backdoor Testing
- **Frontdoors (Good)**: Verifying actions that a real user or public API client can perform and observe.
- **Backdoors (Avoid)**: Peeking directly into private database tables or internal function variables.

Writing frontdoor Gherkin ensures that your acceptance criteria reflect real user journeys and can be automatically validated on every update.

---

## 4. Conducting Living UAT & Verification Sign-Off

In SpecOps, User Acceptance Testing (UAT) is continuous rather than a stressful manual phase at the end of a milestone.

### The UAT Verification Workflow
1. **Inspect Status in the Visualizer**: Open the **Matrix** or **UAT Readiness** view to see real-time passing/failing status for all scenarios.
2. **Review Verifiable Evidence**: Click on any story card to open the detail drawer, inspect the exact automated test evidence, and review git commit provenance.
3. **Export UAT Verification Receipts**: Click **Export UAT Verification Receipt** to download a cryptographically hashed, timestamped Markdown document certifying that all acceptance criteria passed blackbox verification.
4. **Sign-Off**: Add your digital or physical signature to the dual sign-off block for SOC2/ISO compliance and release sign-off.

---

## 5. Hands-On Exercise: Create Your First Idea PRD

You can practice authoring your first specification directly in the browser using the SpecOps Visualizer **Discovery Sandbox**:

1. Open the SpecOps Visualizer in your web browser.
2. Click the **Discovery Sandbox** tab in the navigation bar.
3. Review the guided exercise: **Create your first Idea PRD**.
4. In the editor, compose your Idea PRD with valid frontmatter, target persona, problem statement, and checkable outcomes.
5. Click **Verify PRD Markdown**.
6. When your specification structure is valid, the sandbox awards your confirmation badge:  
   **"PMaC Ready: Your first specification is git-locked!"**

---

## 6. Next Steps & Collaboration

Congratulations! You are now equipped to participate in PMaC workflows. As a product manager, you can now:
- Review pull requests on GitHub or GitLab to verify that stories and PRDs match customer intent.
- Use the **Lead Console** and **Gantt & Timeline** views to track delivery velocity.
- Collaborate with engineering peers through living specifications locked in git.
