import json
from pathlib import Path
import sys
import subprocess

def analyze_conversations(json_path):
    # This function is now a placeholder because we use LLM-generated rules
    # which are dynamically produced by the agent executing the skill manifest.
    return [], [], [], []


def _render_evidence(item):
    lines = []
    for ev in item.get("evidence", []) or []:
        quote = (ev.get("quote", "") or "").replace("\n", " ")
        if len(quote) > 200:
            quote = quote[:197] + "..."
        lines.append(f"  - `{ev.get('session', '?')}` turns {ev.get('turns', '?')}: \"{quote}\"")
    return "\n".join(lines)


def render_plan_markdown(plan_data, output_path):
    """Render the agent evolution plan markdown from the (new-schema) plan JSON.

    Backwards compatible: falls back to the legacy `rules`/`prompts` keys when the new
    `global_rules`/`project_rules`/`successes` keys are absent.
    """
    meta = plan_data.get("meta", {})
    failures = plan_data.get("failures", [])
    successes = plan_data.get("successes", [])
    global_rules = plan_data.get("global_rules", []) or plan_data.get("rules", [])
    project_rules = plan_data.get("project_rules", [])
    skills = plan_data.get("skills", [])
    prompts = plan_data.get("prompts", [])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Agent Evolution Analysis & Plan\n\n")

        if meta:
            f.write(
                f"> Sessions analyzed: **{meta.get('sessions_analyzed', '?')}** · "
                f"Signal strength: **{meta.get('signal_strength', '?')}**\n\n"
            )
            if meta.get("notes"):
                f.write(f"{meta['notes']}\n\n")

        f.write("## 1. Identified Patterns (with evidence)\n")
        if failures:
            for fail in failures:
                f.write(f"### Pattern: {fail.get('type', 'Unknown')}\n")
                f.write(
                    f"- **Scope:** {fail.get('scope', 'n/a')} · "
                    f"**Frequency:** {fail.get('frequency', '?')} · "
                    f"**Confidence:** {fail.get('confidence', '?')} · "
                    f"**Kind:** {fail.get('kind', '?')}\n"
                )
                f.write(f"- **Observation:** {fail.get('description', '')}\n")
                ev = _render_evidence(fail)
                if ev:
                    f.write(f"- **Evidence:**\n{ev}\n")
                f.write("\n")
        else:
            f.write("No evidence-backed failure patterns identified.\n\n")

        f.write("## 2. What Worked (reinforce these)\n")
        if successes:
            for s in successes:
                f.write(f"- {s.get('description', '')}\n")
                ev = _render_evidence(s)
                if ev:
                    f.write(f"{ev}\n")
        else:
            f.write("No notable success patterns recorded.\n")
        f.write("\n")

        f.write("## 3. General Rules -> global config (e.g. ~/AGENTS.md)\n")
        f.write("Stack-agnostic behavioral rules that should transfer to any project:\n\n")
        for rule in global_rules:
            f.write(f"### {rule.get('name', 'Unnamed Rule')}\n")
            f.write(f"{rule.get('description', '')}\n")
            if rule.get("example"):
                f.write(f"\n*Example from traces:* {rule['example']}\n")
            f.write("\n")

        f.write("## 4. Project-Specific Rules -> <project>/AGENTS.md\n")
        if project_rules:
            for rule in project_rules:
                f.write(f"### [{rule.get('project', 'N/A')}] {rule.get('name', 'Unnamed Rule')}\n")
                f.write(f"{rule.get('description', '')}\n\n")
        else:
            f.write("None.\n\n")

        f.write("## 5. Recommended Custom Skills\n")
        f.write("Implement under `.agents/skills/`:\n\n")
        for skill in skills:
            f.write(f"### Skill: `{skill.get('name', 'unnamed-skill')}`\n")
            f.write(f"**Description:** {skill.get('description', '')}\n\n")
            f.write("**Instructions:**\n")
            f.write(f"{skill.get('instructions', '')}\n\n")

        if prompts:
            f.write("## 6. Instructive Prompts for Reference\n")
            for p in prompts:
                f.write(f"- **[{p.get('project', 'N/A')}]** \"{p.get('prompt', '')}\"\n")


def launch_cockpit():
    """Launch the web cockpit in the background (loopback only). Opt-in via `--serve`."""
    import socket
    cockpit_running = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", 8080)) == 0:
                cockpit_running = True
    except Exception:
        pass

    if cockpit_running:
        print("\n🚀 Web Cockpit backend already running on 127.0.0.1:8080.")
        print("👉 Open http://localhost:3000 to view your trajectories.")
        return

    print("\n🚀 Starting Agent Evolution Web Cockpit in the background (loopback only)...")
    try:
        run_app_path = Path(__file__).resolve().parent / "run_app.py"
        log_file = Path(__file__).resolve().parent / "extracted" / "cockpit.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            subprocess.Popen([sys.executable, str(run_app_path)], stdout=f, stderr=f, start_new_session=True)
        print("👉 Web Cockpit started. Open http://localhost:3000 (next free port if occupied).")
    except Exception as e:
        print(f"Failed to start Web Cockpit: {e}")


def main():
    plan_json_path = Path(__file__).resolve().parent / "extracted" / "agent_evolution_plan.json"
    if not plan_json_path.exists():
        print(f"\n📝 No LLM-generated plan found at {plan_json_path}.")
        print("The agent executing the skill must write findings here after reading the traces.")
        plan_json_path.parent.mkdir(parents=True, exist_ok=True)
        initial_template = {
            "meta": {"sessions_analyzed": 0, "signal_strength": "low", "notes": ""},
            "failures": [],
            "successes": [],
            "global_rules": [],
            "project_rules": [],
            "skills": [],
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

    output_path = Path(__file__).resolve().parent / "extracted" / "agent_evolution_plan.md"
    render_plan_markdown(plan_data, output_path)
    print(f"Saved agent evolution plan markdown to {output_path}")

    # The cockpit is now OPT-IN and decoupled from plan generation (no surprise servers).
    if "--serve" in sys.argv:
        launch_cockpit()
    else:
        print("\n(Plan rendered. Run `python3 agent_evolution.py --serve` to open the web cockpit.)")


if __name__ == "__main__":
    main()
