# Codex GSTR-1 Prompt

Continue from the current verified checkpoint in `/Users/raghav/.ares/ares`.

Completed already:
- A1 credit enforcement
- A2 GST invoice drafting
- A3 PDC tracker + collections memory
- A4 batch & expiry inventory
- A5 UPI/payment reconciliation
- A6 Tally / Busy sync contract

Known verified suite status:
- `69 passed` in `tests/ares`

Now implement:
# A7 — GSTR-1 preparation surfaces

Requirements:
- tests first
- local/mock/contract-only unless a real GSTN integration already exists
- produce filing-preparation structures for outward supplies
- cover invoice/customer/tax fields required to prepare a draft GSTR-1 surface
- preserve approval-first and audit-safe behavior
- run targeted tests then broader `tests/ares`
- update `docs/ares/benchmark/IMPLEMENTATION_PROGRAM.md`
- report only files changed, tests run/results, and next slice/blocker

After A7, continue to:
1. ITC / 2A / 2B reconciliation contract
2. E-way bill automation contract
3. Supplier payment scheduling
4. Beat route management
