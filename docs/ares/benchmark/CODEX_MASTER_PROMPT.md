# Codex Master Prompt — Ares from Current Checkpoint to Source-of-Truth

You are working in the Ares repository at:
`/Users/raghav/.ares/ares`

Your mission is to take **Ares** from the current verified benchmark checkpoint to the full **source-of-truth wholesale operating system** described in the benchmark docs.

## Read these first
1. `docs/ares/benchmark/CODEX_HANDOFF.md`
2. `docs/ares/benchmark/SOURCE_OF_TRUTH.md`
3. `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`
4. `docs/ares/benchmark/FEATURE_MATRIX.md`
5. `docs/ares/benchmark/CURRENT_BUILD_GAP_ANALYSIS.md`
6. `docs/ares/benchmark/CODEX_ENVIRONMENT.md`

Treat these as the canonical contract.

## Use Superpowers workflow
Use these skills/workflows explicitly when available:
- `superpowers:writing-plans`
- `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:requesting-code-review`
- `superpowers:finishing-a-development-branch`
- `superpowers:using-git-worktrees`

If a slice is large, write a short plan and then execute immediately. Do not remain in planning mode.

## Current verified checkpoint
Already implemented and independently verified:
- A1: Credit limit enforcement
- A2: GST invoice draft generation
- A3: PDC tracker + collections memory
- A4: Batch & expiry inventory
- A5: UPI/payment reconciliation primitives
- A6: Tally / Busy sync contract

Current known suite status:
- `69 passed` in `tests/ares`

## Immediate next slice
Start with:
# Slice A7 — GSTR-1 preparation surfaces

Minimum expectations:
- local contract-level GSTR-1 preparation workflow
- draft summary structure for outward supplies
- include invoice/customer/tax metadata needed for filing preparation
- keep it clearly labeled local/mock/contract if no live GSTN integration exists
- preserve approval-first and audit-safe behavior
- tests first, then minimal implementation

## Priority order after A7
After A7, continue through the highest-value missing source-of-truth items in this order unless repo reality forces a safer adjacent move:
1. ITC / 2A / 2B reconciliation contract
2. E-way bill automation contract
3. Supplier payment scheduling
4. Beat route management
5. Principal / brand management
6. Claim & scheme reconciliation
7. Regional language support expansion
8. Principal-wise P&L
9. WhatsApp Business execution layer
10. Hosted product shell / control plane

## Non-negotiable execution rules
- Do not stop at summaries.
- Do not claim ship-ready early.
- Work slice-by-slice toward benchmark completion.
- Use TDD for each slice.
- Keep changes inside the existing architecture.
- Label mocked/local-only/contract-only integrations clearly.

## Required loop after every slice
1. run targeted tests
2. run broader `tests/ares`
3. update `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`
4. state the exact limitation of the slice
5. move to the next highest-value benchmark slice

## Only stop when
- the benchmark source-of-truth is genuinely achieved, or
- a real external blocker exists, or
- a decision is required that cannot be safely inferred from repo/docs

## When reporting progress
Report only:
- files changed
- tests run and results
- exact next slice or blocker

Begin with A7 immediately.
