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

## Refactor safely with a differential harness, not by reading
Rewriting 3,273 lines of scheduling logic by eye is unverifiable. What worked: snapshot HEAD, run
both versions over the same generated scenarios (current data + hundreds of randomised teams,
events, bad dates and policies + a fake Google Sheets service that records every API call), and
diff the recorded outputs. 1,313 cases, 0 unintended differences. Coverage of the scenarios was
measured (92% of generate_schedule.py) so the untested branches were known and refactored
mechanically rather than creatively.

## A "harmless" string bug can corrupt the source of truth
`replace_section_in_universal_text` re-emitted a closing fence it had already kept, so every single
generate run appended two stray ``` lines to UNIVERSAL_SCHEDULER.md. Parsing tolerated it, so it
went unnoticed while the file users are told to edit slowly rotted. Lesson: assert on the artefact,
not just the exit code — `tests/test_scheduler.py` now fails if a run changes that file at all.

## Comparison operators are policy
`max_assignments_per_member_per_month: 3` was enforced as `count > 3`, i.e. a real ceiling of 4, and
six people sat at 4 in August. The fairness penalty had been hiding it. When a config value names a
limit, the gate must use `>=`, and the graceful-fallback rule still applies: relax the cap as a last
resort instead of failing the run.

## Read the real artefact before modelling it
The Power Conference KL sheet showed the conference is rostered per session (8 sessions over 3 days),
with an assist director every session, a floor runner on night sessions, and an SDE director who
also edits. Two of those fields were about to be deleted as "dead config" because the scheduler never
filled them. Ask for the real example before trusting the code as the spec.

## Read hand-typed sheet cells as displayed text
The Q4 tab's bad dates like `2/10` were auto-converted by the sheet's US locale, so the raw
(UNFORMATTED) value was 10 Feb; `18 Oct` became a correct serial. Raw values cannot tell the two
apart. Read human-typed blocks with `valueRenderOption=FORMATTED_VALUE`; keep raw serials only for
cells the sheet itself formats as dates (the date row). Unparsed formats were silently dropped, so
the generator scheduled people on known bad dates — log or test every format the sheet uses.

## Measure before blaming a gate
Yellow SDE directors outnumbered the sheet's, and the monthly cap looked like the cause. Exempting
greens from the cap changed nothing; logging candidate scores showed the general fairness term
(total serves x3, monthly x6, high-tier reserve penalties) reaching ~900 for busy greens and
swamping editor rank. Log the top-N candidate scores for the slot before changing a rule.
