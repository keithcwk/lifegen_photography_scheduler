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

yellows:
  - name: Example Yellow 1
    editor_rank: 1
    director_track: true

  - name: Example Yellow 2
    editor_rank: 2

reds:
  - Example Red 1
  - Example Red 2
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
    directors: 1
    editors: 2
    tier: standard

  Prayer Meeting:
    photographers: 2
    directors: 1
    editors: 1
    tier: low

  Leaders Meeting:
    photographers: 2
    directors: 1
    editors: 1
    tier: low

  Special Service:
    photographers: 4
    directors: 1
    editors: 2
    tier: high
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
google_sheets_styles:
  font_family: Montserrat
  pivot_column:
    background_color: "#F3F4F6"
  header_rows:
    bold: true
  borders:
    color: "#D0D7DE"
  month_palette:
    colors:
      - "#D9EAD3"
      - "#D0E0E3"
      - "#FCE5CD"
      - "#EAD1DC"
```

## config/google_sheets_layout.yaml
```yaml
sheet_layout:
  event_matrix:
    pivot_column_label: Role
    event_name_row: 1
    event_date_row: 2
    unavailable_row: 3
  role_rows:
    - Director
    - Assist
    - Photographer 1
    - Photographer 2
    - Photographer 3
    - Photographer 4
    - Photographer 5
    - Floor runner
    - SDE 1
    - SDE 2
  summary_section:
    title: Summary
    headers:
      - Name
      - Shoot
      - SDE
      - Direct/Assist
      - Has Slot
  bad_dates_section:
    title: Bad Dates
    headers:
      - Name
      - Bad Dates
  canonical_scheduler_format:
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
```

## config/google_sheets_sync.yaml
```yaml
# Replace these values before pushing to Google Sheets.
google_sheets:
  spreadsheet_id: "YOUR_SPREADSHEET_ID"
  worksheet_title: "Schedule"
  service_account_json: "/absolute/path/to/google_credentials.json"
  clear_before_write: true
  create_worksheet_if_missing: true
```
