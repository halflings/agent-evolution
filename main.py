import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import extraction logic
import extract_history
import agent_evolution

app = FastAPI(title="Agent Evolution Hub API")

# Enable CORS for Next.js frontend development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EXTRACTED_DIR = Path(__file__).resolve().parent / "extracted"
CONVERSATIONS_JSON = EXTRACTED_DIR / "extracted_conversations.json"
PLAN_MD = EXTRACTED_DIR / "agent_evolution_plan.md"
PLAN_JSON = EXTRACTED_DIR / "agent_evolution_plan.json"

class ApplyRuleRequest(BaseModel):
    project_path: str
    rule_name: str
    rule_content: str

class ApplySkillRequest(BaseModel):
    project_path: str
    skill_name: str
    skill_description: str
    skill_instructions: str

@app.post("/api/refresh")
def refresh_data():
    """Triggers the extraction and agent evolution analysis scripts."""
    try:
        extract_history.main()
        # Re-run agent evolution config sync and server checks
        agent_evolution.main()
        return {"status": "success", "message": "History and analysis refreshed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
def get_sessions():
    """Returns all session summaries."""
    if not CONVERSATIONS_JSON.exists():
        # Auto-refresh if data doesn't exist yet
        refresh_data()
        
    try:
        with open(CONVERSATIONS_JSON, "r", encoding="utf-8") as f:
            sessions = json.load(f)
            
        summaries = []
        for s in sessions:
            summaries.append({
                "session_id": s.get("session_id"),
                "project_path": s.get("project_path"),
                "project_name": s.get("project_name"),
                "title": s.get("title") or "Unnamed Session",
                "turns_count": len(s.get("turns", []))
            })
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}")
def get_session_detail(session_id: str):
    """Returns the full details of a single session."""
    if not CONVERSATIONS_JSON.exists():
        raise HTTPException(status_code=404, detail="Data files not initialized. Run refresh first.")
        
    try:
        with open(CONVERSATIONS_JSON, "r", encoding="utf-8") as f:
            sessions = json.load(f)
            
        for s in sessions:
            if s.get("session_id") == session_id:
                return s
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/improvement-plan")
def get_improvement_plan():
    """Returns the synthesized rules, skills, and past prompts."""
    if not PLAN_JSON.exists():
        # Create an empty initial plan if it doesn't exist
        EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
        with open(PLAN_JSON, "w", encoding="utf-8") as f:
            json.dump({"failures": [], "rules": [], "skills": [], "prompts": []}, f, indent=2)
            
    try:
        with open(PLAN_JSON, "r", encoding="utf-8") as f:
            plan_data = json.load(f)
        global_rules = plan_data.get("global_rules", []) or plan_data.get("rules", [])
        return {
            "meta": plan_data.get("meta", {}),
            "failures": plan_data.get("failures", []),
            "successes": plan_data.get("successes", []),
            "rules": global_rules,
            "global_rules": global_rules,
            "project_rules": plan_data.get("project_rules", []),
            "skills": plan_data.get("skills", []),
            "prompts": plan_data.get("prompts", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/apply-rule")
def apply_rule(req: ApplyRuleRequest):
    """Applies a rule to the target project's .agents/AGENTS.md file."""
    proj_path = Path(req.project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=400, detail=f"Project path {proj_path} does not exist.")
        
    agents_dir = proj_path / ".agents"
    agents_dir.mkdir(exist_ok=True)
    agents_md = agents_dir / "AGENTS.md"
    
    # Dedupe: don't append a rule whose header already exists (keeps AGENTS.md tight over runs).
    existing = agents_md.read_text(encoding="utf-8") if agents_md.exists() else ""
    if f"# {req.rule_name}\n" in existing or f"# {req.rule_name}\r\n" in existing:
        return {"status": "skipped", "message": f"Rule '{req.rule_name}' already present in {agents_md}"}

    rule_formatted = f"\n# {req.rule_name}\n{req.rule_content}\n"

    try:
        with open(agents_md, "a", encoding="utf-8") as f:
            f.write(rule_formatted)
        return {"status": "success", "message": f"Rule successfully appended to {agents_md}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/apply-skill")
def apply_skill(req: ApplySkillRequest):
    """Applies a skill to the target project's .agents/skills/{skill_name}/SKILL.md file."""
    proj_path = Path(req.project_path)
    if not proj_path.exists():
        raise HTTPException(status_code=400, detail=f"Project path {proj_path} does not exist.")
        
    skill_dir = proj_path / ".agents" / "skills" / req.skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    
    skill_content = f"""---
name: {req.skill_name}
description: {req.skill_description}
---

# {req.skill_name}

## Description
{req.skill_description}

## Instructions
{req.skill_instructions}
"""
    
    try:
        with open(skill_md, "w", encoding="utf-8") as f:
            f.write(skill_content)
        return {"status": "success", "message": f"Skill successfully saved to {skill_md}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Loopback only: this API serves raw conversation transcripts; do not expose on the network.
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
