from __future__ import annotations

import json
from pathlib import Path
from string import Template

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from uvicorn import run

from mantrai.core.mantra import load_mantra
from mantrai.core.schema import Mantra, Principle

app = FastAPI(title="MantrAI GUI")

HTML_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head>
    <title>MantrAI</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #0d1117; color: #c9d1d9; }
        h1 { color: #58a6ff; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid #30363d; }
        .tab { padding: 10px 20px; cursor: pointer; background: #21262d; border: none; color: #8b949e; border-radius: 6px 6px 0 0; }
        .tab.active { background: #238636; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .principle { display: flex; align-items: flex-start; gap: 10px; margin: 8px 0; padding: 10px; background: #161b22; border-radius: 6px; }
        .principle input[type=checkbox] { margin-top: 4px; width: 18px; height: 18px; accent-color: #238636; }
        .principle label { flex: 1; cursor: pointer; }
        .actions { margin-top: 20px; display: flex; gap: 10px; }
        button { padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
        .save { background: #238636; color: white; }
        .save:hover { background: #2ea043; }
        .add { background: #1f6feb; color: white; }
        .add:hover { background: #388bfd; }
        .status { margin-top: 15px; padding: 10px; border-radius: 6px; display: none; }
        .status.success { background: #23863633; color: #3fb950; display: block; }
        .status.error { background: #da363333; color: #f85149; display: block; }
        input[type=text] { flex: 1; padding: 8px; background: #0d1117; border: 1px solid #30363d; color: #c9d1d9; border-radius: 6px; }
        .add-row { display: flex; gap: 10px; margin-top: 15px; }
    </style>
</head>
<body>
    <h1>MantrAI</h1>
    <p>Edit your mantra categories. Checked = active. Unchecked = removed on save.</p>

    <div class="tabs">
        <button class="tab active" onclick="switchTab('global')">Global</button>
        <button class="tab" onclick="switchTab('project')">Project</button>
        <button class="tab" onclick="switchTab('folder')">Folder</button>
    </div>

    <form id="mantra-form">
        <div id="global" class="tab-content active">
            <h3>Global Principles</h3>
            <div id="global-list"></div>
            <div class="add-row">
                <input type="text" id="global-new" placeholder="Add new global principle...">
                <button type="button" class="add" onclick="addPrinciple('global')">Add</button>
            </div>
        </div>

        <div id="project" class="tab-content">
            <h3>Project Principles</h3>
            <div id="project-list"></div>
            <div class="add-row">
                <input type="text" id="project-new" placeholder="Add new project principle...">
                <button type="button" class="add" onclick="addPrinciple('project')">Add</button>
            </div>
        </div>

        <div id="folder" class="tab-content">
            <h3>Folder Principles</h3>
            <div id="folder-list"></div>
            <div class="add-row">
                <input type="text" id="folder-new" placeholder="Add new folder principle...">
                <button type="button" class="add" onclick="addPrinciple('folder')">Add</button>
            </div>
        </div>

        <div class="actions">
            <button type="button" class="save" onclick="saveMantra()">Save Mantra</button>
        </div>
    </form>

    <div id="status" class="status"></div>

    <script>
        const defaults = $defaults_json;
        const existing = $existing_json;
        let principles = { global: [], project: [], folder: [] };

        function init() {
            for (const cat of ['global', 'project', 'folder']) {
                const existingTexts = new Set((existing[cat] || []).map(p => p.text));
                principles[cat] = (defaults[cat] || []).map(p => ({
                    text: p.text,
                    checked: existingTexts.has(p.text)
                }));
                for (const ep of (existing[cat] || [])) {
                    if (!defaults[cat].some(dp => dp.text === ep.text)) {
                        principles[cat].push({ text: ep.text, checked: true });
                    }
                }
                render(cat);
            }
        }

        function render(cat) {
            const container = document.getElementById(cat + '-list');
            container.innerHTML = principles[cat].map((p, i) => `
                <div class="principle">
                    <input type="checkbox" id="${cat}_${i}" ${p.checked ? 'checked' : ''}
                        onchange="principles['${cat}'][${i}].checked = this.checked">
                    <label for="${cat}_${i}">${escapeHtml(p.text)}</label>
                </div>
            `).join('');
        }

        function addPrinciple(cat) {
            const input = document.getElementById(cat + '-new');
            const text = input.value.trim();
            if (!text) return;
            principles[cat].push({ text, checked: true });
            input.value = '';
            render(cat);
        }

        function switchTab(cat) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(cat).classList.add('active');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function saveMantra() {
            const data = {};
            for (const cat of ['global', 'project', 'folder']) {
                data[cat] = principles[cat].filter(p => p.checked).map(p => p.text);
            }
            const res = await fetch('/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await res.json();
            const status = document.getElementById('status');
            status.textContent = result.message;
            status.className = 'status ' + (result.success ? 'success' : 'error');
        }

        init();
    </script>
</body>
</html>
""")


def _get_principles_by_category(mantra: Mantra) -> dict:
    result = {"global": [], "project": [], "folder": []}
    for p in mantra.principles:
        cat = p.category or "global"
        result.setdefault(cat, []).append({"text": p.text, "category": cat})
    return result


@app.get("/", response_class=HTMLResponse)
def index():
    from mantrai.core.mantra import get_default_mantra
    defaults = get_default_mantra()
    defaults_by_cat = _get_principles_by_category(defaults)

    try:
        existing = load_mantra()
    except Exception:
        existing = Mantra(level="strict", principles=[])
    existing_by_cat = _get_principles_by_category(existing)

    html = HTML_TEMPLATE.substitute(
        defaults_json=json.dumps(defaults_by_cat),
        existing_json=json.dumps(existing_by_cat),
    )
    return HTMLResponse(content=html)


@app.post("/save")
def save(data: dict):
    try:
        all_principles = []
        for cat in ("global", "project", "folder"):
            for text in data.get(cat, []):
                all_principles.append(Principle(text=text, category=cat))

        if not all_principles:
            return {"success": False, "message": "At least one principle required."}

        from mantrai.core.config import load_config
        from mantrai.core.mantra import _find_project_root
        cfg = load_config()
        existing = load_mantra()

        new_mantra = Mantra(
            level=existing.level,
            author=cfg.get("author") or existing.author,
            token=existing.token,
            principles=all_principles,
        )

        root = _find_project_root(Path.cwd()) or Path.cwd()
        target = root / ".mantrai.md"
        target.write_text(new_mantra.to_markdown(), encoding="utf-8")
        return {"success": True, "message": f"Saved {len(all_principles)} principle(s) to {target}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def start_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    run(app, host=host, port=port)
