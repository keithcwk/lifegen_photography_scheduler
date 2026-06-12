# Lessons

## Greedy scheduler has no backtracking — tightening constraints corners it
`scripts/generate_schedule.py` fills events date-by-date, greedily, with no lookahead.
Every time a new hard constraint was added (mandatory red on Worship; trainees directing
services and draining green assists), generation deterministically failed at the LAST tight
date (repeatedly 2026-08-30) even though a feasible full-quarter solution existed.

Rule: when adding a hard role requirement, also ensure a graceful fallback so a single tight
date cannot crash the whole run. We added `relax_monthly_limit` to `photographer_score` +
`choose_required_photographer`: required green/yellow/red fills retry with the monthly cap
relaxed instead of raising. Fairness still applies as a penalty everywhere else; only the
unavoidable slot goes over cap (observed: one member at 5 in a 5-Sunday month).

## Refactor only what the test data exercises
There is no test suite; the only regression gate is diffing `output/schedule.csv` before/after.
The current Q3 dataset has ZERO high-tier events, so all `tier == "high"` branches are
unexercised — refactoring them is unverifiable and must NOT be done blind. Safe refactors are
limited to code paths the dataset actually runs (e.g. `update_stats`, dead code). Deeper
verbosity reduction needs a multi-scenario regression harness first.

## Incremental sheet push needs 2 passes after a layout shape change
`build_incremental_value_updates` diffs the new grid against the current sheet and writes only
changed segments. When the summary layout changed shape (single quarter-block -> wide per-month
blocks), the first push left ~22 stale cells in the new gap columns (old bad-dates data sat where
the new grid is blank). A second identical push converged them. The diff is idempotent, so the
fix is just: after any push that changes the summary/matrix SHAPE, push twice (or read-back and
re-push until changed_cells==0). Steady-state pushes (same shape, only values change) are single-pass.

## Google Sheets values().get trims trailing empty cells per row
Reading a range back returns rows of UNEQUAL length (trailing blanks dropped), so eyeballing
"column N" by splitting a printed row mis-indexes when gap columns are present. Verify a specific
cell with a targeted A1 range (e.g. `Y19`) or pad rows to a fixed width before comparing.

## Verify column alignment before trusting a row read
Early on, rendering the CSV with collapsed whitespace caused off-by-one column reads
(treating `assist` as a photographer), producing false "missing editor / supervised" findings.
Always parse against the canonical header: event,date,unavailable,director,assist,
photographer_1..5,floor_runner,sde_1,sde_2,shadow. Supervised reds appear as `Red + Guide`
in a photographer cell and count as ONE slot whose lineup includes the green guide.
