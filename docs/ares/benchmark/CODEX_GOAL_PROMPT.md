# Codex Goal Prompt — Ares to Source-of-Truth

Paste this into the **Goal** feature in the Codex app.

---

You are working in the Ares repository at:
`/Users/raghav/.ares/ares`

Your mission is to take **Ares** from its current benchmark-improved pilot state to the full **source-of-truth wholesale operating system** defined in the benchmark docs.

## Non-negotiable source documents
Read and follow these first:

1. `docs/ares/benchmark/CODEX_HANDOFF.md`
2. `docs/ares/benchmark/SOURCE_OF_TRUTH.md`
3. `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`
4. `docs/ares/benchmark/FEATURE_MATRIX.md`
5. `docs/ares/benchmark/CURRENT_BUILD_GAP_ANALYSIS.md`

Treat these as the canonical contract for the work.

## Required workflow: use Superpowers
You must use the installed Superpowers workflow in Codex.

Use these Superpowers skills explicitly as your execution method:
- `superpowers:writing-plans`
- `superpowers:subagent-driven-development`
- `superpowers:test-driven-development`
- `superpowers:requesting-code-review`
- `superpowers:finishing-a-development-branch`
- `superpowers:using-git-worktrees`

If a task is large, break it into a written implementation plan first, then execute plan tasks one by one.

## Current status
Already implemented and locally verified:
- A1: Credit limit enforcement
- A2: GST invoice draft generation
- A3: PDC tracker + collections memory
- A4: Batch & expiry inventory

Current test status at handoff time:
- `63 passed` in `tests/ares`

## Immediate next slice
Start with:

# Slice A5 — UPI/payment reconciliation primitives

Minimum expectations:
- structured receipt / settlement ingest surface
- match receipts to open invoices by party + amount
- exact-match happy path first
- ambiguous matches require approval / review
- unreconciled receipts remain visible and auditable
- tests first, then implementation

## Required execution style
- Do not just plan forever.
- Do not give vague summaries.
- Do not stop after one tiny change unless blocked.
- Work slice-by-slice toward the benchmark.
- Use TDD for each slice.
- After each slice:
  1. run targeted tests
  2. run broader `tests/ares`
  3. update `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`
  4. state what is still missing
  5. continue to the next highest-value benchmark slice

## Priority order after A5
After A5, continue through the highest-value missing source-of-truth items in this order unless repo realities force a safer nearby variant:

1. Tally / Busy sync contract
2. GSTR-1 preparation surfaces
3. ITC / 2A / 2B reconciliation contract
4. E-way bill automation contract
5. Supplier payment scheduling
6. Beat route management
7. Principal / brand management
8. Claim & scheme reconciliation
9. Regional language support expansion
10. Principal-wise P&L
11. WhatsApp Business execution layer
12. Hosted product shell / control plane

## Product constraints
Preserve these properties while building:
- approval-first execution
- owner-safe summaries
- deterministic local/client scaffolding
- auditability
- Tally-compatible design
- WhatsApp-first posture
- Hinglish-primary operator orientation

## Truthfulness constraints
- Do not claim the product is fully ship-ready unless the source-of-truth is genuinely covered.
- If an integration is mocked, local-only, or contract-level, label it clearly.
- Do not create fake completeness.

## Repo discipline
- Stay inside the existing architecture and patterns.
- Keep changes scoped to the benchmark goal.
- Do not create parallel apps or duplicate roots.
- Verify before claiming completion.

## Loop until blocked or benchmark-complete
Your default behavior should be:
1. inspect current slice
2. write failing tests
3. implement minimum viable correct behavior
4. verify
5. document
6. move to next slice

Only stop when one of these is true:
- the benchmark source-of-truth is genuinely achieved
- a real external blocker exists
- a decision is required that cannot be safely inferred from the repo/docs

When you report progress, be concise and evidence-based:
- what changed
- where it changed
- what tests passed
- what slice is next

Now begin with A5 immediately.
