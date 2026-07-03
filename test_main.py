import os
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from main import app, CONVERSATIONS_JSON

client = TestClient(app)

def test_get_sessions():
    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Since we have active session files extracted, there should be at least some sessions
    assert len(data) >= 2
    assert "session_id" in data[0]
    assert "project_path" in data[0]
    assert "title" in data[0]

def test_get_session_detail():
    # Fetch list first to get an ID
    res_list = client.get("/api/sessions")
    sessions = res_list.json()
    session_id = sessions[0]["session_id"]
    
    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert "turns" in data

def test_get_improvement_plan():
    response = client.get("/api/improvement-plan")
    assert response.status_code == 200
    data = response.json()
    assert "failures" in data
    assert "rules" in data
    assert "skills" in data
    assert "prompts" in data

def test_apply_rule_and_skill(tmp_path):
    # Test apply-rule
    rule_payload = {
        "project_path": str(tmp_path),
        "rule_name": "Test Rule",
        "rule_content": "Always write tests."
    }
    response = client.post("/api/apply-rule", json=rule_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    agents_md = tmp_path / ".agents" / "AGENTS.md"
    assert agents_md.exists()
    assert "Test Rule" in agents_md.read_text(encoding="utf-8")
    
    # Test apply-skill
    skill_payload = {
        "project_path": str(tmp_path),
        "skill_name": "test-skill",
        "skill_description": "A skill to test code.",
        "skill_instructions": "Run pytest."
    }
    response = client.post("/api/apply-skill", json=skill_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    skill_md = tmp_path / ".agents" / "skills" / "test-skill" / "SKILL.md"
    assert skill_md.exists()
    skill_text = skill_md.read_text(encoding="utf-8")
    assert "test-skill" in skill_text
    assert "A skill to test code." in skill_text
