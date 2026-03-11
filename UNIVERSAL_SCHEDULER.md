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
Red: New photographers who cannot direct or edit yet.

## Greens

Greens are now ranked in `data/team.yaml` with:

- `shoot_rank`
- `direct_rank`
- `editor_rank`

Lower rank numbers mean stronger priority for that role.

## Yellows (Editor Rank)

1. Charites
2. Dan C
3. Jia En
4. Cindy
5. Patrick
6. Wing Yan
7. Janelle
8. Felise
9. Ashley

Director Development Track:

- Charites
- Dan C

Director-track members may direct at most once per month until this rule is updated.
If a director-track member is directing, the `Assist` slot must be filled by a green.

## Reds

Alvin
Josiah
Issac
Aslvin

## Safety Rule

If Issac or Aslvin are scheduled, they must be accompanied by:

- Any Green, OR
- Dan C

This accompaniment must be visible within the photographer lineup, not only in director or editor slots.

## Team Composition Rules

- High tier events must include at least 2 greens
- High tier events should avoid reds if possible
- Standard and high tier events with photographer slots must include at least 1 green photographer
- High tier events must include at least 2 green photographer slots
- High tier events ideally should have no red photographer slots
- Low tier events should prioritize yellow and red photographer opportunities
- Low tier events should generally avoid using greens in photographer slots unless needed to keep the schedule workable
- Sunday Service must include at least 1 green, 1 yellow, and 1 red
- Sunday Service should ideally avoid having 2 green photographer slots
- No service may have more than 2 reds
- Leaders Meet should only schedule members marked as leaders in `data/team.yaml`
- Leaders Meet only needs 1 photographer
- Creative Team Meet and Lifegen Prayer should be balanced across the quarter so the same person is not repeated in the same role too often
- Each photographer should ideally be able to serve 1 Sunday per month; low tier events are additional opportunities and should not replace a Sunday slot
- Photographers should ideally not be assigned more than 2 times in the same month, regardless of event tier
- Red members should not be scheduled more than 2 times in the same month
- Avoid serving consecutive weeks if possible; high tier events can be an exception when stronger coverage is needed

## Event Risk Levels

High Risk:

- Mother's Day
- Christmas
- Easter
- Father's Day
- Lifegen Camp

Standard:

- Sunday Service

Low Risk:

- Leaders Meet
- Creative Team Meet
- Lifegen Prayer

## Recurring Planning Rules

- Every Sunday is Sunday Service
- The first Tuesday of every month is Lifegen Prayer
- The first Friday of every month is Leaders Meet
- The last Friday of every month is Creative Team Meet

## Schedule Sheet Rules

- The Google Sheets pivot column uses one consistent color for all row labels
- Row 1 and Row 2 are always bold across the full schedule matrix
- Row 3 is `N/A` and lists members who have bad dates for that event
- Photographer slots in the schedule must be listed in tier order: Green, then Yellow, then Red
- `SDE 1` and `SDE 2` must be listed in editor-rank order, strongest first

## Growth Goals (2026)

- Train new directors (Charites and Dan C)
- Greens should shoot or direct at least once per month
```
```
```
```
```
```
```
```
```
```
```
```
```
```

## data/team.yaml
```yaml
greens:
  - name: Nic
    shoot_rank: 1
    direct_rank: 1
    editor_rank: 2
    leader: true

  - name: Keith
    shoot_rank: 2
    direct_rank: 2
    editor_rank: 1
    leader: true

  - name: Dennis
    shoot_rank: 3
    direct_rank: 3
    editor_rank: 3
    leader: true

  - name: Gavin
    shoot_rank: 4
    direct_rank: 4
    editor_rank: 4
    leader: true

  - name: Huey Chyi
    shoot_rank: 5
    direct_rank: 5
    editor_rank: 5
    leader: true

  - name: Joseph
    shoot_rank: 6
    direct_rank: 6
    editor_rank: 6
    leader: true

yellows:
  - name: Charites
    editor_rank: 1
    director_track: true

  - name: Dan C
    editor_rank: 2
    director_track: true

  - name: Jia En
    editor_rank: 3

  - name: Cindy
    editor_rank: 4

  - name: Patrick
    editor_rank: 5

  - name: Wing Yan
    editor_rank: 6

  - name: Janelle
    editor_rank: 7

  - name: Felise
    editor_rank: 8

  - name: Ashley
    editor_rank: 9

reds:
  - Alvin
  - Josiah
  - Issac
  - Aslvin
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
10 May 2026 - Mother's Day
17 May 2026 - Sunday Service
24 May 2026 - Creative Team Meet
31 May 2026 - Sunday Service
-->

3 Apr 2026 - Good Friday
5 Apr 2026 - Easter
10 May 2026 - Mother's Day
29 May 2026 - Lifegen Camp
30 May 2026 - Lifegen Camp
31 May 2026 - Lifegen Camp
1 Jun 2026 - Lifegen Camp
21 Jun 2026 - Father's Day

## Exclusions

3 Apr 2026 - Leaders Meet
29 May 2026 - Creative Team Meet
31 May 2026 - Sunday Service
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
```

## config/event_types.yaml
```yaml
events:
  Sunday Service:
    photographers: 4
    director: 1
    editors: 2
    tier: standard

  Mother's Day:
    photographers: 4
    director: 1
    editors: 2
    tier: high

  Father's Day:
    photographers: 4
    director: 1
    editors: 2
    tier: high

  Easter:
    photographers: 4
    director: 1
    editors: 2
    tier: high

  Good Friday:
    photographers: 4
    director: 1
    editors: 2
    tier: high

  Lifegen Camp:
    photographers: 4
    director: 1
    editors: 2
    tier: high

  Leaders Meet:
    photographers: 1
    director: 1
    editors: 0
    tier: low

  Creative Team Meet:
    photographers: 2
    director: 1
    editors: 1
    tier: low

  Lifegen Prayer:
    photographers: 2
    director: 1
    editors: 1
    tier: low
```

## config/recurring_events.yaml
```yaml
generation_window:
  months_after_last_explicit_event: 1

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
```

## config/google_sheets_sync.yaml
```yaml
# Share the target spreadsheet with your service account email as an editor.
google_sheets:
  spreadsheet_id: "1vEDY8SNbTKOyvSPSxq8xqzSrNZvld3nBD8SvQu3x2Gw"
  worksheet_title: "GPT Schedule Q2 Test"
  service_account_json: "/Users/keithchan/Codes/lifegen_photography_scheduler/google_credentials.json"
  clear_before_write: true
  create_worksheet_if_missing: true
```
