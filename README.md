# Church Photography Scheduler

This project generates a photography schedule automatically from simple files.
The scheduler now uses event requirements, role capability, availability, and simple fairness heuristics instead of a fixed rotation.

## Files

`rules/rulebook.md`
Human-readable rules and philosophy.

`data/team.yaml`
Defines the team structure.
Greens support explicit `shoot_rank`, `direct_rank`, and `editor_rank` fields.

`data/events.md`
List of events and dates.
Event names here must exist in `config/event_types.yaml`.
This file can also contain a `## Exclusions` section to suppress specific generated or explicit events.

`data/bad_dates.md`
Quarter-by-quarter unavailable dates for each member.

`config/event_types.yaml`
Defines requirements per event type.

`config/recurring_events.yaml`
Defines recurring monthly events that are auto-added during schedule generation.
This also supports weekly recurring events such as Sunday Service.
It can also extend recurring generation past the last explicit event month.

`config/google_sheets_styles.yaml`
Defines the visual styling tokens for a future Google Sheets export.

`config/google_sheets_layout.yaml`
Defines the sheet structure for the Google Sheets event-matrix layout.

`config/google_sheets_sync.yaml`
Defines which spreadsheet and worksheet to push to, plus the service account JSON path.

`scripts/generate_schedule.py`
Python script that generates the schedule.

`scripts/push_schedule_to_google_sheet.py`
Pushes the generated schedule into a specific Google Sheet worksheet.

`output/`
Generated `schedule.csv`

`output/google_sheets_styles.yaml`
Validated style manifest copied from the config during generation.

## How To Use

1. Edit the events list:

`data/events.md`

Example template:

```
12 Sep 2026 - Mother's Day
13 Sep 2026 - Creative Team Meet
```

`data/events.md` should contain your one-off events. Recurring monthly events are added automatically from `config/recurring_events.yaml`.
If you need to skip a specific recurring date, add it under `## Exclusions` using the same `DD Mon YYYY - Event Name` format.

2. Update team members if needed:

`data/team.yaml`

Green members can now be ranked per role, for example:

```yaml
greens:
  - name: Nic
    shoot_rank: 1
    direct_rank: 1
    editor_rank: 2
```

Lower numbers mean higher priority for that role.

3. Add any unavailable dates for the quarter:

`data/bad_dates.md`

Example template:

<!--
## 2026 Q2

### Keith
- 06 Apr 2026
- 03 May 2026

### Cindy
- 13 Apr 2026
-->

4. Run the generator:

`python scripts/generate_schedule.py`

The scheduler will:

- skip members on their bad dates
- use staffing counts from `config/event_types.yaml`
- auto-add recurring monthly events from `config/recurring_events.yaml`
- prefer stronger coverage for higher-risk events
- prioritize yellow/red photographer opportunities on low-tier events, keeping greens mainly for directing/editing there
- limit director-track members to one directing assignment per month
- automatically fill a green `Assist` slot when a director-track member is directing
- spread assignments using simple load-balancing heuristics
- validate and export the Google Sheets style config

Quarter headings can be written as `2026 Q2` or `Q2 2026`.

5. The schedule will appear in:

`output/schedule.csv`

The validated style manifest will also appear in:

`output/google_sheets_styles.yaml`

You can import this into Google Sheets.

## Push To Google Sheets

1. Create a Google Cloud service account and enable the Google Sheets API.
2. Share your target spreadsheet with the service account email as an editor.
3. Fill in `config/google_sheets_sync.yaml`:

   - `spreadsheet_id`
   - `worksheet_title`
   - `service_account_json`

4. Install the Python dependencies needed for Google Sheets sync:

   - `pip install -r requirements.txt`

If you use the repo-local virtualenv:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

5. Push the schedule:

```bash
./.venv/bin/python scripts/push_schedule_to_google_sheet.py
```

To update only the sheet contents while preserving existing styling:

```bash
./.venv/bin/python scripts/push_schedule_to_google_sheet.py --values-only
```

Or use the CLI:

```bash
./.venv/bin/python scripts/scheduler_cli.py generate
./.venv/bin/python scripts/scheduler_cli.py push-sheet
./.venv/bin/python scripts/scheduler_cli.py generate-and-push
./.venv/bin/python scripts/scheduler_cli.py push-sheet-values
./.venv/bin/python scripts/scheduler_cli.py generate-and-push-values
```

The push script writes:

- the event-matrix schedule section
- the member workload summary section
- the bad dates section

It then applies basic formatting based on `config/google_sheets_styles.yaml`.

If you use the `values-only` commands, the script updates the table contents but skips all formatting requests so the current Google Sheets styling stays untouched.

## Google Sheets Layout

The draft schedule sheet is not a flat table. It is a column-based event matrix:

- each event occupies one column
- row 1 is the event name
- row 2 is the event date
- row 3 is `N/A` and lists people with bad dates for that event
- the rows below are role slots like `Director`, `Assist`, `Photographer 1` to `Photographer 5`, `Floor runner`, `SDE 1`, and `SDE 2`

`Sunday Service` can still be generated as a recurring event while leaving the event-name cell blank in Google Sheets.

The Google Sheets renderer also keeps event dates as month-day text like `1 May`, and it assigns one shared color to all event columns within the same month.
All cells are center-aligned, and event-name cells are wrapped.
Month colors are chosen from a constrained light swatch palette, and each month block gets its own outline border.

The machine-readable version of that structure lives in `config/google_sheets_layout.yaml`.

The generated CSV now uses a slot-based canonical format that maps cleanly into that sheet layout:

- `event`
- `date`
- `director`
- `assist`
- `photographer_1` to `photographer_5`
- `floor_runner`
- `sde_1`
- `sde_2`

Optional slots stay blank when an event does not use them.

## Future Improvements

- Automatic Google Sheets upload
- Constraint solver for optimal schedules
