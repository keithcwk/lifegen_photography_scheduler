# UNIVERSAL_SCHEDULER.md

This is a starter template for a new ministry.
Only edit inside the fenced code blocks.
Do not rename the `## file/path` headings.
Replace the example names, dates, and sheet settings with your own.
Use `python scripts/compile_universal_scheduler.py --check` before generating a schedule.

## rules/rulebook.md
```md
# Ministry Photography Scheduling Rulebook

## Team Roles

Each main service usually needs:

- 1 Director
- 4 Photographers
- 2 Editors

Directors may also serve as editors when needed.

## Team Categories

Green: Experienced photographers who can direct, edit, and shoot.
Yellow: Developing photographers who can shoot and are learning editing.
Red: New photographers who cannot direct or edit yet.

## Team Composition Rules

- High tier events should be covered by stronger teams
- Low tier events can be used for development opportunities
- Sunday Service should balance experience and development
- Reds must never direct

## Recurring Planning Rules

- Every Sunday is Sunday Service
- The first Tuesday of every month is Prayer Meeting
- The first Friday of every month is Leaders Meeting

## Schedule Sheet Rules

- Photographer slots should appear in tier order: Green, then Yellow, then Red
- `SDE 1` and `SDE 2` should appear in editor-strength order
```

## data/team.yaml
```yaml
greens:
  - name: Example Green 1
    shoot_rank: 1
    direct_rank: 1
    editor_rank: 1

  - name: Example Green 2
    shoot_rank: 2
    direct_rank: 2
    editor_rank: 2

  - name: Example Green 3
    shoot_rank: 3
    direct_rank: 3
    editor_rank: 3

  - name: Example Green 4
    shoot_rank: 4
    direct_rank: 4
    editor_rank: 4

  - name: Example Green 5
    shoot_rank: 5
    direct_rank: 5
    editor_rank: 5

  - name: Example Green 6
    shoot_rank: 6
    direct_rank: 6
    editor_rank: 6

yellows:
  - name: Example Yellow 1
    shoot_rank: 7
    editor_rank: 1
    director_track: true

  - name: Example Yellow 2
    shoot_rank: 8
    editor_rank: 2

  - name: Example Yellow 3
    shoot_rank: 9
    editor_rank: 3

  - name: Example Yellow 4
    shoot_rank: 10
    editor_rank: 4

reds:
  - name: Example Red 1
    shoot_rank: 11
  - name: Example Red 2
    shoot_rank: 12
  - name: Example Red 3
    shoot_rank: 13

shadows: []
```

## data/events.md
```md
# Events

Add one event per line using `DD Mon YYYY - Event Name`.
Keep examples commented out.

<!--
Example
06 Apr 2026 - Special Service
12 Apr 2026 - Sunday Service
19 Apr 2026 - Sunday Service
-->

## Exclusions
<!--
Example
31 May 2026 - Sunday Service
-->
```

## data/bad_dates.md
```md
# Bad Dates

Use quarter headings, then member headings, then bullet dates.
Keep examples commented out.

<!--
Example
## 2026 Q2

### Example Green 1
- 06 Apr 2026

### Example Yellow 1
- 13 Apr 2026
-->
```

## config/event_types.yaml
```yaml
events:
  Sunday Service:
    photographers: 4
    editors: 2
    sde_director: 1
    tier: standard
    min_green_photographers: 1

  Prayer Meeting:
    photographers: 2
    editors: 1
    tier: low

  Leaders Meeting:
    photographers: 2
    editors: 1
    tier: low

  Special Service:
    photographers: 4
    editors: 2
    assist: 1
    sde_director: 1
    floor_runner: 1
    tier: high
    min_green_photographers: 2
    max_red_photographers: 0
```

## config/recurring_events.yaml
```yaml
recurring_events:
  - event: Sunday Service
    frequency: weekly
    weekday: sunday

  - event: Prayer Meeting
    frequency: monthly
    occurrence: first
    weekday: tuesday

  - event: Leaders Meeting
    frequency: monthly
    occurrence: first
    weekday: friday

generation_window:
  months_after_last_explicit_event: 1
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
        key: sde_director
        label: SDE Director
        required: false
      - row: 13
        key: sde_1
        label: SDE 1
        required: true
      - row: 14
        key: sde_2
        label: SDE 2
        required: true
      - row: 15
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
      - sde_director
      - sde_1
      - sde_2
      - shadow
```

## config/google_sheets_sync.yaml
```yaml
# Replace these values before pushing to Google Sheets.
google_sheets:
  spreadsheet_id: "YOUR_SPREADSHEET_ID"
  worksheet_title: "Schedule"
  service_account_json: "/absolute/path/to/google_credentials.json"
  clear_before_write: false
  create_worksheet_if_missing: true
```

## config/scheduler_policy.yaml
```yaml
limits:
  max_assignments_per_member_per_month: 2
  max_director_track_directs_per_month: 1
  max_red_assignments_per_month: 2
  max_high_tier_yellow_shoot_rank: 10
  max_high_tier_yellow_editor_rank: 4
  high_tier_reserve_window_days: 14

penalties:
  consecutive_event_penalty: 30
  repeated_weekday_low_tier_penalty: 35
  weekday_late_low_tier_penalty: 80
  multi_day_high_tier_early_day_strength_reserve: 10
  upcoming_high_tier_reserve_penalty: 18
  upcoming_high_tier_preload_penalty: 55
  upcoming_high_tier_preload_same_role_penalty: 30

bonuses:
  first_monthly_photographer_assignment: 24
  yellow_photo_coverage_bonus: 32
  green_editor_rotation_bonus: 24
  weekend_service_for_weekday_late_member: 18
  multi_day_high_tier_final_day_strength_boost: 18

weights:
  priority_rank: 10
  role_serve_count: 8
  total_serve_count: 3

fallbacks:
  blank_rank_value: 50

safety:
  required_guides_for:
    - Example Red 1

event_roles:
  balanced_service: Sunday Service
  mid_tier_editor: Prayer Meeting
  leaders_meet: Leaders Meeting
  service_marker: service

special_rules:
  frequency_exempt_events: []
```
