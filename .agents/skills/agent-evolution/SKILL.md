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

### Step 1. Run the Extraction Script
Locate and run the python extraction script to compile all raw session files into a unified JSON database.
> [!NOTE]
> The extraction script has **zero external dependencies** and runs on any standard Python 3 interpreter.

```bash
python3 extract_history.py
```
This produces:
*   Unified database: `extracted/extracted_conversations.json`
*   Human-readable log: `extracted/extracted_conversations.md`

### Step 2. Read and Analyze the Trajectories
Open and read `extracted/extracted_conversations.json`. Perform a deep LLM analysis of the turns to identify the following patterns:
1.  **Context Failures**: Did the assistant fail to find files, require manual path guidance, or attempt to edit files that don't exist?
2.  **Tool Failures**: Did tool calls fail with errors, exit codes, or produce unexpected outputs?
3.  **Command Redundancy**: Did the assistant run repetitive terminal commands or get stuck in a diagnostic loop?
4.  **Interruptions**: Where and why did the user interrupt the assistant?

### Step 3. Generate and Stage Recommendations
For each identified pattern, formulate a concrete recommendation. Write these recommendations directly to the central analysis plan:
*   **Plan MD**: Write rules and custom skills into the central plan at `extracted/agent_evolution_plan.md`.

### Step 4. Report Findings
Present the user with a summary of:
*   The sessions analyzed.
*   A list of identified failure/success patterns.
*   The recommended system rules and custom skills that can be imported or staged.
