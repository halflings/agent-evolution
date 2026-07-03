import os
import json
import glob
from pathlib import Path
from datetime import datetime

def clean_user_content(content):
    """
    Cleans user content by removing system caveates, formatting command inputs/outputs,
    and returns a user-readable string or None if it's meta/internal.
    """
    if not content:
        return None
    
    if isinstance(content, str):
        # Ignore caveat message
        if "<local-command-caveat>" in content:
            return None
        # Handle command name and command message
        if "<command-name>" in content:
            # Extract clean command if possible
            return f"Command run: {content.strip()}"
        if "<local-command-stdout>" in content:
            return f"Command output: {content.strip()}"
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text":
                text = item.get("text", "")
                if text and "[Request interrupted by user]" in text:
                    parts.append("[Request interrupted by user]")
                elif text:
                    parts.append(text)
            elif item_type == "tool_result":
                tool_content = item.get("content", "")
                tool_id = item.get("tool_use_id", "")
                parts.append(f"[Tool Result for {tool_id}]: {tool_content}")
        if parts:
            return "\n".join(parts)
        
    return str(content)

def parse_session_file(file_path):
    """
    Parses a single session .jsonl file and extracts a structured conversation history.
    """
    file_path = Path(file_path)
    session_id = file_path.stem
    project_dir = file_path.parent.name
    # Reconstruct project path (e.g. -Users-username-workspace-project -> /Users/username/workspace/project)
    project_path = project_dir.replace("-", "/")
    if not project_path.startswith("/"):
        project_path = "/" + project_path
        
    turns = []
    session_title = ""
    
    # We will build a list of all events with timestamps or order of appearance
    events = []
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                events.append(data)
            except Exception as e:
                print(f"Error parsing line in {file_path}: {e}")
                
    current_assistant_turn = None
    
    for event in events:
        event_type = event.get("type")
        
        if event_type == "ai-title":
            session_title = event.get("aiTitle", "")
            
        elif event_type == "user":
            if current_assistant_turn:
                turns.append(current_assistant_turn)
                current_assistant_turn = None
                
            msg = event.get("message", {})
            raw_content = msg.get("content")
            clean_content = clean_user_content(raw_content)
            
            is_tool_result = False
            if isinstance(raw_content, list):
                is_tool_result = any(item.get("type") == "tool_result" for item in raw_content if isinstance(item, dict))
                
            if clean_content:
                turns.append({
                    "role": "user",
                    "type": "tool_result" if is_tool_result else "prompt",
                    "content": clean_content,
                    "timestamp": event.get("timestamp")
                })
                
        elif event_type == "assistant":
            msg = event.get("message", {})
            content_list = msg.get("content", [])
            
            if not current_assistant_turn:
                current_assistant_turn = {
                    "role": "assistant",
                    "thinking": "",
                    "tool_calls": [],
                    "content": "",
                    "timestamp": event.get("timestamp"),
                    "model": msg.get("model", "")
                }
                
            for item in content_list:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                if item_type == "thinking":
                    current_assistant_turn["thinking"] += item.get("thinking", "")
                elif item_type == "text":
                    current_assistant_turn["content"] += item.get("text", "")
                elif item_type == "tool_use":
                    current_assistant_turn["tool_calls"].append({
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "input": item.get("input")
                    })
                    
        elif event_type == "system":
            if current_assistant_turn:
                turns.append(current_assistant_turn)
                current_assistant_turn = None
                
            subtype = event.get("subtype")
            content = event.get("content")
            if content and subtype == "local_command":
                turns.append({
                    "role": "system",
                    "type": "local_command",
                    "content": content,
                    "timestamp": event.get("timestamp")
                })
                
    if current_assistant_turn:
        turns.append(current_assistant_turn)
        
    return {
        "session_id": session_id,
        "project_path": project_path,
        "project_name": file_path.parent.name,
        "title": session_title,
        "turns": turns
    }

def parse_antigravity_session(file_path):
    """
    Parses a single Antigravity session JSON file and extracts a structured conversation.
    """
    file_path = Path(file_path)
    
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"Error parsing Antigravity JSON {file_path}: {e}")
            return None
            
    session_id = file_path.stem
    project_dir = file_path.parent.parent  # e.g., ~/.gemini/tmp/target-project
    project_name = project_dir.name
    
    # Read project path from .project_root if it exists
    project_path = f"/Users/username/workspace/{project_name}"
    project_root_file = project_dir / ".project_root"
    if project_root_file.exists():
        try:
            project_path = project_root_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
            
    turns = []
    messages = data.get("messages", [])
    first_user_text = ""
    
    for msg in messages:
        m_type = msg.get("type")
        timestamp = msg.get("timestamp")
        
        if m_type == "user":
            content_list = msg.get("content", [])
            text_parts = []
            if isinstance(content_list, list):
                for item in content_list:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
            elif isinstance(content_list, str):
                text_parts.append(content_list)
                
            text_content = "\n".join(text_parts).strip()
            if text_content:
                if not first_user_text:
                    first_user_text = text_content
                turns.append({
                    "role": "user",
                    "type": "prompt",
                    "content": text_content,
                    "timestamp": timestamp
                })
                
        elif m_type == "gemini":
            content = msg.get("content", "")
            # Construct thinking
            thinking_parts = []
            for t in msg.get("thoughts", []):
                subject = t.get("subject", "")
                desc = t.get("description", "")
                thinking_parts.append(f"[{subject}] {desc}")
            thinking_text = "\n".join(thinking_parts)
            
            # Construct tool calls
            tool_calls = []
            for tc in msg.get("toolCalls", []):
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": tc.get("name", ""),
                    "input": tc.get("args", {})
                })
            
            turns.append({
                "role": "assistant",
                "thinking": thinking_text,
                "tool_calls": tool_calls,
                "content": content,
                "timestamp": timestamp,
                "model": msg.get("model", "Gemini")
            })
            
            # Append the tool results as separate user turns
            for tc in msg.get("toolCalls", []):
                result_display = tc.get("resultDisplay", "")
                if result_display:
                    turns.append({
                        "role": "user",
                        "type": "tool_result",
                        "content": f"[Tool Result for {tc.get('id')}]: {result_display}",
                        "timestamp": tc.get("timestamp")
                    })
                    
    # Generate title
    title = first_user_text
    if len(title) > 60:
        title = title[:57] + "..."
    if not title:
        title = f"Antigravity Session {session_id[:8]}"
    else:
        title = f"Antigravity: {title}"
        
    return {
        "session_id": session_id,
        "project_path": project_path,
        "project_name": project_name,
        "title": title,
        "turns": turns
    }

def main():
    # 1. Parse Claude project sessions
    claude_dir = Path.home() / ".claude"
    projects_dir = claude_dir / "projects"
    
    all_sessions = []
    
    if projects_dir.exists():
        session_files = glob.glob(str(projects_dir / "*" / "*.jsonl"))
        print(f"Found {len(session_files)} Claude session files.")
        for sf in session_files:
            print(f"Parsing Claude log: {sf}...")
            session_data = parse_session_file(sf)
            all_sessions.append(session_data)
    else:
        print(f"Claude projects directory not found at {projects_dir}")
        
    # 2. Parse Antigravity project sessions
    gemini_tmp = Path.home() / ".gemini" / "tmp"
    if gemini_tmp.exists():
        antigravity_files = glob.glob(str(gemini_tmp / "*" / "chats" / "session-*.json"))
        print(f"Found {len(antigravity_files)} Antigravity session files.")
        for af in antigravity_files:
            print(f"Parsing Antigravity log: {af}...")
            session_data = parse_antigravity_session(af)
            if session_data:
                all_sessions.append(session_data)
    else:
        print(f"Antigravity tmp directory not found at {gemini_tmp}")
        
    # Write to a clean JSON file
    output_dir = Path(__file__).resolve().parents[3] / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    json_output_path = output_dir / "extracted_conversations.json"
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(all_sessions, f, indent=2)
    print(f"Saved JSON extraction to {json_output_path}")
    
    # Write a beautiful markdown file
    md_output_path = output_dir / "extracted_conversations.md"
    with open(md_output_path, "w", encoding="utf-8") as f:
        f.write("# Conversation History (Claude Code & Antigravity)\n\n")
        f.write(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for sess in all_sessions:
            f.write(f"## Session: {sess['title'] or sess['session_id']}\n")
            f.write(f"- **Project:** `{sess['project_path']}` ({sess['project_name']})\n")
            f.write(f"- **Session ID:** `{sess['session_id']}`\n\n")
            
            for i, turn in enumerate(sess["turns"]):
                role = turn["role"].capitalize()
                t_type = turn.get("type", "")
                
                if role == "User":
                    if t_type == "tool_result":
                        f.write(f"### [User (Tool Result)] Turn {i+1}\n")
                        f.write("```\n")
                        f.write(turn["content"])
                        f.write("\n```\n\n")
                    else:
                        f.write(f"### [User] Turn {i+1}\n")
                        f.write(f"{turn['content']}\n\n")
                elif role == "Assistant":
                    f.write(f"### [Assistant] Turn {i+1}\n")
                    if turn.get("model"):
                        f.write(f"*Model: `{turn['model']}`*\n\n")
                    if turn.get("thinking"):
                        f.write("<details>\n<summary>Thinking Process</summary>\n\n")
                        f.write(turn["thinking"])
                        f.write("\n</details>\n\n")
                    if turn.get("tool_calls"):
                        f.write("#### Tool Calls:\n")
                        for tc in turn["tool_calls"]:
                            f.write(f"- **Tool:** `{tc['name']}`\n")
                            f.write("  **Input:**\n")
                            f.write("  ```json\n")
                            f.write(json.dumps(tc["input"], indent=2))
                            f.write("\n  ```\n")
                        f.write("\n")
                    if turn.get("content"):
                        f.write("#### Response:\n")
                        f.write(f"{turn['content']}\n\n")
                elif role == "System":
                    f.write(f"### [System ({t_type})] Turn {i+1}\n")
                    f.write(f"{turn['content']}\n\n")
            f.write("---\n\n")
            
    print(f"Saved Markdown rendering to {md_output_path}")

if __name__ == "__main__":
    main()
