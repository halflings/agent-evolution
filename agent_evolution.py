import json
from pathlib import Path
import sys
import subprocess

def analyze_conversations(json_path):
    # This function is now a placeholder because we use LLM-generated rules
    # which are dynamically produced by the agent executing the skill manifest.
    return [], [], [], []

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
    
    plan_json_path = Path(__file__).resolve().parent / "extracted" / "agent_evolution_plan.json"
    if not plan_json_path.exists():
        print(f"\n📝 No LLM-generated plan found at {plan_json_path}.")
        print("Please ensure your LLM agent writes the rules and failures to this JSON file after analyzing the conversation logs.")
        # Create an initial empty template file to assist the LLM/user
        plan_json_path.parent.mkdir(parents=True, exist_ok=True)
        initial_template = {
            "failures": [],
            "rules": [],
            "skills": [],
            "prompts": []
        }
        with open(plan_json_path, "w", encoding="utf-8") as f:
            json.dump(initial_template, f, indent=2)
        print(f"Created a template plan JSON file at: {plan_json_path}")
        return
        
    try:
        with open(plan_json_path, "r", encoding="utf-8") as f:
            plan_data = json.load(f)
    except Exception as e:
        print(f"Error reading plan JSON file: {e}")
        return
        
    failures = plan_data.get("failures", [])
    rules = plan_data.get("rules", [])
    skills = plan_data.get("skills", [])
    prompts = plan_data.get("prompts", [])
    
    output_path = Path(__file__).resolve().parent / "extracted" / "agent_evolution_plan.md"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Agent Evolution Analysis & Plan\n\n")
        
        f.write("## 1. Identified Failure & Inefficiency Patterns\n")
        if failures:
            for fail in failures:
                f.write(f"### Pattern: {fail.get('type', 'Unknown')}\n")
                f.write(f"- **Session:** {fail.get('session', 'N/A')}\n")
                f.write(f"- **Project:** `{fail.get('project', 'N/A')}`\n")
                f.write(f"- **Observation:** {fail.get('description', '')}\n\n")
        else:
            f.write("No major failure patterns identified.\n\n")
            
        f.write("## 2. Recommended Rules for AGENTS.md\n")
        f.write("Add the following rules to your global or project-level `AGENTS.md` file:\n\n")
        for rule in rules:
            f.write(f"### {rule.get('name', 'Unnamed Rule')}\n")
            f.write(f"{rule.get('description', '')}\n\n")
            
        f.write("## 3. Recommended Custom Skills\n")
        f.write("You can implement these custom skills under `.agents/skills/` in your workspaces:\n\n")
        for skill in skills:
            f.write(f"### Skill: `{skill.get('name', 'unnamed-skill')}`\n")
            f.write(f"**Description:** {skill.get('description', '')}\n\n")
            f.write("**Instructions:**\n")
            f.write(f"{skill.get('instructions', '')}\n\n")
            
        f.write("## 4. Past Successful Prompts for Reference\n")
        for p in prompts:
            f.write(f"- **[{p.get('project', 'N/A')}]** \"{p.get('prompt', '')}\"\n")
            
    print(f"Saved agent evolution plan markdown to {output_path}")
    
    # Copy rules to global configs
    update_global_configs(rules)
    
    # Check if cockpit backend is already running on port 8080
    cockpit_running = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', 8080)) == 0:
                cockpit_running = True
    except Exception:
        pass
        
    if cockpit_running:
        print("\n🚀 Agent Evolution Web Cockpit backend is already running on port 8080.")
        print("👉 Load your cockpit web page (usually http://localhost:3000) to view your interactive trajectories and stage rules/skills!")
    else:
        print("\n🚀 Starting Agent Evolution Web Cockpit in the background...")
        try:
            run_app_path = Path(__file__).resolve().parent / "run_app.py"
            log_file = Path(__file__).resolve().parent / "extracted" / "cockpit.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a") as f:
                subprocess.Popen([sys.executable, str(run_app_path)], stdout=f, stderr=f, start_new_session=True)
            print("👉 Web Cockpit started successfully!")
            print("👉 Open http://localhost:3000 (or http://localhost:3001 if 3000 is occupied) to view your cockpit!")
        except Exception as e:
            print(f"Failed to start Web Cockpit in the background: {e}")

if __name__ == "__main__":
    main()
