# Church Photography Scheduling Rulebook

## Team Roles

Each Sunday service requires:

- 1 Director
- 4 Photographers
- 2 Editors

Directors may also serve as editors.

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
- If a director-track member is assigned as Director, the Assist slot must be filled by a green and they must never direct alone.
- Director-track members should get low-tier and selected standard-tier leadership opportunities before high-tier events.

## Reds

Alvin
Josiah
Isaac
Aslvin

## Safety Rule

If Isaac or Aslvin are scheduled, they must be accompanied by:

- any member with `guide: true`

This accompaniment must be visible within the photographer lineup, not only in director or editor slots.

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
- A member should generally not appear more than twice across the same multi-day high tier event run
- Low tier events should prioritize yellow and red photographer opportunities
- Low tier events should generally avoid using greens in photographer slots unless needed to keep the schedule workable
- Sunday Service must include at least 1 green, 1 yellow, and 1 red
- Sunday Service must show 4 photographer slots after any supervision pairings are resolved
- Sunday Service should keep at least 2 stronger photographer assignments when workable
- Sunday Service should avoid lineups made up of too many lower-ranked yellows and reds
- Sunday Service should avoid using more than 2 development-heavy photographer assignments when workable
- Events with 2 editor slots should generally pair 1 stronger editor with 1 lower-tier editor
- Events with 2 editor slots must not schedule 2 lower-tier editors together as the editor pair
- High tier events with 2 editor slots should use stronger editors in both slots
- Events with 2 editor slots should mix up editor combinations across the quarter for the same event type, and should avoid repeating the exact same editor pair unless needed
- Creative Team Meet should use 2 editor slots and 3 photographer slots
- Creative Team Meet editor pairs may use 2 decent yellow editors
- Creative Team Meet editor pairs may also use 1 guide-capable strong editor with 1 yellow editor
- If a red member is explicitly marked as edit-capable, Creative Team Meet may pair that red editor with a guide-capable green editor
- Creative Team Meet editor slots should rotate across the quarter and should not keep relying on the same core yellow editors when other valid pairings are available
- If a strong yellow editor has already covered earlier Creative Team Meet dates, later Creative Team Meet dates should prefer safe rotations that bring in guide-capable greens or lower-tier yellow editors
- Creative Team Meet photographer slots should prioritize yellow and red opportunities and should ideally include a stable yellow anchor
- Yellow members who can edit should still receive monthly photographer opportunities where workable, and should not be locked into SDE-only usage
- Green editors may also rotate into SDE slots on standard and low tier events to spread editor load and development
- Sunday Service should ideally avoid having 2 green photographer slots unless needed for stability
- No service may have more than 2 reds
- Leaders Meet should only schedule members marked as leaders in `data/team.yaml`
- Leaders Meet only needs 1 photographer
- Creative Team Meet and Lifegen Prayer should be balanced across the quarter so the same person is not repeated in the same role too often
- Low tier events should also be balanced more holistically, so the same person is not repeatedly used for the same low tier event across the quarter unless needed
- Members marked `weekday_late: true` should be used less on weekday low tier events and can be routed toward occasional Sunday Service opportunities instead
- Each photographer should ideally be able to serve 1 Sunday per month; low tier events are additional opportunities and should not replace a Sunday slot
- If a special event falls on a Sunday, that special event replaces Sunday Service for that date and no separate Sunday Service should be scheduled
- Non-red members should generally not be scheduled more than 3 times in the same calendar month, and low tier or standard events should stop using them once they are already heavily loaded unless a high tier fallback is required
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
