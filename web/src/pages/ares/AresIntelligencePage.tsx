import { useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  FileDown,
  FileText,
  RefreshCw,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { OverviewData } from "./AresShared";

// ─── Markdown Renderer ────────────────────────────────────────────────────────
function renderMarkdown(text: string) {
  if (!text) return null;
  return text.split("\n").map((line, idx) => {
    const trim = line.trim();
    if (trim.startsWith("# ")) return <h1 key={idx} className="text-lg font-black text-amber-500 mt-5 mb-2 uppercase tracking-wide border-b border-amber-500/20 pb-1">{trim.slice(2)}</h1>;
    if (trim.startsWith("## ")) return <h2 key={idx} className="text-sm font-bold text-amber-400 mt-4 mb-2 uppercase tracking-wide">{trim.slice(3)}</h2>;
    if (trim.startsWith("### ")) return <h3 key={idx} className="text-xs font-semibold text-amber-200 mt-3 mb-1">{trim.slice(4)}</h3>;
    if (trim.startsWith("- ") || trim.startsWith("* ")) return <li key={idx} className="ml-5 mb-1 list-disc text-zinc-300 text-xs">{trim.slice(2)}</li>;
    if (!trim) return <div key={idx} className="h-2" />;
    return <p key={idx} className="mb-2 text-zinc-300 leading-relaxed text-xs">{trim}</p>;
  });
}

// ─── GST Compliance Panel ─────────────────────────────────────────────────────
function GSTPanel({
  overview, busyAction, runAction,
}: {
  overview: OverviewData | null;
  busyAction: string;
  runAction: (a: string, p?: any) => Promise<void>;
}) {
  const [gstin, setGstin] = useState("");
  const [period, setPeriod] = useState("");

  const gstrCommands = (overview?.command_groups || [])
    .flatMap((g) => g.commands)
    .filter((c) => c.action && c.action.includes("gstr"));

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          { label: "GSTR-1 Status", value: "Not Filed", color: "text-red-400", bg: "bg-red-950/20 border-red-900/30" },
          { label: "IRN Generated", value: "0", color: "text-amber-400", bg: "bg-amber-950/20 border-amber-900/30" },
          { label: "E-Way Bills", value: "0 Active", color: "text-zinc-400", bg: "bg-zinc-950/40 border-zinc-800" },
        ].map((s, i) => (
          <div key={i} className={cn("p-3.5 rounded-xl border flex flex-col gap-1", s.bg)}>
            <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{s.label}</span>
            <span className={cn("text-lg font-black font-mono", s.color)}>{s.value}</span>
          </div>
        ))}
      </div>

      <div className="p-4 rounded-xl border border-zinc-800/60 bg-zinc-950/30 flex flex-col gap-3">
        <h4 className="text-xs font-bold text-amber-100 uppercase tracking-wide">Generate GSTR-1 Filing</h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Filing Period</label>
            <input
              type="text"
              placeholder="e.g. 2026-04"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="h-9 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-200 px-3 focus:outline-none focus:border-amber-500/50 placeholder:text-zinc-700"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">Seller GSTIN</label>
            <input
              type="text"
              placeholder="15-character GSTIN"
              value={gstin}
              onChange={(e) => setGstin(e.target.value.toUpperCase())}
              className="h-9 rounded-lg bg-zinc-950 border border-zinc-800 text-xs text-zinc-200 px-3 focus:outline-none focus:border-amber-500/50 placeholder:text-zinc-700 font-mono"
            />
          </div>
        </div>
        <button
          onClick={() => runAction("prepare-gstr1", { period, seller_gstin: gstin })}
          disabled={busyAction === "prepare-gstr1" || !period || !gstin}
          className="h-9 w-fit px-6 rounded-lg border border-amber-900/60 bg-amber-950/20 text-xs font-bold text-amber-300 hover:bg-amber-950/40 transition-colors disabled:opacity-40 flex items-center gap-2"
        >
          {busyAction === "prepare-gstr1" ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : null}
          Prepare GSTR-1 Package
        </button>
      </div>

      {gstrCommands.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {gstrCommands.map((cmd) => (
            <div key={cmd.id} className="p-3.5 rounded-xl border border-zinc-800/60 bg-zinc-950/30 flex flex-col gap-2">
              <p className="text-xs font-bold text-zinc-100">{cmd.label}</p>
              <code className="text-[10px] font-mono text-emerald-400 bg-zinc-950 border border-zinc-900 p-1.5 rounded">{cmd.command}</code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Collections Full Analytics ───────────────────────────────────────────────
function CollectionsAnalytics() {
  const brackets = [
    { label: "0–30 Days (Current)", value: 420000, max: 700000, color: "#10b981", bgBar: "#10b98133" },
    { label: "31–60 Days", value: 180000, max: 700000, color: "#f59e0b", bgBar: "#f59e0b22" },
    { label: "61–90 Days", value: 65000, max: 700000, color: "#f97316", bgBar: "#f9731622" },
    { label: "90+ Days Overdue", value: 42000, max: 700000, color: "#ef4444", bgBar: "#ef444422" },
  ];
  const total = brackets.reduce((s, b) => s + b.value, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="p-3 rounded-xl border border-zinc-800/60 bg-zinc-950/40">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Total Outstanding</span>
          <p className="text-xl font-black font-mono text-zinc-100 mt-0.5">₹{(total / 100000).toFixed(2)}L</p>
        </div>
        <div className="p-3 rounded-xl border border-red-900/30 bg-red-950/15">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Overdue (90+)</span>
          <p className="text-xl font-black font-mono text-red-400 mt-0.5">₹42k</p>
        </div>
        <div className="p-3 rounded-xl border border-emerald-900/30 bg-emerald-950/15">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Current (0–30d)</span>
          <p className="text-xl font-black font-mono text-emerald-400 mt-0.5">60%</p>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {brackets.map((b, i) => {
          const pct = (b.value / b.max) * 100;
          return (
            <div key={i} className="flex flex-col gap-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-zinc-300 font-medium">{b.label}</span>
                <div className="flex gap-3">
                  <span className="text-zinc-500 font-mono">{((b.value / total) * 100).toFixed(0)}%</span>
                  <span className="font-bold font-mono" style={{ color: b.color }}>
                    ₹{b.value >= 100000 ? `${(b.value / 100000).toFixed(1)}L` : `${(b.value / 1000).toFixed(0)}k`}
                  </span>
                </div>
              </div>
              <div className="h-4 rounded-lg overflow-hidden" style={{ background: b.bgBar, border: `1px solid ${b.color}22` }}>
                <div
                  className="h-full rounded-lg"
                  style={{
                    width: `${pct}%`,
                    background: `linear-gradient(90deg, ${b.color}88, ${b.color})`,
                    transition: "width 1.2s cubic-bezier(0.4,0,0.2,1)"
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Top debtors */}
      <div className="mt-2">
        <h4 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-3">Top Outstanding Accounts</h4>
        <div className="rounded-xl border border-zinc-800/60 overflow-hidden">
          <div className="grid grid-cols-4 gap-2 p-3 bg-zinc-950/60 border-b border-zinc-800/40">
            {["Customer", "Days Pending", "Amount", "Risk"].map((h) => (
              <span key={h} className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{h}</span>
            ))}
          </div>
          {[
            { name: "City Mart", days: 92, amount: 42000, risk: "HIGH" },
            { name: "Sharma Traders", days: 67, amount: 23500, risk: "MED" },
            { name: "Patel Kirana", days: 45, amount: 12000, risk: "LOW" },
          ].map((row, i) => (
            <div key={i} className="grid grid-cols-4 gap-2 p-3 hover:bg-zinc-900/20 transition-colors items-center border-b border-zinc-900/40">
              <span className="text-xs text-zinc-200">{row.name}</span>
              <span className="text-xs font-mono text-zinc-400">{row.days}d</span>
              <span className="text-xs font-mono font-bold text-zinc-200">₹{row.amount.toLocaleString("en-IN")}</span>
              <span className={cn(
                "text-[10px] font-black px-1.5 py-0.5 rounded border w-fit",
                row.risk === "HIGH" ? "text-red-400 bg-red-950/40 border-red-900/30" :
                row.risk === "MED" ? "text-amber-400 bg-amber-950/40 border-amber-900/30" :
                "text-emerald-400 bg-emerald-950/40 border-emerald-900/30"
              )}>{row.risk}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Stock Heatmap ────────────────────────────────────────────────────────────
function StockHeatmap() {
  const items = [
    { name: "Fortune Mustard Oil 1L", stock: 12, trigger: 50, unit: "Ctns" },
    { name: "Tata Salt 1kg", stock: 85, trigger: 200, unit: "Bags" },
    { name: "Aashirvaad Atta 10kg", stock: 45, trigger: 40, unit: "Bags" },
    { name: "MDH Garam Masala 100g", stock: 18, trigger: 100, unit: "Boxes" },
    { name: "Amul Butter 100g", stock: 6, trigger: 30, unit: "Packs" },
    { name: "Maggi 2-Min Noodles 420g", stock: 120, trigger: 100, unit: "Cases" },
    { name: "Parle-G Biscuits 799g", stock: 34, trigger: 80, unit: "Cartons" },
    { name: "Britannia Milk Bikis", stock: 78, trigger: 60, unit: "Boxes" },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-4 text-[10px] text-zinc-500 pb-1">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded bg-red-500" />Critical (&lt;50% threshold)</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded bg-amber-500" />Warning (50–100%)</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded bg-emerald-500" />Healthy (&gt;100%)</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {items.map((item, i) => {
          const ratio = item.stock / item.trigger;
          const color = ratio < 0.5 ? "#ef4444" : ratio < 1 ? "#f59e0b" : "#10b981";
          const bgColor = ratio < 0.5 ? "#ef444415" : ratio < 1 ? "#f59e0b15" : "#10b98115";
          const borderColor = ratio < 0.5 ? "#ef444430" : ratio < 1 ? "#f59e0b30" : "#10b98130";
          const pct = Math.min(100, ratio * 100);
          return (
            <div key={i} className="p-3.5 rounded-xl flex flex-col gap-2" style={{ background: bgColor, border: `1px solid ${borderColor}` }}>
              <div className="flex justify-between items-start">
                <span className="text-xs font-bold text-zinc-200 leading-tight max-w-[60%]">{item.name}</span>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-xs font-black font-mono" style={{ color }}>{item.stock}</span>
                  <span className="text-[10px] text-zinc-500">/ {item.trigger} {item.unit}</span>
                </div>
              </div>
              <div className="h-2 rounded-full bg-zinc-950/50 overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color, transition: "width 1s ease" }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Command Board ────────────────────────────────────────────────────────────
function CommandBoard({
  overview, busyAction, runAction,
}: {
  overview: OverviewData | null;
  busyAction: string;
  runAction: (a: string, p?: any) => Promise<void>;
}) {
  const [copied, setCopied] = useState("");
  const groups = overview?.command_groups || [];

  const doCopy = async (id: string, cmd: string) => {
    await navigator.clipboard.writeText(cmd).catch(() => {});
    setCopied(id);
    setTimeout(() => setCopied(""), 1500);
  };

  if (!groups.length) {
    return (
      <div className="text-center py-8 text-zinc-500 text-xs border border-zinc-800/40 rounded-xl border-dashed">
        No commands available — load business data to unlock the command board
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {groups.map((group) => (
        <div key={group.section}>
          <h4 className="text-[10px] font-black uppercase tracking-widest text-amber-500/70 mb-3 border-b border-zinc-900 pb-2">{group.section}</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {group.commands.map((cmd) => {
              const needsData = cmd.state === "needs_data";
              return (
                <div key={cmd.id} className={cn(
                  "p-3.5 rounded-xl border flex flex-col gap-2.5",
                  needsData ? "border-zinc-900 border-dashed opacity-55 bg-zinc-950/20" : "border-zinc-800/60 bg-zinc-950/30"
                )}>
                  <div>
                    <p className="text-xs font-bold text-zinc-100">{cmd.label}</p>
                    <p className="text-[11px] text-zinc-500 mt-0.5">{needsData ? "Needs intake files" : cmd.intent}</p>
                  </div>
                  <code className="text-[10px] font-mono text-emerald-400 bg-zinc-950 border border-zinc-900 p-1.5 rounded overflow-x-auto whitespace-pre-wrap">
                    {cmd.command}
                  </code>
                  <div className="flex gap-2">
                    <button
                      onClick={() => doCopy(cmd.id, cmd.command)}
                      className="flex items-center gap-1.5 h-7 px-2.5 rounded border border-zinc-800 bg-zinc-900 text-[10px] text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                    >
                      {copied === cmd.id ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                      {copied === cmd.id ? "Copied" : "Copy"}
                    </button>
                    {cmd.action && !needsData && (
                      <button
                        onClick={() => runAction(cmd.action!, null)}
                        disabled={busyAction === cmd.action}
                        className="flex items-center gap-1 h-7 px-2.5 rounded border border-amber-900/50 bg-amber-950/15 text-[10px] text-amber-300 hover:bg-amber-950/30 transition-colors disabled:opacity-40"
                      >
                        {busyAction === cmd.action ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Run"}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Reports Gallery ──────────────────────────────────────────────────────────
function ReportsGallery({
  inventory, openReport,
}: {
  inventory: any;
  openReport: (path: string) => Promise<{ name: string; content: string }>;
}) {
  const [viewingReport, setViewingReport] = useState<{ name: string; content: string } | null>(null);
  const [loading, setLoading] = useState<string>("");
  const reports = inventory?.reports || [];

  const open = async (report: { name: string; path: string }) => {
    setLoading(report.path);
    try {
      const data = await openReport(report.path);
      setViewingReport(data);
    } catch (e) {}
    finally { setLoading(""); }
  };

  if (!reports.length) {
    return (
      <div className="text-center py-8 text-zinc-500 text-xs border border-zinc-800/40 rounded-xl border-dashed">
        No reports generated yet — run workflows to produce audit reports
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {reports.map((r: any) => (
          <button
            key={r.name}
            onClick={() => open(r)}
            disabled={loading === r.path}
            className="flex flex-col items-start gap-2 p-3.5 rounded-xl border border-zinc-800/60 bg-zinc-950/30 hover:border-amber-500/30 hover:bg-zinc-900/60 transition-all text-left group"
          >
            {loading === r.path
              ? <RefreshCw className="h-5 w-5 text-amber-500/60 animate-spin" />
              : <FileDown className="h-5 w-5 text-amber-500/50 group-hover:text-amber-500 transition-colors" />
            }
            <span className="text-xs font-bold text-zinc-300 group-hover:text-zinc-100 transition-colors leading-snug">{r.name}</span>
          </button>
        ))}
      </div>

      {/* Report Modal */}
      {viewingReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4" onClick={() => setViewingReport(null)}>
          <div className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-amber-500/30 bg-zinc-950 p-6 shadow-2xl flex flex-col gap-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-amber-500" />
                <h3 className="text-sm font-bold uppercase tracking-wide text-amber-400 truncate">{viewingReport.name}</h3>
              </div>
              <button onClick={() => setViewingReport(null)} className="text-zinc-500 hover:text-zinc-200 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 border border-zinc-900/50 bg-zinc-900/20 p-4 rounded-lg max-h-[60vh] overflow-y-auto font-sans text-sm">
              {renderMarkdown(viewingReport.content)}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Main Intelligence Page ───────────────────────────────────────────────────
export default function AresIntelligencePage({
  overview, busyAction, runAction, inventory, openReport,
}: {
  overview: OverviewData | null;
  busyAction: string;
  runAction: (a: string, p?: any) => Promise<void>;
  inventory: any;
  openReport: (path: string) => Promise<{ name: string; content: string }>;
}) {
  const [activeSection, setActiveSection] = useState("collections");
  const sections = [
    { id: "collections", label: "Collections" },
    { id: "stock", label: "Stock Heatmap" },
    { id: "gst", label: "GST & Compliance" },
    { id: "brief", label: "Daily Brief" },
    { id: "commands", label: "Command Board" },
    { id: "reports", label: "Reports" },
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* Section tabs */}
      <div className="flex flex-wrap gap-1 p-1 rounded-xl bg-zinc-950/60 border border-zinc-800/60 w-fit">
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setActiveSection(s.id)}
            className={cn(
              "h-8 px-3.5 rounded-lg text-xs font-bold transition-all",
              activeSection === s.id
                ? "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                : "text-zinc-500 hover:text-zinc-200"
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Section content */}
      <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg">
        {/* Section header */}
        <div className="flex items-center gap-2 mb-5 border-b border-zinc-800/40 pb-4">
          <BookOpen className="h-4 w-4 text-amber-500" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-amber-100">
            {sections.find((s) => s.id === activeSection)?.label}
          </h2>
        </div>

        {activeSection === "collections" && <CollectionsAnalytics />}
        {activeSection === "stock" && <StockHeatmap />}
        {activeSection === "gst" && <GSTPanel overview={overview} busyAction={busyAction} runAction={runAction} />}

        {activeSection === "brief" && (
          <div className="flex flex-col gap-4">
            {overview?.daily_brief_text ? (
              <div className="p-4 rounded-xl border border-zinc-800/60 bg-zinc-950/30 max-h-[60vh] overflow-y-auto">
                {renderMarkdown(overview.daily_brief_text)}
              </div>
            ) : (
              <div className="text-center py-12 flex flex-col items-center gap-4">
                <div className="h-12 w-12 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500 text-2xl">🌅</div>
                <div>
                  <p className="text-sm font-bold text-zinc-200 mb-1">No daily brief generated yet</p>
                  <p className="text-xs text-zinc-500">Run the morning workflow to get your AI-generated briefing</p>
                </div>
                <button
                  onClick={() => runAction("morning-run")}
                  disabled={busyAction === "morning-run"}
                  className="h-9 px-6 rounded-lg border border-amber-900/60 bg-amber-950/20 text-xs font-bold text-amber-300 hover:bg-amber-950/40 transition-colors flex items-center gap-2"
                >
                  {busyAction === "morning-run" ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : "🌅"} Run Morning Briefing
                </button>
              </div>
            )}
          </div>
        )}

        {activeSection === "commands" && (
          <CommandBoard overview={overview} busyAction={busyAction} runAction={runAction} />
        )}

        {activeSection === "reports" && (
          <ReportsGallery inventory={inventory} openReport={openReport} />
        )}
      </div>
    </div>
  );
}
