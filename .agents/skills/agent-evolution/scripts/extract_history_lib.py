import os
import re
import json
import glob
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

# --- Privacy: redact secrets before anything is written to disk or served ---
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),                 # OpenAI-style keys
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),             # Anthropic keys
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),                # Google API keys
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),            # GitHub tokens
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),          # GitHub fine-grained PAT
    re.compile(r"AKIA[0-9A-Z]{16}"),                      # AWS access key id
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),          # Slack tokens
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWTs
    re.compile(r"(?i)(authorization|bearer|api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{12,}"),
]


def redact_secrets(text):
    """Replace likely secrets/credentials with a placeholder. Best-effort, not exhaustive."""
    if not isinstance(text, str):
        return text
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def redact_session(session):
    """Return a deep-ish copy of a session with string content redacted."""
    for turn in session.get("turns", []):
        if isinstance(turn.get("content"), str):
            turn["content"] = redact_secrets(turn["content"])
        turn["thinking"] = redact_secrets(turn.get("thinking", "")) if turn.get("thinking") else turn.get("thinking", "")
        for tc in turn.get("tool_calls", []):
            if isinstance(tc.get("input"), dict):
                tc["input"] = {k: redact_secrets(v) if isinstance(v, str) else v for k, v in tc["input"].items()}
    return session

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
                err = " [ERROR]" if item.get("is_error") else ""
                parts.append(f"[Tool Result for {tool_id}]{err}: {tool_content}")
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
            is_error = False
            if isinstance(raw_content, list):
                is_tool_result = any(item.get("type") == "tool_result" for item in raw_content if isinstance(item, dict))
                is_error = any(item.get("is_error") for item in raw_content if isinstance(item, dict))

            if clean_content:
                turns.append({
                    "role": "user",
                    "type": "tool_result" if is_tool_result else "prompt",
                    "content": clean_content,
                    "is_error": is_error,
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

# --- Antigravity (current "brain" transcript format) ---------------------------------------
# Modern Antigravity/Gemini stores one JSONL transcript per session at
#   ~/.gemini/antigravity-{cli,ide}/brain/<session_id>/.system_generated/logs/transcript.jsonl
# Each line is a "step" record: {step_index, source, type, status, created_at, content, tool_calls?}.
# (The legacy ~/.gemini/tmp/*/chats/session-*.json format is still handled by
# parse_antigravity_session above.)

# Step types that are conversation framing rather than a user prompt or model turn.
_ANTIGRAVITY_SYSTEM_TYPES = {
    "CHECKPOINT", "SYSTEM_MESSAGE", "CONVERSATION_HISTORY", "KNOWLEDGE_ARTIFACTS",
}
_USER_REQUEST_RE = re.compile(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.DOTALL)
# Absolute project roots look like /home/<user>/workspace/<project> (or /Users/...). The brain's
# own artifacts live under ~/.gemini, so a workspace-scoped match reliably picks the real project.
_WORKSPACE_PATH_RE = re.compile(r"/(?:home|Users)/[^/\s\"']+/workspace/[^/\s\"':]+")


def _extract_user_request(text):
    """Pull the human request out of Antigravity's <USER_REQUEST>...</USER_REQUEST> wrapper,
    dropping the appended <ADDITIONAL_METADATA>/<USER_SETTINGS_CHANGE> noise."""
    if not isinstance(text, str):
        return text
    m = _USER_REQUEST_RE.search(text)
    return (m.group(1) if m else text).strip()


def _infer_antigravity_project(records, fallback):
    """Best-effort project path: the most-referenced /.../workspace/<project> root across the
    transcript's tool-call args and content. Falls back when nothing workspace-scoped appears."""
    counter = Counter()
    for r in records:
        blobs = []
        if isinstance(r.get("content"), str):
            blobs.append(r["content"])
        for tc in (r.get("tool_calls") or []):
            args = tc.get("args")
            if isinstance(args, dict):
                blobs.extend(v for v in args.values() if isinstance(v, str))
        for b in blobs:
            for match in _WORKSPACE_PATH_RE.findall(b):
                counter[match] += 1
    return counter.most_common(1)[0][0] if counter else fallback


def parse_antigravity_transcript(file_path):
    """Parse a modern Antigravity brain transcript.jsonl into the unified session schema."""
    file_path = Path(file_path)
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception as e:
                print(f"Error parsing line in {file_path}: {e}")
    if not records:
        return None

    # .../brain/<session_id>/.system_generated/logs/transcript.jsonl -> session_id is parents[2].
    try:
        session_id = file_path.parents[2].name
        fallback_path = str(file_path.parents[2])
    except IndexError:
        session_id = file_path.stem
        fallback_path = str(file_path.parent)
    project_path = _infer_antigravity_project(records, fallback_path)
    project_name = Path(project_path).name

    turns = []
    first_user_text = ""
    for r in records:
        r_type = r.get("type")
        content = r.get("content", "")
        timestamp = r.get("created_at")

        if r_type == "USER_INPUT":
            text = _extract_user_request(content)
            if not text:
                continue
            if not first_user_text:
                first_user_text = text
            turns.append({"role": "user", "type": "prompt", "content": text, "timestamp": timestamp})

        elif r_type == "PLANNER_RESPONSE":
            tool_calls = [
                {"id": tc.get("id", ""), "name": tc.get("name", ""), "input": tc.get("args", {})}
                for tc in (r.get("tool_calls") or [])
            ]
            turns.append({
                "role": "assistant",
                "thinking": "",
                "tool_calls": tool_calls,
                "content": content or "",
                "timestamp": timestamp,
                "model": r.get("model", "Antigravity"),
            })

        elif r_type in _ANTIGRAVITY_SYSTEM_TYPES:
            if content:
                turns.append({"role": "system", "type": (r_type or "system").lower(),
                              "content": content, "timestamp": timestamp})

        else:
            # Tool execution / action result (VIEW_FILE, RUN_COMMAND, CODE_ACTION, GREP_SEARCH, ...).
            if content:
                is_error = str(r.get("status", "")).upper() in {"ERROR", "FAILED"}
                turns.append({"role": "user", "type": "tool_result",
                              "content": f"[{r_type}] {content}", "is_error": is_error,
                              "timestamp": timestamp})

    if not turns:
        return None

    title = first_user_text or f"Antigravity Session {session_id[:8]}"
    if len(title) > 60:
        title = title[:57] + "..."
    if first_user_text:
        title = f"Antigravity: {title}"

    return {
        "session_id": session_id,
        "project_path": project_path,
        "project_name": project_name,
        "title": title,
        "turns": turns,
    }


def discover_antigravity_sessions(gemini_dir):
    """Return [(path, kind)] for every Antigravity transcript under ~/.gemini.

    kind is "transcript" for the modern brain format and "legacy" for the old
    tmp/*/chats/session-*.json format. When a session has both transcript.jsonl and
    transcript_full.jsonl, only transcript.jsonl is kept (they duplicate each other)."""
    gemini_dir = Path(gemini_dir)
    if not gemini_dir.exists():
        return []
    found = []
    logs_seen = set()
    # transcript.jsonl first so it wins over transcript_full.jsonl for the same session.
    for name in ("transcript.jsonl", "transcript_full.jsonl"):
        pattern = str(gemini_dir / "antigravity-*" / "brain" / "*" / ".system_generated" / "logs" / name)
        for p in sorted(glob.glob(pattern)):
            logs_dir = str(Path(p).parent)
            if logs_dir in logs_seen:
                continue
            logs_seen.add(logs_dir)
            found.append((p, "transcript"))
    # Legacy format (older Antigravity installs).
    for p in sorted(glob.glob(str(gemini_dir / "tmp" / "*" / "chats" / "session-*.json"))):
        found.append((p, "legacy"))
    return found


def count_history_sessions():
    """Distinct Claude session ids ever recorded in ~/.claude/history.jsonl. This survives the
    transcript retention cleanup, so it reveals how many sessions once existed."""
    hist = Path.home() / ".claude" / "history.jsonl"
    sessions = set()
    if hist.exists():
        try:
            with hist.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    sid = json.loads(line).get("sessionId")
                    if sid:
                        sessions.add(sid)
        except Exception:
            pass
    return sessions


def _normalize_command(cmd):
    """Collapse whitespace so near-identical commands compare equal."""
    return re.sub(r"\s+", " ", str(cmd)).strip()


def compute_signals(sessions):
    """Pre-compute ATTENTION MARKERS to direct where an analyst should read closely.

    These are deliberately shallow pointers (indices + short quotes), NOT findings. The deep
    reading in the skill's MAP step decides what is actually a pattern.
    """
    out = []
    for s in sessions:
        turns = s.get("turns", [])
        interruptions, tool_errors = [], []
        cmd_counter = Counter()
        cmd_first_turn = {}
        edited_files = defaultdict(list)

        for i, t in enumerate(turns):
            content = str(t.get("content", ""))
            if "[Request interrupted by user]" in content or "interrupted by user for tool use" in content:
                interruptions.append(i)
            if t.get("role") == "user" and t.get("type") == "tool_result":
                if t.get("is_error") or "[ERROR]" in content:
                    tool_errors.append({"turn": i, "quote": content[:160]})
            for tc in t.get("tool_calls", []):
                name = tc.get("name")
                inp = tc.get("input") if isinstance(tc.get("input"), dict) else {}
                if name == "Bash" and inp.get("command"):
                    norm = _normalize_command(inp["command"])
                    cmd_counter[norm] += 1
                    cmd_first_turn.setdefault(norm, i)
                if name in ("Edit", "Write", "NotebookEdit") and inp.get("file_path"):
                    edited_files[inp["file_path"]].append(i)

        repeated_commands = [
            {"command": c[:120], "count": n, "first_turn": cmd_first_turn[c]}
            for c, n in cmd_counter.most_common() if n >= 2
        ]
        # Files touched 3+ times are candidate rework/churn loops worth reading closely.
        edit_loops = [
            {"file": f, "edit_turns": idxs} for f, idxs in edited_files.items() if len(idxs) >= 3
        ]

        out.append({
            "session_id": s.get("session_id"),
            "project_path": s.get("project_path"),
            "title": s.get("title"),
            "turns": len(turns),
            "interruptions": interruptions,
            "tool_errors": tool_errors,
            "repeated_commands": repeated_commands,
            "edit_loops": edit_loops,
        })
    return out


def render_session_markdown(sess):
    """Render a single (already redacted) session to markdown for per-session chunk files."""
    lines = [f"# Session: {sess['title'] or sess['session_id']}",
             f"- **Project:** `{sess['project_path']}` ({sess['project_name']})",
             f"- **Session ID:** `{sess['session_id']}`", ""]
    for i, turn in enumerate(sess["turns"]):
        role = turn["role"].capitalize()
        t_type = turn.get("type", "")
        if role == "User":
            tag = "User (Tool Result)" if t_type == "tool_result" else "User"
            err = " [ERROR]" if turn.get("is_error") else ""
            lines.append(f"### [{tag}{err}] Turn {i+1}")
            lines.append(f"```\n{turn['content']}\n```" if t_type == "tool_result" else turn["content"])
            lines.append("")
        elif role == "Assistant":
            lines.append(f"### [Assistant] Turn {i+1}")
            if turn.get("thinking"):
                lines.append(f"<details><summary>Thinking</summary>\n\n{turn['thinking']}\n</details>")
            for tc in turn.get("tool_calls", []):
                lines.append(f"- **Tool:** `{tc['name']}` input: `{json.dumps(tc['input'])[:400]}`")
            if turn.get("content"):
                lines.append(turn["content"])
            lines.append("")
        elif role == "System":
            lines.append(f"### [System ({t_type})] Turn {i+1}")
            lines.append(turn["content"])
            lines.append("")
    return "\n".join(lines)


def main():
    # 1. Parse Claude project sessions
    claude_dir = Path.home() / ".claude"
    projects_dir = claude_dir / "projects"
    
    all_sessions = []
    
    session_files = []
    if projects_dir.exists():
        session_files = glob.glob(str(projects_dir / "*" / "*.jsonl"))
        print(f"Found {len(session_files)} Claude session files.")
        for sf in session_files:
            print(f"Parsing Claude log: {sf}...")
            session_data = parse_session_file(sf)
            all_sessions.append(session_data)
    else:
        print(f"Claude projects directory not found at {projects_dir}")

    # Warn when Claude Code's retention cleanup has pruned transcripts we can no longer read.
    # ~/.claude/history.jsonl keeps prompts for sessions whose full transcripts are already gone.
    history_sessions = count_history_sessions()
    on_disk_ids = {Path(sf).stem for sf in session_files}
    pruned = history_sessions - on_disk_ids
    if history_sessions and pruned:
        print(
            f"\n⚠️  RETENTION WARNING: history.jsonl references {len(history_sessions)} past Claude "
            f"session(s) but only {len(on_disk_ids)} transcript(s) remain on disk — "
            f"{len(pruned)} were pruned by Claude Code's `cleanupPeriodDays` retention (default 30 "
            f"days) and are unrecoverable. To keep more going forward, raise `cleanupPeriodDays` in "
            f"~/.claude/settings.json (see SKILL.md -> Data retention & coverage).\n"
        )

    # 2. Parse Antigravity / Gemini sessions (modern brain transcripts + legacy chats format).
    gemini_dir = Path.home() / ".gemini"
    antigravity_files = discover_antigravity_sessions(gemini_dir)
    if antigravity_files:
        print(f"Found {len(antigravity_files)} Antigravity session files.")
        for af, kind in antigravity_files:
            print(f"Parsing Antigravity log: {af}...")
            if kind == "transcript":
                session_data = parse_antigravity_transcript(af)
            else:
                session_data = parse_antigravity_session(af)
            if session_data:
                all_sessions.append(session_data)
    else:
        print(f"No Antigravity sessions found under {gemini_dir}")

    # Redact secrets before ANYTHING is written to disk (privacy: these are raw transcripts).
    all_sessions = [redact_session(s) for s in all_sessions]

    # Write to a clean JSON file
    output_dir = Path(__file__).resolve().parents[4] / "extracted"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-computed attention signals to direct deep reading (not findings themselves).
    signals = compute_signals(all_sessions)
    signals_path = output_dir / "signals.json"
    with open(signals_path, "w", encoding="utf-8") as f:
        json.dump(signals, f, indent=2)
    print(f"Saved attention signals to {signals_path}")

    # One readable file per session — the unit the MAP step fans out over.
    sessions_dir = output_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    for sess in all_sessions:
        (sessions_dir / f"{sess['session_id']}.md").write_text(
            render_session_markdown(sess), encoding="utf-8")
    print(f"Saved {len(all_sessions)} per-session chunk files to {sessions_dir}")

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
