# Codex Operator Quickstart

## Best environment
Open Terminal in:
`/Users/raghav/.ares/ares`

Then run:
```bash
./scripts/start_codex_ares.sh
```

That launches Codex with:
- the right repo root
- the right UV cache path
- the latest master prompt
- workspace-write sandbox

## If you want a specific slice prompt
```bash
./scripts/start_codex_ares.sh docs/ares/benchmark/CODEX_GSTR1_PROMPT.md
```

## If Codex stops or the session closes
```bash
./scripts/resume_codex_ares.sh
```

## Best prompts to paste
- main long-run prompt:
  - `docs/ares/benchmark/CODEX_MASTER_PROMPT.md`
- next-slice prompt:
  - `docs/ares/benchmark/CODEX_GSTR1_PROMPT.md`
- supervision nudges:
  - `docs/ares/benchmark/CODEX_PROMPT_PACK.md`

## Ground truth docs
Always keep Codex tied to:
- `CODEX_HANDOFF.md`
- `SOURCE_OF_TRUTH.md`
- `IMPLEMENTATION_PROGRAM.md`
- `FEATURE_MATRIX.md`
- `CURRENT_BUILD_GAP_ANALYSIS.md`

## Current verified checkpoint
- A1–A6 implemented
- `69 passed` in `tests/ares`
