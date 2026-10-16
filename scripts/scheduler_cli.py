import argparse
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from generate_schedule import (
    DATE_FORMAT,
    EVENT_LINE_PATTERN,
    build_members,
    load_yaml,
    parse_bad_dates,
    parse_event_file,
    quarter_key,
)
from universal_scheduler import (
    UNIVERSAL_SCHEDULER_PATH,
    UniversalSchedulerValidationError,
    compile_universal_scheduler,
    validate_universal_scheduler,
    write_universal_scheduler,
    write_universal_scheduler_template,
)

BASE = Path(__file__).resolve().parents[1]
EVENTS_FILE = BASE / "data/events.md"
BAD_DATES_FILE = BASE / "data/bad_dates.md"
VENV_PYTHON = BASE / ".venv/bin/python"

EVENTS_TEMPLATE = """# Events

Add one event per line using `DD Mon YYYY - Event Name`.
Add optional exclusions under `## Exclusions` using the same format to suppress specific generated or explicit events.
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

## Exclusions
29 May 2026 - Creative Team Meet
31 May 2026 - Sunday Service
-->
"""

BAD_DATES_TEMPLATE = """# Bad Dates

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
"""


def ensure_direct_file_editing_allowed():
    if UNIVERSAL_SCHEDULER_PATH.exists():
        raise RuntimeError(
            "UNIVERSAL_SCHEDULER.md is present. Edit that file and run compile-universal instead of mutating generated files directly."
        )


def guarded(action):
    try:
        return action()
    except UniversalSchedulerValidationError as exc:
        print("Universal scheduler needs attention:")
        for issue in exc.issues:
            print(f"- {issue}")
        raise SystemExit(1)


def validate_event_line(event_line):
    match = EVENT_LINE_PATTERN.fullmatch(event_line.strip())
    if not match:
        raise ValueError(f"Event must use '{DATE_FORMAT} - Event Name'.")

    date_str, event_name = match.groups()
    datetime.strptime(date_str, DATE_FORMAT)

    event_name = event_name.strip()
    if event_name not in load_yaml("config/event_types.yaml").get("events", {}):
        raise ValueError(
            f"Unknown event type '{event_name}'. Add it to config/event_types.yaml first."
        )

    return f"{date_str} - {event_name}"


def write_events(event_lines, exclusions=None):
    content = EVENTS_TEMPLATE.rstrip() + "\n\n"
    if event_lines:
        content += "\n".join(event_lines) + "\n"
    if exclusions:
        content += "\n## Exclusions\n" + "\n".join(exclusions) + "\n"

    EVENTS_FILE.write_text(content)


def by_event_date(line):
    return datetime.strptime(line.split(" - ", 1)[0], DATE_FORMAT)


def add_event(event_line):
    ensure_direct_file_editing_allowed()

    normalized = validate_event_line(event_line)
    explicit_events, exclusions = parse_event_file()
    events = {
        f"{event['date'].strftime(DATE_FORMAT)} - {event['event']}" for event in explicit_events
    }
    events.add(normalized)
    write_events(
        sorted(events, key=by_event_date),
        sorted(
            {f"{event_date.strftime(DATE_FORMAT)} - {name}" for event_date, name in exclusions},
            key=by_event_date,
        ),
    )

    print(f"Added event: {normalized}")


def write_bad_dates(bad_dates):
    grouped = defaultdict(lambda: defaultdict(list))
    for name, dates in bad_dates.items():
        for blocked_date in sorted(dates):
            grouped[quarter_key(blocked_date)][name].append(blocked_date)

    lines = [BAD_DATES_TEMPLATE.rstrip()]
    for quarter in sorted(grouped):
        lines += ["", f"## {quarter}", ""]
        for name in sorted(grouped[quarter]):
            lines.append(f"### {name}")
            lines += [f"- {blocked.strftime(DATE_FORMAT)}" for blocked in grouped[quarter][name]]
            lines.append("")

    BAD_DATES_FILE.write_text("\n".join(lines).rstrip() + "\n")


def mark_unavailable(name, date_str):
    ensure_direct_file_editing_allowed()

    blocked_date = datetime.strptime(date_str, DATE_FORMAT).date()
    if name not in build_members(load_yaml("data/team.yaml")):
        raise ValueError(f"Unknown member '{name}'. Update data/team.yaml first.")

    bad_dates = parse_bad_dates()
    bad_dates.setdefault(name, set()).add(blocked_date)
    write_bad_dates(bad_dates)

    print(f"{name} marked unavailable on {date_str}")


def scheduler_python():
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable or "python3"


def run_scheduler():
    subprocess.run([scheduler_python(), str(BASE / "scripts/generate_schedule.py")], check=True)
    print("Schedule regenerated.")


def push_schedule(generate_first=True, values_only=False):
    command = [scheduler_python(), str(BASE / "scripts/push_schedule_to_google_sheet.py")]
    if not generate_first:
        command.append("--skip-generate")
    if values_only:
        command.append("--values-only")

    subprocess.run(command, check=True)
    if values_only:
        print("Schedule values pushed to Google Sheets without restyling.")
    else:
        print("Schedule pushed to Google Sheets.")


def compile_universal():
    written_paths = guarded(compile_universal_scheduler)
    print("Compiled universal scheduler into:")
    for path in written_paths:
        print(path)


def check_universal():
    guarded(validate_universal_scheduler)
    print("Universal scheduler looks valid.")


COMMANDS = {
    "add-event": (["event"], lambda args: (add_event(args.event), run_scheduler())),
    "mark-unavailable": (
        ["name", "date"],
        lambda args: (mark_unavailable(args.name, args.date), run_scheduler()),
    ),
    "generate": ([], lambda args: run_scheduler()),
    "compile-universal": ([], lambda args: compile_universal()),
    "check-universal": ([], lambda args: check_universal()),
    "export-universal": (
        [],
        lambda args: print(f"Universal scheduler exported to {write_universal_scheduler()}"),
    ),
    "write-template": (
        [],
        lambda args: print(f"Template written to {write_universal_scheduler_template()}"),
    ),
    "push-sheet": ([], lambda args: push_schedule(generate_first=False)),
    "generate-and-push": ([], lambda args: push_schedule(generate_first=True)),
    "push-sheet-values": ([], lambda args: push_schedule(generate_first=False, values_only=True)),
    "generate-and-push-values": ([], lambda args: push_schedule(generate_first=True, values_only=True)),
}


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    for name, (arguments, handler) in COMMANDS.items():
        command_parser = subparsers.add_parser(name)
        for argument in arguments:
            command_parser.add_argument(argument)
        command_parser.set_defaults(handler=handler)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.handler(args)


if __name__ == "__main__":
    main()
