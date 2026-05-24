import { useState } from "react";
import {
  Check,
  CheckCircle2,
  Copy,
  FileText,
  RefreshCw,
  RotateCw,
  Send,
  Wallet,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { OverviewData } from "./AresShared";

// ─── Status Badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    approved: "bg-emerald-950/60 text-emerald-400 border-emerald-900/40",
    pending: "bg-amber-950/60 text-amber-400 border-amber-900/40",
    ready: "bg-blue-950/60 text-blue-400 border-blue-900/40",
    blocked: "bg-red-950/60 text-red-400 border-red-900/40",
    needs_input: "bg-zinc-900/60 text-zinc-400 border-zinc-800",
    approval: "bg-amber-950/60 text-amber-400 border-amber-900/40",
    paid: "bg-emerald-950/60 text-emerald-400 border-emerald-900/40",
    overdue: "bg-red-950/60 text-red-400 border-red-900/40",
    draft: "bg-zinc-900/60 text-zinc-500 border-zinc-800",
    sent: "bg-blue-950/60 text-blue-400 border-blue-900/40",
  };
  const cls = map[status?.toLowerCase()] ?? "bg-zinc-900/60 text-zinc-400 border-zinc-800";
  return (
    <span className={cn("px-2 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wider", cls)}>
      {status || "—"}
    </span>
  );
}


// ─── Command Card (for Tally Sync) ────────────────────────────────────────────
function CommandCard({
  label, intent, command, action, busyAction, runAction, needsData,
}: {
  label: string; intent: string; command: string; action: string | null;
  busyAction: string; runAction: (a: string) => void; needsData: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const doCopy = async () => {
    await navigator.clipboard.writeText(command).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className={cn(
      "p-4 rounded-xl border bg-zinc-950/40 flex flex-col gap-3",
      needsData ? "border-zinc-900/50 border-dashed opacity-60" : "border-zinc-800/60"
    )}>
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-zinc-100">{label}</p>
        <p className="text-[11px] text-zinc-500 mt-1">{needsData ? "Requires intake files" : intent}</p>
      </div>
      <code className="text-[10px] font-mono p-2 rounded bg-zinc-950 border border-zinc-900 text-emerald-400 select-all overflow-x-auto whitespace-pre-wrap">
        {command}
      </code>
      <div className="flex gap-2">
        <button onClick={doCopy} className="flex items-center gap-1.5 h-7 px-3 rounded border border-zinc-800 bg-zinc-900 text-[11px] text-zinc-300 hover:bg-zinc-800 transition-colors">
          {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
        {action && (
          <button
            onClick={() => !needsData && runAction(action)}
            disabled={busyAction === action || needsData}
            className="flex items-center gap-1.5 h-7 px-3 rounded border border-amber-900/60 bg-amber-950/20 text-[11px] text-amber-300 hover:bg-amber-950/40 transition-colors disabled:opacity-40"
          >
            {busyAction === action ? <RefreshCw className="h-3 w-3 animate-spin" /> : "Run"}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Tab Components ───────────────────────────────────────────────────────────

function OrdersTab({ overview }: { overview: OverviewData | null }) {
  const orders = overview?.recent_records?.orders || [];
  const mockOrders = orders.length > 0 ? orders : [
    { id: "ORD-001", customer_id: "Sharma Traders", status: "pending", items: [{ name: "X" }], amount: 12500, created_at: "2026-05-23" },
    { id: "ORD-002", customer_id: "Gupta Brothers", status: "approved", items: [{ name: "A" }, { name: "B" }], amount: 8750, created_at: "2026-05-22" },
    { id: "ORD-003", customer_id: "Patel Kirana", status: "blocked", items: [{ name: "C" }], amount: 5200, created_at: "2026-05-22" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 pb-1">
        <span className="text-xs text-zinc-500">{mockOrders.length} orders in system</span>
        <span className="ml-auto text-[10px] text-amber-400 bg-amber-950/20 border border-amber-900/30 px-2 py-0.5 rounded-full">
          {mockOrders.filter((o: any) => o.status === "pending").length} pending approval
        </span>
      </div>
      <div className="rounded-xl border border-zinc-800/60 overflow-hidden">
        <div className="grid grid-cols-5 gap-2 p-3 bg-zinc-950/60 border-b border-zinc-800/40">
          {["Order ID", "Customer", "Status", "Items", "Amount"].map((h) => (
            <span key={h} className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{h}</span>
          ))}
        </div>
        <div className="divide-y divide-zinc-900/60">
          {mockOrders.map((order: any, i: number) => (
            <div key={i} className="grid grid-cols-5 gap-2 p-3 hover:bg-zinc-900/30 transition-colors items-center">
              <span className="text-xs font-mono text-zinc-200">{order.id || order.order_id || `ORD-${String(i + 1).padStart(3, "0")}`}</span>
              <span className="text-xs text-zinc-300 truncate">{order.customer_id || "—"}</span>
              <StatusBadge status={order.status} />
              <span className="text-xs text-zinc-400">{(order.items || []).length} items</span>
              <span className="text-xs font-mono text-zinc-200">₹{(order.amount || 0).toLocaleString("en-IN")}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function InvoicesTab({ overview }: { overview: OverviewData | null }) {
  const invoices = overview?.recent_records?.invoices || [];
  const mockInvoices = invoices.length > 0 ? invoices : [
    { invoice_number: "INV-2026-001", customer_id: "Sharma Traders", amount: 15750, tax_amount: 2362, status: "sent", date: "2026-05-23" },
    { invoice_number: "INV-2026-002", customer_id: "Gupta Brothers", amount: 8900, tax_amount: 1335, status: "paid", date: "2026-05-20" },
    { invoice_number: "INV-2026-003", customer_id: "City Mart", amount: 42000, tax_amount: 6300, status: "overdue", date: "2026-04-15" },
    { invoice_number: "INV-2026-004", customer_id: "Patel Kirana", amount: 6500, tax_amount: 975, status: "draft", date: "2026-05-22" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 pb-1 flex-wrap">
        <span className="text-xs text-zinc-500">{mockInvoices.length} invoices total</span>
        <span className="text-[10px] text-red-400 bg-red-950/20 border border-red-900/30 px-2 py-0.5 rounded-full">
          {mockInvoices.filter((i: any) => i.status === "overdue").length} overdue
        </span>
        <span className="text-[10px] text-amber-400 bg-amber-950/20 border border-amber-900/30 px-2 py-0.5 rounded-full">
          {mockInvoices.filter((i: any) => i.status === "draft").length} drafts
        </span>
      </div>
      <div className="rounded-xl border border-zinc-800/60 overflow-hidden">
        <div className="grid grid-cols-6 gap-2 p-3 bg-zinc-950/60 border-b border-zinc-800/40">
          {["Invoice #", "Customer", "Amount", "GST", "Status", "Action"].map((h) => (
            <span key={h} className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{h}</span>
          ))}
        </div>
        <div className="divide-y divide-zinc-900/60">
          {mockInvoices.map((inv: any, i: number) => (
            <div key={i} className="grid grid-cols-6 gap-2 p-3 hover:bg-zinc-900/30 transition-colors items-center">
              <span className="text-xs font-mono text-zinc-200">{inv.invoice_number}</span>
              <span className="text-xs text-zinc-300 truncate">{inv.customer_id}</span>
              <span className="text-xs font-mono text-zinc-200">₹{inv.amount?.toLocaleString("en-IN")}</span>
              <span className="text-xs font-mono text-zinc-400">₹{inv.tax_amount?.toLocaleString("en-IN")}</span>
              <StatusBadge status={inv.status} />
              <button className="flex items-center gap-1 h-6 px-2 rounded border border-zinc-800 bg-zinc-900 text-[10px] text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors w-fit">
                <Send className="h-2.5 w-2.5" />
                Send
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ApprovalsTab({
  overview, busyAction, runAction,
}: {
  overview: OverviewData | null;
  busyAction: string;
  runAction: (a: string, p?: any) => Promise<void>;
}) {
  const [replyText, setReplyText] = useState<Record<string, string>>({});
  const approvals = overview?.recent_records?.approvals || [];
  const mockApprovals = approvals.length > 0 ? approvals : [
    { id: "APR-001", type: "order_discount", status: "pending", proposed_action: "Apply 5% discount for Sharma Traders (₹15,750)", customer: "Sharma Traders", amount: 787 },
    { id: "APR-002", type: "credit_extension", status: "pending", proposed_action: "Extend credit limit to ₹50,000 for Gupta Brothers", customer: "Gupta Brothers", amount: 50000 },
    { id: "APR-003", type: "return_request", status: "pending", proposed_action: "Accept return of 12 units Tata Salt 1kg from City Mart", customer: "City Mart", amount: 360 },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 pb-1">
        <span className="text-xs text-zinc-500">{mockApprovals.length} pending approvals</span>
        <span className="ml-auto text-xs text-amber-400 animate-pulse">● Action required</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {mockApprovals.map((apr: any, i: number) => (
          <div key={i} className="p-4 rounded-xl border border-amber-900/30 bg-amber-950/10 flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-amber-500">
                    {(apr.type || "approval").replace(/_/g, " ")}
                  </span>
                  <StatusBadge status={apr.status} />
                </div>
                <p className="text-xs text-zinc-200 leading-relaxed">{apr.proposed_action}</p>
              </div>
            </div>
            {apr.customer && (
              <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
                <span className="text-zinc-600">Customer:</span> {apr.customer}
                {apr.amount && <span className="ml-auto font-bold text-zinc-300">₹{apr.amount?.toLocaleString("en-IN")}</span>}
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <input
                type="text"
                placeholder="Reply (e.g. haan, approved)"
                value={replyText[apr.id] || ""}
                onChange={(e) => setReplyText({ ...replyText, [apr.id]: e.target.value })}
                className="h-8 w-full rounded bg-zinc-950 border border-zinc-800 text-xs text-zinc-200 px-3 focus:outline-none focus:border-amber-500/50 placeholder:text-zinc-700"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => runAction("mobile-reply", { reply: `approved ${apr.id}` })}
                  disabled={busyAction === "mobile-reply"}
                  className="flex-1 h-8 rounded border border-emerald-900/60 bg-emerald-950/20 text-[11px] font-bold text-emerald-400 hover:bg-emerald-900/30 transition-colors flex items-center justify-center gap-1.5"
                >
                  <CheckCircle2 className="h-3 w-3" />
                  Approve
                </button>
                <button
                  onClick={() => runAction("mobile-reply", { reply: `rejected ${apr.id}` })}
                  disabled={busyAction === "mobile-reply"}
                  className="flex-1 h-8 rounded border border-red-900/60 bg-red-950/20 text-[11px] font-bold text-red-400 hover:bg-red-900/30 transition-colors flex items-center justify-center gap-1.5"
                >
                  <X className="h-3 w-3" />
                  Reject
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SyncTab({
  overview, busyAction, runAction,
}: {
  overview: OverviewData | null;
  busyAction: string;
  runAction: (a: string) => void;
}) {
  const syncCommands = (overview?.command_groups || [])
    .flatMap((g) => g.commands)
    .filter((c) => ["push-to-tally", "pull-ledger", "push-stock", "sync-tally"].includes(c.action || ""))
    .slice(0, 4);

  const allCommands = overview?.command_groups?.flatMap((g) => g.commands).slice(0, 6) || [];
  const displayCommands = syncCommands.length > 0 ? syncCommands : allCommands;

  return (
    <div className="flex flex-col gap-4">
      {/* Status Row */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Tally Gateway", status: "Checking...", icon: RotateCw, ok: false },
          { label: "WhatsApp Webhook", status: "Not configured", icon: Send, ok: false },
          { label: "Payment Gateway", status: "Sandbox", icon: Wallet, ok: true },
        ].map((item, i) => (
          <div key={i} className={cn(
            "p-3.5 rounded-xl border flex flex-col gap-2",
            item.ok ? "border-emerald-900/40 bg-emerald-950/10" : "border-zinc-800/60 bg-zinc-950/30"
          )}>
            <div className="flex items-center gap-2">
              <item.icon className={cn("h-4 w-4", item.ok ? "text-emerald-400" : "text-zinc-500")} />
              <span className="text-xs font-bold text-zinc-200">{item.label}</span>
            </div>
            <span className={cn("text-[10px]", item.ok ? "text-emerald-400" : "text-zinc-500")}>{item.status}</span>
          </div>
        ))}
      </div>

      {/* Sync Commands Grid */}
      <div>
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-3">Available Sync Commands</h3>
        {displayCommands.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {displayCommands.map((cmd) => (
              <CommandCard
                key={cmd.id}
                label={cmd.label}
                intent={cmd.intent}
                command={cmd.command}
                action={cmd.action}
                busyAction={busyAction}
                runAction={runAction}
                needsData={Boolean(cmd.state === "needs_data")}
              />
            ))}
          </div>
        ) : (
          <div className="p-6 rounded-xl border border-zinc-800/40 border-dashed text-center text-zinc-500 text-xs">
            No sync commands available — load business data first
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Operations Page ─────────────────────────────────────────────────────
export default function AresOperationsPage({
  overview, busyAction, runAction,
}: {
  overview: OverviewData | null;
  busyAction: string;
  runAction: (a: string, p?: any) => Promise<void>;
}) {
  const tabs = [
    { id: "orders", label: "Orders", icon: FileText },
    { id: "invoices", label: "Invoices", icon: FileText },
    { id: "approvals", label: "Approvals", icon: CheckCircle2 },
    { id: "sync", label: "Sync & Integrations", icon: RotateCw },
  ];
  const [activeTab, setActiveTab] = useState("orders");

  return (
    <div className="flex flex-col gap-5">
      {/* Tab Selector */}
      <div className="flex gap-1 p-1 rounded-xl bg-zinc-950/60 border border-zinc-800/60 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex items-center gap-2 h-8 px-4 rounded-lg text-xs font-bold transition-all",
              activeTab === tab.id
                ? "bg-amber-500/10 text-amber-300 border border-amber-500/20 shadow"
                : "text-zinc-500 hover:text-zinc-200"
            )}
          >
            {tab.label}
            {tab.id === "approvals" && overview && overview.metrics.pending_approvals > 0 && (
              <span className="h-4 w-4 rounded-full bg-red-500 text-[9px] font-black text-white flex items-center justify-center">
                {overview.metrics.pending_approvals}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-5 rounded-xl border border-zinc-800/60 bg-zinc-900/30 shadow-lg">
        {activeTab === "orders" && <OrdersTab overview={overview} />}
        {activeTab === "invoices" && <InvoicesTab overview={overview} />}
        {activeTab === "approvals" && <ApprovalsTab overview={overview} busyAction={busyAction} runAction={runAction} />}
        {activeTab === "sync" && <SyncTab overview={overview} busyAction={busyAction} runAction={runAction as any} />}
      </div>
    </div>
  );
}
