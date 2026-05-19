# Ares Architecture Notes

## Hermes Extension Map

- Skills: `agent/skill_commands.py` scans flat/external skill directories, while `hermes_cli/plugins.py` lets plugins register namespaced skills with `PluginContext.register_skill`.
- Plugins: `hermes_cli/plugins.py` discovers bundled, user, project, and entry-point plugins. `plugins/ares` uses the general plugin surface instead of changing Hermes core routing.
- CLI commands: `hermes_cli/main.py` wires plugin CLI commands from `PluginContext.register_cli_command`, so `plugins/ares` can expose `hermes ares ...` when enabled.
- Cron: `cron/jobs.py` supports scheduled prompts and `no_agent` scripts with an absolute `workdir`. Ares provides `apps/ares/config/workflow_schedules.yaml` with commands cron can invoke.
- Memory: `agent/memory_manager.py` owns generic Hermes memory providers. Ares keeps business memory policy in `apps/ares/ares/memory` and client-specific files under `~/.ares/clients/<slug>/memory`.
- Gateway: `gateway/` handles platform delivery. Ares stays gateway-light for MVP and formats owner-ready text that can be delivered by existing Telegram/WhatsApp/email paths later.
- Tools and MCP: `tools/registry.py` is the tool registry. Ares does not add core tools yet; Google Sheets/Drive are dependency-injected connectors under `apps/ares/ares/connectors`.
- Config and profiles: `hermes_cli/config.py` and Hermes profiles remain untouched. Ares adds `ClientProfile` under `apps/ares/ares/profiles.py` and isolates pilot state under `~/.ares/clients/<slug>/`.

## Current MVP Integration

Ares is implemented as an app package plus a thin Hermes plugin adapter:

- Product code: `apps/ares/ares/`
- Vertical config: `apps/ares/config/`
- Hermes plugin adapter: `plugins/ares/`
- Tests: `tests/ares/`

This keeps Hermes update-compatible while still giving the agent a runnable vertical layer.

