import { useCallback, useEffect, useState } from "react";
import { fetchJSON } from "@/lib/api";

export const BASE = "/api/plugins/ares";

// ─── Types ────────────────────────────────────────────────────────────────────
export type AresTone = "emerald" | "amber" | "red" | "blue" | "zinc";
export type AresDisplayStatus = "ready" | "needs_input" | "blocked" | "approval" | "clear" | "empty" | string;

export interface ClientSummary {
  client_slug: string;
  business_name: string;
  owner_name: string;
  language_preference: string;
  timezone: string;
  connector_status: Record<string, "not_configured" | "configured" | "disabled">;
  paths: { root: string; exports: string; inbox: string; reports: string };
  file_counts: { exports: number; inbox: number; reports: number };
}

export interface AresAuditBoundary {
  local_only: boolean;
  approval_first: boolean;
  live_external_api_called: boolean;
  limitation: string;
}

export interface AresReportFile {
  name: string;
  path: string;
  size: number;
  modified_at: number;
}

export interface AresDataFile {
  name: string;
  path: string;
  size: number;
}

export interface AresOperatorAction {
  id: string;
  label: string;
  action: string | null;
  section: string;
  available: boolean;
  state: "ready" | "needs_data" | string;
  command: string;
}

export interface AresOperatorSurface {
  access_model: "dashboard_first";
  operator_home: string;
  cli_role: "admin_dev_fallback";
  local_only: boolean;
  approval_first: boolean;
  live_external_api_called: boolean;
  has_loaded_input: boolean;
  blocking_errors: number;
  primary_action_ids: string[];
  actions: AresOperatorAction[];
}

export interface AresRunReport {
  json_path: string;
  markdown_path: string;
}

export interface AresRunResult {
  client_id: string;
  action: string;
  message: string;
  payload: Record<string, unknown>;
  report: AresRunReport;
  audit: AresAuditBoundary;
}

export interface AresDisplayAction {
  label: string;
  action: string | null;
  status: AresDisplayStatus;
  summary: string;
  cli_fallback: string;
}

export interface AresTodaySummary {
  headline: string;
  status: AresDisplayStatus;
  detail: string;
  next_action: AresDisplayAction | null;
}

export interface AresBusinessCard {
  id: string;
  label: string;
  value: number | string;
  status: AresDisplayStatus;
  tone: AresTone;
  summary: string;
  action: string | null;
}

export interface AresProofItem {
  id: string;
  title: string;
  status: AresDisplayStatus;
  tone: AresTone;
  action: string | null;
  created_at: number | null;
  summary: string;
  path: string;
  size: number;
}

export interface AresReadinessCard {
  id: string;
  label: string;
  status: AresDisplayStatus;
  tone: AresTone;
  summary: string;
  technical_detail: string;
}

export interface AresRecordSummary {
  id: string | null;
  party: string;
  amount: number;
  status: string;
  risk: string;
  next_action: string;
}

export interface AresOperatorView {
  today_summary: AresTodaySummary;
  business_cards: AresBusinessCard[];
  proof_items: AresProofItem[];
  readiness_cards: AresReadinessCard[];
  empty_states: Record<string, string>;
  record_summaries?: {
    invoices?: AresRecordSummary[];
    orders?: AresRecordSummary[];
    stock_records?: AresRecordSummary[];
  };
}

export interface AresRuntimeHealth {
  mode?: string;
  client_id?: string;
  status?: "ready" | "warning" | "blocked" | string;
  checks?: Array<{ id?: string; status?: string; message?: string; [key: string]: unknown }>;
  [key: string]: unknown;
}

export interface OverviewData {
  clients: ClientSummary[];
  selected_client: ClientSummary | null;
  metrics: {
    pending_approvals: number;
    pending_orders: number;
    overdue_invoices: number;
    low_stock_skus: number;
    input_blockers: number;
    files_found: number;
    [key: string]: number;
  };
  validation: {
    blocking_errors: string[];
    parseable_exports: string[];
    exports_found: number;
    inbox_messages: number;
  };
  daily_brief: Record<string, any>;
  daily_brief_text: string;
  top_actions: string[];
  operator_shell: Record<string, any>;
  data_inventory: {
    counts: Record<string, number>;
    reports: AresReportFile[];
    data_files: AresDataFile[];
    has_business_data: boolean;
    has_input_files: boolean;
  };
  work_queue: Array<{
    status: "needs_input" | "ready" | "blocked" | "approval" | "clear";
    title: string;
    detail: string;
    action: string | null;
    command: string;
  }>;
  recent_records: {
    invoices?: Array<Record<string, any>>;
    stock_records?: Array<Record<string, any>>;
    orders?: Array<Record<string, any>>;
    approvals?: Array<Record<string, any>>;
    workflow_runs?: Array<Record<string, any>>;
    action_logs?: Array<Record<string, any>>;
  };
  command_groups: Array<{
    section: string;
    commands: Array<{
      id: string;
      label: string;
      intent: string;
      command: string;
      action: string | null;
      requires_data?: boolean;
      state?: string;
    }>;
  }>;
  primary_commands: Array<{
    id: string;
    label: string;
    intent: string;
    command: string;
    action: string | null;
    requires_data?: boolean;
    state?: string;
  }>;
  operator_surface: AresOperatorSurface;
  operator_view: AresOperatorView;
  paths: Record<string, string>;
  setup_command: string;
  audit: AresAuditBoundary;
}

// ─── Shared Hook ──────────────────────────────────────────────────────────────

export function useAresData() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [selectedClient, setSelectedClientState] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const [busyAction, setBusyAction] = useState<string>("");
  const [lastRun, setLastRun] = useState<AresRunResult | null>(null);
  const [health, setHealth] = useState<AresRuntimeHealth | null>(null);
  const [actionLog, setActionLog] = useState<Array<{ time: string; action: string; message: string; ok: boolean }>>([]);

  const loadOverview = useCallback(async (client: string) => {
    setLoading(true);
    setError("");
    const query = client ? `?client=${encodeURIComponent(client)}` : "";
    try {
      const data = await fetchJSON<OverviewData>(`${BASE}/overview${query}`);
      setOverview(data);
      const active = data.selected_client?.client_slug;
      if (active) setSelectedClientState(active);
    } catch (err: any) {
      setError(err?.message || String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadHealth = useCallback(async (client: string) => {
    const query = client ? `?client=${encodeURIComponent(client)}` : "";
    try {
      setHealth(await fetchJSON<AresRuntimeHealth>(`${BASE}/health${query}`));
    } catch {
      setHealth(null);
    }
  }, []);

  const setSelectedClient = useCallback((slug: string) => {
    setSelectedClientState(slug);
    loadOverview(slug);
    loadHealth(slug);
  }, [loadHealth, loadOverview]);

  useEffect(() => {
    loadOverview("");
    loadHealth("");
  }, [loadHealth, loadOverview]);

  // WebSocket real-time updates
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}${BASE}/ws`;
    let socket: WebSocket | null = null;
    let reconnectTimer: any = null;

    function connect() {
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "update") {
            loadOverview(selectedClient);
            loadHealth(selectedClient);
          }
        } catch (_) {}
      };
      socket.onclose = () => { reconnectTimer = setTimeout(connect, 3000); };
    }
    connect();
    return () => { if (socket) socket.close(); if (reconnectTimer) clearTimeout(reconnectTimer); };
  }, [selectedClient, loadHealth, loadOverview]);

  const runAction = useCallback(async (action: string, params: Record<string, any> | null = null) => {
    if (!selectedClient) return;
    setBusyAction(action);
    setError("");
    const ts = new Date().toLocaleTimeString("en-IN", { hour12: false });
    try {
      const data = await fetchJSON<AresRunResult>(`${BASE}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client: selectedClient, action, params }),
      });
      setLastRun(data);
      setActionLog(prev => [{ time: ts, action, message: data.message || "Done", ok: true }, ...prev.slice(0, 49)]);
      await loadOverview(selectedClient);
      await loadHealth(selectedClient);
      return data;
    } catch (err: any) {
      const msg = err?.message || String(err);
      setError(msg);
      setActionLog(prev => [{ time: ts, action, message: msg, ok: false }, ...prev.slice(0, 49)]);
    } finally {
      setBusyAction("");
    }
  }, [selectedClient, loadHealth, loadOverview]);

  const openReport = useCallback(async (reportPath: string): Promise<{ name: string; content: string }> => {
    return fetchJSON<{ name: string; content: string }>(
      `${BASE}/report?client=${encodeURIComponent(selectedClient)}&path=${encodeURIComponent(reportPath)}`
    );
  }, [selectedClient]);

  const clients = overview?.clients || [];
  const metrics = overview?.metrics || { pending_approvals: 0, pending_orders: 0, overdue_invoices: 0, low_stock_skus: 0, input_blockers: 0, files_found: 0 };
  const selected = overview?.selected_client || null;
  const inventory = overview?.data_inventory || { counts: {}, reports: [], data_files: [], has_business_data: false, has_input_files: false };
  const hasLoadedInput = Boolean(inventory.has_business_data || inventory.has_input_files);

  return {
    overview, clients, metrics, selected, selectedClient, setSelectedClient,
    loading, error, setError, busyAction, lastRun, health, actionLog, hasLoadedInput, inventory,
    loadOverview, loadHealth, runAction, openReport,
  };
}
