# Codex Paste-First Prompt

Work in `/Users/raghav/.ares/ares`.

Before doing anything, read:
- `docs/ares/benchmark/CODEX_HANDOFF.md`
- `docs/ares/benchmark/CODEX_ENVIRONMENT.md`
- `docs/ares/benchmark/SOURCE_OF_TRUTH.md`
- `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`
- `docs/ares/benchmark/FEATURE_MATRIX.md`
- `docs/ares/benchmark/CURRENT_BUILD_GAP_ANALYSIS.md`

Use the Superpowers workflow if available:
- `superpowers:writing-plans`
- `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:requesting-code-review`

Current verified checkpoint:
- A1 credit enforcement complete
- A2 GST invoice drafting complete
- A3 PDC tracker + collections memory complete
- A4 batch & expiry inventory complete
- A5 UPI/payment reconciliation complete
- A6 Tally / Busy sync contract complete
- latest verified suite: `69 passed` in `tests/ares`

Do not repeat completed slices.

Start with the next incomplete benchmark slice:
# A7 — GSTR-1 preparation surfaces

Rules:
- TDD first
- do not stay in planning mode
- keep mocked/local/contract-only integrations labeled clearly
- after each slice run targeted tests and then `tests/ares`
- update `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`
- report only: files changed, tests run/results, next slice or blocker
- do not claim ship-ready until the source-of-truth benchmark is genuinely covered

After A7, continue through the next highest-value benchmark gaps slice-by-slice until blocked.