# Church Photography Scheduling Rulebook

## Team Roles

Each Sunday service requires:

- 1 Director
- 1 SDE Director
- 4 Photographers
- 2 Editors

Directors may also serve as editors.

## SDE Director

The SDE Director oversees the editors. Sunday services and big events use one.

Rules:

- Eligible: any green, or a yellow with `editor_rank` within `limits.max_sde_director_yellow_editor_rank`
  (high tier: `limits.max_high_tier_yellow_editor_rank`). Low tier SDE directors are greens.
- Below high tier the SDE director rotates instead of always going to the top editor
  (editor rank matters less than workload); `weights.green_sde_director` shifts it toward yellows.
- Overseeing editors is light work: below high tier a green may be SDE director past their monthly
  cap, scored only on their SDE director turns (`weights.green_sde_director_turn`) and this month's
  load (`weights.green_sde_director_month`), not their shooting/directing load.
- Under an SDE director, avoid stacking greens or strong editors as SDE 1/2
  (`weights.strong_editor_under_sde_director`); only when nobody else is free.
- The SDE Director is a different person from the director, assist, editors and photographers
  of that event.
- On Sunday services the SDE Director supervises only. On big (high tier) events the SDE
  Director is the third member of the editing team and edits as well.
- Counts as an oversight slot: it appears in the `Direct/Assist` column of the sheet summary.
- Turn it on per event with `sde_director: 1` in `config/event_types.yaml`.

## Assist Director

- A trainee director on a standard or high tier event is paired with a green assist. Trainees
  lead low tier events (e.g. Lifegen Prayer, Creative Team Meet) without an assist.
- A trainee directing without a green assist always has a core green (green with `direct_rank`
  within `limits.core_green_max_direct_rank`) in the photographer lineup.
- A trainee-directed lineup has at most 1 red and no extra idle-red slot.
- Events configured with `assist: 1` always get an assist director: a green, or a
  director-track member when the event director is already green.

## Floor Runner

- Events configured with `floor_runner: 1` get one floor runner.
- Floor running is a development slot: reds are preferred, then yellows, greens last.
- Members who need a guide may only floor-run when a guide is already in the photographer lineup.

## Team Categories

Green: Experienced photographers who can direct, edit, and shoot.
Yellow: Developing photographers who can shoot and are learning editing.
Red: New photographers who cannot direct and normally do not edit unless explicitly marked for Creative Team Meet editor development.
Shadow: Observer only. No active service responsibility.

## Greens

Greens are ranked in `data/team.yaml` with:

- `shoot_rank`
- `direct_rank`
- `editor_rank`

Lower rank numbers mean stronger priority for that role.

## Yellows (Editor Rank)

Yellows are ranked in `data/team.yaml` with:

- `shoot_rank`
- `editor_rank`

Some yellows may also be marked as:

- `director_track: true`
- `guide: true`
- `leader: true`
- `weekday_late: true`

## Director Track

Director-track members are being developed toward directing.

Rules:

- Director-track members may direct at most once per calendar month.
- If a director-track member directs a standard or high tier event, a green assists, or failing that a core green shoots (see Assist Director).
- Director-track members should get low-tier and selected standard-tier leadership opportunities before high-tier events.
- From August onward, director-track members may also direct standard services (e.g. Sunday Service, Worship Encounter), still under green-assist supervision.
- When a director-track member directs, the photographer lineup must keep at least one non-red member (never an all-red lineup).

## Reds

Alvin
Josiah
Isaac
Aslvin
Nick How
Brandel
See Qian
Sheryl
Samantha

## Safety Rule

If Isaac or Aslvin are scheduled, they must be accompanied by:

- any member with `guide: true`

This accompaniment must be visible within the photographer lineup, not only in director or editor slots.

Only Isaac and Aslvin require this guide accompaniment. The other reds (Josiah, Alvin) serve without a guide or assist.

## Team Composition Rules

- High tier events must include at least 2 green photographers
- High tier events should avoid reds if possible
- Standard and high tier events with photographer slots must include at least 1 green photographer
- High tier events should prioritize stronger `shoot_rank` values across the photographer lineup
- High tier events should prioritize stronger editors
- High tier events must not use reds or low-tier yellows in active roster slots
- High tier events should avoid wide `shoot_rank` gaps when a tighter lineup is workable
- High tier events should also rotate opportunities across qualified members where workable
- The same person should not be used too often across high tier assignments
- Adjacent or same-window high tier events should avoid reusing the same people unless that is truly needed for coverage
- When a high tier event is upcoming, the one to two weeks before it should avoid overusing members likely needed for that event
- Lead-up planning should be holistic across those pre-event weeks, so the same person is not repeatedly used right before the high tier event and then used again on the event itself unless needed
- Multi-day high tier events should reserve the strongest practical roster for the final day
- Multi-day high tier events should still rotate qualified people across the run and should not keep using the same person day after day unless needed
- Appearances within one multi-day high tier run are soft-capped by `limits.max_same_high_tier_event_assignments`: going past it is allowed but heavily penalised, since big events often need the same strong people more than once
- Low tier events should prioritize yellow and red photographer opportunities
- Reds should be steered toward low tier event photographer slots (Creative Team Meet, Lifegen Prayer) as their main development opportunities, on top of their required Sunday Service red slot
- Every red should receive at least one photographer slot across the quarter
- Low tier events should generally avoid using greens in photographer slots unless needed to keep the schedule workable
- Sunday Service must include at least 1 green, 1 yellow, and 1 red
- Sunday Service must show 4 photographer slots after any supervision pairings are resolved
- Sunday Service should keep at least 2 stronger photographer assignments when workable
- Sunday Service should avoid lineups made up of too many lower-ranked yellows and reds
- Sunday Service should avoid using more than 2 development-heavy photographer assignments when workable
- Events with 2 editor slots should generally pair 1 stronger editor with 1 lower-tier editor
- Events with 2 editor slots must not schedule 2 lower-tier editors together as the editor pair, unless an SDE director oversees them: then the SDE director is the strong editor and the pair may be two developing editors
- High tier events with 2 editor slots should use stronger editors in both slots
- Events with 2 editor slots should mix up editor combinations across the quarter for the same event type, and should avoid repeating the exact same editor pair unless needed
- Creative Team Meet should use 2 editor slots and 3 photographer slots
- Creative Team Meet editor pairs may use 2 decent yellow editors
- Creative Team Meet editor pairs may also use 1 guide-capable strong editor with 1 yellow editor
- If a red member is explicitly marked as edit-capable, Creative Team Meet may pair that red editor with a guide-capable green editor
- Creative Team Meet editor slots should rotate across the quarter and should not keep relying on the same core yellow editors when other valid pairings are available
- If a strong yellow editor has already covered earlier Creative Team Meet dates, later Creative Team Meet dates should prefer safe rotations that bring in guide-capable greens or lower-tier yellow editors
- Creative Team Meet photographer slots should prioritize yellow and red opportunities and should ideally include a stable yellow anchor
- Creative Team Meet / Advance never has 3 reds: at least 1 yellow photographer, ideally 2 (`target_yellow_photographers: 2`)
- Yellow members who can edit should still receive monthly photographer opportunities where workable, and should not be locked into SDE-only usage
- Green editors may also rotate into SDE slots on standard and low tier events to spread editor load and development
- Sunday Service should ideally avoid having 2 green photographer slots unless needed for stability
- No service may have more than 2 reds
- Below high tier, stronger greens (lower `direct_rank`) direct more often (`weights.green_direct_rank`)
- Directing should be spread across the team so each director directs at most once per calendar month wherever the month's event count allows; idle directors should be used before anyone directs twice
- Leaders Meet should only schedule members marked as leaders in `data/team.yaml`
- Leaders Meet needs at least 1 photographer and 1 editor (the director), all of whom must be leaders
- Worship Encounter is a slightly higher tier service: it follows Sunday Service composition but uses no reds, with 4 photographer slots filled from greens and yellows only (at least 1 green and 1 yellow) and 2 editor slots
- Lifegen Prayer editor may be a yellow or mid-low tier editor and should not default to a top-strength editor
- Lifegen Prayer has a green SDE director over its 1 editor (low tier SDE directors are always green)
- Lifegen Prayer has 2 photographers (at most 1 red), plus a third slot for a red who has not served in `limits.red_idle_days` (`extra_red_photographer: 1`)
- Leaders Meet and Leaders Retreat: the director also edits (`director_edits: true`), so each needs only a director and a photographer
- Baptism and Watchnight Service use no reds and at least 2 green photographers
- Creative Team Meet and Lifegen Prayer should be balanced across the quarter so the same person is not repeated in the same role too often
- Low tier events should also be balanced more holistically, so the same person is not repeatedly used for the same low tier event across the quarter unless needed
- Members marked `weekday_late: true` should be used less on weekday low tier events and can be routed toward occasional Sunday Service opportunities instead
- Each photographer should ideally be able to serve 1 Sunday per month; low tier events are additional opportunities and should not replace a Sunday slot
- If a special event falls on a Sunday, that special event replaces Sunday Service for that date and no separate Sunday Service should be scheduled
- Monthly caps are per tier: `limits.max_green_assignments_per_month` (4), `limits.max_yellow_assignments_per_month` (3) and `limits.max_red_assignments_per_month` (2); a tier without its own cap uses `limits.max_assignments_per_member_per_month`
- The monthly cap is a real ceiling, not a soft target: a member at the limit is not picked again that month
- Photographer slots keep to that ceiling; the cap is only exceeded when no one under it can serve the slot at all
- Director, assist, SDE director and editor slots may exceed the ceiling when manpower is genuinely short, because those roles have a smaller eligible pool
- Avoid serving consecutive event dates if possible; high tier events can be an exception when stronger coverage is needed

## Event Risk Levels

High Risk:

- Mother's Day
- Christmas
- Easter
- Father's Day
- Lifegen Camp
- Good Friday

Standard:

- Sunday Service

Low Risk:

- Leaders Meet
- Creative Team Meet
- Lifegen Prayer

Greens-only events (for example Power Conference JB) set `greens_only: true`, which limits every
slot to green members.

Multi-session events use one line per session in `data/events.md`:
`11 Sep 2026 - Power Conference KL | Night 1`. Each session gets its own roster column and may
carry its own staffing block in `config/event_types.yaml` (key `Power Conference KL | Night 1`),
falling back to the event type's block.

Special Events (frequency-exempt):

- Power Conference KL
- Power Conference JB
- Power Festival

Special events are multi-day or one-off events. Their slots do not count toward
monthly assignment caps, consecutive-date penalties, or role frequency fairness,
so members can serve them without affecting their normal load. Listed in
`config/scheduler_policy.yaml` under `special_rules.frequency_exempt_events`.

## Recurring Planning Rules

- Every Sunday is Sunday Service unless a special event is scheduled on that Sunday; in that case the special event is the only event for that day
- The first Tuesday of every month is Lifegen Prayer
- The first Friday of every month is Leaders Meet
- The last Friday of every month is Creative Team Meet

## Schedule Sheet Rules

- The Google Sheets pivot column uses one consistent color for all row labels
- Row 1 and Row 2 are always bold across the full schedule matrix
- Row 3 is `N/A` and lists members who have bad dates for that event
- Photographer slots in the schedule must be listed in tier order: Green, then Yellow, then Red
- `SDE Director` sits above `SDE 1` and `SDE 2`
- `SDE 1` and `SDE 2` must be listed in editor-rank order, strongest first

## Scheduling Score Model

When selecting among valid candidates, prefer the lowest total score.

Candidate score should be computed from:

- priority rank weight
- role serve count weight
- total serve count weight
- consecutive-date penalty
- optional event-tier penalty for overused high-tier members

Default weights:

- priority rank: x10
- role serve count: x8
- total serve count: x3
- consecutive-date penalty: +30

Interpretation:

- Lower score = picked first
- Blank rank values should be treated as a neutral fallback value
- The scoring model is only used after hard constraints are satisfied

## Growth Goals (2026)

- Train new directors
- Greens should shoot or direct at least once per month
- Low tier events should be used deliberately for growth and leadership development
