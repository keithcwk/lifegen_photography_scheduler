# TODO

## Round 9 — rules rebalanced against the hand-built "Q4 Schedule" tab

- [x] T1: Importer reads every bad-date format in the tab (`D/M`, `D/M/YYYY`, `D Mon`, ranges) from
      the displayed text, plus the `N/A` row; `--bad-dates-only`. 12 members' Q4 dates imported.
- [x] T2: Per-tier monthly caps: green 4, yellow 3, red 2.
- [x] T3: Lifegen Prayer: green SDE director, 2 photographers + 1 slot for an idle red.
- [x] T4: Leaders Retreat: director also edits. Baptism / Watchnight: no reds, min 2 greens.
- [x] T5: Trainee directs low tier alone; elsewhere green assist, else a core green shoots.
- [x] T6: Two developing editors allowed under an SDE director.
- [x] T7: Load vs sheet (Oct–Dec per-member totals): mean abs diff 1.33 -> 1.08.
- [ ] T8: Charites still over-served vs sheet (10 vs 7); sparing director-track yellows from
      editing was declined for now.
- [ ] T9: CTA 27–28 Nov, Baptism Class, LGY Christmas shapes: sheet incomplete, unchanged.

- [x] T10: Trainee directors: any tier without a green assist gets a core green photographer;
      max 1 red; no idle-red extra slot (fixes Charites + Nick How + Samantha at CTM).
- [x] T11: SDE director below high tier = growth slot (yellows to editor_rank 6, greens fallback);
      greens/strong editors under it penalised (non-high stacked pairs 5 -> 2, both late Aug).
- [x] T12: Leaders Meet: director edits.
- [x] T13: Weights tuned against the sheet (Oct–Dec, per member per role): `green_direct_rank: 8`,
      SDE director rank x5, `green_sde_director: 0`. Totals MAE 0.92 -> 0.83, roles 2.92 -> 2.58.
- [x] T14: Green SDE directors below high tier skip the monthly cap and are scored on SDE turns +
      monthly load only. The cap alone changed nothing: greens' total-load fairness term (~900 by
      Dec) was what pushed the slot to yellows. Totals MAE 0.83 -> 0.79, roles 2.58 -> 2.46;
      yellow SDE share 11/18 -> 3/18 (sheet 6/17; raise green_sde_director_turn to ~80 for ~6/18 yellows, at a small MAE cost).

Commits: user handles (do NOT commit).

## Round 8 — Q4 2026 drafted from the existing sheet

- [x] T1: `scripts/import_sheet_quarter.py` + `config/sheet_import.yaml` read a quarter tab:
      special events from row 2/3 and the bad-dates block, mapped through alias tables.
      Imported See Qian, Dan C and Janelle's Q4 dates.
- [x] T2: New event types: Leaders Retreat (Leaders Meet rules), Baptism, Baptism Class,
      Creative Team Advance, LGY Christmas, Watchnight Service, Christmas (highest tier).
      Prayer dates are explicit (13 Oct, 10 Nov, 8 Dec); recurring Prayer/LM/CTM excluded for Q4.
- [x] T3: An explicitly listed Sunday Service is no longer dropped when a special event falls on
      that Sunday, so 25 Oct carries both the Leaders Retreat and the service.
- [x] T4: `Nic` renamed `Nic Wong` to match the sheet's summary formulas.
- [x] T5: Matrix-only push mode (`mode: matrix_only`, `layout_profile: quarter_tab`) writes rows
      1-15 of a hand-built tab only, keeps hand-typed labels, dates, N/A notes and rosters, and
      supports `--dry-run`, `--restructure` and `--target`.
- [x] T6: Pushed Q4 (months re-spanned B:J / K:S / T:AA, summary blocks rebuilt, Nov `Has Slot`
      formula fixed) and PCJB (Bump In + Session 1-3, greens only). Both converge on a second pass.
- [ ] T7: Decide whether to widen SDE director eligibility (editor_rank <= 6) — 21 member-months
      sit at 4 assignments against a cap of 3.
- [ ] T8: December events beyond the agreed list (any LGY/CG extras) if the plan changes.

Commits: user handles (do NOT commit).

## Round 7 — audit, minimal refactor, new roles

- [x] T1: Behaviour-preserving refactor of all five scripts (5,989 -> ~4,100 lines). Verified with a
      throwaway differential harness: 1,313 cases (current data, 900 randomised teams/events/policies,
      Google push against a fake Sheets API, universal validate/compile/sync, CLI) byte-identical
      except one deliberately unified error message.
- [x] T2: Fixed `replace_section_in_universal_text` emitting a duplicate closing fence — every
      generate run was adding two stray ``` lines to UNIVERSAL_SCHEDULER.md (13 -> 19 after 3 runs).
      Existing strays cleaned by re-exporting the file.
- [x] T3: Fixed silent data loss in `sync_sections_if_needed`: the universal file's mtime was re-read
      inside the loop, so the second hand-edited generated file was overwritten from the universal copy.
- [x] T4: Monthly cap now means what it says (`>=`, not `>`). Photographers keep to it; director,
      assist, SDE director and editor slots may exceed it only when nobody under the cap can serve.
      Photographer fills relax as a last resort instead of failing the whole run.
- [x] T5: Config made authoritative: `min_green_photographers` is a floor not an override,
      `max_red_photographers` takes the stricter of config and the service rule, `leaders_only`
      drives picking (was hardcoded to the name "Leaders Meet").
- [x] T6: `max_same_high_tier_event_assignments` enforced as a soft cap (penalty past the limit),
      matching how PCKL really staffed 8 sessions.
- [x] T7: Trainee service-directing gate moved from a hardcoded `month >= 8` to
      `special_rules.trainee_service_directing_from`.
- [x] T8: Event names behind behaviours moved into `event_roles` in the policy file.
- [x] T9: New roles filled by the scheduler: SDE director (`sde_director: 1`), assist director
      (`assist: 1`), floor runner (`floor_runner: 1`, reds first), plus `greens_only` events.
      SDE Director row added to the sheet layout and the CSV; counts in the summary's Direct/Assist.
- [x] T10: Multi-session events: `11 Sep 2026 - Power Conference KL | Night 1`, with optional
      per-session staffing blocks in `config/event_types.yaml`.
- [x] T11: PCJB configured greens-only and small: director + SDE director + 1 editor + 3 photographers.
- [x] T12: Starter template fixed (it could not generate at all: wrong styles/layout schema, team too
      small) and covered by a smoke check.
- [x] T13: `tests/test_scheduler.py` added — golden CSV, per-event invariants, template smoke,
      universal-file stability, hand-edit precedence. Runs in under a second.
- [ ] T14: Decide whether to widen SDE director eligibility (17 new slots land on the same 10 people;
      11 member-months now sit at 4 assignments in a 3-cap month).
- [ ] T15: Push to Google Sheets (needs two passes because the SDE Director row changes the shape).

Commits: user handles (do NOT commit).

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
