---
name: agent-evolution
description: |
  Analyzes past conversation histories from Claude Code and Antigravity logs for any workspace,
  reads every trace carefully (via subagents or iteration), distills GENERAL, transferable
  guidelines that improve the agent on new/unrelated projects, and stages them as AGENTS.md
  rules and custom skills — with cited evidence, confidence calibration, and de-duplication.
---

# Agent Evolution Skill

Use this skill to analyze past conversation trajectories (Claude Code and Antigravity) to
diagnose recurring agent behaviors, extract what worked, and produce **general working rules**
that make the agent better everywhere — not just on the exact projects in the traces.

## Guiding principles (read first)

These principles govern every step below. When in doubt, favor them over volume of output.

1. **Read everything; sample nothing.** The corpus is usually far too large for one context
   window. Do **not** skim or rely on keyword/substring matching to reach conclusions. Read the
   full traces — fan out with subagents (one per session/chunk) or iterate session-by-session so
   that 100% of the material is actually read by *some* agent. Pre-computed signals only tell you
   *where to look harder*; they never decide a finding.
2. **Generalize; don't overfit.** The point is a better agent on future, unrelated work. Every
   rule must pass the test: *"Strip all project-specific nouns — would this still guide behavior
   on a different project/stack?"* If not, it is a project fact, not a global rule (see routing).
3. **Cite evidence or drop it.** Every finding must point to concrete turns (session id + turn
   range + a verbatim quote). No evidence → it does not go in the plan.
4. **Calibrate and threshold.** Distinguish an explicit *user preference* (authoritative even
   from one instance) from an *inferred pattern* (promote to a rule only if it recurs across ≥2
   distinct sessions/projects). One-offs stay as notes, not rules.
5. **Scale ambition to signal.** With few sessions or weak signal, say so and produce a handful
   of high-confidence items. A short, sharp list beats a long generic one.
6. **Weight successes too.** Reinforcing what reliably worked is as valuable as fixing failures.

## Execution workflow

### Step 1 — Compile the history + attention signals
Run the extraction script (zero external deps, any Python 3):

```bash
python3 extract_history.py
```

This produces, under `extracted/`:
* `extracted_conversations.json` — unified, **redacted** database of all sessions.
* `extracted_conversations.md` — human-readable rendering.
* `sessions/<session_id>.md` — one readable file per session (the unit you fan out over).
* `signals.json` — pre-computed *attention markers* per session (interruptions, tool errors,
  repeated commands, edit/revert loops). These direct where to read closely; they are **not**
  findings.

### Step 2 — MAP: read every trace in full (subagents / iteration)
For each session (splitting very long sessions into turn-range chunks), have an agent read the
**entire** chunk from `sessions/` and emit structured candidate observations. Fan these out as
parallel read-only subagents when the corpus is large, or iterate one at a time if not.

Give each reader this **subtle-issue rubric** — look for behaviors, not keywords:
* **Rework loops** — edit → user correction → re-edit on the same target (logic or aesthetic churn).
* **Premature "done"** — success claimed before running the check that later surfaced a bug.
* **Silent inefficiency** — re-reading the same file, re-deriving known context, needless server/process restarts.
* **Assumption failures** — acting on a guessed path / API / config that proved wrong.
* **Violated stated preferences** — user said X once; agent later did not-X.
* **Over-engineering / ignored constraints** — did more (or other) than asked.
* **Communication gaps** — failed to surface a tradeoff, or plowed ahead where it should have asked.
* **What worked** — verification loops, workflows, or phrasings that reliably produced good outcomes.

Each candidate observation must carry: a short behavioral description, `session_id`, turn range,
a **verbatim quote** as evidence, and whether it is a `user-preference` or an `inferred-pattern`.

### Step 3 — REDUCE: synthesize, generalize, calibrate
Collect all candidates and:
* **Dedupe & count.** Merge equivalent observations; record how many distinct sessions/projects each spans.
* **Apply the generalization filter** (principle 2) to every candidate rule. Rephrase it
  stack-agnostically, keeping the concrete trace only as a *cited example* — not as the rule
  itself. (e.g. "verify env-var typing in your build tool" — not "add vite/client for import.meta.env".)
* **Threshold** (principle 4): promote to a rule only if it recurs ≥2× or is an explicit user preference.
* **Check against what already exists.** Read the target `AGENTS.md` / config and any project
  `CLAUDE.md`; do not "discover" rules the user already wrote.

Write the result to `extracted/agent_evolution_plan.json` with this schema:
```json
{
  "meta": { "sessions_analyzed": 0, "signal_strength": "low|medium|high", "notes": "" },
  "failures": [
    {
      "type": "Rework loop",
      "scope": "global | project",
      "description": "General behavioral observation...",
      "evidence": [ { "session": "<id>", "turns": "420-471", "quote": "verbatim user/agent text" } ],
      "frequency": 2,
      "confidence": "low|medium|high",
      "kind": "user-preference | inferred-pattern"
    }
  ],
  "successes": [
    { "description": "What worked and why", "evidence": [ { "session": "<id>", "turns": "..", "quote": ".." } ] }
  ],
  "global_rules": [
    { "name": "General, transferable rule", "description": "Stack-agnostic guidance.", "example": "concrete trace instance" }
  ],
  "project_rules": [
    { "project": "/abs/path", "name": "Project-specific rule", "description": "Facts true only for this project." }
  ],
  "skills": [
    { "name": "kebab-name", "description": "...", "instructions": "Step-by-step, generic where possible." }
  ]
}
```

### Step 4 — Route outputs (don't dump everything into global config)
Merge — never blind-append — using the `scope`/routing above:
* **`global_rules`** → the user's global rules file (default `~/AGENTS.md`; ask if a different
  target such as `~/.clauderc` or `~/.gemini/GEMINI.md` is preferred). Only stack-agnostic
  behavioral rules belong here.
* **`project_rules`** → that project's own `AGENTS.md` (`<project>/AGENTS.md`), not global config.
* Before writing, **read existing rules and dedupe/supersede** conflicting or redundant entries so
  configs stay tight over repeated runs. Preserve clean markdown and existing structure.

### Step 5 — Render the plan
```bash
python3 agent_evolution.py
```
Generates `extracted/agent_evolution_plan.md` from the JSON. This step has **no side effects** —
it does not start any server.

### Step 6 — (Optional) Web cockpit
Only if the user asks to inspect trajectories visually. The dashboard binds to `127.0.0.1`
(loopback only) because it serves raw transcripts:
```bash
python3 agent_evolution.py --serve   # or: uv run python run_app.py
```

### Step 7 — Report
Present a concise visual summary (ASCII box) plus:
1. Identified patterns, each with its evidence citation, frequency, and confidence.
2. What worked (successes worth reinforcing).
3. Where each rule was routed (global vs which project), and clickable links to the updated files
   and `extracted/agent_evolution_plan.md`.
4. If signal was thin, say so honestly rather than padding the list.

```
┌────────────────────────────────────────────────────────┐
│             AGENT EVOLUTION ANALYSIS REPORT              │
├────────────────────────────────────────────────────────┤
│  Sessions read (in full): [N]   Signal: [low/med/high]   │
│  Patterns (evidence-backed): [N]   Successes: [N]        │
├────────────────────────────────────────────────────────┤
│  [x] <general rule>            -> ~/AGENTS.md            │
│  [x] <project fact>            -> <project>/AGENTS.md    │
└────────────────────────────────────────────────────────┘
```
