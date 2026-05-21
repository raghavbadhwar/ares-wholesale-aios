# Codex Environment for Ares

## Purpose
This is the **preferred local environment** for Codex to work on Ares from the current benchmark checkpoint.

## Repo
- Path: `/Users/raghav/.ares/ares`
- Branch: `feat/pilot-readiness`

## Verified checkpoint before this prompt pack
Implemented and independently verified:
- A1: credit enforcement
- A2: GST invoice drafting
- A3: PDC tracker + collections memory
- A4: batch & expiry inventory
- A5: UPI/payment reconciliation
- A6: Tally / Busy sync contract

Latest independently verified suite status:
- `69 passed` in `tests/ares`

## Best way to launch Codex
### Fresh run with the latest master prompt
```bash
cd /Users/raghav/.ares/ares
./scripts/start_codex_ares.sh
```

### Fresh run with a specific prompt file
```bash
cd /Users/raghav/.ares/ares
./scripts/start_codex_ares.sh docs/ares/benchmark/CODEX_GSTR1_PROMPT.md
```

### Resume the last Codex session
```bash
cd /Users/raghav/.ares/ares
./scripts/resume_codex_ares.sh
```

## Environment defaults
The launcher sets:
- `UV_CACHE_DIR=/private/tmp/ares-uv-cache`
- Codex sandbox: `workspace-write`
- repo root: `/Users/raghav/.ares/ares`

## What Codex should read first
1. `docs/ares/benchmark/CODEX_HANDOFF.md`
2. `docs/ares/benchmark/SOURCE_OF_TRUTH.md`
3. `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`
4. `docs/ares/benchmark/FEATURE_MATRIX.md`
5. `docs/ares/benchmark/CURRENT_BUILD_GAP_ANALYSIS.md`

## Operating rule
Codex should work slice-by-slice with TDD and should not claim ship-ready until the source-of-truth benchmark is genuinely covered.
