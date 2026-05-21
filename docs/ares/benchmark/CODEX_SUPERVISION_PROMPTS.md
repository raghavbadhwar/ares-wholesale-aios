# Codex Supervision Prompts

Use these as repeated follow-up prompts inside Codex while it works.

## Prompt 1 — progress check
Show me the current benchmark slice, the exact files you changed, the tests you ran, and the next concrete step. If you have only planned and not implemented, start implementation now.

## Prompt 2 — no-stall instruction
Do not stop at summaries. Continue building the next benchmark slice with TDD. Run the smallest targeted RED/GREEN cycle first, then the broader `tests/ares` suite if the slice passes.

## Prompt 3 — benchmark guardrail
Compare your current work against `docs/ares/benchmark/SOURCE_OF_TRUTH.md` and `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`. Do not drift into generic cleanup. Only do work that materially advances Ares toward the benchmark.

## Prompt 4 — ship-readiness guardrail
Do not call this ship-ready unless the missing P0/P1 modules are explicitly covered. Tell me which source-of-truth gaps remain after your current slice, then keep implementing the next one.

## Prompt 5 — quality gate
Before moving to the next slice, show:
- targeted test command and result
- broader test command and result
- docs updated
- any mocked or contract-only parts clearly labeled

## Prompt 6 — resume after interruption
Resume from the current repo state and benchmark docs. Re-read `docs/ares/benchmark/CODEX_HANDOFF.md` and continue from the next incomplete slice without repeating already-completed work.
