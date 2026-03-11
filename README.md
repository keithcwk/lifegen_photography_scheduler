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
