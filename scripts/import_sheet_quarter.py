"""Import a quarter's events and bad dates from a Google Sheets tab.

Reads the tab's event row, date row and BAD DATES section, maps the sheet's labels onto
event types, and shows what it would add to data/events.md and data/bad_dates.md.

    python scripts/import_sheet_quarter.py --tab Q4            # preview
    python scripts/import_sheet_quarter.py --tab Q4 --write    # apply
"""

import argparse
import calendar
from datetime import date, timedelta

from generate_schedule import EVENTS_PATH, build_members, load_yaml, parse_bad_dates, parse_event_file
from push_schedule_to_google_sheet import get_sheets_service, load_sync_config
from scheduler_cli import write_bad_dates
from universal_scheduler import DATE_FORMAT, event_type, sync_universal_scheduler_if_needed

IMPORT_CONFIG = "config/sheet_import.yaml"
SHEET_EPOCH = date(1899, 12, 30)
MONTHS = {name: number for number, name in enumerate(calendar.month_abbr) if name}


def parse_sheet_day(text, year):
    """One date: a sheet serial, 'D/M', 'D/M/YYYY' or 'D Mon'."""
    text = text.strip().rstrip(".")
    try:
        if text.isdigit():
            serial = int(text)  # small numbers are day labels like "27", not serials
            return SHEET_EPOCH + timedelta(days=serial) if serial >= 40000 else None
        if "/" in text:
            parts = [part.strip() for part in text.split("/")]
            if len(parts) in (2, 3) and all(part.isdigit() for part in parts):
                return date(int(parts[2]) if len(parts) == 3 else year, int(parts[1]), int(parts[0]))
            return None
        day, _, month = text.partition(" ")
        month_number = MONTHS.get(month.strip()[:3].title())
        return date(year, month_number, int(day)) if day.isdigit() and month_number else None
    except ValueError:
        return None


def sheet_dates(value, year):
    """Every date in a cell, expanding ranges like '11/10 - 20/10' or '26/11-2/12'."""
    text = str(value).strip()
    start, separator, end = text.partition("-")
    if separator:
        first, last = parse_sheet_day(start, year), parse_sheet_day(end, year)
        if first and last and first <= last:
            return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
        return []
    single = parse_sheet_day(text, year)
    return [single] if single else []


def sheet_date(value, fallback_year):
    found = sheet_dates(value, fallback_year)
    return found[0] if len(found) == 1 else None


def read_tab(tab, render="UNFORMATTED_VALUE"):
    sync_config = load_sync_config()
    service = get_sheets_service(sync_config["service_account_json"])
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=sync_config["spreadsheet_id"],
            range=f"'{tab}'!A1:AZ200",
            valueRenderOption=render,
        )
        .execute()
    )
    return response.get("values", [])


def cell(rows, row_index, column_index):
    if row_index >= len(rows) or column_index >= len(rows[row_index]):
        return ""
    return str(rows[row_index][column_index]).strip()


def import_events(rows, layout, aliases, known_types):
    """Row 2 holds the special event label, row 3 the date; a blank label means a plain service."""
    event_row = layout["event_row"] - 1
    date_row = layout["date_row"] - 1
    default_event = layout["default_event"]

    events = []
    unknown = []
    width = max(len(rows[event_row]) if event_row < len(rows) else 0, len(rows[date_row]))
    for column in range(1, width):
        event_date = sheet_date(cell(rows, date_row, column), date.today().year)
        if event_date is None:
            continue

        label = cell(rows, event_row, column).replace("\n", " ").strip()
        name = aliases.get(label, aliases.get(label.lower(), label)) or default_event
        if not label:
            name = default_event
        if name not in known_types and event_type(name) not in known_types:
            unknown.append(label)
            continue
        events.append(f"{event_date.strftime(DATE_FORMAT)} - {name}")

    return events, unknown


def resolve_member(name, member_aliases):
    aliases = {alias.casefold(): member for alias, member in member_aliases.items()}
    return aliases.get(name.casefold(), name)


def import_unavailable_row(rows, layout, member_aliases, known_members, blocked, unknown):
    """The N/A row lists, under each dated column, who cannot serve that day."""
    if not layout.get("unavailable_row"):
        return
    year = layout.get("year") or date.today().year
    na_row, date_row = layout["unavailable_row"] - 1, layout["date_row"] - 1
    width = len(rows[na_row]) if na_row < len(rows) else 0
    for column in range(1, width):
        event_date = sheet_date(cell(rows, date_row, column), year)
        if event_date is None:
            continue
        for name in filter(None, (part.strip() for part in cell(rows, na_row, column).split(","))):
            member = resolve_member(name, member_aliases)
            if member in known_members:
                blocked.setdefault(member, set()).add(event_date)
            else:
                unknown.append(name)


def import_bad_dates(rows, layout, member_aliases, known_members, typed_rows=None):
    """The bad dates block is 'Names | Dates | Reason', a blank name continuing the row above.

    The block is read from `typed_rows` (the sheet's displayed text) when given: a typed '2/10'
    is auto-converted by the sheet's US locale, so its raw value is 10 Feb, not 2 Oct.
    """
    blocked = {}
    unknown = []
    import_unavailable_row(rows, layout, member_aliases, known_members, blocked, unknown)
    rows = typed_rows or rows

    heading = layout["bad_dates_heading"].casefold()
    start = next(
        (index for index, row in enumerate(rows) if row and str(row[0]).strip().casefold() == heading),
        None,
    )
    if start is None:
        return blocked, unknown

    year = layout.get("year") or date.today().year
    member = None
    for row_index in range(start + 2, len(rows)):  # +2 skips the column headers
        name = cell(rows, row_index, 0)
        dates = cell(rows, row_index, 1)
        if not name and not dates:
            break
        if name:
            member = resolve_member(name, member_aliases)
            if member not in known_members:
                unknown.append(name)
                member = None
        if member is None:
            continue

        found = [day for piece in dates.split(",") for day in sheet_dates(piece, year)]
        if found:
            blocked.setdefault(member, set()).update(found)

    return blocked, unknown


def merge_events(new_lines):
    """Insert missing event lines above the exclusions block, leaving the rest of the file alone."""
    existing, _ = parse_event_file()
    known = {f"{event['date'].strftime(DATE_FORMAT)} - {event['event']}" for event in existing}
    missing = [line for line in new_lines if line not in known]
    if not missing:
        return []

    text = EVENTS_PATH.read_text()
    marker = "\n## Exclusions"
    head, separator, tail = text.partition(marker)
    EVENTS_PATH.write_text(head.rstrip() + "\n" + "\n".join(missing) + "\n" + separator + tail)
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tab", required=True, help="Worksheet title to read, e.g. Q4")
    parser.add_argument("--write", action="store_true", help="Apply the changes to data/")
    parser.add_argument("--bad-dates-only", action="store_true", help="Skip the event row")
    args = parser.parse_args()

    settings = load_yaml(IMPORT_CONFIG)
    layout = settings["layout"]
    known_types = set(load_yaml("config/event_types.yaml").get("events", {}))
    known_members = set(build_members(load_yaml("data/team.yaml")))

    rows = read_tab(args.tab)
    events, unknown_events = [], []
    if not args.bad_dates_only:
        events, unknown_events = import_events(rows, layout, settings.get("event_aliases", {}), known_types)
    blocked, unknown_members = import_bad_dates(
        rows, layout, settings.get("member_aliases", {}), known_members, read_tab(args.tab, "FORMATTED_VALUE")
    )

    if unknown_events:
        raise SystemExit(
            "Unknown event labels in the sheet: "
            + ", ".join(sorted(set(unknown_events)))
            + f"\nAdd them to {IMPORT_CONFIG} (event_aliases) or config/event_types.yaml."
        )
    if unknown_members:
        raise SystemExit(
            "Unknown member names in the bad dates block: "
            + ", ".join(sorted(set(unknown_members)))
            + f"\nAdd them to {IMPORT_CONFIG} (member_aliases) or data/team.yaml."
        )

    print(f"Events found in '{args.tab}':")
    for line in events:
        print(f"  {line}")
    print(f"Bad dates found in '{args.tab}':")
    for member in sorted(blocked):
        print(f"  {member}: " + ", ".join(d.strftime(DATE_FORMAT) for d in sorted(blocked[member])))

    if not args.write:
        print("\nPreview only. Re-run with --write to apply.")
        return

    added = merge_events(events)
    print(f"\nAdded {len(added)} event line(s) to data/events.md")

    current = parse_bad_dates()
    for member, dates in blocked.items():
        current.setdefault(member, set()).update(dates)
    write_bad_dates(current)
    print(f"Updated data/bad_dates.md for {len(blocked)} member(s)")

    sync_universal_scheduler_if_needed()
    print("Synced UNIVERSAL_SCHEDULER.md. Run scripts/generate_schedule.py next.")


if __name__ == "__main__":
    main()
