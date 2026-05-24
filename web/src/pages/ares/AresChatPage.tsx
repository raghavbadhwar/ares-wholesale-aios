/**
 * AresChatPage.tsx
 *
 * Full-featured chat interface for the Ares AIOS dashboard.
 * Connects to /api/chat WebSocket, renders a premium message thread,
 * supports markdown, code blocks, streaming indicators, and session history.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Bot,
  BookOpen,
  CheckCircle2,
  ChevronDown,

  Clock,
  Command,
  Copy,
  Download,
  FileText,
  Loader2,
  MessageSquare,
  Paperclip,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  User,
  X,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { HERMES_BASE_PATH, fetchJSON } from "@/lib/api";
import type { SkillInfo } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

type Role = "user" | "assistant" | "system" | "error";

interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  timestamp: Date;
  thinking?: boolean;
  tool?: string;
  files?: ChatFile[];
}

interface SessionSummary {
  id: string;
  started_at: string;
  title?: string;
  last_message?: string;
  message_count?: number;
  model?: string;
}

interface StoredSessionMessage {
  id?: number;
  role: Role | string;
  content: unknown;
  timestamp?: number;
}

interface ChatFile {
  name: string;
  path: string;
  url: string;
  size?: number | null;
  type?: string;
  kind?: "attachment" | "created" | "file";
}

interface ChatCommand {
  id: string;
  label: string;
  value: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  kind: "client" | "prompt" | "skill";
}

// ─── Token from window (injected by backend) ─────────────────────────────────
function getSessionToken(): string {
  return (window as any).__HERMES_SESSION_TOKEN__ || (window as any).__ARES_SESSION_TOKEN__ || "";
}

// ─── Markdown-ish renderer ────────────────────────────────────────────────────
// Simple inline renderer — no heavy dep needed for the dashboard
function renderContent(text: string): React.ReactNode {
  if (!text) return null;

  // Split on code blocks first
  const parts = text.split(/(```[\s\S]*?```|`[^`]+`)/g);

  return parts.map((part, i) => {
    // Fenced code block
    if (part.startsWith("```") && part.endsWith("```")) {
      const lines = part.slice(3, -3).split("\n");
      const lang = lines[0]?.trim() || "";
      const code = lines.slice(lang ? 1 : 0).join("\n");
      return (
        <div key={i} className="my-3 rounded-xl overflow-hidden border border-zinc-800/80">
          {lang && (
            <div className="flex items-center justify-between px-4 py-1.5 bg-zinc-900 border-b border-zinc-800">
              <span className="text-[10px] font-mono text-amber-500/70 uppercase tracking-widest">{lang}</span>
              <CopyBtn text={code} />
            </div>
          )}
          <pre className="p-4 text-xs font-mono text-emerald-300 overflow-x-auto bg-zinc-950/60 leading-relaxed">
            <code>{code}</code>
          </pre>
        </div>
      );
    }
    // Inline code
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={i} className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-emerald-400 text-[11px] font-mono">
          {part.slice(1, -1)}
        </code>
      );
    }
    // Normal text — render line breaks and bold
    return (
      <span key={i}>
        {part.split("\n").map((line, j) => {
          // Bold **text**
          const boldParts = line.split(/(\*\*[^*]+\*\*)/g);
          const rendered = boldParts.map((bp, k) =>
            bp.startsWith("**") && bp.endsWith("**")
              ? <strong key={k} className="font-bold text-zinc-100">{bp.slice(2, -2)}</strong>
              : <span key={k}>{bp}</span>
          );
          return (
            <span key={j}>
              {rendered}
              {j < part.split("\n").length - 1 && <br />}
            </span>
          );
        })}
      </span>
    );
  });
}

// ─── Copy button ──────────────────────────────────────────────────────────────
function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button onClick={copy} className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-200 transition-colors">
      {copied ? <CheckCircle2 className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes < 0) return "file";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function chatFileHref(file: ChatFile, download = false): string {
  const raw = file.url || `/api/chat/files?path=${encodeURIComponent(file.path)}`;
  const prefix = raw.startsWith("http") ? "" : HERMES_BASE_PATH;
  const separator = raw.includes("?") ? "&" : "?";
  return `${prefix}${raw}${download ? `${separator}download=true` : ""}`;
}

function FileCards({ files }: { files?: ChatFile[] }) {
  if (!files?.length) return null;
  return (
    <div className="mt-2 grid gap-2">
      {files.map((file) => (
        <div
          key={`${file.path}-${file.kind || "file"}`}
          className="flex min-w-0 items-center gap-2 rounded-xl border border-zinc-700/50 bg-zinc-950/60 px-3 py-2"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-amber-500/20 bg-amber-500/10">
            <FileText className="h-4 w-4 text-amber-400" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-zinc-200">{file.name}</p>
            <p className="truncate text-[10px] text-zinc-600">
              {file.kind === "created" ? "Created file" : "Attached file"} · {formatBytes(file.size)} · {file.path}
            </p>
          </div>
          <a
            href={chatFileHref(file, true)}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
            title="Download file"
          >
            <Download className="h-3.5 w-3.5" />
          </a>
        </div>
      ))}
    </div>
  );
}

// ─── Thinking indicator ────────────────────────────────────────────────────────
function ThinkingIndicator({ tool }: { tool?: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      <div className="h-7 w-7 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0">
        <Bot className="h-4 w-4 text-amber-500" />
      </div>
      <div className="flex items-center gap-2">
        {tool ? (
          <span className="text-xs text-amber-400/80 font-mono">
            <Zap className="h-3 w-3 inline mr-1 text-amber-500" />
            {tool}…
          </span>
        ) : (
          <span className="text-xs text-zinc-500 italic">Thinking</span>
        )}
        <span className="flex gap-1">
          {[0, 1, 2].map(i => (
            <span key={i} className="h-1.5 w-1.5 rounded-full bg-amber-500/60 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </span>
      </div>
    </div>
  );
}

// ─── Message bubble ───────────────────────────────────────────────────────────
function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  const isError = msg.role === "error";

  if (msg.thinking) return <ThinkingIndicator tool={msg.tool} />;

  return (
    <div className={cn("flex gap-3 px-4 py-2 group", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div className={cn(
        "h-7 w-7 rounded-full flex items-center justify-center shrink-0 mt-0.5",
        isUser
          ? "bg-amber-500/15 border border-amber-500/25"
          : isError
            ? "bg-red-950/40 border border-red-900/30"
            : "bg-zinc-800/80 border border-zinc-700/40"
      )}>
        {isUser
          ? <User className="h-3.5 w-3.5 text-amber-400" />
          : isError
            ? <AlertCircle className="h-3.5 w-3.5 text-red-400" />
            : <Bot className="h-3.5 w-3.5 text-amber-500" />}
      </div>

      {/* Bubble */}
      <div className={cn("flex flex-col gap-1 max-w-[80%]", isUser && "items-end")}>
        <div className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
          isUser
            ? "bg-amber-500/10 border border-amber-500/20 text-amber-50 rounded-tr-sm"
            : isError
              ? "bg-red-950/20 border border-red-900/30 text-red-300 rounded-tl-sm"
              : "bg-zinc-800/50 border border-zinc-700/40 text-zinc-200 rounded-tl-sm"
        )}>
          {isUser ? msg.content : <div className="prose-content">{renderContent(msg.content)}</div>}
          <FileCards files={msg.files} />
        </div>
        <div className={cn("flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity", isUser && "flex-row-reverse")}>
          <span className="text-[10px] text-zinc-600 font-mono">
            {msg.timestamp.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true })}
          </span>
          {!isUser && (
            <CopyBtn text={msg.content} />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Session list sidebar item ─────────────────────────────────────────────────
function SessionItem({ session, active, onClick }: { session: SessionSummary; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex flex-col items-start gap-0.5 p-3 rounded-xl border text-left transition-all",
        active
          ? "bg-amber-500/10 border-amber-500/20 text-amber-200"
          : "border-transparent hover:bg-zinc-900/60 hover:border-zinc-800 text-zinc-400 hover:text-zinc-200"
      )}
    >
      <span className="text-xs font-bold truncate w-full">
        {session.title || session.last_message?.slice(0, 40) || "New conversation"}
      </span>
      <div className="flex items-center gap-2 text-[10px]">
        <Clock className="h-2.5 w-2.5 text-zinc-600" />
        <span className="text-zinc-600">{new Date(session.started_at).toLocaleDateString("en-IN")}</span>
        {session.message_count && <span className="text-zinc-700">• {session.message_count} msgs</span>}
      </div>
    </button>
  );
}

// ─── Suggested prompts ────────────────────────────────────────────────────────
const SUGGESTED_PROMPTS = [
  "What's the status of pending approvals?",
  "Generate a daily business brief",
  "Which invoices are overdue?",
  "Run stock radar and tell me what's low",
  "What orders are pending dispatch today?",
  "Help me prepare GSTR-1 for this month",
  "Who are my top customers by revenue?",
  "Summarise today's payment collections",
];

const BASE_COMMANDS: ChatCommand[] = [
  { id: "new", label: "/new", value: "/new", description: "Start a fresh chat", icon: Plus, kind: "client" },
  { id: "clear", label: "/clear", value: "/clear", description: "Clear the visible thread", icon: Trash2, kind: "client" },
  { id: "history", label: "/history", value: "/history", description: "Open conversation history", icon: Clock, kind: "client" },
  { id: "skills", label: "/skills", value: "/skills", description: "Show enabled skills", icon: BookOpen, kind: "client" },
  { id: "help", label: "/help", value: "/help", description: "Show Ares chat commands", icon: Command, kind: "prompt" },
  { id: "memory", label: "/memory", value: "/memory", description: "Show memory status", icon: Sparkles, kind: "prompt" },
  { id: "validate-inputs", label: "/validate-inputs", value: "/validate-inputs", description: "Check intake files and blockers", icon: CheckCircle2, kind: "prompt" },
  { id: "daily-brief", label: "/daily-brief", value: "/daily-brief", description: "Generate the owner daily brief", icon: MessageSquare, kind: "prompt" },
  { id: "stock-radar", label: "/stock-radar", value: "/stock-radar", description: "Find low stock and reorder risks", icon: Zap, kind: "prompt" },
];

// ─── Main Chat Page ────────────────────────────────────────────────────────────
export default function AresChatPage({ businessName }: { businessName?: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [model, setModel] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [wsError, setWsError] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [showSessions, setShowSessions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [showSkillsPanel, setShowSkillsPanel] = useState(false);
  const [attachments, setAttachments] = useState<ChatFile[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const reconnectTimer = useRef<any>(null);

  const uid = () => Math.random().toString(36).slice(2, 10);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, 50);
  }, []);

  // Fetch past sessions for the sidebar
  const loadSessions = useCallback(async () => {
    try {
      const data = await fetchJSON<{ sessions: SessionSummary[] }>("/api/sessions?limit=20");
      setSessions(data.sessions || []);
    } catch (_) {}
  }, []);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  useEffect(() => {
    fetchJSON<SkillInfo[]>("/api/skills")
      .then((data) => setSkills((data || []).filter((skill) => skill.enabled !== false)))
      .catch(() => setSkills([]));
  }, []);

  const skillCommands = useMemo<ChatCommand[]>(() => {
    return skills.slice(0, 80).map((skill) => {
      const slug = skill.name
        .toLowerCase()
        .replace(/[_\s]+/g, "-")
        .replace(/[^a-z0-9-]/g, "")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "");
      return {
        id: `skill:${skill.name}`,
        label: `/${slug || skill.name}`,
        value: `/${slug || skill.name}`,
        description: skill.description || "Invoke this skill",
        icon: BookOpen,
        kind: "skill",
      };
    });
  }, [skills]);

  const commandMatches = useMemo(() => {
    const raw = inputText.trimStart();
    if (!raw.startsWith("/")) return [];
    const query = raw.slice(1).toLowerCase();
    return [...BASE_COMMANDS, ...skillCommands]
      .filter((cmd) =>
        cmd.label.toLowerCase().includes(query) ||
        cmd.description.toLowerCase().includes(query)
      )
      .slice(0, 10);
  }, [inputText, skillCommands]);

  const loadSessionMessages = useCallback(async (id: string) => {
    if (!id) return;
    setLoadingHistory(true);
    setWsError("");
    try {
      const data = await fetchJSON<{ session_id: string; messages: StoredSessionMessage[] }>(
        `/api/sessions/${encodeURIComponent(id)}/messages`
      );
      const restored = (data.messages || [])
        .filter((m) => ["user", "assistant", "system", "error"].includes(String(m.role)))
        .filter((m) => m.content !== null && m.content !== undefined && String(m.content).trim())
        .map((m) => ({
          id: String(m.id ?? uid()),
          role: m.role as Role,
          content: typeof m.content === "string" ? m.content : JSON.stringify(m.content, null, 2),
          timestamp: new Date((m.timestamp || Date.now() / 1000) * 1000),
        }));
      setMessages(restored);
      setSessionId(data.session_id || id);
      setShowSuggestions(restored.length === 0);
      setShowSessions(false);
      scrollToBottom();
    } catch (err: any) {
      setWsError(err?.message || String(err));
    } finally {
      setLoadingHistory(false);
    }
  }, [scrollToBottom]);

  const uploadFiles = useCallback(async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    setUploadingFiles(true);
    setWsError("");
    try {
      const uploaded: ChatFile[] = [];
      for (const file of Array.from(fileList)) {
        const form = new FormData();
        form.append("file", file);
        const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
        const token = getSessionToken();
        const res = await fetch(`${HERMES_BASE_PATH}/api/chat/uploads${qs}`, {
          method: "POST",
          headers: token ? { "X-Ares-Session-Token": token, "X-Hermes-Session-Token": token } : undefined,
          body: form,
        });
        if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
        uploaded.push(await res.json());
      }
      setAttachments((prev) => [...prev, ...uploaded]);
      setShowSuggestions(false);
    } catch (err: any) {
      setWsError(err?.message || String(err));
    } finally {
      setUploadingFiles(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [sessionId]);

  const removeAttachment = useCallback((path: string) => {
    setAttachments((prev) => prev.filter((file) => file.path !== path));
  }, []);

  const applyCommand = useCallback((command: ChatCommand) => {
    if (command.kind === "client") {
      if (command.id === "new") startNewChat();
      if (command.id === "clear") {
        setMessages([]);
        setShowSuggestions(true);
      }
      if (command.id === "history") setShowSessions(true);
      if (command.id === "skills") setShowSkillsPanel((value) => !value);
      setInputText("");
      return;
    }
    setInputText(`${command.value} `);
    setShowSuggestions(false);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  // Connect WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const token = getSessionToken();
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}${HERMES_BASE_PATH}/api/chat?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setWsError("");
    };

    ws.onclose = (e) => {
      setIsConnected(false);
      if (e.code === 4401) {
        setWsError("Authentication failed — please refresh the page.");
        return;
      }
      // Reconnect after 2s unless closed cleanly
      if (e.code !== 1000) {
        reconnectTimer.current = setTimeout(connect, 2000);
      }
    };

    ws.onerror = () => {
      setWsError("Connection error — check the server is running.");
      setIsConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const frame = JSON.parse(event.data);

        if (frame.type === "welcome") {
          setIsConnected(true);
          setModel(frame.model || "");
          setSessionId(frame.session_id || "");
          setWsError("");
          return;
        }

        if (frame.type === "session") {
          if (frame.session_id) setSessionId(frame.session_id);
          return;
        }

        if (frame.type === "thinking" || frame.type === "tool") {
          setIsThinking(true);
          // Update or add the thinking bubble
          setMessages(prev => {
            const withoutThinking = prev.filter(m => !m.thinking);
            return [...withoutThinking, {
              id: "thinking",
              role: "assistant",
              content: frame.type === "tool" ? frame.name : "...",
              timestamp: new Date(),
              thinking: true,
              tool: frame.type === "tool" ? frame.name : undefined,
            }];
          });
          scrollToBottom();
          return;
        }

        if (frame.type === "done") {
          setIsThinking(false);
          setMessages(prev => {
            const withoutThinking = prev.filter(m => !m.thinking);
            return [...withoutThinking, {
              id: uid(),
              role: "assistant",
              content: frame.message,
              timestamp: new Date(),
              files: Array.isArray(frame.files) ? frame.files : undefined,
            }];
          });
          if (frame.session_id) setSessionId(frame.session_id);
          scrollToBottom();
          loadSessions(); // refresh session list
          return;
        }

        if (frame.type === "error") {
          setIsThinking(false);
          setMessages(prev => {
            const withoutThinking = prev.filter(m => !m.thinking);
            return [...withoutThinking, {
              id: uid(),
              role: "error",
              content: frame.message,
              timestamp: new Date(),
            }];
          });
          scrollToBottom();
        }
      } catch (_) {}
    };
  }, [scrollToBottom, loadSessions]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close(1000);
    };
  }, [connect]);

  const sendMessage = useCallback((text: string) => {
    const msg = text.trim();
    if ((!msg && attachments.length === 0) || !isConnected || isThinking) return;
    if (attachments.length === 0) {
      const localCommand = BASE_COMMANDS.find((cmd) => cmd.kind === "client" && cmd.value === msg);
      if (localCommand) {
        applyCommand(localCommand);
        return;
      }
    }
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      connect();
      return;
    }

    const outgoingAttachments = attachments;
    setShowSuggestions(false);
    setMessages(prev => [...prev, {
      id: uid(),
      role: "user",
      content: msg || "Attached files",
      timestamp: new Date(),
      files: outgoingAttachments,
    }]);
    setInputText("");
    setAttachments([]);
    scrollToBottom();

    wsRef.current.send(JSON.stringify({
      message: msg,
      session_id: sessionId,
      new_session: !sessionId,
      attachments: outgoingAttachments,
    }));

    // Resize textarea back
    if (inputRef.current) inputRef.current.style.height = "44px";
  }, [applyCommand, attachments, isConnected, isThinking, sessionId, connect, scrollToBottom]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputText);
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    // Auto-resize
    e.target.style.height = "44px";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  };

  const startNewChat = () => {
    setMessages([]);
    setSessionId("");
    setAttachments([]);
    setShowSuggestions(true);
    setShowSessions(false);
    setShowSkillsPanel(false);
    inputRef.current?.focus();
  };

  return (
    <div className="flex h-full min-h-[32rem] gap-0">
      {/* ── Session sidebar ──────────────────────────────────────────────── */}
      <div className={cn(
        "flex flex-col gap-2 border-r border-zinc-800/60 bg-zinc-950/40 transition-all duration-300 overflow-hidden shrink-0",
        showSessions ? "w-56" : "w-0"
      )}>
        {showSessions && (
          <>
            <div className="flex items-center justify-between px-3 pt-4 pb-2">
              <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">Conversations</span>
              <button onClick={startNewChat}
                className="flex items-center gap-1 text-[10px] text-amber-400 hover:text-amber-300 transition-colors">
                <Plus className="h-3 w-3" /> New
              </button>
            </div>
            <div className="flex flex-col gap-1 px-2 overflow-y-auto flex-1 pb-4">
              {loadingHistory ? (
                <p className="text-[10px] text-zinc-600 px-2 pt-2">Loading history…</p>
              ) : sessions.length === 0 ? (
                <p className="text-[10px] text-zinc-600 px-2 pt-2">No sessions yet</p>
              ) : (
                sessions.map(s => (
                  <SessionItem
                    key={s.id}
                    session={s}
                    active={s.id === sessionId}
                    onClick={() => { void loadSessionMessages(s.id); }}
                  />
                ))
              )}
            </div>
          </>
        )}
      </div>

      {/* ── Main chat area ───────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/60 bg-zinc-950/30 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSessions(s => !s)}
              className="flex items-center gap-2 text-zinc-500 hover:text-zinc-200 transition-colors"
            >
              <MessageSquare className="h-4 w-4" />
              <span className="text-xs font-bold uppercase tracking-wide">Chat</span>
            </button>
            {sessionId && (
              <span className="text-[10px] text-zinc-600 font-mono hidden sm:block truncate max-w-[100px]">#{sessionId.slice(0, 8)}</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* Connection status */}
            <div className="flex items-center gap-1.5">
              <span className={cn("h-1.5 w-1.5 rounded-full", isConnected ? "bg-emerald-500" : "bg-red-500 animate-pulse")} />
              <span className="text-[10px] text-zinc-500">
                {isConnected ? (model ? model.split("/").pop() : "Connected") : "Reconnecting…"}
              </span>
            </div>
            {messages.length > 0 && (
              <button onClick={startNewChat} className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg border border-zinc-800 bg-zinc-900 text-[11px] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors">
                <Plus className="h-3 w-3" /> New chat
              </button>
            )}
            <button onClick={() => { wsRef.current?.close(); connect(); }}
              className="text-zinc-600 hover:text-zinc-400 transition-colors" title="Reconnect">
              <RefreshCw className={cn("h-3.5 w-3.5", !isConnected && "animate-spin")} />
            </button>
          </div>
        </div>

        {/* Error banner */}
        {wsError && (
          <div className="flex items-center gap-2.5 px-4 py-2.5 bg-red-950/20 border-b border-red-900/30 text-xs text-red-300">
            <AlertCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
            {wsError}
            <button onClick={() => setWsError("")} className="ml-auto text-red-500 hover:text-red-300"><X className="h-3 w-3" /></button>
          </div>
        )}

        {/* Message thread */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto py-4 space-y-1 min-h-0 scroll-smooth"
          style={{ scrollbarWidth: "thin", scrollbarColor: "#27272a transparent" }}
        >
          {/* Welcome / empty state */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-6 px-6 py-10 text-center">
              <div className="relative">
                <div className="h-16 w-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                  <Sparkles className="h-8 w-8 text-amber-500" />
                </div>
                <span className={cn(
                  "absolute -bottom-1 -right-1 h-4 w-4 rounded-full border-2 border-zinc-950 flex items-center justify-center",
                  isConnected ? "bg-emerald-500" : "bg-zinc-700"
                )} />
              </div>
              <div>
                <h2 className="text-base font-black uppercase tracking-widest text-amber-400 mb-1">
                  Ares AI
                </h2>
                <p className="text-xs text-zinc-500 leading-relaxed max-w-xs">
                  {businessName ? `Wholesaler AIOS for ${businessName}` : "Your AI operating system for wholesale operations"}
                </p>
                {model && <p className="text-[10px] text-zinc-600 mt-1 font-mono">{model}</p>}
              </div>

              {/* Suggested prompts */}
              {showSuggestions && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                  {SUGGESTED_PROMPTS.map((p, i) => (
                    <button
                      key={i}
                      onClick={() => { setInputText(p); inputRef.current?.focus(); }}
                      disabled={!isConnected}
                      className="flex items-start gap-2.5 p-3 rounded-xl border border-zinc-800/60 bg-zinc-900/40 hover:border-amber-500/30 hover:bg-zinc-900/70 transition-all text-left group disabled:opacity-40"
                    >
                      <Zap className="h-3.5 w-3.5 text-amber-500/50 group-hover:text-amber-500 transition-colors shrink-0 mt-0.5" />
                      <span className="text-xs text-zinc-400 group-hover:text-zinc-200 transition-colors leading-relaxed">{p}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Messages */}
          {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
        </div>

        {/* Input area */}
        <div className="px-4 py-3 border-t border-zinc-800/60 bg-zinc-950/40 shrink-0">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(event) => void uploadFiles(event.target.files)}
          />

          {(commandMatches.length > 0 || showSkillsPanel) && (
            <div className="mb-2 overflow-hidden rounded-2xl border border-zinc-800/80 bg-zinc-950/95 shadow-2xl">
              <div className="flex items-center justify-between border-b border-zinc-800/60 px-3 py-2">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">
                  <Command className="h-3.5 w-3.5 text-amber-500" />
                  {showSkillsPanel ? "Skills" : "Commands"}
                </div>
                <button
                  onClick={() => setShowSkillsPanel(false)}
                  className="text-zinc-600 transition-colors hover:text-zinc-300"
                  title="Close"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="max-h-56 overflow-y-auto p-1">
                {(showSkillsPanel ? skillCommands.slice(0, 40) : commandMatches).map((cmd) => {
                  const Icon = cmd.icon;
                  return (
                    <button
                      key={cmd.id}
                      onClick={() => applyCommand(cmd)}
                      className="flex w-full min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors hover:bg-zinc-900"
                    >
                      <Icon className="h-4 w-4 shrink-0 text-amber-500/80" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-semibold text-zinc-200">{cmd.label}</p>
                        <p className="truncate text-[10px] text-zinc-600">{cmd.description}</p>
                      </div>
                      {cmd.kind === "skill" && <BookOpen className="h-3 w-3 shrink-0 text-zinc-700" />}
                    </button>
                  );
                })}
                {showSkillsPanel && skillCommands.length === 0 && (
                  <p className="px-3 py-4 text-center text-xs text-zinc-600">No enabled skills found</p>
                )}
              </div>
            </div>
          )}

          {attachments.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {attachments.map((file) => (
                <div key={file.path} className="flex max-w-full items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900/70 px-2.5 py-1.5">
                  <FileText className="h-3.5 w-3.5 shrink-0 text-amber-500" />
                  <span className="max-w-[12rem] truncate text-[11px] text-zinc-300">{file.name}</span>
                  <span className="text-[10px] text-zinc-600">{formatBytes(file.size)}</span>
                  <button
                    onClick={() => removeAttachment(file.path)}
                    className="text-zinc-600 transition-colors hover:text-zinc-300"
                    title="Remove attachment"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className={cn(
            "flex items-end gap-3 p-3 rounded-2xl border transition-all",
            isConnected
              ? "bg-zinc-900/60 border-zinc-700/50 focus-within:border-amber-500/40 focus-within:bg-zinc-900/80"
              : "bg-zinc-950 border-zinc-900 opacity-60"
          )}>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={!isConnected || isThinking || uploadingFiles}
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-all",
                isConnected && !isThinking && !uploadingFiles
                  ? "text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"
                  : "text-zinc-700 cursor-not-allowed"
              )}
              title="Attach files"
            >
              {uploadingFiles ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
            </button>
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              disabled={!isConnected || isThinking}
              placeholder={
                !isConnected ? "Connecting to Ares…" :
                isThinking ? "Ares is thinking…" :
                "Ask Ares anything about your business…"
              }
              rows={1}
              className="flex-1 bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 resize-none outline-none leading-relaxed min-h-[28px] max-h-[160px] overflow-y-auto"
              style={{ height: "44px" }}
            />
            <div className="flex items-center gap-2 shrink-0">
              {inputText.trim() && (
                <span className="text-[10px] text-zinc-600 hidden sm:block">
                  ⏎ send · ⇧⏎ newline
                </span>
              )}
              <button
                onClick={() => setShowSkillsPanel((value) => !value)}
                disabled={!isConnected || isThinking}
                className="hidden h-9 items-center gap-1.5 rounded-xl px-2 text-[11px] text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200 sm:flex disabled:cursor-not-allowed disabled:text-zinc-700"
                title="Browse skills"
              >
                <BookOpen className="h-3.5 w-3.5" />
                Skills
                <ChevronDown className="h-3 w-3" />
              </button>
              <button
                onClick={() => sendMessage(inputText)}
                disabled={(!inputText.trim() && attachments.length === 0) || !isConnected || isThinking}
                className={cn(
                  "h-9 w-9 rounded-xl flex items-center justify-center transition-all",
                  (inputText.trim() || attachments.length > 0) && isConnected && !isThinking
                    ? "bg-amber-500 hover:bg-amber-400 text-zinc-950 shadow-lg hover:shadow-amber-500/20"
                    : "bg-zinc-800 text-zinc-600 cursor-not-allowed"
                )}
              >
                {isThinking
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <p className="text-[10px] text-zinc-700 mt-1.5 text-center">
            Ares has access to your business data and can run workflows
          </p>
        </div>
      </div>
    </div>
  );
}
