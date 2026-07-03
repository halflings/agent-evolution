import json
from pathlib import Path
from agent_evolution import analyze_conversations

def test_analyze_conversations(tmp_path):
    # Mock extracted conversations JSON
    mock_conversations = [
        {
            "title": "Refactor agent.py",
            "project_path": "/Users/username/workspace/target-project",
            "turns": [
                {
                    "role": "user",
                    "type": "prompt",
                    "content": "in agent.py ; let's organize the code"
                },
                {
                    "role": "assistant",
                    "content": "I can't find an agent.py file in the project."
                },
                {
                    "role": "user",
                    "type": "prompt",
                    "content": "[Request interrupted by user]"
                }
            ]
        }
    ]
    
    json_file = tmp_path / "mock_extracted.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(mock_conversations, f)
        
    failures, rules, skills, prompts = analyze_conversations(json_file)
    
    # Assert failures are detected
    assert len(failures) == 2
    assert failures[0]["type"] == "File Path / Context Missing"
    assert failures[1]["type"] == "User Interruption"
    
    # Assert rules and skills are populated
    assert len(rules) > 0
    assert len(skills) > 0
    assert len(prompts) == 2  # including the interruption as prompt unless filtered, wait, let's verify prompts length:
    # "in agent.py ; let's organize the code" (len > 10, not starting with /)
    # "[Request interrupted by user]" (len > 10, not starting with /) -> so 2 prompts. Correct!
