import argparse
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from generate_schedule import (
    DATE_FORMAT,
    EVENT_LINE_PATTERN,
    build_members,
    load_team,
    load_event_types,
    parse_bad_dates,
    parse_event_file,
    parse_events,
    quarter_key,
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


def validate_event_line(event_line):
    match = EVENT_LINE_PATTERN.fullmatch(event_line.strip())
    if not match:
        raise ValueError(f"Event must use '{DATE_FORMAT} - Event Name'.")

    date_str, event_name = match.groups()
    datetime.strptime(date_str, DATE_FORMAT)

    event_types = load_event_types()
    if event_name.strip() not in event_types:
        raise ValueError(
            f"Unknown event type '{event_name.strip()}'. Add it to config/event_types.yaml first."
        )

    return f"{date_str} - {event_name.strip()}"


def write_events(event_lines, exclusions=None):
    content = EVENTS_TEMPLATE.rstrip() + "\n\n"
    if event_lines:
        content += "\n".join(event_lines) + "\n"
    if exclusions:
        content += "\n## Exclusions\n"
        content += "\n".join(exclusions) + "\n"

    with open(EVENTS_FILE, "w") as f:
        f.write(content)


def add_event(event_line):
    normalized = validate_event_line(event_line)
    explicit_events, exclusions = parse_event_file()
    existing = {
        f"{event['date'].strftime(DATE_FORMAT)} - {event['event']}" for event in explicit_events
    }
    existing.add(normalized)

    sorted_events = sorted(
        existing,
        key=lambda line: datetime.strptime(line.split(" - ", 1)[0], DATE_FORMAT),
    )
    sorted_exclusions = sorted(
        {
            f"{event_date.strftime(DATE_FORMAT)} - {event_name}"
            for event_date, event_name in exclusions
        },
        key=lambda line: datetime.strptime(line.split(" - ", 1)[0], DATE_FORMAT),
    )
    write_events(sorted_events, sorted_exclusions)

    print(f"Added event: {normalized}")


def quarter_sort_key(quarter_label):
    year_str, quarter_str = quarter_label.split()
    return int(year_str), int(quarter_str[1:])


def write_bad_dates(bad_dates):
    grouped = defaultdict(lambda: defaultdict(list))

    for name, dates in bad_dates.items():
        for blocked_date in sorted(dates):
            grouped[quarter_key(blocked_date)][name].append(blocked_date)

    lines = [BAD_DATES_TEMPLATE.rstrip()]

    for quarter in sorted(grouped, key=quarter_sort_key):
        lines.extend(["", f"## {quarter}", ""])

        for name in sorted(grouped[quarter]):
            lines.append(f"### {name}")
            for blocked_date in grouped[quarter][name]:
                lines.append(f"- {blocked_date.strftime(DATE_FORMAT)}")
            lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    with open(BAD_DATES_FILE, "w") as f:
        f.write(content)


def mark_unavailable(name, date_str):
    blocked_date = datetime.strptime(date_str, DATE_FORMAT).date()
    known_members = build_members(load_team())
    if name not in known_members:
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
    subprocess.run([scheduler_python(), "scripts/generate_schedule.py"], check=True)
    print("Schedule regenerated.")


def push_schedule(generate_first=True, values_only=False):
    command = [scheduler_python(), "scripts/push_schedule_to_google_sheet.py"]
    if not generate_first:
        command.append("--skip-generate")
    if values_only:
        command.append("--values-only")

    subprocess.run(command, check=True)
    if values_only:
        print("Schedule values pushed to Google Sheets without restyling.")
    else:
        print("Schedule pushed to Google Sheets.")


def suggest_replacement(name, date):
    print(f"Suggesting replacement for {name} on {date}")
    print("Not implemented yet. Next step: read output/schedule.csv and score backups.")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    add_event_cmd = sub.add_parser("add-event")
    add_event_cmd.add_argument("event")

    unavailable_cmd = sub.add_parser("mark-unavailable")
    unavailable_cmd.add_argument("name")
    unavailable_cmd.add_argument("date")

    replace_cmd = sub.add_parser("suggest-replacement")
    replace_cmd.add_argument("name")
    replace_cmd.add_argument("date")

    sub.add_parser("generate")
    sub.add_parser("push-sheet")
    sub.add_parser("generate-and-push")
    sub.add_parser("push-sheet-values")
    sub.add_parser("generate-and-push-values")

    args = parser.parse_args()

    if args.command == "add-event":
        add_event(args.event)
        run_scheduler()
    elif args.command == "mark-unavailable":
        mark_unavailable(args.name, args.date)
        run_scheduler()
    elif args.command == "suggest-replacement":
        suggest_replacement(args.name, args.date)
    elif args.command == "generate":
        run_scheduler()
    elif args.command == "push-sheet":
        push_schedule(generate_first=False)
    elif args.command == "generate-and-push":
        push_schedule(generate_first=True)
    elif args.command == "push-sheet-values":
        push_schedule(generate_first=False, values_only=True)
    elif args.command == "generate-and-push-values":
        push_schedule(generate_first=True, values_only=True)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
