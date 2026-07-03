import json
from pathlib import Path
import sys
import subprocess

def analyze_conversations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        sessions = json.load(f)
        
    rules = []
    skills = []
    prompts = []
    failures = []
    
    for sess in sessions:
        title = sess.get("title", "") or "Unnamed Session"
        project = sess.get("project_path", "")
        turns = sess.get("turns", [])
        
        # Analyze failures/issues
        # 1. Missing files / path confusion
        has_file_not_found = False
        has_interrupted = False
        for turn in turns:
            if turn.get("role") == "assistant":
                content = turn.get("content", "")
                if "can't find" in content.lower() or "missing" in content.lower():
                    has_file_not_found = True
            elif turn.get("role") == "user":
                content = turn.get("content", "")
                if "[Request interrupted by user]" in content:
                    has_interrupted = True
                    
        if has_file_not_found:
            failures.append({
                "session": title,
                "project": project,
                "type": "File Path / Context Missing",
                "description": "Assistant could not find the target file (e.g., agent.py) immediately, requiring manual guidance or search."
            })
        if has_interrupted:
            failures.append({
                "session": title,
                "project": project,
                "type": "User Interruption",
                "description": "The user had to interrupt a running command or generation."
            })
            
        # Extract prompt patterns
        for turn in turns:
            if turn.get("role") == "user" and turn.get("type") == "prompt":
                content = turn.get("content", "").strip()
                if len(content) > 10 and not content.startswith("/"):
                    prompts.append({
                        "session": title,
                        "project": project,
                        "prompt": content
                    })

    # Synthesize Rules
    # Rule 1: Always verify file paths using find/grep before declaring a file missing
    rules.append({
        "name": "Verify File Locations Proactively",
        "description": "Before stating that a file (like `agent.py`) is missing, search the entire workspace using glob patterns or grep search. Files are often nested in subdirectory folders (e.g., `backend/agent.py`)."
    })
    
    # Rule 2: Keep code modular and write standalone testable units
    rules.append({
        "name": "Modular and Standalone Testing",
        "description": "When refactoring code (e.g., in `agent.py`), factor out self-contained logic (like trajectory formatting, score calculation, or API payload building) into pure helper functions. Create corresponding unit tests next to them immediately."
    })
    
    # Rule 3: Use uv and pytest
    rules.append({
        "name": "Use uv and pytest",
        "description": "Always use `uv add` for package management and `pytest` for running unit tests. Place tests next to the files they test."
    })
    
    # Synthesize Skills (Custom instructions/actions)
    skills.append({
        "name": "refactor-modular",
        "description": "Refactor a target file to extract self-contained logic into standalone functions and add unit tests.",
        "instructions": (
            "1. Read the target file completely.\n"
            "2. Identify functions or logic blocks that do not depend on class state or external I/O (pure functions).\n"
            "3. Extract them into clean, documented functions.\n"
            "4. Create a test file named `test_<filename>.py` in the same directory.\n"
            "5. Write comprehensive tests using pytest, covering edge cases.\n"
            "6. Run the tests using `uv run pytest` and fix any failures."
        )
    })
    
    return failures, rules, skills, prompts

def update_global_configs(rules):
    # 1. Update Gemini config (~/.gemini/GEMINI.md)
    gemini_md_path = Path.home() / ".gemini" / "GEMINI.md"
    try:
        gemini_md_path.parent.mkdir(parents=True, exist_ok=True)
        existing_content = ""
        if gemini_md_path.exists():
            existing_content = gemini_md_path.read_text(encoding="utf-8")
            
        new_rules_text = ""
        for rule in rules:
            rule_header = f"## {rule['name']}"
            if rule_header not in existing_content:
                new_rules_text += f"\n{rule_header}\n{rule['description']}\n"
                
        if new_rules_text:
            with open(gemini_md_path, "a", encoding="utf-8") as f:
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")
                f.write("\n# Agent Evolution Rules\n" + new_rules_text)
            print(f"Added new rules to Gemini config: {gemini_md_path}")
    except Exception as e:
        print(f"Failed to update Gemini config: {e}")
        
    # 2. Update Claude config (~/.clauderc)
    claude_rc_path = Path.home() / ".clauderc"
    try:
        existing_rc_content = ""
        if claude_rc_path.exists():
            existing_rc_content = claude_rc_path.read_text(encoding="utf-8")
            
        new_rc_text = ""
        for rule in rules:
            rule_name = rule['name']
            if rule_name not in existing_rc_content:
                new_rc_text += f"\n# {rule_name}\n{rule['description']}\n"
                
        if new_rc_text:
            with open(claude_rc_path, "a", encoding="utf-8") as f:
                if existing_rc_content and not existing_rc_content.endswith("\n"):
                    f.write("\n")
                if not existing_rc_content:
                    f.write("# Claude Code Global Custom Rules\n")
                else:
                    f.write("\n# Agent Evolution Rules\n")
                f.write(new_rc_text)
            print(f"Added new rules to Claude config: {claude_rc_path}")
    except Exception as e:
        print(f"Failed to update Claude config: {e}")

def main():
    import socket
    
    json_path = Path(__file__).resolve().parent / "extracted" / "extracted_conversations.json"
    if not json_path.exists():
        print(f"Extraction file not found at {json_path}. Please run extract_history.py first.")
        return
        
    failures, rules, skills, prompts = analyze_conversations(json_path)
    
    output_path = Path(__file__).resolve().parent / "extracted" / "agent_evolution_plan.md"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Agent Evolution Analysis & Plan\n\n")
        
        f.write("## 1. Identified Failure & Inefficiency Patterns\n")
        if failures:
            for fail in failures:
                f.write(f"### Pattern: {fail['type']}\n")
                f.write(f"- **Session:** {fail['session']}\n")
                f.write(f"- **Project:** `{fail['project']}`\n")
                f.write(f"- **Observation:** {fail['description']}\n\n")
        else:
            f.write("No major failure patterns identified directly from logs.\n\n")
            
        f.write("## 2. Recommended Rules for AGENTS.md\n")
        f.write("Add the following rules to your global or project-level `AGENTS.md` file:\n\n")
        for rule in rules:
            f.write(f"### {rule['name']}\n")
            f.write(f"{rule['description']}\n\n")
            
        f.write("## 3. Recommended Custom Skills\n")
        f.write("You can implement these custom skills under `.agents/skills/` in your workspaces:\n\n")
        for skill in skills:
            f.write(f"### Skill: `{skill['name']}`\n")
            f.write(f"**Description:** {skill['description']}\n\n")
            f.write("**Instructions:**\n")
            f.write(f"{skill['instructions']}\n\n")
            
        f.write("## 4. Past Successful Prompts for Reference\n")
        for p in prompts:
            f.write(f"- **[{p['project']}]** \"{p['prompt']}\"\n")
            
    print(f"Saved agent evolution plan to {output_path}")
    
    # Copy rules to global configs
    update_global_configs(rules)
    
    # Check if cockpit is already running on port 3000
    cockpit_running = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', 3000)) == 0:
                cockpit_running = True
    except Exception:
        pass
        
    if cockpit_running:
        print("\n🚀 Agent Evolution Web Cockpit is already running on http://localhost:3000")
        print("👉 Load http://localhost:3000 to view your interactive trajectories and stage rules/skills!")
    else:
        print("\n🚀 Starting Agent Evolution Web Cockpit in the background...")
        try:
            run_app_path = Path(__file__).resolve().parent / "run_app.py"
            log_file = Path(__file__).resolve().parent / "extracted" / "cockpit.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a") as f:
                subprocess.Popen([sys.executable, str(run_app_path)], stdout=f, stderr=f, start_new_session=True)
            print("👉 Web Cockpit started successfully!")
            print("👉 Open http://localhost:3000 to view your interactive trajectories and stage rules/skills!")
        except Exception as e:
            print(f"Failed to start Web Cockpit in the background: {e}")

if __name__ == "__main__":
    main()
