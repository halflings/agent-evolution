import json
from pathlib import Path
from agent_evolution import analyze_conversations

def test_analyze_conversations(tmp_path):
    json_file = tmp_path / "mock_extracted.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump([], f)
        
    failures, rules, skills, prompts = analyze_conversations(json_file)
    
    assert len(failures) == 0
    assert len(rules) == 0
    assert len(skills) == 0
    assert len(prompts) == 0
