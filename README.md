# Church Photography Scheduler

This repo can now be used in a non-developer workflow.
The main file a normal user should edit is `UNIVERSAL_SCHEDULER.md`.
Everything else is generated from it or used by the scripts.

## Start Here

If you are not technical, use this workflow only:

1. Open `UNIVERSAL_SCHEDULER.md`
2. Edit only inside the fenced code blocks
3. Run `executables/Validate Universal Scheduler.command`
4. Run `executables/Generate Schedule.command`
5. If needed, run `executables/Push Schedule To Google Sheets.command`

Do not rename the `## rules/...`, `## data/...`, or `## config/...` headings.
Do not remove the triple backticks.

## Safe Files

Normal users only need these files:

- `UNIVERSAL_SCHEDULER.md`: the single source of truth you edit
- `UNIVERSAL_SCHEDULER.template.md`: reusable starter template for a new ministry
- `README.md`: setup and usage guide

Everything else is support machinery.

## One-Click Scripts

If you are on macOS, you can double-click these files from Finder:

- `executables/Validate Universal Scheduler.command`
- `executables/Generate Schedule.command`
- `executables/Push Schedule To Google Sheets.command`

They use the repo's `.venv` if present. Otherwise they fall back to `python3`.

## Command Line Equivalents

```bash
./.venv/bin/python scripts/compile_universal_scheduler.py --check
./.venv/bin/python scripts/generate_schedule.py
./.venv/bin/python scripts/push_schedule_to_google_sheet.py
```

Run the checks after changing anything:

```bash
./.venv/bin/python tests/test_scheduler.py
```

Import a quarter tab from the Google Sheet (special events in row 2, the `N/A` row 4 and the BAD DATES block become bad dates):

```bash
./.venv/bin/python scripts/import_sheet_quarter.py --tab Q4          # preview
./.venv/bin/python scripts/import_sheet_quarter.py --tab Q4 --write  # apply
./.venv/bin/python scripts/import_sheet_quarter.py --tab "Q4 Schedule" --bad-dates-only --write
```

Write the roster into a hand-built quarter tab, leaving its formulas and formatting alone:

```bash
./.venv/bin/python scripts/push_schedule_to_google_sheet.py --dry-run
./.venv/bin/python scripts/push_schedule_to_google_sheet.py --restructure
./.venv/bin/python scripts/push_schedule_to_google_sheet.py --target pcjb
```

`--dry-run` prints every range it would touch. `--restructure` also rebuilds the month header
merges and the per-month summary formulas after the column layout changes; normal pushes leave
rows 18 and below untouched.

Useful extra commands:

```bash
./.venv/bin/python scripts/compile_universal_scheduler.py --export-current
./.venv/bin/python scripts/compile_universal_scheduler.py --write-template
./.venv/bin/python scripts/scheduler_cli.py check-universal
./.venv/bin/python scripts/scheduler_cli.py compile-universal
./.venv/bin/python scripts/scheduler_cli.py write-template
```

## What The Validator Checks

The validator tries to catch the mistakes non-dev users usually make:

- broken YAML in team or config sections
- unknown member names in bad dates
- unknown event names in events or recurring rules
- bad event date format
- bad quarter headings in bad dates
- dates placed in the wrong quarter
- blank Google Sheets sync fields
- duplicate member names

The goal is for users to see a short list of problems instead of a Python traceback.

## Reusing This For Another Ministry

Use `UNIVERSAL_SCHEDULER.template.md` as the starter.

Suggested process:

1. Copy this repo or duplicate the template file into a new repo
2. Replace the example team with the new ministry's members
3. Replace event types and recurring rules with the new ministry's reality
4. Update Google Sheets settings
5. Run the validator
6. Generate the schedule

That gives other teams the same engine, while only changing one human-edited file.

## Roles The Scheduler Fills

Per event, `config/event_types.yaml` decides which slots exist:

- `photographers` and `editors`: the core lineup
- `sde_director: 1`: the person overseeing the editors. Sunday services and big events use one.
  Eligible: greens plus anyone within the strong-editor rank limit. Always a different person
  from the director, editors and photographers; on high tier events they edit as well.
- `assist: 1`: an assist director for every run of that event. A trainee director always gets a
  green assist whether or not the event asks for one.
- `floor_runner: 1`: a floor runner, preferring reds as a development slot.
- `greens_only: true`: restricts every slot of that event to greens (used by Power Conference JB).
- `director_edits: true`: the director also fills the editor slot (used by Leaders Meet and Leaders Retreat).
- `extra_red_photographer: 1`: one more photographer slot, only for a red who has not served in
  `limits.red_idle_days` (used by Lifegen Prayer).
- `leaders_only: true`: restricts every slot to members marked `leader: true`.

Multi-session events get one line per session in `data/events.md`:

```
11 Sep 2026 - Power Conference KL | Night 1
11 Sep 2026 - Power Conference KL | Night 2
```

Each session is its own column with its own roster. Staffing comes from the event type, or from a
block named `Power Conference KL | Night 1` if you want that session shaped differently.

## Team Fields

Useful optional fields inside `data/team.yaml` or the team section of `UNIVERSAL_SCHEDULER.md`:

- `leader: true` marks members who may serve at leaders-only events (`leaders: true` also works)
- `guide: true` marks members who may guide `Isaac` or `Aslvin`
- `weekday_late: true` tells the scheduler to avoid weekday low-tier events for that member when workable and prefer occasional Sunday usage instead
- greens still use `shoot_rank`, `direct_rank`, and `editor_rank`
- yellows still use `editor_rank`, and may also use `director_track: true`
- `shadows: []` can hold observer-only members with no active assignment slots

Guided photographer slots are displayed as `Name + Guide`, for example `Isaac + Dan C`.

## Files Generated From The Universal File

All managed files in the universal scheduler are now kept in sync automatically with their matching sections inside `UNIVERSAL_SCHEDULER.md`. If one of the generated files is edited directly, the more recently edited copy wins during validation, compile, and schedule generation.

When `UNIVERSAL_SCHEDULER.md` is newer than the generated repo files, schedule generation automatically syncs these files from it first:

- `rules/rulebook.md`
- `data/team.yaml`
- `data/events.md`
- `data/bad_dates.md`
- `config/event_types.yaml`
- `config/recurring_events.yaml`
- `config/google_sheets_styles.yaml`
- `config/google_sheets_layout.yaml`
- `config/google_sheets_sync.yaml`
- `config/scheduler_policy.yaml`

## Google Sheets

To push to Google Sheets you still need:

- a spreadsheet ID
- a worksheet title
- a service account JSON path in `config/google_sheets_sync.yaml`
- the spreadsheet shared with the service account as `Editor`

### Google Credentials Setup

1. Open Google Cloud Console and create or choose a project.
2. Enable the Google Sheets API for that project.
3. Create a Service Account for the project.
4. Create a JSON key for that service account and download it.
5. Save that JSON file somewhere on your Mac.
   Example: `/Users/yourname/path/to/google_credentials.json`
6. Put that absolute file path into `config/google_sheets_sync.yaml` or the matching section in `UNIVERSAL_SCHEDULER.md`:

```yaml
google_sheets:
  spreadsheet_id: "YOUR_SPREADSHEET_ID"
  worksheet_title: "Your Sheet Tab Name"
  service_account_json: "/Users/yourname/path/to/google_credentials.json"
  clear_before_write: false
  create_worksheet_if_missing: true
```

7. Open the target Google Sheet and share it with the service account email as an `Editor`.
   The service account email is inside the JSON file under `client_email`.
8. Run:

```bash
./.venv/bin/python scripts/push_schedule_to_google_sheet.py
```

Notes:

- `google_credentials.json` is already ignored by git in this repo, so it will not be committed by default.
- If push fails with a permission error, the sheet is usually not shared with the service account yet.
- If push fails with an API-disabled error, enable Google Sheets API in the same Google Cloud project and retry after a few minutes.

Pushes update cell values only and leave your live formatting alone. To restyle the managed
ranges as well:

```bash
./.venv/bin/python scripts/push_schedule_to_google_sheet.py --with-formatting
```

After a change to the sheet's shape (new rows or columns), push twice: the incremental diff
clears stale cells on the second pass.

## Troubleshooting

If validation fails:

1. Read the exact file and line mentioned in the error list
2. Fix only that line first
3. Run validation again

If generation fails after validation passes:

- check whether the ministry rules are impossible to satisfy with the current team and bad dates
- check whether required Google or Python dependencies are missing

If you want to change scheduler behavior itself, that is a maintainer task and usually means editing Python, not just the universal file.
