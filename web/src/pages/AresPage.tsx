import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Clock,
  Copy,
  Database,
  FileText,
  FolderInput,
  LayoutDashboard,
  Loader2,
  MessageSquare,
  Package,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  TrendingUp,
  Users,
  X,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAresData, type AresBusinessCard, type AresProofItem, type AresReadinessCard } from "./ares/AresShared";
import AresChatPage from "./ares/AresChatPage";

// ─── Page ids ─────────────────────────────────────────────────────────────────
type PageId = "today" | "approvals" | "records" | "reports" | "readiness" | "chat";

const PAGES: { id: PageId; label: string; icon: any; badge?: (ov: any) => number }[] = [
  { id: "today", label: "Today", icon: LayoutDashboard },
  { id: "approvals", label: "Approvals", icon: CheckCircle2, badge: (ov) => ov?.metrics?.pending_approvals ?? 0 },
  { id: "records", label: "Records", icon: ClipboardList },
  { id: "reports", label: "Reports", icon: BarChart3 },
  { id: "readiness", label: "Readiness", icon: ShieldCheck },
  { id: "chat", label: "Chat", icon: MessageSquare },
];

// ─── Utilities ────────────────────────────────────────────────────────────────

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-70", ok ? "bg-emerald-500" : "bg-amber-500")} />
      <span className={cn("relative rounded-full h-2 w-2", ok ? "bg-emerald-500" : "bg-amber-500")} />
    </span>
  );
}

function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes < 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatWhen(epochSeconds?: number | null): string {
  if (!epochSeconds) return "unknown";
  return new Date(epochSeconds * 1000).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function SectionHeader({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-4 pb-3 border-b border-zinc-800/50">
      <div>
        <h2 className="text-xs font-black uppercase tracking-widest text-amber-400">{title}</h2>
        {subtitle && <p className="text-[10px] text-zinc-500 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

// ─── Animated number ─────────────────────────────────────────────────────────
function AnimNum({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    if (!value) { setDisplay(0); return; }
    let v = 0;
    const steps = 30;
    const inc = value / steps;
    const t = setInterval(() => {
      v += inc;
      if (v >= value) { setDisplay(value); clearInterval(t); }
      else setDisplay(Math.floor(v));
    }, 16);
    return () => clearInterval(t);
  }, [value]);
  return <>{display}</>;
}

// ─── Status badge ─────────────────────────────────────────────────────────────
function Badge({ status }: { status: string }) {
  const s = status?.toLowerCase() || "";
  const cls =
    s === "approved" || s === "paid" || s === "ready" || s === "completed" ? "bg-emerald-950/60 text-emerald-400 border-emerald-900/40" :
    s === "pending" || s === "approval" ? "bg-amber-950/60 text-amber-400 border-amber-900/40" :
    s === "blocked" || s === "overdue" || s === "rejected" ? "bg-red-950/60 text-red-400 border-red-900/40" :
    "bg-zinc-900 text-zinc-400 border-zinc-800";
  return <span className={cn("px-1.5 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wide", cls)}>{status || "—"}</span>;
}

function toneClasses(tone?: string) {
  switch (tone) {
    case "emerald": return "border-emerald-500/20 bg-emerald-500/[0.06] text-emerald-300";
    case "amber": return "border-amber-500/25 bg-amber-500/[0.07] text-amber-300";
    case "red": return "border-red-500/25 bg-red-500/[0.07] text-red-300";
    case "blue": return "border-blue-500/20 bg-blue-500/[0.06] text-blue-300";
    default: return "border-zinc-800 bg-zinc-950/45 text-zinc-300";
  }
}

function StatusGlyph({ tone }: { tone?: string }) {
  const cls =
    tone === "emerald" ? "bg-emerald-500" :
    tone === "amber" ? "bg-amber-500" :
    tone === "red" ? "bg-red-500" :
    tone === "blue" ? "bg-blue-500" :
    "bg-zinc-600";
  return <span className={cn("h-2.5 w-2.5 shrink-0 rounded-full", cls)} />;
}

function formatMoney(value?: number | null): string {
  return `₹${(value || 0).toLocaleString("en-IN")}`;
}

function humanize(value?: string | null): string {
  return (value || "—").replace(/[_-]/g, " ");
}

function TechnicalDetails({ title = "Technical details", children }: { title?: string; children: React.ReactNode }) {
  return (
    <details className="group rounded-lg border border-zinc-900 bg-zinc-950/45 px-3 py-2 text-[10px] text-zinc-500">
      <summary className="cursor-pointer select-none font-bold uppercase tracking-widest text-zinc-500 transition-colors group-open:text-zinc-300">
        {title}
      </summary>
      <div className="mt-2 overflow-x-auto rounded border border-zinc-900 bg-black/20 p-2 font-mono leading-relaxed text-zinc-500">
        {children}
      </div>
    </details>
  );
}

function CopyCliFallback({ command }: { command?: string | null }) {
  const [copied, setCopied] = useState(false);
  if (!command) return null;
  const copy = async () => {
    await navigator.clipboard.writeText(command).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };
  return (
    <TechnicalDetails title="Copy CLI fallback">
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 whitespace-pre-wrap break-words text-emerald-400">{command}</code>
        <button onClick={copy} className="flex h-7 shrink-0 items-center gap-1 rounded border border-zinc-800 px-2 text-[10px] font-bold text-zinc-300 hover:bg-zinc-900">
          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </TechnicalDetails>
  );
}

// ─── Action button ────────────────────────────────────────────────────────────
function ActionBtn({
  label, icon: Icon = Play, onClick, busy = false, variant = "default", disabled = false, className = "",
}: {
  label: string; icon?: any; onClick: () => void; busy?: boolean; variant?: "default" | "primary" | "danger" | "ghost"; disabled?: boolean; className?: string;
}) {
  const base = "flex items-center gap-2 h-8 px-3 rounded-lg border text-xs font-bold transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed select-none";
  const v = {
    primary: "bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20 hover:border-amber-400/40",
    default: "bg-zinc-900 border-zinc-800 text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100",
    danger: "bg-red-950/20 border-red-900/40 text-red-400 hover:bg-red-950/40",
    ghost: "bg-transparent border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900",
  };
  return (
    <button className={cn(base, v[variant], className)} onClick={onClick} disabled={busy || disabled}>
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      {label}
    </button>
  );
}

// ─── Toast notifications ──────────────────────────────────────────────────────
function Toast({ message, ok, onClose }: { message: string; ok: boolean; onClose: () => void }) {
  useEffect(() => { const t = setTimeout(onClose, 4000); return () => clearTimeout(t); }, [onClose]);
  return (
    <div className={cn(
      "flex items-start gap-2.5 p-3.5 rounded-xl border shadow-2xl backdrop-blur-sm text-xs max-w-sm animate-ares-fade-up",
      ok ? "bg-emerald-950/90 border-emerald-700/40 text-emerald-200" : "bg-red-950/90 border-red-700/40 text-red-200"
    )}>
      {ok ? <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" /> : <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />}
      <span className="flex-1 leading-relaxed">{message}</span>
      <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 transition-colors shrink-0"><X className="h-3.5 w-3.5" /></button>
    </div>
  );
}

// ─── Modal wrapper ────────────────────────────────────────────────────────────
function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className={cn("rounded-2xl border border-zinc-700/60 bg-zinc-950 shadow-2xl flex flex-col gap-0 overflow-hidden max-h-[90vh]", wide ? "w-full max-w-3xl" : "w-full max-w-lg")}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <h3 className="text-sm font-black uppercase tracking-widest text-amber-400">{title}</h3>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-200 transition-colors"><X className="h-4 w-4" /></button>
        </div>
        <div className="overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  );
}

function ReportSections({ content }: { content: string }) {
  const blocks = content
    .split(/\n(?=#{1,3}\s)/)
    .map(block => block.trim())
    .filter(Boolean);

  if (blocks.length === 0) {
    return <p className="text-xs text-zinc-500">This report is empty.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {blocks.map((block, index) => {
        const lines = block.split("\n").map(line => line.trim()).filter(Boolean);
        const heading = lines[0]?.replace(/^#{1,3}\s*/, "") || `Section ${index + 1}`;
        const body = lines.slice(1);
        const bullets = body.filter(line => line.startsWith("- "));
        const paragraphs = body.filter(line => !line.startsWith("- "));
        return (
          <section key={`${heading}-${index}`} className="rounded-xl border border-zinc-800/70 bg-zinc-950/45 p-4">
            <h4 className="text-sm font-black text-zinc-100">{heading}</h4>
            {paragraphs.length > 0 && (
              <div className="mt-3 flex flex-col gap-2">
                {paragraphs.map((line, i) => (
                  <p key={i} className="text-xs leading-relaxed text-zinc-400">{line}</p>
                ))}
              </div>
            )}
            {bullets.length > 0 && (
              <ul className="mt-3 flex flex-col gap-1.5">
                {bullets.map((line, i) => (
                  <li key={i} className="flex gap-2 text-xs leading-relaxed text-zinc-400">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500/70" />
                    <span>{line.replace(/^- /, "")}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// DASHBOARD PAGE
// ──────────────────────────────────────────────────────────────────────────────

function DashboardPage({ overview, metrics, inventory, busyAction, runAction, hasLoadedInput }: any) {
  const [gstin, setGstin] = useState("");
  const [period, setPeriod] = useState("");
  const validation = overview?.validation || { blocking_errors: [], parseable_exports: [], exports_found: 0, inbox_messages: 0 };
  const workQueue = overview?.work_queue || [];
  const topActions = overview?.top_actions || [];
  const counts = inventory?.counts || {};
  const operatorSurface = overview?.operator_surface;
  const operatorView = overview?.operator_view;
  const todaySummary = operatorView?.today_summary;
  const businessCards = operatorView?.business_cards || [];
  const primaryActions = (operatorSurface?.actions || []).filter((action: any) => operatorSurface?.primary_action_ids?.includes(action.id));
  const nextRunnable = todaySummary?.next_action || workQueue.find((item: any) => item.action);

  const kpis = [
    { label: "Approvals", value: metrics.pending_approvals, color: "text-amber-400", bg: "border-amber-500/15 bg-amber-500/[0.04]", alert: true },
    { label: "Orders", value: metrics.pending_orders, color: "text-emerald-400", bg: "border-emerald-500/15 bg-emerald-500/[0.04]" },
    { label: "Overdue", value: metrics.overdue_invoices, color: "text-red-400", bg: "border-red-400/15 bg-red-400/[0.04]", alert: true },
    { label: "Low Stock", value: metrics.low_stock_skus, color: "text-orange-400", bg: "border-orange-400/15 bg-orange-400/[0.04]", alert: true },
    { label: "Blockers", value: metrics.input_blockers, color: "text-red-500", bg: "border-red-500/15 bg-red-500/[0.04]", alert: true },
    { label: "Files", value: metrics.files_found, color: "text-blue-400", bg: "border-blue-400/15 bg-blue-400/[0.04]" },
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* Operator command center */}
      <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_0.9fr] gap-4">
        <div className="rounded-xl border border-amber-500/20 bg-gradient-to-br from-zinc-950 via-zinc-950/95 to-red-950/20 p-5 shadow-xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-emerald-300">
                  <ShieldCheck className="h-3 w-3" /> Dashboard first
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-amber-300">
                  Local only
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-900/70 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-zinc-400">
                  Approval first
                </span>
              </div>
              <h2 className="text-lg font-black text-zinc-100 tracking-tight">{todaySummary?.headline || "Today"}</h2>
              <p className="mt-1 max-w-2xl text-xs leading-relaxed text-zinc-400">
                {todaySummary?.detail || "Run the wholesaler day from here: intake checks, collection work, stock risk, order review, owner approvals, reports, and chat."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <ActionBtn label="Morning Run" icon={Zap} onClick={() => runAction("morning-run")} busy={busyAction === "morning-run"} variant="primary" />
              <ActionBtn label="Validate Inputs" icon={FolderInput} onClick={() => runAction("validate-inputs")} busy={busyAction === "validate-inputs"} />
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
            {[
              { label: "Intake files", value: `${validation.exports_found + validation.inbox_messages}`, detail: `${validation.exports_found} exports · ${validation.inbox_messages} inbox` },
              { label: "Runnable actions", value: `${operatorSurface?.actions?.filter((a: any) => a.available).length || 0}`, detail: `${primaryActions.length} primary workflows surfaced` },
              { label: "Boundary", value: operatorSurface?.live_external_api_called ? "Live" : "Local", detail: "No browser-side provider calls or secrets" },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-zinc-800 bg-zinc-950/55 p-3">
                <p className="text-[10px] font-black uppercase tracking-widest text-zinc-600">{item.label}</p>
                <p className="mt-1 text-xl font-black text-amber-100">{item.value}</p>
                <p className="mt-1 text-[10px] text-zinc-500">{item.detail}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 shadow-lg">
          <SectionHeader title="Next Best Move" subtitle={hasLoadedInput ? "From local Ares state" : "Workspace needs data"} />
          {nextRunnable ? (
            <div className="flex flex-col gap-3">
              <div>
                <p className="text-sm font-black text-zinc-100">{nextRunnable.label || nextRunnable.title}</p>
                <p className="mt-1 text-xs leading-relaxed text-zinc-500">{nextRunnable.summary || nextRunnable.detail}</p>
              </div>
              <ActionBtn
                label={`Run ${nextRunnable.action}`}
                icon={Play}
                onClick={() => runAction(nextRunnable.action)}
                busy={busyAction === nextRunnable.action}
                variant={nextRunnable.status === "blocked" ? "danger" : "primary"}
                className="w-fit"
              />
              <CopyCliFallback command={nextRunnable.cli_fallback || nextRunnable.command} />
            </div>
          ) : (
            <div className="flex flex-col gap-3 text-xs text-zinc-500">
              <p>Drop Tally/Busy exports into the exports folder or customer messages into the inbox, then run validation here.</p>
              <ActionBtn label="Validate folders" icon={FolderInput} onClick={() => runAction("validate-inputs")} busy={busyAction === "validate-inputs"} className="w-fit" />
            </div>
          )}
        </div>
      </div>

      {/* Blocking alert */}
      {validation.blocking_errors.length > 0 && (
        <div className="flex items-start gap-3 p-3.5 rounded-xl border border-red-500/25 bg-red-950/20 animate-pulse-slow">
          <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
          <div className="flex flex-col gap-0.5">
            <span className="text-xs font-bold text-red-300">Intake Blockers</span>
            {validation.blocking_errors.slice(0, 2).map((e: string, i: number) => <span key={i} className="text-xs text-red-400/80">{e}</span>)}
          </div>
        </div>
      )}

      {/* Business cards */}
      {businessCards.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {businessCards.map((card: AresBusinessCard) => (
            <button
              key={card.id}
              onClick={() => card.action && runAction(card.action)}
              disabled={!card.action || !!busyAction}
              className={cn("rounded-xl border p-4 text-left shadow-md transition-all hover:scale-[1.01] disabled:cursor-default disabled:hover:scale-100", toneClasses(card.tone))}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-widest opacity-70">{card.label}</p>
                  <p className="mt-1 text-3xl font-black text-zinc-50"><AnimNum value={Number(card.value) || 0} /></p>
                </div>
                <Badge status={card.status} />
              </div>
              <p className="mt-3 text-xs leading-relaxed text-zinc-400">{card.summary}</p>
              {card.action && <p className="mt-3 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Run from dashboard</p>}
            </button>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
          {kpis.map((k) => (
            <div key={k.label} className={cn("p-3.5 rounded-xl border flex flex-col gap-1.5 shadow-md", k.bg, k.alert && k.value > 0 && "ring-1 ring-red-500/15")}>
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{k.label}</span>
              <span className={cn("text-2xl font-black font-mono", k.alert && k.value > 0 ? "text-red-400" : k.color)}>
                <AnimNum value={k.value} />
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg">
          <SectionHeader title="Run Workflows" subtitle="Daily operator actions, not CLI-first" />
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
            {[
              { id: "morning-run", label: "Morning Run", icon: Zap, hint: "Start the day" },
              { id: "daily-brief", label: "Daily Brief", icon: FileText, hint: "Owner summary" },
              { id: "payment-radar", label: "Payment Radar", icon: TrendingUp, hint: "Collections" },
              { id: "stock-radar", label: "Stock Radar", icon: Package, hint: "Reorder risk" },
              { id: "order-capture", label: "Order Capture", icon: ClipboardList, hint: "Pending orders" },
              { id: "validate-inputs", label: "Validate Inputs", icon: Check, hint: "Intake check" },
              { id: "mobile-approvals", label: "Approvals", icon: CheckCircle2, hint: "Owner gate" },
              { id: "autonomous-cycle", label: "Auto Cycle", icon: Activity, hint: "Local cycle" },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => runAction(item.id)}
                disabled={!!busyAction}
                className="flex min-h-24 flex-col items-start justify-between rounded-xl border border-zinc-800/60 bg-zinc-950/40 p-3 text-left transition-all hover:border-amber-500/30 hover:bg-zinc-900/60 disabled:opacity-40"
              >
                <div className="flex w-full items-center justify-between">
                  <item.icon className="h-4 w-4 text-amber-500/70" />
                  {busyAction === item.id && <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500" />}
                </div>
                <div>
                  <p className="text-xs font-bold text-zinc-200">{item.label}</p>
                  <p className="text-[10px] text-zinc-500">{item.hint}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg">
          <SectionHeader title="GSTR-1 Prep" subtitle="Prepare a local filing package" />
          <div className="flex flex-col gap-3">
            <input type="text" placeholder="Period, e.g. 2026-04" value={period} onChange={e => setPeriod(e.target.value)}
              className="h-9 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-xs text-zinc-200 placeholder:text-zinc-700 focus:border-amber-500/50 focus:outline-none" />
            <input type="text" placeholder="Seller GSTIN" value={gstin} onChange={e => setGstin(e.target.value.toUpperCase())}
              className="h-9 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-xs text-zinc-200 placeholder:text-zinc-700 focus:border-amber-500/50 focus:outline-none" />
            <ActionBtn
              label="Prepare GSTR-1"
              icon={FileText}
              onClick={() => runAction("prepare-gstr1", { period, seller_gstin: gstin })}
              busy={busyAction === "prepare-gstr1"}
              disabled={!period || !gstin}
              variant="primary"
              className="w-fit"
            />
            <p className="text-[10px] leading-relaxed text-zinc-600">Creates a local preparation report only. GSTN filing is not executed from the browser.</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Work queue */}
        <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg flex flex-col gap-3">
          <SectionHeader title="Live Work Queue" subtitle={`${workQueue.length} items`}>
            <span className={cn("text-[10px] px-2 py-0.5 rounded-full border", hasLoadedInput ? "bg-emerald-950 text-emerald-400 border-emerald-900/30" : "bg-zinc-950 text-zinc-500 border-zinc-800")}>
              {hasLoadedInput ? "Active" : "No data"}
            </span>
          </SectionHeader>
          {workQueue.length === 0 ? (
            <div className="flex items-center gap-3 py-6 justify-center text-zinc-600 text-sm">
              <CheckCircle2 className="h-5 w-5 text-emerald-500/40" />
              All clear
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {workQueue.slice(0, 5).map((item: any, i: number) => (
                <div key={i} className={cn(
                  "flex items-center gap-3 p-3 rounded-lg border bg-zinc-950/40",
                  item.status === "ready" ? "border-emerald-900/40" :
                  item.status === "blocked" || item.status === "needs_input" ? "border-red-900/30" :
                  item.status === "approval" ? "border-amber-900/40" :
                  "border-zinc-900/40"
                )}>
                  <span className={cn("h-2 w-2 rounded-full shrink-0",
                    item.status === "ready" ? "bg-emerald-500 animate-pulse" :
                    item.status === "blocked" ? "bg-red-500" :
                    item.status === "approval" ? "bg-amber-500 animate-pulse" :
                    "bg-zinc-600"
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold text-zinc-200 uppercase tracking-wide truncate">{item.title}</p>
                    <p className="text-[10px] text-zinc-500 truncate">{item.detail}</p>
                  </div>
                  {item.action && (
                    <button
                      onClick={() => runAction(item.action)}
                      disabled={busyAction === item.action}
                      className="shrink-0 h-6 px-2.5 rounded border border-amber-900/50 bg-amber-950/20 text-[10px] font-bold text-amber-300 hover:bg-amber-900/30 transition-colors disabled:opacity-40 flex items-center gap-1"
                    >
                      {busyAction === item.action ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                      Run
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Today's priorities */}
        <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg flex flex-col gap-3">
          <SectionHeader title="Today's AI Priorities" subtitle={`${topActions.length} tasks from brief`} />
          {topActions.length > 0 ? (
            <ol className="flex flex-col gap-2.5">
              {topActions.slice(0, 5).map((a: string, i: number) => (
                <li key={i} className="flex gap-3 items-start group">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-500/10 border border-amber-500/20 text-[10px] font-black text-amber-500 shrink-0">{i + 1}</span>
                  <span className="text-xs text-zinc-300 leading-relaxed group-hover:text-zinc-100 transition-colors">{a}</span>
                </li>
              ))}
            </ol>
          ) : (
            <div className="flex flex-col gap-2">
              {overview?.primary_commands?.slice(0, 5).map((cmd: any) => (
                <button key={cmd.id} onClick={() => cmd.action && runAction(cmd.action)} disabled={!cmd.action || busyAction === cmd.action}
                  className="flex items-center gap-3 p-3 rounded-lg border border-zinc-800 bg-zinc-950/40 hover:border-amber-500/30 hover:bg-zinc-900/60 transition-all text-left disabled:opacity-40"
                >
                  <div className="flex-1">
                    <p className="text-xs font-bold text-zinc-200 uppercase tracking-wide">{cmd.label}</p>
                    <p className="text-[10px] text-zinc-500">{cmd.intent}</p>
                  </div>
                  {busyAction === cmd.action ? <Loader2 className="h-3.5 w-3.5 text-amber-500 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5 text-zinc-600" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Data counts grid */}
      <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg">
        <SectionHeader title="Business Records" subtitle="Local Ares counts visible to the operator" />
        <div className="grid grid-cols-4 sm:grid-cols-8 gap-3">
          {[
            { l: "Customers", k: "customers", icon: Users },
            { l: "Invoices", k: "invoices", icon: FileText },
            { l: "Stock SKUs", k: "stock_records", icon: Package },
            { l: "Orders", k: "orders", icon: ClipboardList },
            { l: "Approvals", k: "pending_approvals", icon: CheckCircle2 },
            { l: "Workflows", k: "workflow_runs", icon: Activity },
            { l: "Reports", k: "reports", icon: BarChart3 },
            { l: "Audit Logs", k: "action_logs", icon: Clock },
          ].map(({ l, k, icon: Icon }) => (
            <div key={k} className="p-3 rounded-lg border border-zinc-900 bg-zinc-950/60 flex flex-col items-center gap-1 shadow-inner">
              <Icon className="h-3.5 w-3.5 text-zinc-600" />
              <span className="text-[9px] font-bold text-zinc-600 uppercase tracking-wider text-center">{l}</span>
              <span className="text-xl font-black text-zinc-100 font-mono"><AnimNum value={counts[k] || 0} /></span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// APPROVALS PAGE — owner decisions without leaving the dashboard
// ──────────────────────────────────────────────────────────────────────────────

function ApprovalsPage({ overview, busyAction, runAction, actionLog }: any) {
  const [replyText, setReplyText] = useState("");
  const approvals = overview?.recent_records?.approvals || [];
  const pendingApprovals = approvals.filter((approval: any) => approval.status === "pending");

  const sendReply = () => {
    const reply = replyText.trim();
    if (!reply) return;
    runAction("mobile-reply", { reply });
    setReplyText("");
  };

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.25fr_0.75fr]">
      <div className="rounded-xl border border-amber-900/25 bg-amber-950/5 p-5 shadow-lg">
        <SectionHeader title="Owner Approvals" subtitle={`${pendingApprovals.length} pending decisions`}>
          <ActionBtn label="Refresh" icon={RefreshCw} onClick={() => runAction("mobile-approvals")} busy={busyAction === "mobile-approvals"} />
        </SectionHeader>

        {pendingApprovals.length === 0 ? (
          <div className="rounded-xl border border-zinc-800/60 bg-zinc-950/40 p-8 text-center">
            <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500/60" />
            <p className="mt-3 text-sm font-bold text-zinc-200">No owner decisions pending</p>
            <p className="mt-1 text-xs text-zinc-500">Run payment, stock, order, or daily workflows to generate approval-gated drafts.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {pendingApprovals.map((apr: any, i: number) => (
              <div key={apr.id || i} className="rounded-xl border border-amber-900/35 bg-zinc-950/45 p-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="text-[10px] font-black uppercase tracking-widest text-amber-500">{(apr.type || "approval").replace(/_/g, " ")}</p>
                    <p className="mt-1 text-xs leading-relaxed text-zinc-200">{apr.proposed_action || apr.summary || "Approval requested"}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-zinc-500">
                      {apr.customer_id && <span className="font-mono">Customer: {apr.customer_id}</span>}
                      {apr.id && <span className="font-mono">ID: {apr.id}</span>}
                    </div>
                  </div>
                  <Badge status={apr.status || "pending"} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button onClick={() => runAction("mobile-reply", { reply: `approved ${apr.id || i}` })} disabled={!!busyAction}
                    className="flex h-8 items-center gap-1.5 rounded-lg border border-emerald-900/50 bg-emerald-950/20 px-3 text-[11px] font-bold text-emerald-400 transition-colors hover:bg-emerald-900/30 disabled:opacity-40">
                    <Check className="h-3 w-3" /> Approve
                  </button>
                  <button onClick={() => runAction("mobile-reply", { reply: `rejected ${apr.id || i}` })} disabled={!!busyAction}
                    className="flex h-8 items-center gap-1.5 rounded-lg border border-red-900/50 bg-red-950/20 px-3 text-[11px] font-bold text-red-400 transition-colors hover:bg-red-900/30 disabled:opacity-40">
                    <X className="h-3 w-3" /> Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-5 border-t border-zinc-800/50 pt-4">
          <label className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Manual owner reply</label>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={replyText}
              onChange={e => setReplyText(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") sendReply(); }}
              placeholder="e.g. approved appr_xxx, rejected appr_xxx, haan approved"
              className="h-10 flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-3 font-mono text-xs text-zinc-200 placeholder:text-zinc-700 focus:border-amber-500/50 focus:outline-none"
            />
            <button onClick={sendReply} disabled={!replyText.trim() || !!busyAction}
              className="flex h-10 items-center justify-center gap-2 rounded-lg border border-amber-900/50 bg-amber-950/20 px-4 text-xs font-bold text-amber-300 transition-colors hover:bg-amber-950/40 disabled:opacity-40">
              <Send className="h-3.5 w-3.5" /> Send Reply
            </button>
          </div>
          <p className="mt-2 text-[10px] text-zinc-600">Replies are processed through the local Ares approval adapter. No live WhatsApp message is sent from this browser.</p>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 shadow-lg">
        <SectionHeader title="Approval Proof" subtitle="Latest dashboard runs" />
        {actionLog.length === 0 ? (
          <p className="text-xs leading-relaxed text-zinc-500">No approval actions run in this browser session yet.</p>
        ) : (
          <div className="flex max-h-96 flex-col gap-2 overflow-y-auto pr-1">
            {actionLog.slice(0, 12).map((entry: any, i: number) => (
              <div key={`${entry.time}-${i}`} className="rounded-lg border border-zinc-900 bg-zinc-950/50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className={cn("text-[10px] font-black uppercase tracking-widest", entry.ok ? "text-emerald-400" : "text-red-400")}>{entry.action}</span>
                  <span className="font-mono text-[10px] text-zinc-600">{entry.time}</span>
                </div>
                <p className="mt-1 truncate text-xs text-zinc-400">{entry.message}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// RECORDS PAGE — view and manage data records
// ──────────────────────────────────────────────────────────────────────────────

function RecordsPage({ overview, inventory }: any) {
  const [tab, setTab] = useState<"invoices" | "orders" | "stock">("invoices");
  const records = overview?.recent_records || {};
  const recordSummaries = overview?.operator_view?.record_summaries || {};
  const invoices = records.invoices || [];
  const orders = records.orders || [];
  const stock = records.stock_records || [];

  const tabs = [
    { id: "invoices" as const, label: `Invoices (${invoices.length})`, icon: FileText },
    { id: "orders" as const, label: `Orders (${orders.length})`, icon: ClipboardList },
    { id: "stock" as const, label: `Stock (${stock.length})`, icon: Package },
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl bg-zinc-950/60 border border-zinc-800/60 w-fit">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={cn("flex items-center gap-1.5 h-8 px-3.5 rounded-lg text-xs font-bold transition-all",
              tab === t.id ? "bg-amber-500/10 text-amber-300 border border-amber-500/20" : "text-zinc-500 hover:text-zinc-200"
            )}>
            <t.icon className="h-3.5 w-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Table content */}
      <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg overflow-hidden">
        {tab === "invoices" && (
          invoices.length === 0 ? (
            <div className="p-10 text-center text-zinc-600 text-xs">No invoices loaded — drop intake files into the exports folder</div>
          ) : (
            <div>
              <div className="grid gap-2 p-3 bg-zinc-950/60 border-b border-zinc-800/40" style={{ gridTemplateColumns: "2fr 2fr 1fr 1fr 1fr" }}>
                {["Invoice #", "Customer", "Amount", "GST", "Status"].map(h => (
                  <span key={h} className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{h}</span>
                ))}
              </div>
              <div className="divide-y divide-zinc-900/40">
                {invoices.map((inv: any, i: number) => (
                  <div key={i} className="grid gap-2 p-3 hover:bg-zinc-900/30 transition-colors items-center" style={{ gridTemplateColumns: "2fr 2fr 1fr 1fr 1fr" }}>
                    <span className="text-xs font-mono text-zinc-200">{inv.invoice_number}</span>
                    <span className="text-xs text-zinc-300 truncate">{inv.customer_id || "—"}</span>
                    <span className="text-xs font-mono">₹{(inv.amount || 0).toLocaleString("en-IN")}</span>
                    <span className="text-xs font-mono text-zinc-500">₹{(inv.tax_amount || 0).toLocaleString("en-IN")}</span>
                    <Badge status={inv.status || "draft"} />
                  </div>
                ))}
              </div>
            </div>
          )
        )}

        {tab === "invoices" && (recordSummaries.invoices || []).length > 0 && (
          <div className="border-t border-zinc-900/60 p-4">
            <p className="mb-3 text-[10px] font-black uppercase tracking-widest text-zinc-500">Suggested next actions</p>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {(recordSummaries.invoices || []).slice(0, 4).map((row: any, index: number) => (
                <div key={row.id || index} className="rounded-lg border border-zinc-900 bg-zinc-950/50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-xs font-bold text-zinc-200">{row.party}</p>
                    <Badge status={row.risk} />
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-500">{formatMoney(row.amount)} · {row.next_action}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "orders" && (
          orders.length === 0 ? (
            <div className="p-10 text-center text-zinc-600 text-xs">No orders in system yet</div>
          ) : (
            <div>
              <div className="grid gap-2 p-3 bg-zinc-950/60 border-b border-zinc-800/40" style={{ gridTemplateColumns: "1fr 2fr 1fr 1fr 1fr" }}>
                {["Order ID", "Customer", "Amount", "Items", "Status"].map(h => (
                  <span key={h} className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{h}</span>
                ))}
              </div>
              <div className="divide-y divide-zinc-900/40">
                {orders.map((o: any, i: number) => (
                  <div key={i} className="grid gap-2 p-3 hover:bg-zinc-900/30 transition-colors items-center" style={{ gridTemplateColumns: "1fr 2fr 1fr 1fr 1fr" }}>
                    <span className="text-xs font-mono text-zinc-200">{o.id || o.order_id || "—"}</span>
                    <span className="text-xs text-zinc-300 truncate">{o.customer_id || "—"}</span>
                    <span className="text-xs font-mono">₹{(o.amount || 0).toLocaleString("en-IN")}</span>
                    <span className="text-xs text-zinc-400">{(o.items || []).length} items</span>
                    <Badge status={o.status || "pending"} />
                  </div>
                ))}
              </div>
            </div>
          )
        )}

        {tab === "stock" && (
          stock.length === 0 ? (
            <div className="p-10 text-center text-zinc-600 text-xs">No stock records loaded</div>
          ) : (
            <div>
              <div className="grid gap-2 p-3 bg-zinc-950/60 border-b border-zinc-800/40" style={{ gridTemplateColumns: "3fr 1fr 1fr 1fr" }}>
                {["Item Name", "Current Stock", "Reorder Level", "Status"].map(h => (
                  <span key={h} className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{h}</span>
                ))}
              </div>
              <div className="divide-y divide-zinc-900/40">
                {stock.map((s: any, i: number) => {
                  const isLow = (s.current_stock || 0) <= (s.reorder_level || 0);
                  return (
                    <div key={i} className="grid gap-2 p-3 hover:bg-zinc-900/30 transition-colors items-center" style={{ gridTemplateColumns: "3fr 1fr 1fr 1fr" }}>
                      <span className="text-xs text-zinc-200 truncate">{s.item_name || s.sku_name || "—"}</span>
                      <span className={cn("text-xs font-mono font-bold", isLow ? "text-red-400" : "text-emerald-400")}>{s.current_stock}</span>
                      <span className="text-xs font-mono text-zinc-400">{s.reorder_level}</span>
                      <Badge status={isLow ? "low" : "healthy"} />
                    </div>
                  );
                })}
              </div>
            </div>
          )
        )}
      </div>

      {inventory?.data_files?.length > 0 && (
        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 shadow-lg">
          <SectionHeader title="Local Data Files" subtitle="Available as proof, hidden from daily operation" />
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {inventory.data_files.map((file: any) => (
              <div key={file.path} className="flex min-w-0 items-center gap-3 rounded-lg border border-zinc-900 bg-zinc-950/50 p-3">
                <Database className="h-4 w-4 shrink-0 text-zinc-600" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-bold text-zinc-300">{file.name}</p>
                  <p className="text-[10px] text-zinc-600">{formatBytes(file.size)}</p>
                  <TechnicalDetails title="View file path">
                    {file.path}
                  </TechnicalDetails>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// REPORTS PAGE — visual proof reports with raw details collapsed
// ──────────────────────────────────────────────────────────────────────────────

function ReportsPage({ overview, inventory, openReport }: any) {
  const [viewingReport, setViewingReport] = useState<{ name: string; content: string; path?: string } | null>(null);
  const [loadingReport, setLoadingReport] = useState("");
  const proofItems: AresProofItem[] = overview?.operator_view?.proof_items || [];
  const reports = (inventory?.reports || []).filter((report: any) => String(report.name || "").endsWith(".md"));
  const cards = proofItems.length > 0
    ? proofItems
    : reports.map((report: any) => ({
      id: report.name,
      title: humanize(report.name.replace(/\.(md|json)$/i, "")),
      status: "created",
      tone: "blue",
      action: null,
      created_at: report.modified_at,
      summary: "Local proof report generated by Ares.",
      path: report.path,
      size: report.size,
    }));

  const openRpt = async (path: string) => {
    setLoadingReport(path);
    try {
      const report = await openReport(path);
      setViewingReport({ ...report, path });
    } catch (_) {
      setViewingReport({ name: "Report unavailable", content: "The report could not be opened from the local workspace.", path });
    } finally {
      setLoadingReport("");
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 shadow-lg">
        <SectionHeader title="Reports" subtitle="Business summaries first; proof details on demand" />
        {cards.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-950/35 p-10 text-center">
            <FileText className="mx-auto h-8 w-8 text-zinc-700" />
            <p className="mt-3 text-sm font-bold text-zinc-300">{overview?.operator_view?.empty_states?.reports || "No reports generated yet"}</p>
            <p className="mt-1 text-xs text-zinc-600">Run Validate Inputs, Daily Brief, Payment Radar, Stock Radar, or another workflow from Today.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {cards.map((item: AresProofItem) => (
              <div key={item.path || item.id} className="rounded-xl border border-zinc-800/60 bg-zinc-950/40 p-4 shadow-inner">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-black text-zinc-100">{item.title}</p>
                    <p className="mt-1 text-xs leading-relaxed text-zinc-500">{item.summary}</p>
                  </div>
                  <Badge status={item.status} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-zinc-600">
                  <span>{formatWhen(item.created_at)}</span>
                  <span>{formatBytes(item.size)}</span>
                  {item.action && <span>{humanize(item.action)}</span>}
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <ActionBtn
                    label="Open Report"
                    icon={FileText}
                    onClick={() => openRpt(item.path)}
                    busy={loadingReport === item.path}
                    disabled={!item.path}
                  />
                </div>
                <div className="mt-3">
                  <TechnicalDetails title="View proof">
                    <div className="whitespace-pre-wrap break-words">{item.path}</div>
                  </TechnicalDetails>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {viewingReport && (
        <Modal title={viewingReport.name} onClose={() => setViewingReport(null)} wide>
          <div className="flex flex-col gap-4 p-5">
            <ReportSections content={viewingReport.content} />
            <TechnicalDetails title="Raw report markdown">
              <pre className="whitespace-pre-wrap break-words">{viewingReport.content}</pre>
            </TechnicalDetails>
            {viewingReport.path && (
              <TechnicalDetails title="Report path">
                {viewingReport.path}
              </TechnicalDetails>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// READINESS PAGE — local readiness and access boundary
// ──────────────────────────────────────────────────────────────────────────────

function ReadinessPage({ overview, health, inventory, loadOverview, loadHealth, selectedClient, loading }: any) {
  const selected = overview?.selected_client;
  const audit = overview?.audit;
  const operatorSurface = overview?.operator_surface;
  const readinessCards: AresReadinessCard[] = overview?.operator_view?.readiness_cards || [];
  const checks = Array.isArray(health?.checks) ? health.checks : [];

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[0.9fr_1.1fr]">
      <div className="flex flex-col gap-5">
        <div className="rounded-xl border border-emerald-900/30 bg-emerald-950/5 p-5 shadow-lg">
          <SectionHeader title="Access Boundary" subtitle="Dashboard-first operator model" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {[
              { label: "Operator home", value: operatorSurface?.operator_home || "/ares" },
              { label: "CLI role", value: operatorSurface?.cli_role || "admin_dev_fallback" },
              { label: "Execution", value: audit?.live_external_api_called ? "live external" : "local only" },
              { label: "Approval mode", value: audit?.approval_first ? "approval first" : "not enforced" },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-zinc-800 bg-zinc-950/55 p-3">
                <p className="text-[10px] font-black uppercase tracking-widest text-zinc-600">{item.label}</p>
                <p className="mt-1 text-sm font-bold text-zinc-100">{item.value}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-relaxed text-zinc-500">{audit?.limitation || "Local Ares command center only; live integrations are not invoked."}</p>
        </div>

        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 shadow-lg">
          <SectionHeader title="Traffic Lights" subtitle="Simple readiness view for operators" />
          <div className="flex flex-col gap-2">
            {readinessCards.map((card) => (
              <div key={card.id} className={cn("rounded-lg border p-3", toneClasses(card.tone))}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 gap-2">
                    <StatusGlyph tone={card.tone} />
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-zinc-100">{card.label}</p>
                      <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">{card.summary}</p>
                    </div>
                  </div>
                  <Badge status={card.status} />
                </div>
                <div className="mt-3">
                  <TechnicalDetails>{card.technical_detail}</TechnicalDetails>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-5">
        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 shadow-lg">
          <SectionHeader title="Runtime Health" subtitle={health?.status ? `Status: ${health.status}` : "Local health snapshot"}>
            <ActionBtn label="Refresh" icon={RefreshCw} onClick={() => { loadOverview(selectedClient); loadHealth(selectedClient); }} busy={loading} />
          </SectionHeader>
          {checks.length === 0 ? (
            <p className="text-xs text-zinc-500">No runtime checks returned yet.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {checks.map((check: any, i: number) => (
                <div key={check.id || i} className="rounded-lg border border-zinc-900 bg-zinc-950/50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs font-bold text-zinc-200">{check.id || `check-${i + 1}`}</span>
                    <Badge status={check.status || "unknown"} />
                  </div>
                  {check.message && <p className="mt-1 text-[11px] leading-relaxed text-zinc-500">{check.message}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-5 shadow-lg">
          <SectionHeader title="Workspace Inventory" subtitle="What the dashboard can access locally" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Exports", value: inventory?.counts?.export_files || 0 },
              { label: "Inbox", value: inventory?.counts?.inbox_files || 0 },
              { label: "Reports", value: inventory?.counts?.reports || 0 },
              { label: "Data files", value: inventory?.data_files?.length || 0 },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-zinc-900 bg-zinc-950/50 p-3">
                <p className="text-[10px] font-black uppercase tracking-widest text-zinc-600">{item.label}</p>
                <p className="mt-1 font-mono text-xl font-black text-zinc-100">{item.value}</p>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <TechnicalDetails title="Workspace path">
              {overview?.paths?.client_root || selected?.paths?.root || "No client path loaded"}
            </TechnicalDetails>
          </div>
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// MAIN ARES PAGE
// ──────────────────────────────────────────────────────────────────────────────

export default function AresPage() {
  const {
    overview, clients, metrics, selected, selectedClient, setSelectedClient,
    loading, error, setError, busyAction, lastRun, health, actionLog, hasLoadedInput, inventory,
    loadOverview, loadHealth, runAction, openReport,
  } = useAresData();

  const [activePage, setActivePage] = useState<PageId>("today");
  const [toasts, setToasts] = useState<Array<{ id: string; message: string; ok: boolean }>>([]);

  // Show toast whenever lastRun changes
  useEffect(() => {
    if (!lastRun) return;
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, message: lastRun.message || "Action complete", ok: true }]);
  }, [lastRun]);

  useEffect(() => {
    if (!error) return;
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, message: error, ok: false }]);
    setError("");
  }, [error, setError]);

  const removeToast = (id: string) => setToasts(prev => prev.filter(t => t.id !== id));

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading && !overview) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[24rem] gap-4 text-amber-500/60">
        <div className="relative h-12 w-12">
          <div className="h-12 w-12 rounded-full border-2 border-amber-500/20 animate-spin border-t-amber-500" />
          <div className="absolute inset-0 flex items-center justify-center">
            <Activity className="h-5 w-5 text-amber-500" />
          </div>
        </div>
        <p className="text-sm font-bold uppercase tracking-widest text-amber-500/70">Loading Ares AIOS…</p>
      </div>
    );
  }

  // ── No workspace ───────────────────────────────────────────────────────────
  if (overview && !overview.selected_client) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[24rem] p-8 max-w-lg mx-auto text-center gap-6">
        <AlertCircle className="h-12 w-12 text-red-400/50" />
        <div>
          <h1 className="text-xl font-black text-zinc-100 uppercase tracking-wide mb-2">No Workspace Found</h1>
          <p className="text-xs text-zinc-400 leading-relaxed">{overview.operator_view?.empty_states?.setup || "Initialize a local Ares workspace to start using the dashboard."}</p>
        </div>
        <div className="w-full text-left">
          <CopyCliFallback command={overview.setup_command} />
        </div>
      </div>
    );
  }

  const pendingApprovals = metrics.pending_approvals || 0;
  const hasAlerts = (metrics.input_blockers || 0) > 0;

  return (
    <div className="flex flex-col gap-0 w-full">
      {/* ── Toast notifications ─────────────────────────────────────────────── */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 items-end">
        {toasts.map(t => <Toast key={t.id} message={t.message} ok={t.ok} onClose={() => removeToast(t.id)} />)}
      </div>

      {/* ── Header strip ────────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-20 mb-5">
        {/* Business identity */}
        <div className="flex items-center justify-between px-4 py-3 rounded-t-xl bg-gradient-to-r from-red-950/30 via-zinc-900/80 to-zinc-950/60 border border-zinc-800/60 border-b-0 backdrop-blur-md shadow-lg">
          <div className="flex items-center gap-3 min-w-0">
            <StatusDot ok={!hasAlerts} />
            <div className="min-w-0">
              <h1 className="text-sm font-black uppercase tracking-widest text-amber-100 truncate">
                {selected?.business_name || "Ares AIOS"}
              </h1>
              <p className="text-[10px] text-zinc-500 font-mono truncate">
                {selected?.owner_name} • {selected?.timezone} • {selected?.language_preference}
              </p>
            </div>
            {pendingApprovals > 0 && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/25 text-[10px] font-bold text-amber-300 animate-pulse-slow shrink-0">
                {pendingApprovals} pending
              </span>
            )}
            <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-bold text-emerald-300 shrink-0">
              <ShieldCheck className="h-3 w-3" /> local only
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {clients.length > 1 && (
              <div className="relative">
                <select value={selectedClient} onChange={e => setSelectedClient(e.target.value)} disabled={loading}
                  className="h-8 pl-3 pr-7 bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-amber-100 focus:outline-none focus:border-amber-500/50 appearance-none cursor-pointer">
                  {clients.map(c => <option key={c.client_slug} value={c.client_slug}>{c.business_name}</option>)}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-zinc-500 pointer-events-none" />
              </div>
            )}
            <button onClick={() => loadOverview(selectedClient)} disabled={loading}
              className="h-8 w-8 flex items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-400 hover:text-amber-400 transition-all">
              <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            </button>
          </div>
        </div>

        {/* Page tab nav */}
        <div className="flex items-center overflow-x-auto scrollbar-none bg-zinc-950/80 border border-zinc-800/60 border-t-0 rounded-b-xl px-3 backdrop-blur-sm">
          {PAGES.map(page => {
            const badgeCount = page.badge ? page.badge(overview) : 0;
            return (
              <button key={page.id} onClick={() => setActivePage(page.id)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2.5 text-xs font-bold transition-all border-b-2 -mb-px",
                  activePage === page.id ? "text-amber-300 border-amber-500" : "text-zinc-500 border-transparent hover:text-zinc-200 hover:border-zinc-700"
                )}>
                <page.icon className="h-3.5 w-3.5" />
                <span className="uppercase tracking-wide">{page.label}</span>
                {badgeCount > 0 && (
                  <span className="h-4 min-w-4 px-1 flex items-center justify-center rounded-full bg-red-500 text-[9px] font-black text-white">{badgeCount}</span>
                )}
              </button>
            );
          })}
          {busyAction && (
            <div className="ml-auto flex items-center gap-2 py-2 text-[10px] text-amber-400">
              <Loader2 className="h-3 w-3 animate-spin" />
              Running {busyAction}…
            </div>
          )}
          {lastRun && !busyAction && (
            <div className="ml-auto flex items-center gap-1.5 py-2 text-[10px] text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              {lastRun.action} complete
            </div>
          )}
        </div>
      </div>

      {lastRun?.report && (
        <div className="mb-5 flex flex-col gap-3 rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-3 text-xs sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="font-bold text-emerald-300">{lastRun.action} completed with local proof report</p>
            <p className="text-[10px] text-zinc-500">Report created locally. Open Reports for the business view.</p>
            <div className="mt-2 max-w-xl">
              <TechnicalDetails title="View proof path">{lastRun.report.markdown_path}</TechnicalDetails>
            </div>
          </div>
          <button
            onClick={() => setActivePage("reports")}
            className="flex h-8 shrink-0 items-center justify-center gap-2 rounded-lg border border-emerald-900/50 bg-emerald-950/20 px-3 text-[11px] font-bold text-emerald-300 hover:bg-emerald-900/30"
          >
            <FileText className="h-3.5 w-3.5" /> Open Reports
          </button>
        </div>
      )}

      {/* ── Page content ────────────────────────────────────────────────────── */}
      <div className="flex-1">
        {activePage === "today" && (
          <DashboardPage overview={overview} metrics={metrics} inventory={inventory} busyAction={busyAction} runAction={runAction} hasLoadedInput={hasLoadedInput} />
        )}
        {activePage === "approvals" && (
          <ApprovalsPage overview={overview} busyAction={busyAction} runAction={runAction} actionLog={actionLog} />
        )}
        {activePage === "records" && (
          <RecordsPage overview={overview} inventory={inventory} />
        )}
        {activePage === "reports" && (
          <ReportsPage overview={overview} inventory={inventory} openReport={openReport} />
        )}
        {activePage === "readiness" && (
          <ReadinessPage overview={overview} health={health} inventory={inventory} loadOverview={loadOverview} loadHealth={loadHealth} selectedClient={selectedClient} loading={loading} />
        )}
        {activePage === "chat" && (
          <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/20 shadow-lg overflow-hidden" style={{ minHeight: "32rem" }}>
            <AresChatPage businessName={selected?.business_name} />
          </div>
        )}
      </div>
    </div>
  );
}
