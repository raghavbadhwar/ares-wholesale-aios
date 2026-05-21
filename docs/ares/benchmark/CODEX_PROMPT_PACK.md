# Codex Prompt Pack

## Prompt 1 — start from current checkpoint
Use the repo docs as source-of-truth and continue from the current verified checkpoint. Do not repeat A1–A6. Start with A7 (GSTR-1 preparation surfaces), use TDD, run targeted tests then `tests/ares`, update `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`, clearly label any local/mock/contract-only behavior, and then continue to the next highest-value benchmark slice.

## Prompt 2 — stop stalling
Do not remain in planning mode. Move from plan to RED/GREEN immediately. Show only files changed, tests run/results, and the next slice or blocker.

## Prompt 3 — benchmark guardrail
Compare your current work against `docs/ares/benchmark/SOURCE_OF_TRUTH.md`, `FEATURE_MATRIX.md`, and `IMPLEMENTATION_PROGRAM.md`. Do not drift into generic cleanup. Only do work that materially advances Ares toward benchmark completion.

## Prompt 4 — quality gate
Before moving to the next slice, show:
- targeted test command + result
- broader `tests/ares` command + result
- benchmark docs updated
- exact limitation of the slice

## Prompt 5 — resume after interruption
Resume from the current repo state. Re-read `CODEX_HANDOFF.md`, `CODEX_ENVIRONMENT.md`, and `IMPLEMENTATION_PROGRAM.md`. Continue from the next incomplete slice and do not repeat completed work.

## Prompt 6 — ship-readiness truthfulness
Do not call Ares ship-ready unless the source-of-truth benchmark is genuinely covered. If an integration is mock/local/contract-level only, say so explicitly.
