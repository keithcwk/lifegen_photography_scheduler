# TODO

## Round 6 — director spread + per-month summary section

- [x] T1: Director spread — penalize directing >1x/calendar-month in `director_score` so idle
      directors (e.g. Nic) get used before anyone doubles. NOTE: 9 Aug events vs 8 eligible
      directors (6 green + 2 trainee@1/mo) => exactly ONE double is unavoidable (pigeonhole);
      goal is to reduce current TWO doubles (Huey Chyi, Joseph) to one and fill Nic's idle slot.
- [x] T2: Sheet summary section — rewrote build_summary_values to tile per-MONTH 7-col blocks
      [#, Name, Shoot, SDE, Direct/Assist, Has Slot, Total] aligned under each month's columns,
      counting that month's rows only. Added count_member_role_frequency helper.
- [x] Regenerate + verify director spread (Aug: one unavoidable double only); re-push;
      re-read sheet: all 775 summary cells match computed per-month grid (0 mismatches).
      NOTE: big layout change needed TWO incremental pushes to fully converge (22 stale gap cells
      cleared on 2nd pass). Steady-state pushes (same layout) are single-pass.

Commits: user handles (do NOT commit).

## Round 5 — special events as high-tier + rotation, push, refactor (DONE)
- Power Conf KL/JB -> high tier + freq-exempt + within-run rotation; pushed; high_tier_role_penalties refactor.
