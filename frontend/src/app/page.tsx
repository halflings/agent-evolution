"use client";

import { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

interface SessionSummary {
  session_id: string;
  project_path: string;
  project_name: string;
  title: string;
  turns_count: number;
}

interface FailurePattern {
  session: string;
  project: string;
  type: string;
  description: string;
}

interface RecommendedRule {
  name: string;
  description: string;
}

interface RecommendedSkill {
  name: string;
  description: string;
  instructions: string;
}

interface PastPrompt {
  session: string;
  project: string;
  prompt: string;
}

interface ImprovementPlan {
  failures: FailurePattern[];
  rules: RecommendedRule[];
  skills: RecommendedSkill[];
  prompts: PastPrompt[];
}

interface ToolCall {
  id: string;
  name: string;
  input: any;
}

interface Turn {
  role: string;
  type?: string;
  content?: string;
  thinking?: string;
  tool_calls?: ToolCall[];
  model?: string;
  timestamp?: string;
}

interface SessionDetail extends SessionSummary {
  turns: Turn[];
}

export default function Home() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeView, setActiveView] = useState<"plan" | string>("plan");
  const [plan, setPlan] = useState<ImprovementPlan | null>(null);
  const [activeSession, setActiveSession] = useState<SessionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Edit states for rules and skills
  const [editedRules, setEditedRules] = useState<Record<number, string>>({});
  const [editedSkillInstructions, setEditedSkillInstructions] = useState<Record<number, string>>({});
  const [targetProjectPaths, setTargetProjectPaths] = useState<Record<string, string>>({});

  // Custom rule generator state
  const [customRuleName, setCustomRuleName] = useState("");
  const [customRuleContent, setCustomRuleContent] = useState("");

  const showNotification = (message: string, type: "success" | "error" = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (err) {
      console.error("Error fetching sessions:", err);
    }
  };

  const fetchPlan = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/improvement-plan`);
      if (res.ok) {
        const data = await res.json();
        setPlan(data);
        // Initialize edited states
        const rulesMap: Record<number, string> = {};
        data.rules.forEach((r: RecommendedRule, idx: number) => {
          rulesMap[idx] = r.description;
        });
        setEditedRules(rulesMap);

        const skillsMap: Record<number, string> = {};
        data.skills.forEach((s: RecommendedSkill, idx: number) => {
          skillsMap[idx] = s.instructions;
        });
        setEditedSkillInstructions(skillsMap);
      }
    } catch (err) {
      console.error("Error fetching plan:", err);
    }
  };

  const fetchSessionDetail = async (id: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${id}`);
      if (res.ok) {
        const data = await res.json();
        setActiveSession(data);
      }
    } catch (err) {
      console.error("Error fetching session detail:", err);
      showNotification("Failed to load session details", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch(`${API_BASE}/api/refresh`, { method: "POST" });
      if (res.ok) {
        await fetchSessions();
        await fetchPlan();
        showNotification("History refreshed & analyzed successfully!");
        if (activeView !== "plan") {
          fetchSessionDetail(activeView);
        }
      } else {
        showNotification("Failed to refresh history", "error");
      }
    } catch (err) {
      console.error("Error refreshing:", err);
      showNotification("Error connecting to backend server", "error");
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleApplyRule = async (ruleIndex: number, ruleName: string, defaultPath: string) => {
    const projectPath = targetProjectPaths[`rule-${ruleIndex}`] || defaultPath;
    const ruleContent = editedRules[ruleIndex];

    if (!projectPath) {
      showNotification("Please specify a target project path", "error");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/apply-rule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_path: projectPath,
          rule_name: ruleName,
          rule_content: ruleContent
        })
      });
      const data = await res.json();
      if (res.ok) {
        showNotification(`Rule applied successfully to ${projectPath}!`);
      } else {
        showNotification(data.detail || "Failed to apply rule", "error");
      }
    } catch (err) {
      showNotification("Error applying rule", "error");
    }
  };

  const handleApplySkill = async (skillIndex: number, skill: RecommendedSkill, defaultPath: string) => {
    const projectPath = targetProjectPaths[`skill-${skillIndex}`] || defaultPath;
    const instructions = editedSkillInstructions[skillIndex];

    if (!projectPath) {
      showNotification("Please specify a target project path", "error");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/apply-skill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_path: projectPath,
          skill_name: skill.name,
          skill_description: skill.description,
          skill_instructions: instructions
        })
      });
      const data = await res.json();
      if (res.ok) {
        showNotification(`Skill ${skill.name} successfully installed to ${projectPath}!`);
      } else {
        showNotification(data.detail || "Failed to install skill", "error");
      }
    } catch (err) {
      showNotification("Error installing skill", "error");
    }
  };

  const handleApplyCustomRule = async (projectPath: string) => {
    if (!projectPath) {
      showNotification("Please specify a target project path", "error");
      return;
    }
    if (!customRuleName || !customRuleContent) {
      showNotification("Rule name and content are required", "error");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/apply-rule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_path: projectPath,
          rule_name: customRuleName,
          rule_content: customRuleContent
        })
      });
      const data = await res.json();
      if (res.ok) {
        showNotification(`Custom rule applied to ${projectPath}!`);
        setCustomRuleName("");
        setCustomRuleContent("");
      } else {
        showNotification(data.detail || "Failed to apply custom rule", "error");
      }
    } catch (err) {
      showNotification("Error applying rule", "error");
    }
  };

  useEffect(() => {
    fetchSessions();
    fetchPlan();
  }, []);

  const handleViewChange = (view: string) => {
    setActiveView(view);
    if (view === "plan") {
      setActiveSession(null);
      fetchPlan();
    } else {
      fetchSessionDetail(view);
    }
  };

  // Get a list of unique project paths from the sessions
  const knownProjects = Array.from(new Set(sessions.map(s => s.project_path)));

  return (
    <div className="flex h-screen bg-zinc-50 font-sans text-zinc-800">
      {/* Toast Notification */}
      {notification && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2 rounded-lg px-4 py-3 shadow-lg transition-all duration-300 ${
          notification.type === "success" ? "bg-emerald-500 text-white" : "bg-rose-500 text-white"
        }`}>
          <span>{notification.message}</span>
        </div>
      )}

      {/* Sidebar */}
      <aside className="w-80 border-r border-zinc-200 bg-white flex flex-col">
        <div className="p-6 border-b border-zinc-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-indigo-500 animate-pulse"></span>
            <h1 className="font-semibold text-lg tracking-tight text-zinc-900">Agent Evolution</h1>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 text-zinc-600 disabled:opacity-50 transition-colors flex items-center justify-center"
            title="Refresh history from disk"
          >
            <svg
              className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3m0 0l3 3m-3-3v12" />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <div className="p-4 border-b border-zinc-100 bg-zinc-50/50">
          <button
            onClick={() => handleViewChange("plan")}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-medium text-sm transition-all duration-200 ${
              activeView === "plan"
                ? "bg-indigo-50 text-indigo-700 shadow-sm border border-indigo-100"
                : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100/80 border border-transparent"
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
            </svg>
            Global Analysis Plan
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider px-2 block mb-1">
            Past Conversations
          </span>
          {sessions.map((sess) => (
            <button
              key={sess.session_id}
              onClick={() => handleViewChange(sess.session_id)}
              className={`w-full text-left p-3.5 rounded-xl border transition-all duration-200 flex flex-col gap-1.5 ${
                activeView === sess.session_id
                  ? "bg-white border-indigo-400 shadow-md ring-1 ring-indigo-400/20"
                  : "bg-white/60 hover:bg-white border-zinc-100 hover:border-zinc-200"
              }`}
            >
              <span className="font-semibold text-sm text-zinc-900 line-clamp-1">
                {sess.title}
              </span>
              <span className="text-xs text-zinc-500 font-mono truncate">
                {sess.project_name}
              </span>
              <div className="flex items-center justify-between mt-1 text-[10px] text-zinc-400">
                <span>{sess.turns_count} turns</span>
                <span className="font-mono">{sess.session_id.substring(0, 8)}</span>
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden bg-zinc-50">
        {activeView === "plan" ? (
          /* Global Plan View */
          <div className="flex-1 overflow-y-auto p-8 max-w-5xl mx-auto w-full space-y-8">
            <div>
              <h2 className="text-2xl font-semibold text-zinc-900 tracking-tight">Global Agent Evolution Plan</h2>
              <p className="text-sm text-zinc-500 mt-1">Synthesized guidelines and custom skills generated from your past active sessions.</p>
            </div>

            {/* Failure Patterns */}
            {plan && plan.failures && plan.failures.length > 0 && (
              <section className="bg-white rounded-2xl border border-zinc-200/80 p-6 shadow-sm space-y-4">
                <div className="flex items-center gap-2 border-b border-zinc-100 pb-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                  <h3 className="font-semibold text-base text-zinc-900">Identified Failure & Inefficiency Patterns</h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {plan.failures.map((fail, idx) => (
                    <div key={idx} className="p-4 rounded-xl bg-amber-50/40 border border-amber-200/50 flex flex-col gap-1.5">
                      <span className="text-xs font-semibold text-amber-800 uppercase tracking-wider">{fail.type}</span>
                      <p className="text-sm text-zinc-700 leading-relaxed font-medium">{fail.description}</p>
                      <span className="text-[10px] text-zinc-400 mt-2 font-mono">Session: {fail.session}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Recommended Rules */}
            <section className="space-y-4">
              <h3 className="font-semibold text-lg text-zinc-900">Recommended System Rules (AGENTS.md)</h3>
              <div className="space-y-4">
                {plan?.rules.map((rule, idx) => (
                  <div key={idx} className="bg-white rounded-2xl border border-zinc-200/80 p-6 shadow-sm flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold text-base text-zinc-900">{rule.name}</h4>
                      <span className="text-xs bg-zinc-100 text-zinc-600 px-2.5 py-1 rounded-full font-medium">Standard Rule</span>
                    </div>
                    <textarea
                      value={editedRules[idx] || ""}
                      onChange={(e) => setEditedRules({ ...editedRules, [idx]: e.target.value })}
                      className="w-full h-24 p-3 rounded-xl border border-zinc-200 font-mono text-xs bg-zinc-50/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all resize-none"
                    />
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2 border-t border-zinc-100">
                      <div className="flex-1">
                        <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Target Project Path</label>
                        <select
                          onChange={(e) => setTargetProjectPaths({ ...targetProjectPaths, [`rule-${idx}`]: e.target.value })}
                          className="w-full text-xs p-2.5 rounded-lg border border-zinc-200 bg-white"
                          value={targetProjectPaths[`rule-${idx}`] || ""}
                        >
                          <option value="">-- Select Project --</option>
                          {knownProjects.map((p, pIdx) => (
                            <option key={pIdx} value={p}>{p}</option>
                          ))}
                        </select>
                      </div>
                      <div className="flex items-end justify-end">
                        <button
                          onClick={() => handleApplyRule(idx, rule.name, knownProjects[0] || "")}
                          className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs transition-colors flex items-center gap-2"
                        >
                          Apply to AGENTS.md
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Recommended Skills */}
            <section className="space-y-4">
              <h3 className="font-semibold text-lg text-zinc-900">Recommended Custom Skills</h3>
              <div className="space-y-4">
                {plan?.skills.map((skill, idx) => (
                  <div key={idx} className="bg-white rounded-2xl border border-zinc-200/80 p-6 shadow-sm flex flex-col gap-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-semibold text-base text-zinc-900">{skill.name}</h4>
                        <p className="text-xs text-zinc-500 mt-1">{skill.description}</p>
                      </div>
                      <span className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-100/50 px-2.5 py-1 rounded-full font-medium">Skill Manifest</span>
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">SKILL.md Instructions</label>
                      <textarea
                        value={editedSkillInstructions[idx] || ""}
                        onChange={(e) => setEditedSkillInstructions({ ...editedSkillInstructions, [idx]: e.target.value })}
                        className="w-full h-36 p-3 rounded-xl border border-zinc-200 font-mono text-xs bg-zinc-50/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all resize-none"
                      />
                    </div>
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2 border-t border-zinc-100">
                      <div className="flex-1">
                        <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Target Project Path</label>
                        <select
                          onChange={(e) => setTargetProjectPaths({ ...targetProjectPaths, [`skill-${idx}`]: e.target.value })}
                          className="w-full text-xs p-2.5 rounded-lg border border-zinc-200 bg-white"
                          value={targetProjectPaths[`skill-${idx}`] || ""}
                        >
                          <option value="">-- Select Project --</option>
                          {knownProjects.map((p, pIdx) => (
                            <option key={pIdx} value={p}>{p}</option>
                          ))}
                        </select>
                      </div>
                      <div className="flex items-end justify-end">
                        <button
                          onClick={() => handleApplySkill(idx, skill, knownProjects[0] || "")}
                          className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs transition-colors flex items-center gap-2"
                        >
                          Install Skill Directory
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Custom Rules Appender */}
            <section className="bg-white rounded-2xl border border-zinc-200/80 p-6 shadow-sm space-y-4">
              <h3 className="font-semibold text-base text-zinc-900">Add a Custom Rule Directly</h3>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-zinc-500 mb-1">Rule Name</label>
                    <input
                      type="text"
                      placeholder="e.g., Avoid standard imports"
                      value={customRuleName}
                      onChange={(e) => setCustomRuleName(e.target.value)}
                      className="w-full p-2.5 border border-zinc-200 rounded-xl text-xs bg-zinc-50/50 focus:bg-white focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-zinc-500 mb-1">Target Project</label>
                    <select
                      onChange={(e) => setTargetProjectPaths({ ...targetProjectPaths, "custom-rule": e.target.value })}
                      className="w-full text-xs p-2.5 rounded-xl border border-zinc-200 bg-white"
                      value={targetProjectPaths["custom-rule"] || ""}
                    >
                      <option value="">-- Select Project --</option>
                      {knownProjects.map((p, pIdx) => (
                        <option key={pIdx} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-zinc-500 mb-1">Rule Description / Body</label>
                  <textarea
                    placeholder="Provide the exact guidelines that you want the coding agents to follow."
                    value={customRuleContent}
                    onChange={(e) => setCustomRuleContent(e.target.value)}
                    className="w-full h-24 p-3 border border-zinc-200 rounded-xl text-xs bg-zinc-50/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all resize-none"
                  />
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={() => handleApplyCustomRule(targetProjectPaths["custom-rule"] || knownProjects[0] || "")}
                    className="px-4 py-2.5 bg-zinc-900 hover:bg-zinc-800 text-white rounded-xl text-xs font-semibold transition-colors"
                  >
                    Save Custom Rule
                  </button>
                </div>
              </div>
            </section>
          </div>
        ) : (
          /* Session Conversation View */
          <div className="flex-1 flex flex-col overflow-hidden">
            {isLoading ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-3">
                <span className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></span>
                <span className="text-xs text-zinc-400 font-medium">Loading session details...</span>
              </div>
            ) : activeSession ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Header */}
                <header className="p-6 border-b border-zinc-200 bg-white flex flex-col sm:flex-row justify-between gap-4 items-start sm:items-center">
                  <div>
                    <h2 className="font-semibold text-lg text-zinc-900 leading-tight">{activeSession.title}</h2>
                    <span className="text-xs text-indigo-600 font-mono mt-1 block">Project: {activeSession.project_path}</span>
                  </div>
                  <div className="text-[10px] text-zinc-400 bg-zinc-100 border border-zinc-200/50 rounded-lg px-2.5 py-1 font-mono uppercase tracking-wider">
                    Session ID: {activeSession.session_id.substring(0, 16)}...
                  </div>
                </header>

                {/* Conversation Feed */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  {activeSession.turns.map((turn, idx) => {
                    const isUser = turn.role === "user";
                    const isToolResult = turn.type === "tool_result";
                    const isSystem = turn.role === "system";

                    if (isSystem) {
                      return (
                        <div key={idx} className="flex justify-center">
                          <div className="bg-zinc-100 border border-zinc-200/60 rounded-xl px-4 py-2 text-xs text-zinc-600 font-mono max-w-2xl text-center">
                            <span className="font-bold mr-1">System Action:</span>
                            {turn.content}
                          </div>
                        </div>
                      );
                    }

                    if (isUser && isToolResult) {
                      return (
                        <div key={idx} className="flex justify-start">
                          <div className="w-full max-w-4xl border border-zinc-200 bg-zinc-900 rounded-xl overflow-hidden font-mono text-[11px] text-zinc-300">
                            <div className="bg-zinc-800 px-4 py-2 text-[10px] text-zinc-400 font-semibold flex items-center justify-between border-b border-zinc-950">
                              <span>Tool Execution Results</span>
                              <span className="opacity-65">{turn.timestamp?.substring(11, 19)}</span>
                            </div>
                            <pre className="p-4 overflow-x-auto max-h-72 whitespace-pre-wrap">
                              <code>{turn.content}</code>
                            </pre>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <div key={idx} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-2xl rounded-2xl p-5 shadow-sm space-y-3 ${
                          isUser ? "bg-indigo-600 text-white rounded-tr-none" : "bg-white border border-zinc-200 rounded-tl-none text-zinc-800"
                        }`}>
                          <div className={`flex items-center justify-between text-[10px] ${isUser ? "text-indigo-200" : "text-zinc-400"} font-medium`}>
                            <span>{isUser ? "User Prompt" : `Assistant (${turn.model || "Claude"})`}</span>
                            <span>{turn.timestamp?.substring(11, 19)}</span>
                          </div>

                          {/* Assistant Thinking */}
                          {!isUser && turn.thinking && (
                            <details className="text-xs border border-zinc-100 rounded-lg p-2.5 bg-zinc-50 text-zinc-600">
                              <summary className="font-semibold cursor-pointer outline-none select-none">Thinking Process</summary>
                              <pre className="mt-2 whitespace-pre-wrap font-mono text-[10px] max-h-48 overflow-y-auto leading-relaxed">{turn.thinking}</pre>
                            </details>
                          )}

                          {/* Tool Calls listing */}
                          {!isUser && turn.tool_calls && turn.tool_calls.length > 0 && (
                            <div className="space-y-1.5">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 block">Invoked Tools</span>
                              {turn.tool_calls.map((tc, tcIdx) => (
                                <div key={tcIdx} className="bg-zinc-50 border border-zinc-100 rounded-lg p-2 font-mono text-[10px] text-zinc-600">
                                  <span className="font-bold text-zinc-800">{tc.name}</span>({JSON.stringify(tc.input)})
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Content Body */}
                          <div className={`text-sm leading-relaxed whitespace-pre-wrap ${isUser ? "font-medium" : ""}`}>
                            {turn.content}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Session specific actions footer */}
                <footer className="p-6 border-t border-zinc-200 bg-white">
                  <h3 className="font-semibold text-sm text-zinc-800 mb-3">Dynamically generate rule from this session</h3>
                  <div className="flex gap-4 items-stretch">
                    <input
                      type="text"
                      placeholder="Rule Title (e.g., Refactoring guidelines)"
                      value={customRuleName}
                      onChange={(e) => setCustomRuleName(e.target.value)}
                      className="flex-1 p-2.5 border border-zinc-200 rounded-xl text-xs"
                    />
                    <button
                      onClick={() => {
                        const ruleText = `Based on conversation session ${activeSession.session_id}:\n` + 
                          activeSession.turns
                            .filter(t => t.role === "user" && t.type === "prompt")
                            .map(t => `- User requested: ${t.content}`)
                            .join("\n");
                        setCustomRuleContent(ruleText);
                        setCustomRuleName(`Refactor Guidelines for ${activeSession.project_name}`);
                        showNotification("Template rule compiled! See Global Analysis Plan to customize and save it.", "success");
                        handleViewChange("plan");
                      }}
                      className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold transition-colors flex items-center gap-1.5"
                    >
                      Draft Rule Template
                    </button>
                  </div>
                </footer>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-zinc-400">
                Select a session to view conversation details
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
