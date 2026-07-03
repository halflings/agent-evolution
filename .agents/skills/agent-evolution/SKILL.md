---
name: agent-evolution
description: |
  Analyzes past conversation histories from Claude Code and Antigravity logs for any workspace,
  dynamically identifies failure patterns/inefficiencies, and generates custom AGENTS.md rules
  and custom skills to improve agent behavior.
---

# Agent Evolution Skill

Use this skill when you need to analyze past conversation trajectories (from both Claude Code and Antigravity) to diagnose agent failures, extract successful patterns, and generate system rules/custom skills.

## 🚀 Execution Workflow

When this skill is triggered, you must perform the following actions:

### Step 1. Compile History Log Database
Locate and run the python extraction script to compile all raw session files into a unified JSON database.
> [!NOTE]
> The extraction script has **zero external dependencies** and runs on any standard Python 3 interpreter.

```bash
python3 extract_history.py
```
This produces:
*   Unified database: `extracted/extracted_conversations.json`
*   Human-readable log: `extracted/extracted_conversations.md`

### Step 2. Read and Analyze Trajectories with LLM
Open and read `extracted/extracted_conversations.json`. Perform a deep LLM analysis of the turns to identify critical patterns (Context Failures, Tool Failures, Command Loops, or Interruptions).
Avoid using generic substring-matching heuristics (e.g. flagging "missing" or interrupt events blindly). Instead, review the full context of the transcripts to extract genuine issues.

### Step 3. Generate and Stage Recommendations in JSON
Synthesize your findings and write the recommended improvements directly into `extracted/agent_evolution_plan.json`. This JSON should have the following structure:
```json
{
  "failures": [
    {
      "type": "File Path / Context Missing",
      "session": "Refactor agent.py",
      "project": "/Users/username/workspace/target-project",
      "description": "Observation details..."
    }
  ],
  "rules": [
    {
      "name": "Verify File Locations Proactively",
      "description": "Rule details..."
    }
  ],
  "skills": [
    {
      "name": "refactor-modular",
      "description": "Skill details...",
      "instructions": "Step-by-step instructions..."
    }
  ],
  "prompts": [
    {
      "project": "/Users/username/workspace/target-project",
      "prompt": "Prompt string..."
    }
  ]
}
```

### Step 4. Run the Evolution Sync Script
Once the `extracted/agent_evolution_plan.json` file has been written, run the agent evolution script:
```bash
python3 agent_evolution.py
```
This script will:
*   Generate the formatted markdown plan at `extracted/agent_evolution_plan.md`.
*   Directly apply the rules to your global user rules (appending to `~/.gemini/GEMINI.md` and `~/.clauderc`).
*   Launch the interactive Web Cockpit dev server (Uvicorn backend on port `8080` + Next.js frontend on port `3000` or `3001` if occupied).

### Step 5. Report Findings and Direct User to Cockpit
Present the user with a summary of the analyzed sessions, the rules applied globally, and direct the user to load the Web Cockpit UI at `http://localhost:3000` (or `http://localhost:3001` if port 3000 is occupied) to visually explore trajectories and rules.
