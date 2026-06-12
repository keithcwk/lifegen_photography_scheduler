# UNIVERSAL_SCHEDULER.md

This file is the single human-edited source of truth for the scheduler.
Only edit inside the fenced code blocks.
Do not rename the `## file/path` headings.
After editing, run the validator or the generate script.
If this file is newer than the generated repo files, schedule generation auto-syncs from it.

Safe workflow for non-dev users:

1. Edit the content inside the code block for the section you want to change.
2. Run `executables/Validate Universal Scheduler.command` or `python scripts/compile_universal_scheduler.py --check`.
3. Run `executables/Generate Schedule.command` or `python scripts/generate_schedule.py`.
4. If needed, run `executables/Push Schedule To Google Sheets.command`.

## rules/rulebook.md

```md
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
- A member should generally not appear more than twice across the same multi-day high tier event run
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
- Directing should be spread across the team so each director directs at most once per calendar month wherever the month's event count allows; idle directors should be used before anyone directs twice
- Leaders Meet should only schedule members marked as leaders in `data/team.yaml`
- Leaders Meet needs at least 1 photographer and 1 editor, both of whom must be leaders
- Worship Encounter is a slightly higher tier service: it follows Sunday Service composition but uses no reds, with 4 photographer slots filled from greens and yellows only (at least 1 green and 1 yellow) and 2 editor slots
- Lifegen Prayer editor may be a yellow or mid-low tier editor and should not default to a top-strength editor
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
```

## data/team.yaml

```yaml
greens:
  - name: Nic
    shoot_rank: 1
    direct_rank: 1
    editor_rank: 2
    guide: true
    leader: true

  - name: Keith
    shoot_rank: 2
    direct_rank: 2
    editor_rank: 1
    guide: true
    leader: true

  - name: Dennis
    shoot_rank: 3
    direct_rank: 3
    editor_rank: 3
    guide: true
    leader: true

  - name: Gavin
    shoot_rank: 4
    direct_rank: 4
    editor_rank: 4
    guide: true
    leader: true

  - name: Huey Chyi
    shoot_rank: 5
    direct_rank: 5
    editor_rank: 5
    guide: true
    leader: true

  - name: Joseph
    shoot_rank: 8
    direct_rank: 6
    editor_rank: 6
    guide: true
    leader: true

yellows:
  - name: Charites
    shoot_rank: 6
    editor_rank: 1
    director_track: true
    guide: false
    leader: false

  - name: Dan C
    shoot_rank: 7
    editor_rank: 2
    director_track: true
    guide: true
    leader: false

  - name: Jia En
    shoot_rank: 8
    editor_rank: 3
    director_track: false
    guide: false
    leader: false

  - name: Cindy
    shoot_rank: 9
    editor_rank: 4
    director_track: false
    guide: false
    leader: false

  - name: Wing Yan
    shoot_rank: 10
    editor_rank: 6
    director_track: false
    guide: false
    leader: false

  - name: Patrick
    shoot_rank: 11
    editor_rank: 5
    director_track: false
    guide: false
    leader: false

  - name: Janelle
    shoot_rank: 12
    editor_rank: 7
    director_track: false
    guide: false
    leader: false

  - name: Felise
    shoot_rank: 13
    editor_rank: 8
    director_track: false
    guide: false
    leader: false

  - name: Ashley
    shoot_rank: 14
    editor_rank: 9
    director_track: false
    guide: false
    leader: false

reds:
  - name: Alvin
    shoot_rank: 15

  - name: Josiah
    shoot_rank: 16
    weekday_late: true

  - name: Isaac
    shoot_rank: 17

  - name: Aslvin
    shoot_rank: 18

  - name: Nick How
    shoot_rank: 19

  - name: Brandel
    shoot_rank: 20

  - name: See Qian
    shoot_rank: 21

  - name: Sheryl
    shoot_rank: 22

  - name: Samantha
    shoot_rank: 23

shadows: []
```

## data/events.md

```md
# Events

Add one event per line using `DD Mon YYYY - Event Name`.
Uncomment or replace the example block below when you want to use it.

<!--
Example
06 Apr 2026 - Sunday Service
13 Apr 2026 - Sunday Service
20 Apr 2026 - Sunday Service
27 Apr 2026 - Sunday Service

03 May 2026 - Leaders Meet
05 May 2026 - Lifegen Prayer
10 May 2026 - Mother's Day
29 May 2026 - Lifegen Camp
30 May 2026 - Lifegen Camp
31 May 2026 - Lifegen Camp
01 Jun 2026 - Lifegen Camp
-->

05 Jul 2026 - Worship Encounter
07 Jul 2026 - Lifegen Prayer
10 Jul 2026 - Leaders Meet
12 Jul 2026 - Sunday Service
19 Jul 2026 - Sunday Service
24 Jul 2026 - Creative Team Meet
26 Jul 2026 - Sunday Service
02 Aug 2026 - Sunday Service
09 Aug 2026 - Sunday Service
11 Aug 2026 - Lifegen Prayer
14 Aug 2026 - Leaders Meet
16 Aug 2026 - Sunday Service
18 Aug 2026 - Power Night
23 Aug 2026 - Sunday Service
28 Aug 2026 - Creative Team Meet
30 Aug 2026 - Sunday Service
01 Sep 2026 - Lifegen Prayer
06 Sep 2026 - Sunday Service
11 Sep 2026 - Power Conference KL
12 Sep 2026 - Power Conference KL
13 Sep 2026 - Power Conference KL
18 Sep 2026 - Creative Team Meet
20 Sep 2026 - Sunday Service
27 Sep 2026 - Sunday Service
02 Oct 2026 - Power Conference JB
03 Oct 2026 - Power Conference JB
04 Oct 2026 - Power Conference JB

## Exclusions

03 Jul 2026 - Leaders Meet
31 Jul 2026 - Creative Team Meet
04 Aug 2026 - Lifegen Prayer
07 Aug 2026 - Leaders Meet
04 Sep 2026 - Leaders Meet
25 Sep 2026 - Creative Team Meet
02 Oct 2026 - Leaders Meet
06 Oct 2026 - Lifegen Prayer
11 Oct 2026 - Sunday Service
18 Oct 2026 - Sunday Service
25 Oct 2026 - Sunday Service
30 Oct 2026 - Creative Team Meet
```

## data/bad_dates.md

```md
# Bad Dates

Use quarter headings, then list each member's unavailable dates for that quarter.
Uncomment or replace the example block below when you want to use it.

<!--
Example
## 2026 Q2

### Keith
- 06 Apr 2026
- 03 May 2026

### Cindy
- 13 Apr 2026

### Alvin
- 24 May 2026
-->

## 2026 Q3

### Charites

- 23 Aug 2026
- 30 Aug 2026
- 06 Sep 2026

### Cindy

- 26 Jul 2026

### Joseph

- 12 Jul 2026
- 19 Jul 2026
- 26 Jul 2026

### Nic

- 05 Jul 2026

### Wing Yan

- 11 Jul 2026
- 12 Jul 2026
- 22 Aug 2026
- 23 Aug 2026

### Josiah

- 07 Jul 2026
- 11 Aug 2026
- 01 Sep 2026

### Gavin

- 02 Aug 2026

### Alvin

- 30 Aug 2026

### Sheryl

- 13 Aug 2026
- 14 Aug 2026
- 15 Aug 2026
- 16 Aug 2026
- 17 Aug 2026
- 18 Aug 2026
- 19 Aug 2026
- 20 Aug 2026
```

```

```

````

## config/event_types.yaml

```yaml
events:
  Sunday Service:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: standard
    min_green_photographers: 1
    min_yellow_photographers: 1
    min_red_photographers: 1
    max_red_photographers: 2

  Mother's Day:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: high
    min_green_photographers: 2
    max_red_photographers: 0

  Father's Day:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: high
    min_green_photographers: 2
    max_red_photographers: 0

  Easter:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: high
    min_green_photographers: 2
    max_red_photographers: 0

  Good Friday:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: high
    min_green_photographers: 2
    max_red_photographers: 0

  Lifegen Camp:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: high
    min_green_photographers: 2
    max_red_photographers: 0

  Worship Encounter:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: standard
    min_green_photographers: 1
    min_yellow_photographers: 1
    max_red_photographers: 0

  Power Night:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: standard
    min_green_photographers: 1
    max_red_photographers: 2

  Power Conference KL:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: high
    min_green_photographers: 2
    max_red_photographers: 0

  Power Conference JB:
    photographers: 4
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: high
    min_green_photographers: 2
    max_red_photographers: 0

  Leaders Meet:
    photographers: 1
    director: 1
    assist: 0
    editors: 1
    floor_runner: 0
    shadow: 0
    tier: low
    leaders_only: true

  Creative Team Meet:
    photographers: 3
    director: 1
    assist: 0
    editors: 2
    floor_runner: 0
    shadow: 0
    tier: low
    min_yellow_photographers: 1
    max_red_photographers: 2

  Lifegen Prayer:
    photographers: 2
    director: 1
    assist: 0
    editors: 1
    floor_runner: 0
    shadow: 0
    tier: low
````

## config/recurring_events.yaml

```yaml
generation_window:
  months_after_last_explicit_event: 0

recurring_events:
  - event: Sunday Service
    frequency: weekly
    weekday: sunday

  - event: Lifegen Prayer
    frequency: monthly
    weekday: tuesday
    occurrence: first

  - event: Leaders Meet
    frequency: monthly
    weekday: friday
    occurrence: first

  - event: Creative Team Meet
    frequency: monthly
    weekday: friday
    occurrence: last
```

## config/google_sheets_styles.yaml

```yaml
sheet:
  freeze_header_row: true
  header_row_height: 32
  font_family: Montserrat
  horizontal_alignment: CENTER
  vertical_alignment: MIDDLE

pivot_column:
  font_weight: bold
  background_color: "#D9EAF4"
  text_color: "#1F1F1F"

event_name:
  font_weight: bold
  background_color: "#F4F7FB"
  text_color: "#1F1F1F"
  wrap_strategy: WRAP

date_column:
  font_weight: bold
  background_color: "#FAFAFA"
  text_color: "#333333"

availability_row:
  font_weight: normal
  background_color: "#FFF8E1"
  text_color: "#6B5600"

month_palette:
  colors:
    - "#F4CCCC"
    - "#FCE5CD"
    - "#FFF2CC"
    - "#D9EAD3"
    - "#D0E0E3"
    - "#CFE2F3"
    - "#D9D2E9"
    - "#EAD1DC"

month_group_border:
  enabled: true
  color: "#6B7280"
  style: SOLID_MEDIUM

column_separator:
  enabled: true
  color: "#9AA0A6"
  style: SOLID

header_divider:
  enabled: true
  color: "#000000"
  style: SOLID

alternating_rows:
  enabled: true
  odd_row_background: "#FFFFFF"
  even_row_background: "#F8FAFC"

borders:
  enabled: true
  color: "#D0D7DE"
```

## config/google_sheets_layout.yaml

```yaml
sheet_layout:
  orientation: column_based_event_matrix
  description: >
    Each event occupies one column. Rows represent event metadata first, then
    assignment roles. A separate summary section tracks workload, and a bad
    dates section records availability constraints.

  blank_event_titles:
    - Sunday Service

  event_column:
    metadata_rows:
      - row: 1
        key: event_name
        label: Event Name
      - row: 2
        key: event_date
        label: Event Date
      - row: 3
        key: unavailable
        label: N/A

    role_rows:
      - row: 4
        key: director
        label: Director
        required: true
      - row: 5
        key: assist
        label: Assist
        required: false
      - row: 6
        key: photographer_1
        label: Photographer 1
        required: true
      - row: 7
        key: photographer_2
        label: Photographer 2
        required: true
      - row: 8
        key: photographer_3
        label: Photographer 3
        required: true
      - row: 9
        key: photographer_4
        label: Photographer 4
        required: true
      - row: 10
        key: photographer_5
        label: Photographer 5
        required: false
      - row: 11
        key: floor_runner
        label: Floor runner
        required: false
      - row: 12
        key: sde_1
        label: SDE 1
        required: true
      - row: 13
        key: sde_2
        label: SDE 2
        required: true
      - row: 14
        key: shadow
        label: Shadow
        required: false

  default_event_profiles:
    sunday_service:
      uses_roles:
        - director
        - photographer_1
        - photographer_2
        - photographer_3
        - photographer_4
        - sde_1
        - sde_2
      optional_roles:
        - assist
        - photographer_5
        - floor_runner
        - shadow

  summary_section:
    orientation: row_based_members
    columns:
      - Name
      - Shoot
      - SDE
      - Direct/Assist
      - Has Slot

  bad_dates_section:
    columns:
      - Member Name
      - Bad Dates

  canonical_scheduler_format:
    description: >
      The scheduler may keep an internal flat format for logic and CSV export,
      then map it into the Google Sheets event-matrix layout during sheet
      rendering.
    columns:
      - event
      - date
      - unavailable
      - director
      - assist
      - photographer_1
      - photographer_2
      - photographer_3
      - photographer_4
      - photographer_5
      - floor_runner
      - sde_1
      - sde_2
      - shadow
```

## config/google_sheets_sync.yaml

```yaml
google_sheets:
  spreadsheet_id: "1vEDY8SNbTKOyvSPSxq8xqzSrNZvld3nBD8SvQu3x2Gw"
  worksheet_title: "GPT Schedule Q3 Test"
  service_account_json: "/Users/keithchan/Codes/lifegen_photography_scheduler/google_credentials.json"
  clear_before_write: false
  create_worksheet_if_missing: true
```

## config/scheduler_policy.yaml

```yaml
limits:
  max_assignments_per_member_per_month: 3
  max_director_track_directs_per_month: 1
  max_red_assignments_per_month: 2
  max_high_tier_yellow_shoot_rank: 8
  max_high_tier_yellow_editor_rank: 4
  high_tier_reserve_window_days: 14
  high_tier_recent_window_days: 10
  max_same_high_tier_event_assignments: 3
  creative_team_meet_max_yellow_editor_rank: 4
  creative_team_meet_anchor_yellow_shoot_rank: 10
  creative_team_meet_editor_soft_cap_per_quarter: 2

penalties:
  consecutive_event_penalty: 30
  repeated_high_tier_event_penalty: 140
  recent_high_tier_window_penalty: 120
  repeated_event_editor_pair_penalty: 110
  repeated_low_tier_event_penalty: 55
  repeated_weekday_low_tier_penalty: 35
  creative_team_meet_editor_repeat_penalty: 65
  creative_team_meet_editor_overuse_penalty: 140
  weekday_late_low_tier_penalty: 80
  repeated_monthly_director_penalty: 200
  multi_day_high_tier_early_day_strength_reserve: 10
  upcoming_high_tier_reserve_penalty: 35
  upcoming_high_tier_preload_penalty: 90
  upcoming_high_tier_preload_same_role_penalty: 50

weights:
  priority_rank: 10
  role_serve_count: 8
  total_serve_count: 3

bonuses:
  first_monthly_photographer_assignment: 24
  yellow_photo_coverage_bonus: 32
  green_editor_rotation_bonus: 24
  creative_team_meet_green_editor_rotation_bonus: 18
  creative_team_meet_lower_yellow_editor_rotation_bonus: 22
  weekend_service_for_weekday_late_member: 18
  multi_day_high_tier_final_day_strength_boost: 18
  creative_team_meet_anchor_bonus: 20

fallbacks:
  blank_rank_value: 50

safety:
  required_guides_for:
    - Isaac
    - Aslvin

special_rules:
  use_scoring_only_after_hard_constraints: true
  frequency_exempt_events:
    - Power Conference KL
    - Power Conference JB
    - Power Festival
```
