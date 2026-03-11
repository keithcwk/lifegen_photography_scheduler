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

## Team Fields

Useful optional fields inside `data/team.yaml` or the team section of `UNIVERSAL_SCHEDULER.md`:

- `leaders: true` marks members who may serve at `Leaders Meet`
- `can_guide: true` marks members who may guide `Issac` or `Aslvin`
- greens still use `shoot_rank`, `direct_rank`, and `editor_rank`
- yellows still use `editor_rank`, and may also use `director_track: true`

Guided photographer slots are displayed as `Name + Guide`, for example `Issac + Dan C`.

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

Values-only push is available if you want to preserve live formatting:

```bash
./.venv/bin/python scripts/push_schedule_to_google_sheet.py --values-only
```

## Troubleshooting

If validation fails:

1. Read the exact file and line mentioned in the error list
2. Fix only that line first
3. Run validation again

If generation fails after validation passes:

- check whether the ministry rules are impossible to satisfy with the current team and bad dates
- check whether required Google or Python dependencies are missing

If you want to change scheduler behavior itself, that is a maintainer task and usually means editing Python, not just the universal file.
