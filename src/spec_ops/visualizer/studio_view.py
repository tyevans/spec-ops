"""Zero-dependency browser-native PRD Studio and Story Assistant view generator."""

from __future__ import annotations


def render_studio_html() -> str:
    """Renders standalone vanilla HTML/JS/CSS PRD Studio interface with zero CDN dependencies."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SpecOps PRD Studio</title>
  <style>
    :root {
      --bg: #0f172a; --surface: #1e293b; --border: #334155; --text: #f8fafc;
      --muted: #94a3b8; --accent: #38bdf8; --accent-hover: #0ea5e9;
      --danger: #ef4444; --danger-bg: #450a0a; --success: #22c55e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
    header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }
    .brand { font-size: 1.1rem; font-weight: 700; color: var(--accent); }
    .nav-tabs { display: flex; gap: 8px; }
    .tab-btn { background: transparent; border: 1px solid var(--border); color: var(--muted); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
    .tab-btn.active { background: var(--accent); color: #000; border-color: var(--accent); font-weight: 600; }
    .container { flex: 1; display: flex; overflow: hidden; }
    .pane { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
    .pane-left { border-right: 1px solid var(--border); }
    .form-group { display: flex; flex-direction: column; gap: 6px; }
    label { font-size: 0.85rem; font-weight: 600; color: var(--muted); }
    input, select, textarea { background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 10px 12px; border-radius: 6px; font-size: 0.9rem; outline: none; }
    input:focus, select:focus, textarea:focus { border-color: var(--accent); }
    textarea { resize: vertical; min-height: 80px; font-family: inherit; }
    .btn-row { display: flex; gap: 10px; margin-top: 8px; }
    button.btn-primary { background: var(--accent); color: #000; border: none; padding: 10px 18px; border-radius: 6px; font-weight: 600; cursor: pointer; }
    button.btn-primary:hover { background: var(--accent-hover); }
    button.btn-secondary { background: var(--surface); color: var(--text); border: 1px solid var(--border); padding: 10px 18px; border-radius: 6px; font-weight: 600; cursor: pointer; }
    .alert { padding: 12px 16px; border-radius: 6px; font-size: 0.85rem; display: none; }
    .alert-danger { background: var(--danger-bg); border: 1px solid var(--danger); color: #fca5a5; }
    .alert-success { background: #064e3b; border: 1px solid var(--success); color: #86efac; }
    .preview-pane { background: #020617; border-radius: 8px; padding: 24px; flex: 1; border: 1px solid var(--border); overflow-y: auto; }
    .preview-pane h1 { font-size: 1.5rem; margin-bottom: 14px; border-bottom: 1px solid var(--border); padding-bottom: 6px; color: var(--accent); }
    .preview-pane h2 { font-size: 1.15rem; margin: 14px 0 6px; color: #e2e8f0; }
    .preview-pane p { margin-bottom: 10px; line-height: 1.5; color: #cbd5e1; font-size: 0.9rem; }
    .preview-pane ul { margin: 0 0 10px 20px; }
    .preview-pane li { margin-bottom: 4px; color: #cbd5e1; font-size: 0.9rem; }
    .autocomplete-list { background: var(--surface); border: 1px solid var(--accent); border-radius: 6px; max-height: 180px; overflow-y: auto; display: none; }
    .autocomplete-item { padding: 8px 12px; cursor: pointer; font-size: 0.85rem; border-bottom: 1px solid var(--border); }
    .autocomplete-item:hover { background: rgba(56, 189, 248, 0.15); color: var(--accent); }
    .badge { font-size: 0.75rem; background: var(--border); padding: 2px 6px; border-radius: 4px; margin-left: 8px; }
  </style>
</head>
<body>
  <header>
    <div class="brand">⚡ SpecOps PRD Studio</div>
    <div class="nav-tabs">
      <button class="tab-btn active" id="tabPrd" onclick="switchTab('prd')">PRDs & Features</button>
      <button class="tab-btn" id="tabStory" onclick="switchTab('story')">Story Studio</button>
      <button class="tab-btn" id="btnExportUat" onclick="exportUatMatrix()">Export UAT Matrix</button>
    </div>
  </header>

  <div class="container" id="prdView">
    <div class="pane pane-left">
      <h2 style="font-size: 1.1rem; color: var(--text);">Author PRD Draft</h2>
      <div id="validationAlert" class="alert alert-danger"></div>
      <div id="successAlert" class="alert alert-success"></div>

      <div class="form-group">
        <label for="prdTitle">PRD Title *</label>
        <input type="text" id="prdTitle" placeholder="Self-Service Customer Billing Portal" oninput="triggerAutoSave()">
      </div>

      <div class="form-group">
        <label for="prdPersona">Target Persona *</label>
        <select id="prdPersona" onchange="triggerAutoSave()">
          <option value="">-- Select Persona --</option>
          <option value="Alex">Alex (The Agentic Systems Architect)</option>
          <option value="Jordan">Jordan (The Full-Stack Engineer)</option>
          <option value="Morgan">Morgan (The Platform Engineer)</option>
          <option value="Riley">Riley (The QA Automation Engineer)</option>
          <option value="Taylor">Taylor (The Product Manager)</option>
          <option value="Sasha">Sasha (The Tech Lead)</option>
        </select>
      </div>

      <div class="form-group">
        <label for="prdComponent">Component</label>
        <input type="text" id="prdComponent" value="billing" oninput="triggerAutoSave()">
      </div>

      <div class="form-group">
        <label for="prdProblem">Problem Statement *</label>
        <textarea id="prdProblem" placeholder="Customers cannot update payment methods self-serve" oninput="triggerAutoSave()"></textarea>
      </div>

      <div class="form-group">
        <label for="prdOutcomes">Checkable Outcomes (1 per line) *</label>
        <textarea id="prdOutcomes" placeholder="User updates credit card via web dashboard&#10;Stripe webhook confirms card update with 200 OK" oninput="triggerAutoSave()"></textarea>
      </div>

      <div class="btn-row">
        <button class="btn-primary" onclick="saveDraft()">Save PRD Draft</button>
        <button class="btn-secondary" onclick="commitPrd()">Commit Specification</button>
      </div>
    </div>

    <div class="pane">
      <h2 style="font-size: 1.1rem; color: var(--muted);">Diataxis Live Preview (Split-Pane)</h2>
      <div class="preview-pane" id="markdownPreview">
        <p style="color: var(--muted);">Fill in fields to preview document...</p>
      </div>
    </div>
  </div>

  <div class="container" id="storyView" style="display: none;">
    <div class="pane pane-left">
      <h2 style="font-size: 1.1rem;">Story Studio & Gherkin Assistant</h2>
      <div id="storyBackdoorAlert" class="alert alert-danger"></div>
      <div id="storySuccessAlert" class="alert alert-success"></div>

      <div class="form-group">
        <label for="storyTitle">User Story Title *</label>
        <input type="text" id="storyTitle" placeholder="Low-Code Gherkin BDD Story Authoring Assistant" value="Low-Code Gherkin BDD Story Authoring Assistant">
      </div>

      <div class="form-group">
        <label for="storyPrd">Governing PRD</label>
        <input type="text" id="storyPrd" placeholder="PRD-0003" value="PRD-0003">
      </div>

      <div class="form-group">
        <label for="storyPersona">Target Persona</label>
        <select id="storyPersona">
          <option value="Taylor">Taylor (The Product Manager)</option>
          <option value="Alex">Alex (The Agentic Systems Architect)</option>
          <option value="Jordan">Jordan (The Full-Stack Engineer)</option>
          <option value="Morgan">Morgan (The Platform Engineer)</option>
          <option value="Riley">Riley (The QA Automation Engineer)</option>
          <option value="Sasha">Sasha (The Tech Lead)</option>
        </select>
      </div>

      <div class="form-group">
        <label for="scenarioInput">Gherkin Step Autocomplete</label>
        <input type="text" id="scenarioInput" placeholder="Given " oninput="onStepInput(this.value)">
        <div id="autocompleteDropdown" class="autocomplete-list"></div>
      </div>

      <div class="form-group">
        <label for="scenarioFull">Scenario Specification</label>
        <textarea id="scenarioFull" style="height: 140px;" placeholder="Scenario: User story scenario&#10;  Given a project initialized with SpecOps&#10;  When Taylor authors a story&#10;  Then it is saved cleanly"></textarea>
      </div>

      <div class="btn-row">
        <button class="btn-primary" onclick="acceptStory()">Accept User Story</button>
      </div>
    </div>

    <div class="pane">
      <h2 style="font-size: 1.1rem; color: var(--muted);">Registered Frontdoor Fixtures</h2>
      <div class="preview-pane" id="frontdoorList">
        <p style="color: var(--muted);">Loading established frontdoor fixtures...</p>
      </div>
    </div>
  </div>

  <script>
    let currentPrdFilePath = "";
    let currentDraftHash = null;
    let autoSaveTimer = null;
    let frontdoorSteps = [];

    function triggerAutoSave() {
      updatePreview();
      if (!currentPrdFilePath) return;
      clearTimeout(autoSaveTimer);
      autoSaveTimer = setTimeout(autoSaveDraft, 500);
    }

    async function autoSaveDraft() {
      if (!currentPrdFilePath) return;
      const title = document.getElementById("prdTitle").value || "Untitled PRD";
      const persona = document.getElementById("prdPersona").value || "Taylor";
      const component = document.getElementById("prdComponent").value || "core";
      const problem = document.getElementById("prdProblem").value || "";
      const outcomes = document.getElementById("prdOutcomes").value.split("\\n").filter(o => o.trim());
      const body = `---\\nid: PRD-DRAFT\\ntitle: ${title}\\nstatus: Idea\\ntarget_persona: ${persona}\\ncomponent: ${component}\\n---\\n\\n# PRD: ${title}\\n\\n## Problem Statement\\n${problem}\\n\\n## Checkable Outcomes\\n` + outcomes.map(o => `- ${o}`).join("\\n") + "\\n";

      try {
        const res = await fetch("/api/prd/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_path: currentPrdFilePath, content: body, expected_hash: currentDraftHash })
        });
        const data = await res.json();
        if (data.status === "saved") {
          currentDraftHash = data.revision_digest;
          const success = document.getElementById("successAlert");
          success.style.display = "block";
          success.innerText = "Draft auto-saved (" + data.revision_digest.slice(0, 8) + ")";
        } else if (data.status === "conflict") {
          const alert = document.getElementById("validationAlert");
          alert.style.display = "block";
          alert.innerText = data.message;
        }
      } catch (err) {
        console.error("Auto-save failed", err);
      }
    }

    function parseMarkdown(md) {
      if (!md) return "";
      let html = md
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/\\*\\*(.*?)\\*\\*/gim, '<strong>$1</strong>')
        .replace(/\\*(.*?)\\*/gim, '<em>$1</em>')
        .replace(/^\\- (.*$)/gim, '<li>$1</li>');
      html = html.replace(/(<li>.*<\\/li>)/s, '<ul>$1</ul>');
      html = html.replace(/^(?!<[h|u|l])(.*$)/gim, '<p>$1</p>');
      return html;
    }

    function updatePreview() {
      const title = document.getElementById("prdTitle").value || "Untitled PRD";
      const persona = document.getElementById("prdPersona").value || "[Persona]";
      const component = document.getElementById("prdComponent").value || "core";
      const problem = document.getElementById("prdProblem").value || "";
      const outcomes = document.getElementById("prdOutcomes").value.split("\\n").filter(o => o.trim());

      let md = `# PRD: ${title}\\n\\n**Persona**: ${persona} | **Component**: ${component}\\n\\n## Problem Statement\\n${problem}\\n\\n## Checkable Outcomes\\n`;
      outcomes.forEach(o => { md += `- ${o}\\n`; });
      document.getElementById("markdownPreview").innerHTML = parseMarkdown(md);
    }

    function switchTab(tab) {
      const isPrd = tab === 'prd';
      document.getElementById("prdView").style.display = isPrd ? "flex" : "none";
      document.getElementById("storyView").style.display = isPrd ? "none" : "flex";
      document.getElementById("tabPrd").className = isPrd ? "tab-btn active" : "tab-btn";
      document.getElementById("tabStory").className = isPrd ? "tab-btn" : "tab-btn active";
      if (!isPrd) loadFrontdoorSteps();
    }

    async function loadFrontdoorSteps() {
      try {
        const res = await fetch("/api/steps/frontdoor");
        const steps = await res.json();
        frontdoorSteps = steps;
        let html = "<ul>";
        steps.forEach(s => {
          html += `<li><strong>${s.pattern}</strong> <span class="badge">${s.domain}</span></li>`;
        });
        html += "</ul>";
        document.getElementById("frontdoorList").innerHTML = html;
      } catch (err) {
        console.error(err);
      }
    }

    function onStepInput(val) {
      const alert = document.getElementById("storyBackdoorAlert");
      const dropdown = document.getElementById("autocompleteDropdown");
      const lower = val.toLowerCase();
      if (lower.includes("database table") || lower.includes("has record") || lower.includes("mock") || lower.includes("direct state")) {
        alert.style.display = "block";
        alert.innerText = "Backdoor violation (ADR-0003): Tests must exercise public frontdoors. Direct state manipulation is prohibited.";
      } else {
        alert.style.display = "none";
      }

      if (val.trim().length > 1) {
        const matches = frontdoorSteps.filter(s => s.pattern.toLowerCase().includes(val.toLowerCase()));
        if (matches.length > 0) {
          dropdown.style.display = "block";
          dropdown.innerHTML = matches.map(m => `<div class="autocomplete-item" onclick="selectStep('${m.pattern}')">${m.pattern} <span class="badge">${m.domain}</span></div>`).join("");
          return;
        }
      }
      dropdown.style.display = "none";
    }

    function selectStep(step) {
      document.getElementById("scenarioInput").value = step;
      document.getElementById("autocompleteDropdown").style.display = "none";
      const full = document.getElementById("scenarioFull");
      full.value += (full.value ? "\\n" : "") + step;
    }

    async function saveDraft() {
      const alert = document.getElementById("validationAlert");
      const success = document.getElementById("successAlert");
      alert.style.display = "none";
      success.style.display = "none";

      const title = document.getElementById("prdTitle").value;
      const persona = document.getElementById("prdPersona").value;
      const component = document.getElementById("prdComponent").value;
      const statement = document.getElementById("prdProblem").value;
      const outcomes = document.getElementById("prdOutcomes").value.split("\\n").filter(o => o.trim());

      const res = await fetch("/api/prd/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, persona, component, problem_statement: statement, outcomes })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        alert.style.display = "block";
        alert.innerText = data.message || "Validation Error (ADR-0001)";
      } else {
        success.style.display = "block";
        success.innerText = data.message;
        currentPrdFilePath = data.file_path;
        currentDraftHash = data.revision_digest || null;
      }
    }

    async function commitPrd() {
      if (!currentPrdFilePath) await saveDraft();
      if (!currentPrdFilePath) return;
      const title = document.getElementById("prdTitle").value;
      const res = await fetch("/api/prd/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: currentPrdFilePath, commit_message: "spec(prd): update " + title })
      });
      const data = await res.json();
      const success = document.getElementById("successAlert");
      if (data.success) {
        success.style.display = "block";
        success.innerText = data.message;
      }
    }

    async function acceptStory() {
      const alert = document.getElementById("storyBackdoorAlert");
      const success = document.getElementById("storySuccessAlert");
      alert.style.display = "none";
      success.style.display = "none";

      const title = document.getElementById("storyTitle").value;
      const persona = document.getElementById("storyPersona").value;
      const prd = document.getElementById("storyPrd").value;
      const scenario = document.getElementById("scenarioFull").value || document.getElementById("scenarioInput").value;

      const res = await fetch("/api/story/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, persona, governing_prd: prd, scenario })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        alert.style.display = "block";
        alert.innerText = data.message || "Validation Error";
      } else {
        success.style.display = "block";
        success.innerText = data.message;
      }
    }

    function exportUatMatrix() {
      const prd = (document.getElementById("storyPrd") && document.getElementById("storyPrd").value) || "PRD-0003";
      window.open("/api/uat/export?prd=" + encodeURIComponent(prd), "_blank");
    }

    loadFrontdoorSteps();
    updatePreview();
  </script>
</body>
</html>
"""
