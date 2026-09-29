# Explanation: Project Management as Code (PMaC)

Why version-lock project management in git instead of using external issue trackers like Jira or Linear?

---

## 1. The Specification Drift Problem

When requirements, user stories, and acceptance criteria live in external SaaS tools, they inevitably drift from the code repository. Branches are merged without updating ticket descriptions. Acceptance criteria change in discussions without updating tickets. Coding agents lack access to true project context and rely on outdated or truncated instructions.

---

## 2. Git as the Single Source of Truth

With Project Management as Code (PMaC):
- Requirements and source code share the exact same commit hash.
- Changes to user stories or tasks are reviewed via standard pull requests.
- Autonomous coding agents have instant, offline access to full project context directly in the workspace.
- There are zero external API dependencies or synchronization bottlenecks.
