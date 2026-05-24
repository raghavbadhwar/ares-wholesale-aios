(function () {
  const SDK = window.__ARES_PLUGIN_SDK__ || window.__HERMES_PLUGIN_SDK__;
  const registry = window.__ARES_PLUGINS__ || window.__HERMES_PLUGINS__;
  if (!SDK || !registry) return;

  const React = SDK.React;
  const { useCallback, useEffect, useMemo, useState } = SDK.hooks;
  const fetchJSON = SDK.fetchJSON;
  const h = React.createElement;
  const BASE = "/api/plugins/ares";

  function AresHeaderBanner() {
    const path = (window.location.pathname || "").replace(/\/$/, "") || "/";
    if (path !== "/ares" && path !== "/chat") return null;
    return h("div", { className: "ares-header-banner" }, [
      h("span", { className: "ares-header-title", key: "title" }, "Ares Wholesale Command Center"),
      h("span", { className: "ares-header-meta", key: "meta" }, "approval-first / local pilot / wholesaler ops"),
    ]);
  }

  function AresCommandCenter() {
    const [overview, setOverview] = useState(null);
    const [selectedClient, setSelectedClient] = useState("");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [busyAction, setBusyAction] = useState("");
    const [lastRun, setLastRun] = useState(null);
    const [copiedId, setCopiedId] = useState("");
    const [actionParams, setActionParams] = useState({});
    const [viewingReport, setViewingReport] = useState(null);

    const loadOverview = useCallback(async (client) => {
      setLoading(true);
      setError("");
      const query = client ? "?client=" + encodeURIComponent(client) : "";
      try {
        const data = await fetchJSON(BASE + "/overview" + query);
        setOverview(data);
        const active = data.selected_client && data.selected_client.client_slug;
        if (active) setSelectedClient(active);
      } catch (err) {
        setError(err && err.message ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    }, []);

    useEffect(() => {
      loadOverview("");
    }, [loadOverview]);

    useEffect(() => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = protocol + "//" + window.location.host + BASE + "/ws";
      let socket = null;
      let reconnectTimer = null;

      function connect() {
        socket = new WebSocket(wsUrl);
        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "update") {
              loadOverview(selectedClient);
            }
          } catch (e) {
            // ignore
          }
        };
        socket.onclose = () => {
          reconnectTimer = setTimeout(connect, 3000);
        };
      }

      connect();

      return () => {
        if (socket) socket.close();
        if (reconnectTimer) clearTimeout(reconnectTimer);
      };
    }, [selectedClient, loadOverview]);

    const clients = overview && overview.clients ? overview.clients : [];
    const metrics = overview && overview.metrics ? overview.metrics : {};
    const selected = overview && overview.selected_client ? overview.selected_client : null;
    const commandGroups = overview && overview.command_groups ? overview.command_groups : [];
    const primaryCommands = overview && overview.primary_commands ? overview.primary_commands : [];
    const paths = overview && overview.paths ? overview.paths : {};
    const topActions = overview && overview.top_actions ? overview.top_actions : [];
    const inventory = overview && overview.data_inventory ? overview.data_inventory : { counts: {}, reports: [], has_business_data: false, has_input_files: false };
    const counts = inventory.counts || {};
    const hasLoadedInput = Boolean(inventory.has_business_data || inventory.has_input_files);
    const fallbackWorkQueue = selected ? [
      {
        status: "needs_input",
        title: "Load real business files",
        detail: "No invoices, stock records, orders, approvals, inbox messages, or exports are loaded for this client.",
        action: null,
        command: "Drop exports into " + (paths.exports || "the client exports folder") + " and order/payment text into " + (paths.inbox || "the client inbox folder"),
      },
      {
        status: "ready",
        title: "Validate intake folders",
        detail: "Run the local preflight after adding files. It will report parseable exports and blocking issues.",
        action: "validate-inputs",
        command: "ares validate-inputs --client " + selectedClient,
      },
    ] : [];
    const workQueue = overview && Array.isArray(overview.work_queue) && overview.work_queue.length
      ? overview.work_queue
      : (hasLoadedInput ? [] : fallbackWorkQueue);
    const recentRecords = overview && overview.recent_records ? overview.recent_records : {};

    const chatHref = useMemo(() => {
      const basePath = window.__ARES_BASE_PATH__ || "";
      return basePath + "/chat";
    }, []);

    async function runAction(action, params = null) {
      if (!selectedClient) return;
      setBusyAction(action);
      setError("");
      try {
        const data = await fetchJSON(BASE + "/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ client: selectedClient, action, params }),
        });
        setLastRun(data);
        await loadOverview(selectedClient);
      } catch (err) {
        setError(err && err.message ? err.message : String(err));
      } finally {
        setBusyAction("");
      }
    }

    async function openReport(reportPath) {
      setError("");
      try {
        const data = await fetchJSON(BASE + "/report?client=" + encodeURIComponent(selectedClient) + "&path=" + encodeURIComponent(reportPath));
        setViewingReport(data);
      } catch (err) {
        setError("Failed to load report: " + (err && err.message ? err.message : String(err)));
      }
    }

    async function copyCommand(command) {
      try {
        await navigator.clipboard.writeText(command.command);
        setCopiedId(command.id);
        setTimeout(() => setCopiedId(""), 1200);
      } catch (err) {
        setError("Clipboard copy failed.");
      }
    }

    function commandNeedsData(command) {
      return Boolean(command && (command.state === "needs_data" || (command.requires_data && !hasLoadedInput)));
    }

    if (loading && !overview) {
      return h("main", { className: "ares-page ares-loading", "aria-busy": "true" }, "Loading Ares...");
    }

    if (overview && !overview.selected_client) {
      return h("main", { className: "ares-page" }, [
        h("section", { className: "ares-empty", key: "empty" }, [
          h("p", { className: "ares-kicker", key: "kicker" }, "No local Ares client"),
          h("h1", { key: "title" }, "Create a wholesaler workspace"),
          h("code", { key: "code" }, overview.setup_command),
        ]),
      ]);
    }

    return h("main", { className: "ares-page" }, [
      h("section", { className: "ares-topbar", key: "topbar" }, [
        h("div", { className: "ares-title-block", key: "title" }, [
          h("p", { className: "ares-kicker", key: "kicker" }, "Ares wholesaler agent"),
          h("h1", { key: "h1" }, selected ? selected.business_name : "Command Center"),
          h("p", { className: "ares-owner", key: "owner" }, selected ? selected.owner_name + " / " + selected.timezone : ""),
        ]),
        h("div", { className: "ares-client-tools", key: "tools" }, [
          h("select", {
            className: "ares-select",
            value: selectedClient,
            onChange: (event) => {
              const next = event.target.value;
              setSelectedClient(next);
              loadOverview(next);
            },
            key: "select",
          }, clients.map((client) => h("option", { key: client.client_slug, value: client.client_slug }, client.business_name))),
          h("button", { className: "ares-button ares-button-ghost", onClick: () => loadOverview(selectedClient), key: "refresh" }, "Refresh"),
          h("a", { className: "ares-button ares-button-ghost", href: chatHref, key: "chat" }, "Open TUI Chat"),
        ]),
      ]),

      error ? h("div", { className: "ares-alert", role: "alert", key: "error" }, error) : null,

      h("section", { className: "ares-primary-actions", key: "primary" },
        primaryCommands.map((command) => {
          const needsData = commandNeedsData(command);
          return (
          h("button", {
            className: "ares-action" + (needsData ? " ares-action-muted" : ""),
            disabled: !command.action || busyAction === command.action || needsData,
            key: command.id,
            onClick: () => command.action && !needsData && runAction(command.action),
          }, [
            h("span", { className: "ares-action-label", key: "label" }, command.label),
            h("span", { className: "ares-action-intent", key: "intent" }, needsData ? "Needs local invoices, stock, orders, approvals, or input files before this can do real work." : command.intent),
          ])
          );
        }),
      ),

      h("section", { className: "ares-metrics", key: "metrics" }, [
        metric("Pending approvals", metrics.pending_approvals),
        metric("Pending orders", metrics.pending_orders),
        metric("Overdue invoices", metrics.overdue_invoices),
        metric("Low-stock SKUs", metrics.low_stock_skus),
        metric("Input blockers", metrics.input_blockers),
        metric("Files found", metrics.files_found),
      ]),

      h("section", { className: "ares-work", key: "work" }, [
        h("div", { className: "ares-panel-head", key: "head" }, [
          h("h2", { key: "h2" }, "Real Work Queue"),
          h("span", { key: "state" }, hasLoadedInput ? "local data present" : "waiting for files"),
        ]),
        h("div", { className: "ares-work-list", key: "list" },
          workQueue.map((item, index) =>
            h("div", { className: "ares-work-item ares-work-" + item.status, key: index }, [
              h("div", { className: "ares-work-copy", key: "copy" }, [
                h("strong", { key: "title" }, item.title),
                h("span", { key: "detail" }, item.detail),
                h("code", { key: "command" }, item.command),
              ]),
              item.action ? h("button", {
                className: "ares-mini-button ares-mini-button-run",
                disabled: busyAction === item.action,
                onClick: () => runAction(item.action),
                key: "run",
              }, busyAction === item.action ? "Running" : "Run") : null,
            ]),
          ),
        ),
      ]),

      h("section", { className: "ares-grid", key: "grid" }, [
        h("div", { className: "ares-panel", key: "actions" }, [
          h("div", { className: "ares-panel-head", key: "head" }, [
            h("h2", { key: "h2" }, "Today"),
            h("span", { key: "count" }, topActions.length + " actions"),
          ]),
          topActions.length
            ? h("ol", { className: "ares-action-list", key: "list" },
                topActions.map((item, index) => h("li", { key: index }, item)),
              )
            : h("p", { className: "ares-muted", key: "none" }, "No urgent action from current local data."),
        ]),
        h("div", { className: "ares-panel", key: "paths" }, [
          h("div", { className: "ares-panel-head", key: "head" }, [
            h("h2", { key: "h2" }, "Intake"),
            h("span", { key: "state" }, (overview.validation && overview.validation.blocking_errors.length) ? "blocked" : "ready"),
          ]),
          pathRow("Exports", paths.exports),
          pathRow("Inbox", paths.inbox),
          pathRow("Reports", paths.reports),
        ]),
      ]),

      h("section", { className: "ares-data-proof", key: "proof" }, [
        h("div", { className: "ares-panel-head", key: "head" }, [
          h("h2", { key: "h2" }, "Local Data Proof"),
          h("span", { key: "state" }, (inventory.data_files || []).length + " data files / " + (inventory.reports || []).length + " reports"),
        ]),
        h("div", { className: "ares-proof-grid", key: "grid" }, [
          proofMetric("Customers", counts.customers),
          proofMetric("Invoices", counts.invoices),
          proofMetric("Stock rows", counts.stock_records),
          proofMetric("Orders", counts.orders),
          proofMetric("Approvals", counts.pending_approvals),
          proofMetric("Workflow runs", counts.workflow_runs),
          proofMetric("Reports", counts.reports),
          proofMetric("Action logs", counts.action_logs),
        ]),
        recordsTable(recentRecords),
        inventory.reports && inventory.reports.length ? h("div", { className: "ares-recent-reports", key: "recent-reports", style: { marginTop: "16px", padding: "12px", borderTop: "1px dashed #333" } }, [
          h("h4", { style: { color: "#c99a49", marginBottom: "8px", fontSize: "13px" } }, "Recent Reports (Click to View)"),
          h("div", { style: { display: "flex", flexWrap: "wrap", gap: "8px" } },
            inventory.reports.slice(0, 5).map((r) => h("button", {
              className: "ares-mini-button",
              onClick: () => openReport(r.path),
              key: r.name,
              style: { padding: "4px 8px", fontSize: "11px", backgroundColor: "#222", border: "1px solid #444", color: "#e0e0e0" }
            }, r.name))
          )
        ]) : null
      ]),

      h("section", { className: "ares-command-board", key: "commands" }, [
        h("div", { className: "ares-panel-head ares-board-head", key: "head" }, [
          h("h2", { key: "h2" }, "Daily Command Board"),
          h("span", { key: "client" }, selectedClient),
        ]),
        h("div", { className: "ares-command-groups", key: "groups" },
          commandGroups.map((group) =>
            h("div", { className: "ares-command-group", key: group.section }, [
              h("h3", { key: "section" }, group.section),
              group.commands.map((command) =>
                h("div", { className: "ares-command-row" + (commandNeedsData(command) ? " ares-command-row-muted" : ""), key: command.id }, [
                  h("div", { className: "ares-command-copy", key: "copy" }, [
                    h("strong", { key: "label" }, command.label),
                    h("span", { key: "intent" }, commandNeedsData(command) ? "Needs local business data before this can do real work." : command.intent),
                    h("code", { key: "command" }, command.command),
                    command.action === "mobile-reply" ? h("div", { className: "ares-command-input-container", key: "reply-input", style: { display: "flex", gap: "8px", marginTop: "8px" } }, [
                      h("input", {
                        type: "text",
                        placeholder: "e.g. haan appr_sharma",
                        className: "ares-input",
                        value: actionParams["mobile-reply"] || "",
                        onChange: (e) => setActionParams({ ...actionParams, "mobile-reply": e.target.value }),
                        style: {
                          backgroundColor: "#111",
                          border: "1px solid #333",
                          borderRadius: "4px",
                          color: "#fff",
                          padding: "4px 8px",
                          fontSize: "12px",
                          width: "180px"
                        }
                      })
                    ]) : null,
                    command.action === "prepare-gstr1" ? h("div", { className: "ares-command-input-container", key: "gstr1-inputs", style: { display: "flex", gap: "8px", marginTop: "8px" } }, [
                      h("input", {
                        type: "text",
                        placeholder: "Period (YYYY-MM)",
                        className: "ares-input",
                        value: actionParams["gstr1-period"] || "",
                        onChange: (e) => setActionParams({ ...actionParams, "gstr1-period": e.target.value }),
                        style: {
                          backgroundColor: "#111",
                          border: "1px solid #333",
                          borderRadius: "4px",
                          color: "#fff",
                          padding: "4px 8px",
                          fontSize: "12px",
                          width: "120px"
                        }
                      }),
                      h("input", {
                        type: "text",
                        placeholder: "Seller GSTIN",
                        className: "ares-input",
                        value: actionParams["gstr1-gstin"] || "",
                        onChange: (e) => setActionParams({ ...actionParams, "gstr1-gstin": e.target.value }),
                        style: {
                          backgroundColor: "#111",
                          border: "1px solid #333",
                          borderRadius: "4px",
                          color: "#fff",
                          padding: "4px 8px",
                          fontSize: "12px",
                          width: "140px"
                        }
                      })
                    ]) : null,
                  ]),
                  h("div", { className: "ares-row-actions", key: "actions" }, [
                    h("button", { className: "ares-mini-button", onClick: () => copyCommand(command), key: "copybtn" }, copiedId === command.id ? "Copied" : "Copy"),
                    command.action ? h("button", {
                      className: "ares-mini-button ares-mini-button-run",
                      disabled: busyAction === command.action || commandNeedsData(command) || (command.action === "mobile-reply" && !actionParams["mobile-reply"]) || (command.action === "prepare-gstr1" && (!actionParams["gstr1-period"] || !actionParams["gstr1-gstin"])),
                      onClick: () => {
                        if (commandNeedsData(command)) return;
                        let params = null;
                        if (command.action === "mobile-reply") {
                          params = { reply: actionParams["mobile-reply"] };
                        } else if (command.action === "prepare-gstr1") {
                          params = { period: actionParams["gstr1-period"], seller_gstin: actionParams["gstr1-gstin"] };
                        }
                        runAction(command.action, params);
                      },
                      key: "run",
                    }, commandNeedsData(command) ? "Needs data" : (busyAction === command.action ? "Running" : "Run")) : null,
                  ]),
                ]),
              ),
            ]),
          ),
        ),
      ]),

      h("section", { className: "ares-run-output", key: "output" }, [
        h("div", { className: "ares-panel-head", key: "head" }, [
          h("h2", { key: "h2" }, "Run Output"),
          h("span", { key: "status" }, lastRun ? lastRun.action : "idle"),
        ]),
        lastRun && lastRun.report && lastRun.report.markdown_path ? h("button", {
          className: "ares-mini-button",
          onClick: () => openReport(lastRun.report.markdown_path),
          style: { float: "right", margin: "8px 12px 0 0", padding: "6px 12px", fontSize: "12px", backgroundColor: "#c99a49", color: "#000", fontWeight: "bold" },
          key: "view-report-btn"
        }, "View Saved Report") : null,
        h("pre", { key: "pre", style: { clear: "both" } }, lastRun ? formatRun(lastRun) : "No action run from this dashboard yet."),
      ]),
      renderReportModal()
    ]);

    function renderReportModal() {
      if (!viewingReport) return null;
      return h("div", {
        className: "ares-modal-overlay",
        onClick: () => setViewingReport(null),
        style: {
          position: "fixed",
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: "rgba(0,0,0,0.7)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 9999,
          backdropFilter: "blur(4px)"
        }
      }, [
        h("div", {
          className: "ares-modal-content",
          onClick: (e) => e.stopPropagation(),
          style: {
            backgroundColor: "#1e1e1e",
            border: "1px solid #c99a49",
            borderRadius: "8px",
            padding: "24px",
            width: "90%",
            maxWidth: "700px",
            maxHeight: "80vh",
            overflowY: "auto",
            color: "#e0e0e0",
            boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
            fontFamily: "var(--font-sans, sans-serif)"
          }
        }, [
          h("div", {
            style: {
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: "1px solid #333",
              paddingBottom: "12px",
              marginBottom: "16px"
            }
          }, [
            h("h3", { style: { margin: 0, color: "#c99a49" } }, viewingReport.name),
            h("button", {
              onClick: () => setViewingReport(null),
              style: {
                background: "none",
                border: "none",
                color: "#888",
                cursor: "pointer",
                fontSize: "20px"
              }
            }, "×")
          ]),
          h("div", {
            style: {
              lineHeight: "1.6",
              fontSize: "14px"
            }
          }, parseMarkdown(viewingReport.content))
        ])
      ]);
    }

    function parseMarkdown(text) {
      if (!text) return [];
      const lines = text.split("\n");
      return lines.map((line, idx) => {
        const trimmed = line.trim();
        if (trimmed.startsWith("# ")) {
          return h("h1", { key: idx, style: { color: "#c99a49", marginTop: "16px", marginBottom: "8px", fontSize: "20px", fontWeight: "bold" } }, trimmed.slice(2));
        }
        if (trimmed.startsWith("## ")) {
          return h("h2", { key: idx, style: { color: "#c99a49", marginTop: "14px", marginBottom: "6px", fontSize: "16px", fontWeight: "bold" } }, trimmed.slice(3));
        }
        if (trimmed.startsWith("### ")) {
          return h("h3", { key: idx, style: { color: "#c99a49", marginTop: "12px", marginBottom: "6px", fontSize: "14px", fontWeight: "bold" } }, trimmed.slice(4));
        }
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
          return h("li", { key: idx, style: { marginLeft: "20px", marginBottom: "4px", listStyleType: "disc" } }, trimmed.slice(2));
        }
        if (!trimmed) {
          return h("br", { key: idx });
        }
        return h("p", { key: idx, style: { marginBottom: "8px" } }, trimmed);
      });
    }
  }


  function metric(label, value) {
    return h("div", { className: "ares-metric", key: label }, [
      h("span", { className: "ares-metric-label", key: "label" }, label),
      h("strong", { key: "value" }, value == null ? "0" : String(value)),
    ]);
  }

  function proofMetric(label, value) {
    return h("div", { className: "ares-proof-metric", key: label }, [
      h("span", { key: "label" }, label),
      h("strong", { key: "value" }, value == null ? "0" : String(value)),
    ]);
  }

  function recordsTable(records) {
    const rows = [];
    const invoices = records.invoices || [];
    const stock = records.stock_records || [];
    const orders = records.orders || [];
    const approvals = records.approvals || [];
    const runs = records.workflow_runs || [];
    invoices.slice(0, 3).forEach((item) => rows.push(["Invoice", item.invoice_number, item.customer_id || "-", "INR " + item.amount]));
    stock.slice(0, 3).forEach((item) => rows.push(["Stock", item.name, item.sku_id, item.current_stock + " / reorder " + item.reorder_level]));
    orders.slice(0, 3).forEach((item) => rows.push(["Order", item.customer_id || "unknown", item.status, (item.items || []).length + " item(s)"]));
    approvals.slice(0, 3).forEach((item) => rows.push(["Approval", item.type, item.status, item.proposed_action]));
    runs.slice(0, 3).forEach((item) => rows.push(["Run", item.workflow_name, item.status, item.started_at]));

    if (!rows.length) {
      return h("p", { className: "ares-muted ares-proof-empty", key: "empty" }, "No business records yet. Add exports or inbox files, then run Today Command Center.");
    }

    return h("div", { className: "ares-record-table", key: "records" },
      rows.map((row, index) =>
        h("div", { className: "ares-record-row", key: index },
          row.map((cell, cellIndex) => h(cellIndex === 0 ? "strong" : "span", { key: cellIndex }, String(cell || "-"))),
        ),
      ),
    );
  }

  function pathRow(label, value) {
    return h("div", { className: "ares-path-row", key: label }, [
      h("span", { key: "label" }, label),
      h("code", { key: "value" }, value || "-"),
    ]);
  }

  function formatRun(run) {
    const payload = run && run.payload ? run.payload : {};
    const lines = [run.message || "Ares action complete."];
    if (payload.metrics) lines.push(JSON.stringify(payload.metrics, null, 2));
    else if (payload.prompt) lines.push(payload.prompt);
    else if (payload.top_actions) lines.push(payload.top_actions.join("\n"));
    else if (payload.count != null) lines.push("Pending approvals: " + payload.count);
    if (run.report && run.report.markdown_path) lines.push("Report saved:\n" + run.report.markdown_path);
    return lines.join("\n\n");
  }

  registry.register("ares", AresCommandCenter);
  registry.registerSlot("ares", "header-banner", AresHeaderBanner);
})();
