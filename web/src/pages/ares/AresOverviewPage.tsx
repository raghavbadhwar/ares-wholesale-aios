import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Activity,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock,
  FileText,
  Layers,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  UserCheck,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { OverviewData } from "./AresShared";

// ─── Animated counter ─────────────────────────────────────────────────────────
function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0;
    const end = value;
    if (end === 0) { setDisplay(0); return; }
    const duration = 800;
    const stepTime = 16;
    const steps = Math.ceil(duration / stepTime);
    const increment = end / steps;
    const timer = setInterval(() => {
      start += increment;
      if (start >= end) { setDisplay(end); clearInterval(timer); }
      else setDisplay(Math.floor(start));
    }, stepTime);
    return () => clearInterval(timer);
  }, [value]);
  return <>{display}</>;
}

// ─── Donut Chart (SVG) ────────────────────────────────────────────────────────
function DonutChart({ segments }: { segments: { label: string; value: number; color: string }[] }) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = 56, cx = 64, cy = 64;
  const circumference = 2 * Math.PI * r;
  let offset = 0;
  const arcs = segments.map((seg) => {
    const pct = seg.value / total;
    const arc = { ...seg, pct, offset, dash: pct * circumference };
    offset += arc.dash;
    return arc;
  });
  return (
    <div className="flex items-center gap-6">
      <svg width="128" height="128" className="shrink-0 -rotate-90">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1a1a1f" strokeWidth="20" />
        {arcs.map((arc, i) => (
          <circle
            key={i}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={arc.color}
            strokeWidth="20"
            strokeDasharray={`${arc.dash} ${circumference - arc.dash}`}
            strokeDashoffset={-arc.offset}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 1.2s ease-out" }}
          />
        ))}
      </svg>
      <div className="flex flex-col gap-2.5">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: seg.color }} />
            <span className="text-xs text-zinc-400">{seg.label}</span>
            <span className="ml-auto text-xs font-bold text-zinc-100 font-mono pl-3">
              ₹{seg.value >= 100000 ? `${(seg.value / 100000).toFixed(1)}L` : seg.value >= 1000 ? `${(seg.value / 1000).toFixed(0)}k` : seg.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({
  label, value, icon: Icon, color, bg, trend, alert,
}: {
  label: string; value: number; icon: any; color: string; bg: string; trend?: "up" | "down"; alert?: boolean;
}) {
  return (
    <div className={cn(
      "relative p-4 rounded-xl border flex flex-col gap-2 shadow-lg overflow-hidden group transition-all duration-300",
      "hover:scale-[1.02] hover:shadow-xl",
      bg,
      alert && value > 0 && "ring-1 ring-red-500/20",
    )}>
      <div className="absolute top-0 right-0 w-20 h-20 opacity-[0.04] pointer-events-none">
        <Icon className="w-full h-full" />
      </div>
      <div className="flex justify-between items-center">
        <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{label}</span>
        <Icon className={cn("h-4 w-4", color)} />
      </div>
      <div className="flex items-end gap-2">
        <span className={cn("text-3xl font-black tracking-tight font-mono", value > 0 && alert ? "text-red-400" : "text-zinc-100")}>
          <AnimatedNumber value={value} />
        </span>
        {trend === "up" && value > 0 && <TrendingUp className="h-3.5 w-3.5 text-red-400 mb-1" />}
        {trend === "down" && value > 0 && <TrendingDown className="h-3.5 w-3.5 text-emerald-400 mb-1" />}
      </div>
    </div>
  );
}

// ─── Progress Bar Row ─────────────────────────────────────────────────────────
function ProgressRow({ label, value, max, color, unit }: { label: string; value: number; max: number; color: string; unit?: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) { el.style.width = "0%"; requestAnimationFrame(() => { el.style.width = `${pct}%`; }); }
  }, [pct]);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-400 font-medium">{label}</span>
        <span className="text-zinc-200 font-mono font-semibold">{unit ? `${unit} ${value.toLocaleString("en-IN")}` : value}</span>
      </div>
      <div className="h-2 rounded-full bg-zinc-950/80 border border-zinc-900 overflow-hidden">
        <div ref={ref} className="h-full rounded-full" style={{ background: color, transition: "width 1.1s cubic-bezier(0.4,0,0.2,1)", width: 0 }} />
      </div>
    </div>
  );
}

// ─── Alert Flash Banner ───────────────────────────────────────────────────────
function AlertBanner({ errors }: { errors: string[] }) {
  if (!errors.length) return null;
  return (
    <div className="flex items-start gap-3 p-3.5 rounded-xl border border-red-500/25 bg-red-950/20 shadow animate-pulse-slow">
      <AlertTriangle className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
      <div className="flex flex-col gap-1">
        <span className="text-xs font-bold text-red-300 uppercase tracking-wider">Intake Blockers Detected</span>
        {errors.map((e, i) => <span key={i} className="text-xs text-red-400/80">{e}</span>)}
      </div>
    </div>
  );
}

// ─── Main Overview Page ───────────────────────────────────────────────────────
export default function AresOverviewPage({
  overview, metrics, hasLoadedInput, inventory, busyAction, runAction,
}: {
  overview: OverviewData | null;
  metrics: any;
  hasLoadedInput: boolean;
  inventory: any;
  busyAction: string;
  runAction: (action: string, params?: any) => Promise<void>;
}) {
  const topActions = overview?.top_actions || [];
  const workQueue = overview?.work_queue || [];
  const validation = overview?.validation || { blocking_errors: [], parseable_exports: [], exports_found: 0, inbox_messages: 0 };
  const counts = inventory?.counts || {};
  const paths = overview?.paths || {};

  const agingData = [
    { label: "0–30 days (current)", value: 420000, color: "#10b981" },
    { label: "31–60 days", value: 180000, color: "#f59e0b" },
    { label: "61–90 days", value: 65000, color: "#f97316" },
    { label: "90+ days (overdue)", value: 42000, color: "#ef4444" },
  ];

  const stockItems = [
    { item: "Fortune Mustard Oil 1L", stock: 12, trigger: 50 },
    { item: "Tata Salt 1kg", stock: 85, trigger: 200 },
    { item: "Aashirvaad Atta 10kg", stock: 45, trigger: 40 },
    { item: "MDH Garam Masala 100g", stock: 18, trigger: 100 },
    { item: "Amul Butter 100g", stock: 6, trigger: 30 },
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* Blocking errors */}
      <AlertBanner errors={validation.blocking_errors} />

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard label="Pending Approvals" value={metrics.pending_approvals} icon={UserCheck} color="text-amber-500" bg="bg-amber-500/[0.04] border-amber-500/15" trend="up" alert />
        <StatCard label="Active Orders" value={metrics.pending_orders} icon={Activity} color="text-emerald-500" bg="bg-emerald-500/[0.04] border-emerald-500/15" />
        <StatCard label="Overdue Invoices" value={metrics.overdue_invoices} icon={TrendingDown} color="text-red-400" bg="bg-red-400/[0.04] border-red-400/15" trend="up" alert />
        <StatCard label="Low-Stock SKUs" value={metrics.low_stock_skus} icon={Layers} color="text-orange-400" bg="bg-orange-400/[0.04] border-orange-400/15" trend="up" alert />
        <StatCard label="Input Blockers" value={metrics.input_blockers} icon={AlertTriangle} color="text-red-500" bg="bg-red-500/[0.04] border-red-500/15" alert />
        <StatCard label="Intake Files" value={metrics.files_found} icon={FileText} color="text-blue-400" bg="bg-blue-400/[0.04] border-blue-400/15" />
      </div>

      {/* Analytics Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Collections Aging Donut */}
        <div className="p-5 rounded-xl border border-zinc-800/60 bg-gradient-to-br from-zinc-900/50 to-zinc-950/30 shadow-lg backdrop-blur-sm">
          <div className="flex items-center justify-between mb-5 border-b border-zinc-800/40 pb-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-amber-500" />
              <h2 className="text-xs font-bold uppercase tracking-widest text-amber-100">Collections Aging</h2>
            </div>
            <span className="text-[10px] text-zinc-500 bg-zinc-950 px-2 py-0.5 rounded-full border border-zinc-800">Outstanding Dues</span>
          </div>
          <DonutChart segments={agingData} />
        </div>

        {/* Stock Levels */}
        <div className="p-5 rounded-xl border border-zinc-800/60 bg-gradient-to-br from-zinc-900/50 to-zinc-950/30 shadow-lg backdrop-blur-sm">
          <div className="flex items-center justify-between mb-5 border-b border-zinc-800/40 pb-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-amber-500" />
              <h2 className="text-xs font-bold uppercase tracking-widest text-amber-100">Stock vs Reorder Threshold</h2>
            </div>
            <span className="text-[10px] text-zinc-500 bg-zinc-950 px-2 py-0.5 rounded-full border border-zinc-800">Live</span>
          </div>
          <div className="flex flex-col gap-3.5">
            {stockItems.map((s, i) => {
              const isLow = s.stock <= s.trigger;
              return (
                <div key={i} className="flex flex-col gap-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-zinc-300 font-medium">{s.item}</span>
                    <span className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-bold border",
                      isLow
                        ? "bg-red-950/50 text-red-400 border-red-900/30"
                        : "bg-emerald-950/50 text-emerald-400 border-emerald-900/30"
                    )}>
                      {s.stock} / {s.trigger}
                    </span>
                  </div>
                  <ProgressRow
                    label="" value={s.stock} max={s.trigger * 2}
                    color={isLow ? "#ef4444" : "#10b981"}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Work Queue + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Operations Queue */}
        <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-zinc-800/40 pb-3">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-500" />
              <h2 className="text-xs font-bold uppercase tracking-widest text-amber-100">Operations Queue</h2>
            </div>
            <span className={cn("text-[10px] px-2 py-0.5 rounded-full border",
              hasLoadedInput ? "bg-emerald-950 text-emerald-400 border-emerald-900/30" : "bg-zinc-950 text-zinc-500 border-zinc-800"
            )}>{hasLoadedInput ? "Active" : "Pending Intake"}</span>
          </div>

          {workQueue.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 gap-3 text-zinc-500">
              <CheckCircle2 className="h-8 w-8 text-emerald-500/50" />
              <span className="text-sm font-medium">All clear — records up to date</span>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {workQueue.slice(0, 4).map((item, idx) => (
                <div key={idx} className={cn(
                  "flex items-start gap-3 p-3.5 rounded-lg border bg-zinc-950/40",
                  item.status === "ready" ? "border-emerald-900/50 hover:border-emerald-700/50" :
                  item.status === "blocked" || item.status === "needs_input" ? "border-red-900/40" :
                  "border-amber-900/40"
                )}>
                  <span className={cn("h-2 w-2 rounded-full mt-1.5 shrink-0",
                    item.status === "ready" ? "bg-emerald-500 animate-pulse" :
                    item.status === "blocked" ? "bg-red-500" :
                    item.status === "approval" ? "bg-amber-500 animate-pulse" :
                    "bg-zinc-500"
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold text-zinc-100 uppercase tracking-wide">{item.title}</p>
                    <p className="text-xs text-zinc-500 mt-0.5 leading-relaxed">{item.detail}</p>
                  </div>
                  {item.action && (
                    <button
                      onClick={() => runAction(item.action!)}
                      disabled={busyAction === item.action}
                      className="shrink-0 h-7 px-3 rounded border border-emerald-900 bg-emerald-950/30 text-[11px] font-bold text-emerald-400 hover:bg-emerald-900/30 transition-colors"
                    >
                      {busyAction === item.action ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Run"}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Today's Priorities */}
        <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg flex flex-col gap-4">
          <div className="flex items-center justify-between border-b border-zinc-800/40 pb-3">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-500" />
              <h2 className="text-xs font-bold uppercase tracking-widest text-amber-100">Today's Priority Actions</h2>
            </div>
            <span className="text-[10px] text-zinc-500">{topActions.length} tasks</span>
          </div>

          {topActions.length > 0 ? (
            <ol className="flex flex-col gap-2.5">
              {topActions.map((action, idx) => (
                <li key={idx} className="flex items-start gap-3 group">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-500/10 border border-amber-500/20 text-[10px] font-black text-amber-500 shrink-0 mt-0.5">
                    {idx + 1}
                  </span>
                  <span className="text-xs text-zinc-300 leading-relaxed group-hover:text-zinc-100 transition-colors">{action}</span>
                </li>
              ))}
            </ol>
          ) : (
            <div className="flex flex-col gap-4">
              {overview?.primary_commands?.slice(0, 4).map((cmd) => (
                <button
                  key={cmd.id}
                  onClick={() => cmd.action && runAction(cmd.action)}
                  disabled={!cmd.action || busyAction === cmd.action}
                  className="flex items-center gap-3 p-3 rounded-lg border border-zinc-800 bg-zinc-950/40 hover:border-amber-500/30 hover:bg-zinc-900/60 transition-all text-left group disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex-1">
                    <p className="text-xs font-bold uppercase tracking-wide text-zinc-200 group-hover:text-amber-100">{cmd.label}</p>
                    <p className="text-[10px] text-zinc-500 mt-0.5">{cmd.intent}</p>
                  </div>
                  {busyAction === cmd.action
                    ? <RefreshCw className="h-3.5 w-3.5 text-amber-500 animate-spin shrink-0" />
                    : <ArrowRight className="h-3.5 w-3.5 text-zinc-600 group-hover:text-amber-500 transition-colors shrink-0" />
                  }
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Data Inventory */}
      <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg">
        <div className="flex items-center gap-2 mb-4">
          <FileText className="h-4 w-4 text-amber-500" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-amber-100">Local Data Proof</h2>
          <span className="ml-auto text-[10px] text-zinc-500">Aggregated database counts</span>
        </div>
        <div className="grid grid-cols-4 sm:grid-cols-8 gap-3">
          {[
            { label: "Customers", val: counts.customers },
            { label: "Invoices", val: counts.invoices },
            { label: "Stock", val: counts.stock_records },
            { label: "Orders", val: counts.orders },
            { label: "Approvals", val: counts.pending_approvals },
            { label: "Runs", val: counts.workflow_runs },
            { label: "Reports", val: counts.reports },
            { label: "Audit Logs", val: counts.action_logs },
          ].map((c, idx) => (
            <div key={idx} className="p-3 rounded-lg border border-zinc-900 bg-zinc-950/60 flex flex-col gap-1 text-center shadow-inner">
              <span className="text-[9px] font-bold text-zinc-600 uppercase tracking-wider">{c.label}</span>
              <span className="text-xl font-black text-zinc-100 font-mono"><AnimatedNumber value={c.val || 0} /></span>
            </div>
          ))}
        </div>
      </div>

      {/* Intake paths */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          { label: "Exports Dir", path: paths.exports },
          { label: "Inbox Dir", path: paths.inbox },
          { label: "Reports Dir", path: paths.reports },
        ].map((p, i) => (
          <div key={i} className="flex items-center gap-2.5 p-3 rounded-lg border border-zinc-900 bg-zinc-950/40">
            <span className="text-[10px] font-bold text-zinc-500 uppercase shrink-0 w-16">{p.label}</span>
            <code className="text-[10px] text-emerald-400 font-mono overflow-hidden text-ellipsis whitespace-nowrap flex-1">{p.path || "—"}</code>
          </div>
        ))}
      </div>
    </div>
  );
}
