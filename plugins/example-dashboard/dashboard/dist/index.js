(function () {
  "use strict";

  const SDK = window.__ARES_PLUGIN_SDK__ || window.__HERMES_PLUGIN_SDK__;
  const registry = window.__ARES_PLUGINS__ || window.__HERMES_PLUGINS__;
  if (!SDK || !registry) return;

  const React = SDK.React;
  const h = React.createElement;
  const useEffect = SDK.hooks.useEffect;
  const useState = SDK.hooks.useState;
  const Button = SDK.components.Button;

  function ExampleDashboardPlugin() {
    const [state, setState] = useState({ loading: true, error: "", data: null });

    useEffect(function () {
      let cancelled = false;
      SDK.fetchJSON("/api/plugins/example/hello")
        .then(function (data) {
          if (!cancelled) setState({ loading: false, error: "", data: data });
        })
        .catch(function (err) {
          if (!cancelled) setState({ loading: false, error: err && err.message ? err.message : String(err), data: null });
        });
      return function () { cancelled = true; };
    }, []);

    return h("div", { className: "flex min-h-[24rem] flex-col gap-4 rounded border border-current/20 bg-background-base/40 p-5" }, [
      h("div", { key: "head", className: "flex items-center justify-between gap-3" }, [
        h("div", { key: "copy" }, [
          h("h1", { key: "title", className: "text-sm font-bold uppercase tracking-wide text-midground" }, "Example Plugin"),
          h("p", { key: "desc", className: "mt-1 max-w-xl text-xs normal-case tracking-normal text-midground/60" }, "A small bundled plugin used to verify dashboard plugin loading, API calls, and session-token auth.")
        ]),
        h(Button, { key: "reload", onClick: function () { window.location.reload(); } }, "Reload")
      ]),
      state.loading
        ? h("p", { key: "loading", className: "text-xs text-midground/60" }, "Loading example API...")
        : state.error
          ? h("pre", { key: "error", className: "whitespace-pre-wrap rounded border border-red-500/30 bg-red-950/20 p-3 text-xs text-red-300" }, state.error)
          : h("pre", { key: "data", className: "whitespace-pre-wrap rounded border border-emerald-500/20 bg-emerald-950/10 p-3 text-xs text-emerald-200" }, JSON.stringify(state.data, null, 2))
    ]);
  }

  registry.register("example", ExampleDashboardPlugin);
})();
