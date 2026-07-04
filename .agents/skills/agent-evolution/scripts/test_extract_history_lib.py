import json
from pathlib import Path
import pytest
from extract_history_lib import (
    clean_user_content,
    parse_session_file,
    parse_antigravity_session,
    redact_secrets,
    compute_signals,
)


def test_redact_secrets():
    assert redact_secrets("token sk-ant-abcdefghijklmnop1234") == "token [REDACTED]"
    assert "[REDACTED]" in redact_secrets("key=AIzaSyABCDEFGHIJKLMNOPQRSTUVWX12345")
    assert redact_secrets("nothing secret here") == "nothing secret here"
    assert redact_secrets(None) is None


def test_clean_user_content_error_flag():
    content = [{"type": "tool_result", "tool_use_id": "t1", "content": "boom", "is_error": True}]
    assert "[Tool Result for t1] [ERROR]: boom" in clean_user_content(content)


def test_compute_signals_detects_patterns():
    sessions = [{
        "session_id": "s1",
        "project_path": "/p",
        "title": "t",
        "turns": [
            {"role": "user", "type": "prompt", "content": "[Request interrupted by user]"},
            {"role": "user", "type": "tool_result", "content": "fail", "is_error": True},
            {"role": "assistant", "tool_calls": [{"name": "Bash", "input": {"command": "npm run build"}}]},
            {"role": "assistant", "tool_calls": [{"name": "Bash", "input": {"command": "npm  run   build"}}]},
        ],
    }]
    sig = compute_signals(sessions)[0]
    assert sig["interruptions"] == [0]
    assert sig["tool_errors"] and sig["tool_errors"][0]["turn"] == 1
    assert any(c["count"] == 2 for c in sig["repeated_commands"])

def test_clean_user_content_caveat():
    content = "<local-command-caveat>Test Caveat</local-command-caveat>"
    assert clean_user_content(content) is None

def test_clean_user_content_str():
    content = "hello world"
    assert clean_user_content(content) == "hello world"

def test_clean_user_content_list():
    content = [
        {"type": "text", "text": "Hello User"},
        {"type": "tool_result", "tool_use_id": "tool-1", "content": "Success"}
    ]
    cleaned = clean_user_content(content)
    assert "Hello User" in cleaned
    assert "[Tool Result for tool-1]: Success" in cleaned

def test_parse_session_file(tmp_path):
    # Create a mock session JSONL file
    session_file = tmp_path / "test_session.jsonl"
    
    events = [
        {"type": "ai-title", "aiTitle": "Test Title", "sessionId": "test_session"},
        {
            "type": "user",
            "message": {"role": "user", "content": "How are you?"},
            "timestamp": "2026-07-03T12:00:00Z",
            "sessionId": "test_session"
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "model": "claude-test-model",
                "content": [
                    {"type": "thinking", "thinking": "Thinking..."},
                    {"type": "text", "text": "I am fine, thank you."}
                ]
            },
            "timestamp": "2026-07-03T12:01:00Z",
            "sessionId": "test_session"
        }
    ]
    
    with open(session_file, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
            
    parsed = parse_session_file(session_file)
    
    assert parsed["session_id"] == "test_session"
    assert parsed["title"] == "Test Title"
    assert len(parsed["turns"]) == 2
    
    # Check user turn
    assert parsed["turns"][0]["role"] == "user"
    assert parsed["turns"][0]["content"] == "How are you?"
    
    # Check assistant turn
    assert parsed["turns"][1]["role"] == "assistant"
    assert parsed["turns"][1]["thinking"] == "Thinking..."
    assert parsed["turns"][1]["content"] == "I am fine, thank you."
    assert parsed["turns"][1]["model"] == "claude-test-model"

def test_parse_antigravity_session(tmp_path):
    # Create a mock Antigravity session JSON file
    # Structure: chats/session-*.json
    chats_dir = tmp_path / "chats"
    chats_dir.mkdir()
    session_file = chats_dir / "session-12345.json"
    
    data = {
        "sessionId": "12345",
        "startTime": "2026-07-03T12:00:00Z",
        "messages": [
            {
                "type": "user",
                "content": [{"text": "Hello Gemini"}]
            },
            {
                "type": "gemini",
                "content": "Hello! How can I help you?",
                "thoughts": [
                    {"subject": "Initial thought", "description": "Analyzing request"}
                ],
                "toolCalls": [
                    {
                        "id": "tool-1",
                        "name": "search_web",
                        "args": {"query": "test"},
                        "resultDisplay": "Search completed successfully",
                        "timestamp": "2026-07-03T12:00:05Z"
                    }
                ],
                "model": "gemini-3.5-flash"
            }
        ]
    }
    
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    parsed = parse_antigravity_session(session_file)
    
    assert parsed is not None
    assert parsed["session_id"] == "session-12345"
    assert "Antigravity: Hello Gemini" in parsed["title"]
    # Turns should contain: user prompt, gemini assistant, and tool result user prompt
    assert len(parsed["turns"]) == 3
    
    assert parsed["turns"][0]["role"] == "user"
    assert parsed["turns"][0]["content"] == "Hello Gemini"
    
    assert parsed["turns"][1]["role"] == "assistant"
    assert "[Initial thought] Analyzing request" in parsed["turns"][1]["thinking"]
    assert parsed["turns"][1]["content"] == "Hello! How can I help you?"
    assert parsed["turns"][1]["model"] == "gemini-3.5-flash"
    assert len(parsed["turns"][1]["tool_calls"]) == 1
    assert parsed["turns"][1]["tool_calls"][0]["name"] == "search_web"
    
    assert parsed["turns"][2]["role"] == "user"
    assert parsed["turns"][2]["type"] == "tool_result"
    assert "[Tool Result for tool-1]: Search completed successfully" in parsed["turns"][2]["content"]
