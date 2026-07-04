```
========================================================================
    ___                         __   ______               __      __  _ 
   /   |  ____ _ ___   ____  _ / /_ / ____/ _  __ ____   / /__  _/ /_(_)____   ____ 
  / /| | / __ `// _ \ / __ \(_/ __// __/   | |/_// __ \ / / / / / __/ // __ \ / __ \
 / ___ |/ /_/ //  __// / / // / /_ / /___ _>  < / /_/ // / /_/ / /_ / // /_/ // / / /
/_/  |_|\__, / \___//_/ /_//_/\__//_____//_/|_| \____//_/\__,_/\__//_/ \____//_/ /_/ 
       /____/                                                                       
========================================================================
```

## 🚀 Get Started

To run this agent skill, copy and paste the following prompt into your coding agent:

> Please use your terminal tools to clone the `agent-evolution` skill from `https://github.com/halflings/agent-evolution.git` into the standard cross-agent directory `.agents/skills/agent-evolution/`. 
> 
> Once downloaded, read its manifest at `.agents/skills/agent-evolution/SKILL.md` to understand its context and requirements. Finally, execute the skill according to its instructions to analyze my past logs and update my workspace rules (`AGENTS.md`).

---

## 🛠️ Technical Details & Setup

### Prerequisites
* **Python 3.13+**, **NodeJS**, and **uv** (fast Python package installer).

### Local Workspace Cockpit
To visually inspect developer trajectories, view thinking processes, and stage rule configurations, run the unified dev server launcher:
```bash
uv run python run_app.py
```
This runs:
* **Frontend Dashboard**: `http://localhost:3000` (Next.js + Tailwind CSS)
* **Backend API**: `http://localhost:8080/docs` (FastAPI)

### Custom Agent Skill
The workspace is formatted as a reusable Custom Skill:
* **Manifest**: `.agents/skills/agent-evolution/SKILL.md`
* **Behavior**:
  1. Scrapes raw logs (Claude & Antigravity), **redacting secrets**, into per-session chunk files plus a `signals.json` index of attention markers (interruptions, tool errors, repeated commands, edit/revert loops).
  2. **Reads every trace in full** — fanning out with read-only subagents (one per session/chunk) or iterating — guided by a subtle-issue rubric, instead of keyword sampling.
  3. Distills **general, transferable rules** (generalization filter, cited evidence, confidence, de-duplication), routing stack-agnostic behavior to your global `~/AGENTS.md` and project-specific facts to `<project>/AGENTS.md`.
  4. Renders the plan with **no side effects**. The web dashboard is **opt-in** (`python3 agent_evolution.py --serve`) and binds to `127.0.0.1` only (it serves raw transcripts).

### Running Tests
Verify parsers, scrapers, and API endpoints:
```bash
uv run python -m pytest
```
