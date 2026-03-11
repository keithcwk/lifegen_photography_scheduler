import csv
import calendar
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from universal_scheduler import UniversalSchedulerValidationError, sync_universal_scheduler_if_needed

BASE = Path(__file__).resolve().parents[1]
TEAM_PATH = BASE / "data/team.yaml"
EVENTS_PATH = BASE / "data/events.md"
EVENT_TYPES_PATH = BASE / "config/event_types.yaml"
RECURRING_EVENTS_PATH = BASE / "config/recurring_events.yaml"
BAD_DATES_PATH = BASE / "data/bad_dates.md"
SHEET_STYLES_PATH = BASE / "config/google_sheets_styles.yaml"
SHEET_LAYOUT_PATH = BASE / "config/google_sheets_layout.yaml"
OUTPUT_PATH = BASE / "output/schedule.csv"
STYLE_OUTPUT_PATH = BASE / "output/google_sheets_styles.yaml"

DATE_FORMAT = "%d %b %Y"
RISKY_REDS = {"Issac", "Aslvin"}
EVENT_LINE_PATTERN = re.compile(r"(\d{1,2} [A-Za-z]{3} \d{4}) - (.+)")


class SchedulingError(Exception):
    pass


def load_team():
    with open(TEAM_PATH) as f:
        return yaml.safe_load(f)


def load_event_types():
    with open(EVENT_TYPES_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data.get("events", {})


def load_recurring_events():
    with open(RECURRING_EVENTS_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data


def load_google_sheets_styles():
    with open(SHEET_STYLES_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data


def load_google_sheets_layout():
    with open(SHEET_LAYOUT_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data


def iter_active_lines(path, with_line_numbers=False):
    in_comment_block = False

    with open(path) as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()

            if in_comment_block:
                if "-->" in line:
                    in_comment_block = False
                continue

            if "<!--" in line:
                if "-->" not in line:
                    in_comment_block = True
                continue

            if with_line_numbers:
                yield line_number, line
            else:
                yield line


def parse_event_file():
    explicit_events = []
    exclusions = set()
    section = "events"

    for line_number, line in iter_active_lines(EVENTS_PATH, with_line_numbers=True):
        if not line:
            continue

        if line.startswith("#"):
            normalized_heading = line.lower().strip()
            if normalized_heading == "## exclusions":
                section = "exclusions"
            elif normalized_heading == "## events":
                section = "events"
            continue

        match = EVENT_LINE_PATTERN.fullmatch(line)
        if not match:
            continue

        date_str, event_name = match.groups()
        event_date = datetime.strptime(date_str, DATE_FORMAT)
        normalized_event = {"date": event_date, "event": event_name.strip()}

        if section == "exclusions":
            exclusions.add((normalized_event["date"].date(), normalized_event["event"]))
        else:
            explicit_events.append(normalized_event)

    return explicit_events, exclusions


def parse_events():
    events, exclusions = parse_event_file()

    recurring_config = load_recurring_events()
    recurring_events = build_recurring_events(events, recurring_config)

    deduped = {}
    for event in [*events, *recurring_events]:
        if (event["date"].date(), event["event"]) in exclusions:
            continue
        deduped[(event["date"].date(), event["event"])] = event

    normalized_events = sorted(deduped.values(), key=lambda event: event["date"])
    replacement_dates = {
        event["date"].date()
        for event in normalized_events
        if event["event"] != "Sunday Service"
        and event["date"].weekday() == calendar.SUNDAY
    }
    if not replacement_dates:
        return normalized_events

    return [
        event
        for event in normalized_events
        if not (
            event["event"] == "Sunday Service"
            and event["date"].date() in replacement_dates
        )
    ]


def quarter_key(date_value):
    quarter = ((date_value.month - 1) // 3) + 1
    return f"{date_value.year} Q{quarter}"


def normalize_quarter(label):
    label = label.strip()
    patterns = (
        r"(?i)^(\d{4})\s+Q([1-4])$",
        r"(?i)^Q([1-4])\s+(\d{4})$",
    )

    for pattern in patterns:
        match = re.match(pattern, label)
        if not match:
            continue

        if pattern.startswith("(?i)^(\\d{4})"):
            year, quarter = match.groups()
        else:
            quarter, year = match.groups()
        return f"{int(year)} Q{int(quarter)}"

    raise ValueError(
        f"Invalid quarter heading '{label}'. Use '2026 Q2' or 'Q2 2026'."
    )


def parse_bad_dates():
    if not BAD_DATES_PATH.exists():
        return {}

    bad_dates = defaultdict(set)
    current_quarter = None
    current_member = None

    for line_number, line in iter_active_lines(BAD_DATES_PATH, with_line_numbers=True):
        if not line or line.startswith("# "):
            continue

        if line.startswith("## "):
            current_quarter = normalize_quarter(line[3:])
            current_member = None
            continue

        if line.startswith("### "):
            if current_quarter is None:
                raise ValueError(
                    f"{BAD_DATES_PATH}:{line_number} member heading appears before a quarter heading."
                )
            current_member = line[4:].strip()
            bad_dates.setdefault(current_member, set())
            continue

        if line.startswith("- "):
            if current_quarter is None or current_member is None:
                raise ValueError(
                    f"{BAD_DATES_PATH}:{line_number} date entry must be under a quarter and member heading."
                )

            blocked_date = datetime.strptime(line[2:].strip(), DATE_FORMAT).date()
            if quarter_key(blocked_date) != current_quarter:
                raise ValueError(
                    f"{BAD_DATES_PATH}:{line_number} date {blocked_date} does not belong to {current_quarter}."
                )

            bad_dates[current_member].add(blocked_date)
            continue

        if current_quarter is None and current_member is None:
            continue

        raise ValueError(
            f"{BAD_DATES_PATH}:{line_number} invalid line '{line}'. "
            f"Use quarter headings, member headings, and bullet dates."
        )

    return dict(bad_dates)


def month_span(events, months_after_last_explicit_event=0):
    if not events:
        return []

    start_year = events[0]["date"].year
    start_month = events[0]["date"].month
    end_year = events[-1]["date"].year
    end_month = events[-1]["date"].month

    for _ in range(months_after_last_explicit_event):
        if end_month == 12:
            end_year += 1
            end_month = 1
        else:
            end_month += 1

    months = []
    year = start_year
    month = start_month

    while (year, month) <= (end_year, end_month):
        months.append((year, month))
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return months


def nth_weekday_of_month(year, month, weekday_index, occurrence):
    month_calendar = calendar.monthcalendar(year, month)
    candidates = [
        week[weekday_index] for week in month_calendar if week[weekday_index] != 0
    ]

    if occurrence == "first":
        return candidates[0]
    if occurrence == "last":
        return candidates[-1]

    raise ValueError(f"Unsupported recurring occurrence: {occurrence}")


def build_recurring_events(base_events, recurring_config):
    recurring_rules = recurring_config.get("recurring_events", [])
    generation_window = recurring_config.get("generation_window", {})
    months_after_last_explicit_event = int(
        generation_window.get("months_after_last_explicit_event", 0)
    )

    if not base_events or not recurring_rules:
        return []

    weekday_map = {
        "monday": calendar.MONDAY,
        "tuesday": calendar.TUESDAY,
        "wednesday": calendar.WEDNESDAY,
        "thursday": calendar.THURSDAY,
        "friday": calendar.FRIDAY,
        "saturday": calendar.SATURDAY,
        "sunday": calendar.SUNDAY,
    }

    recurring_events = []
    start_date = base_events[0]["date"].date()
    end_year = base_events[-1]["date"].year
    end_month = base_events[-1]["date"].month
    for _ in range(months_after_last_explicit_event):
        if end_month == 12:
            end_year += 1
            end_month = 1
        else:
            end_month += 1
    end_date = datetime(
        end_year,
        end_month,
        calendar.monthrange(end_year, end_month)[1],
    ).date()

    for year, month in month_span(base_events, months_after_last_explicit_event):
        for rule in recurring_rules:
            frequency = str(rule.get("frequency", "")).lower()
            if frequency == "weekly":
                continue

            if frequency != "monthly":
                raise ValueError(
                    f"Unsupported recurring event frequency: {rule.get('frequency')}"
                )

            weekday_name = str(rule["weekday"]).lower()
            occurrence = str(rule["occurrence"]).lower()
            weekday_index = weekday_map.get(weekday_name)
            if weekday_index is None:
                raise ValueError(
                    f"Unsupported recurring event weekday: {rule['weekday']}"
                )

            day = nth_weekday_of_month(year, month, weekday_index, occurrence)
            recurring_events.append(
                {
                    "date": datetime(year, month, day),
                    "event": str(rule["event"]).strip(),
                }
            )

    current_date = start_date
    while current_date <= end_date:
        weekday_name = current_date.strftime("%A").lower()
        for rule in recurring_rules:
            if str(rule.get("frequency", "")).lower() != "weekly":
                continue

            if str(rule["weekday"]).lower() != weekday_name:
                continue

            recurring_events.append(
                {
                    "date": datetime.combine(current_date, datetime.min.time()),
                    "event": str(rule["event"]).strip(),
                }
            )
        current_date += timedelta(days=1)

    return recurring_events


def build_members(team):
    members = {}

    greens = team["greens"]
    if isinstance(greens, dict):
        legacy_greens = []
        for index, name in enumerate(greens.get("core", []), start=1):
            legacy_greens.append(
                {
                    "name": name,
                    "shoot_rank": index,
                    "direct_rank": index,
                    "editor_rank": index,
                }
            )
        offset = len(legacy_greens)
        for index, name in enumerate(greens.get("standard", []), start=1):
            rank = offset + index
            legacy_greens.append(
                {
                    "name": name,
                    "shoot_rank": rank,
                    "direct_rank": rank,
                    "editor_rank": rank,
                }
            )
        greens = legacy_greens

    for person in greens:
        name = person["name"]
        members[name] = {
            "name": name,
            "role": "green",
            "can_direct": True,
            "can_edit": True,
            "can_shoot": True,
            "shoot_rank": int(person.get("shoot_rank", 99)),
            "direct_rank": int(person.get("direct_rank", 99)),
            "editor_rank": int(person.get("editor_rank", 99)),
            "director_track": False,
            "leader": bool(person.get("leaders", person.get("leader", True))),
            "can_guide": bool(person.get("can_guide", True)),
        }

    for person in team["yellows"]:
        name = person["name"]
        members[name] = {
            "name": name,
            "role": "yellow",
            "can_direct": bool(person.get("director_track", False)),
            "can_edit": True,
            "can_shoot": True,
            "shoot_rank": int(person.get("shoot_rank", person.get("editor_rank", 99))),
            "direct_rank": int(person.get("direct_rank", 99)),
            "editor_rank": int(person.get("editor_rank", 99)),
            "director_track": bool(person.get("director_track", False)),
            "leader": bool(person.get("leaders", person.get("leader", False))),
            "can_guide": bool(person.get("can_guide", name == "Dan C")),
        }

    for person in team["reds"]:
        if isinstance(person, dict):
            name = person["name"]
            shoot_rank = int(person.get("shoot_rank", 999))
        else:
            name = str(person)
            shoot_rank = 999

        members[name] = {
            "name": name,
            "role": "red",
            "can_direct": False,
            "can_edit": False,
            "can_shoot": True,
            "shoot_rank": shoot_rank,
            "direct_rank": 999,
            "editor_rank": 999,
            "director_track": False,
            "leader": False,
            "can_guide": False,
        }

    return members


def validate_bad_dates(members, bad_dates):
    unknown_members = sorted(set(bad_dates) - set(members))
    if unknown_members:
        raise ValueError(
            "Unknown members in data/bad_dates.md: " + ", ".join(unknown_members)
        )


def validate_events(events, event_types):
    unknown_event_types = sorted(
        {event["event"] for event in events if event["event"] not in event_types}
    )
    if unknown_event_types:
        raise ValueError(
            "Unknown event types in data/events.md: " + ", ".join(unknown_event_types)
        )


def validate_hex_color(value, field_name):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError(
            f"Invalid color for {field_name}: {value!r}. Use hex like '#D9EAF4'."
        )


def validate_font_weight(value, field_name):
    valid_weights = {"normal", "bold"}
    if value not in valid_weights:
        raise ValueError(
            f"Invalid font weight for {field_name}: {value!r}. Use one of {sorted(valid_weights)}."
        )


def validate_boolean(value, field_name):
    if not isinstance(value, bool):
        raise ValueError(f"Invalid boolean for {field_name}: {value!r}.")


def validate_int(value, field_name, minimum=0):
    if not isinstance(value, int) or value < minimum:
        raise ValueError(
            f"Invalid integer for {field_name}: {value!r}. Must be >= {minimum}."
        )


def validate_google_sheets_styles(styles):
    required_sections = {
        "sheet",
        "pivot_column",
        "event_name",
        "date_column",
        "availability_row",
        "month_palette",
        "month_group_border",
        "column_separator",
        "header_divider",
        "alternating_rows",
        "borders",
    }
    missing_sections = sorted(required_sections - set(styles))
    if missing_sections:
        raise ValueError(
            "Missing sections in config/google_sheets_styles.yaml: "
            + ", ".join(missing_sections)
        )

    validate_boolean(styles["sheet"]["freeze_header_row"], "sheet.freeze_header_row")
    validate_int(styles["sheet"]["header_row_height"], "sheet.header_row_height", 1)
    if not isinstance(styles["sheet"]["font_family"], str) or not styles["sheet"]["font_family"].strip():
        raise ValueError("Invalid sheet.font_family in config/google_sheets_styles.yaml.")
    if styles["sheet"]["horizontal_alignment"] not in {"LEFT", "CENTER", "RIGHT"}:
        raise ValueError("Invalid sheet.horizontal_alignment in config/google_sheets_styles.yaml.")
    if styles["sheet"]["vertical_alignment"] not in {"TOP", "MIDDLE", "BOTTOM"}:
        raise ValueError("Invalid sheet.vertical_alignment in config/google_sheets_styles.yaml.")

    for section_name in ("pivot_column", "event_name", "date_column", "availability_row"):
        section = styles[section_name]
        validate_font_weight(section["font_weight"], f"{section_name}.font_weight")
        validate_hex_color(section["background_color"], f"{section_name}.background_color")
        validate_hex_color(section["text_color"], f"{section_name}.text_color")
    if styles["event_name"].get("wrap_strategy") not in {"OVERFLOW_CELL", "LEGACY_WRAP", "CLIP", "WRAP"}:
        raise ValueError("Invalid event_name.wrap_strategy in config/google_sheets_styles.yaml.")

    month_palette = styles["month_palette"]
    palette_colors = month_palette.get("colors", [])
    if not isinstance(palette_colors, list) or not palette_colors:
        raise ValueError("month_palette.colors must be a non-empty list.")
    for index, color in enumerate(palette_colors):
        validate_hex_color(color, f"month_palette.colors[{index}]")

    month_group_border = styles["month_group_border"]
    validate_boolean(month_group_border["enabled"], "month_group_border.enabled")
    validate_hex_color(month_group_border["color"], "month_group_border.color")
    if month_group_border["style"] not in {"SOLID", "SOLID_MEDIUM", "SOLID_THICK"}:
        raise ValueError("Invalid month_group_border.style in config/google_sheets_styles.yaml.")

    column_separator = styles["column_separator"]
    validate_boolean(column_separator["enabled"], "column_separator.enabled")
    validate_hex_color(column_separator["color"], "column_separator.color")
    if column_separator["style"] not in {"SOLID", "SOLID_MEDIUM", "SOLID_THICK"}:
        raise ValueError("Invalid column_separator.style in config/google_sheets_styles.yaml.")

    header_divider = styles["header_divider"]
    validate_boolean(header_divider["enabled"], "header_divider.enabled")
    validate_hex_color(header_divider["color"], "header_divider.color")
    if header_divider["style"] not in {"SOLID", "SOLID_MEDIUM", "SOLID_THICK"}:
        raise ValueError("Invalid header_divider.style in config/google_sheets_styles.yaml.")

    alternating_rows = styles["alternating_rows"]
    validate_boolean(alternating_rows["enabled"], "alternating_rows.enabled")
    validate_hex_color(
        alternating_rows["odd_row_background"],
        "alternating_rows.odd_row_background",
    )
    validate_hex_color(
        alternating_rows["even_row_background"],
        "alternating_rows.even_row_background",
    )

    borders = styles["borders"]
    validate_boolean(borders["enabled"], "borders.enabled")
    validate_hex_color(borders["color"], "borders.color")


def validate_google_sheets_layout(layout):
    sheet_layout = layout.get("sheet_layout")
    if not sheet_layout:
        raise ValueError("Missing 'sheet_layout' in config/google_sheets_layout.yaml.")

    canonical = sheet_layout.get("canonical_scheduler_format", {})
    columns = canonical.get("columns")
    if not columns:
        raise ValueError(
            "Missing canonical_scheduler_format.columns in config/google_sheets_layout.yaml."
        )

    required_columns = {
        "event",
        "date",
        "director",
        "assist",
        "photographer_1",
        "photographer_2",
        "photographer_3",
        "photographer_4",
        "photographer_5",
        "floor_runner",
        "sde_1",
        "sde_2",
    }
    missing_columns = sorted(required_columns - set(columns))
    if missing_columns:
        raise ValueError(
            "Missing canonical scheduler columns in config/google_sheets_layout.yaml: "
            + ", ".join(missing_columns)
        )


def write_styles_manifest(styles):
    STYLE_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STYLE_OUTPUT_PATH, "w") as f:
        yaml.safe_dump(styles, f, sort_keys=False)


def photographer_display_rank(name, members):
    member = members[name]
    role_priority = {"green": 0, "yellow": 1, "red": 2}

    if member["role"] == "green":
        return (role_priority["green"], member["shoot_rank"], name)
    if member["role"] == "yellow":
        return (role_priority["yellow"], member["shoot_rank"], name)
    return (role_priority["red"], member["shoot_rank"], name)


def sort_photographers_for_display(photographers, members):
    return sorted(photographers, key=lambda name: photographer_display_rank(name, members))


def guide_display_rank(name, members):
    member = members[name]
    return (0 if member["role"] == "green" else 1, member["shoot_rank"], name)


def format_photographer_slots(photographers, members):
    ordered_photographers = sort_photographers_for_display(photographers, members)
    risky_names = [name for name in ordered_photographers if name in RISKY_REDS]
    if not risky_names:
        return ordered_photographers

    formatted = []
    hidden_guides = set()

    for risky_name in risky_names:
        guide_candidates = [
            name
            for name in ordered_photographers
            if name != risky_name and name not in hidden_guides and is_safety_anchor(name, members)
        ]
        if not guide_candidates:
            continue
        chosen_guide = min(guide_candidates, key=lambda name: guide_display_rank(name, members))
        hidden_guides.add(chosen_guide)

    for name in ordered_photographers:
        if name in hidden_guides:
            continue
        if name in RISKY_REDS:
            paired_guides = [
                guide_name
                for guide_name in ordered_photographers
                if guide_name in hidden_guides and guide_name != name and is_safety_anchor(guide_name, members)
            ]
            if paired_guides:
                formatted.append(f"{name} + {paired_guides[0]}")
                continue
        formatted.append(name)

    return formatted


def visible_photographer_slot_count(photographers, members):
    return len(format_photographer_slots(photographers, members))


def editor_display_rank(name, members):
    member = members[name]
    role_priority = {"green": 0, "yellow": 1, "red": 2}
    return (member["editor_rank"], role_priority[member["role"]], name)


def sort_editors_for_display(editors, members):
    return sorted(editors, key=lambda name: editor_display_rank(name, members))


def build_output_row(event, director, assist, editors, photographers, fieldnames, members):
    row = {field: "" for field in fieldnames}
    row["event"] = event["event"]
    row["date"] = event["date"].strftime("%Y-%m-%d")
    row["director"] = director
    row["assist"] = assist

    formatted_photographers = format_photographer_slots(photographers, members)
    for index, photographer in enumerate(formatted_photographers[:5], start=1):
        row[f"photographer_{index}"] = photographer

    ordered_editors = sort_editors_for_display(editors, members)
    for index, editor in enumerate(ordered_editors[:2], start=1):
        row[f"sde_{index}"] = editor

    return row


def month_key(event_date):
    return event_date.year, event_date.month


def is_available(name, event_date, bad_dates):
    return event_date.date() not in bad_dates.get(name, set())


def init_stats(members):
    return {
        name: {
            "total_events": 0,
            "monthly_events": defaultdict(int),
            "high_tier_events": 0,
            "monthly_high_tier_events": defaultdict(int),
            "high_tier_role_counts": defaultdict(int),
            "monthly_high_tier_role_counts": defaultdict(lambda: defaultdict(int)),
            "role_counts": defaultdict(int),
            "monthly_role_counts": defaultdict(lambda: defaultdict(int)),
            "monthly_event_role_counts": defaultdict(lambda: defaultdict(lambda: defaultdict(int))),
            "quarterly_event_role_counts": defaultdict(lambda: defaultdict(lambda: defaultdict(int))),
            "last_assigned": None,
            "last_high_tier_assigned": None,
            "last_high_tier_role_assigned": {},
        }
        for name in members
    }


def fairness_penalty(stats, name, event_date, tier):
    person_stats = stats[name]
    penalty = person_stats["total_events"] * 12
    penalty += person_stats["monthly_events"][month_key(event_date)] * 18

    last_assigned = person_stats["last_assigned"]
    if last_assigned is None:
        penalty -= 6
    else:
        gap = (event_date.date() - last_assigned).days
        if gap < 7:
            penalty += 12 if tier == "high" else 30
        elif gap < 14:
            penalty += 4 if tier == "high" else 20
        elif gap < 21:
            penalty += 2 if tier == "high" else 5

    return penalty


def role_count_penalty(stats, name, role):
    return stats[name]["role_counts"][role] * 6


def repeated_event_role_penalty(stats, name, event_name, role, event_date):
    quarter = quarter_key(event_date.date())
    repeats = stats[name]["quarterly_event_role_counts"][quarter][event_name][role]
    if repeats == 0:
        return 0

    if event_name in {"Creative Team Meet", "Lifegen Prayer"}:
        return repeats * 45
    if event_name == "Leaders Meet":
        return repeats * 30
    return repeats * 12


def monthly_event_role_count(stats, name, event_name, role, event_date):
    return stats[name]["monthly_event_role_counts"][month_key(event_date)][event_name][role]


def monthly_role_count(stats, name, role, event_date):
    return stats[name]["monthly_role_counts"][month_key(event_date)][role]


def is_safety_anchor(name, members):
    return members[name].get("can_guide", False)


def has_safety_anchor(names, members):
    return any(is_safety_anchor(name, members) for name in names)


def role_counts(names, members):
    counts = {"green": 0, "yellow": 0, "red": 0}
    for name in names:
        counts[members[name]["role"]] += 1
    return counts


def is_service_event(event_name):
    return "service" in event_name.lower()


def choose_best_candidate(candidate_names, score_fn, failure_message):
    scored_candidates = []

    for name in candidate_names:
        score = score_fn(name)
        if score is None:
            continue
        scored_candidates.append((score, name))

    if not scored_candidates:
        raise SchedulingError(failure_message)

    scored_candidates.sort()
    return scored_candidates[0][1]


def available_names(members, bad_dates, event_date, used):
    return [
        name
        for name in members
        if name not in used and is_available(name, event_date, bad_dates)
    ]


def high_tier_shoot_strength_penalty(member, weight_by_role):
    weight = weight_by_role.get(member["role"])
    if weight is None:
        return 0
    return member["shoot_rank"] * weight


def high_tier_rank_spread_penalty(candidate_name, selected_photographers, members):
    if not selected_photographers:
        return 0

    existing_ranks = [members[name]["shoot_rank"] for name in selected_photographers]
    candidate_rank = members[candidate_name]["shoot_rank"]
    projected_min = min(*existing_ranks, candidate_rank)
    projected_max = max(*existing_ranks, candidate_rank)
    projected_spread = projected_max - projected_min
    average_rank = sum(existing_ranks) / len(existing_ranks)

    penalty = max(0, projected_spread - 4) * 35
    penalty += int(abs(candidate_rank - average_rank) * 8)
    return penalty


def high_tier_rotation_penalty(stats, name, event_date, role):
    person_stats = stats[name]
    penalty = person_stats["high_tier_events"] * 18
    penalty += person_stats["monthly_high_tier_events"][month_key(event_date)] * 28
    penalty += person_stats["high_tier_role_counts"][role] * 10
    penalty += (
        person_stats["monthly_high_tier_role_counts"][month_key(event_date)][role] * 18
    )

    last_high_tier = person_stats["last_high_tier_assigned"]
    if last_high_tier is not None:
        gap = (event_date.date() - last_high_tier).days
        if gap < 3:
            penalty += 45
        elif gap < 8:
            penalty += 24

    last_same_role = person_stats["last_high_tier_role_assigned"].get(role)
    if last_same_role is not None:
        gap = (event_date.date() - last_same_role).days
        if gap < 3:
            penalty += 65
        elif gap < 8:
            penalty += 32

    return penalty


def director_score(name, members, stats, event_name, event_date, tier):
    member = members[name]
    if not member["can_direct"]:
        return None

    if event_name == "Leaders Meet" and not member.get("leader", False):
        return None

    if tier == "high" and member["role"] != "green":
        return None

    score = fairness_penalty(stats, name, event_date, tier)
    score += role_count_penalty(stats, name, "director")
    score += repeated_event_role_penalty(stats, name, event_name, "director", event_date)
    if tier == "high":
        score += high_tier_rotation_penalty(stats, name, event_date, "director")

    if member["role"] == "green":
        if tier == "high":
            score += high_tier_shoot_strength_penalty(
                member,
                {"green": 2},
            )
            score -= max(0, 14 - (member["direct_rank"] * 2))
        elif tier == "low":
            score += 10
    elif member["director_track"]:
        if monthly_role_count(stats, name, "director", event_date) >= 1:
            return None
        if tier == "low":
            score -= 18
        else:
            score += 35
    else:
        return None

    return score


def assist_score(name, members, stats, event_name, event_date, tier="standard"):
    member = members[name]
    if member["role"] != "green":
        return None
    if event_name == "Leaders Meet" and not member.get("leader", False):
        return None

    score = fairness_penalty(stats, name, event_date, tier)
    score += repeated_event_role_penalty(stats, name, event_name, "assist", event_date)
    score += role_count_penalty(stats, name, "assist")
    score += monthly_role_count(stats, name, "assist", event_date) * 8
    if tier == "high":
        score += high_tier_rotation_penalty(stats, name, event_date, "assist")
        score += high_tier_shoot_strength_penalty(
            member,
            {"green": 3},
        )
    score -= max(0, 14 - (member["direct_rank"] * 2))
    return score


def editor_score(name, members, stats, event_name, event_date, tier, director_name):
    member = members[name]
    if not member["can_edit"]:
        return None
    if event_name == "Leaders Meet" and not member.get("leader", False):
        return None

    score = fairness_penalty(stats, name, event_date, tier)
    score += role_count_penalty(stats, name, "editor")
    score += repeated_event_role_penalty(stats, name, event_name, "editor", event_date)

    if member["role"] == "yellow":
        if tier == "high":
            score += high_tier_rotation_penalty(stats, name, event_date, "editor")
            score += member["editor_rank"] * 14
            if member["editor_rank"] > 4:
                score += (member["editor_rank"] - 4) * 24
        else:
            rank_weight = {"standard": 3, "low": 1}.get(tier, 3)
            score += member["editor_rank"] * rank_weight
    elif member["role"] == "green":
        if tier == "high":
            score += high_tier_rotation_penalty(stats, name, event_date, "editor")
            score += member["editor_rank"] * 10
            if member["editor_rank"] > 4:
                score += (member["editor_rank"] - 4) * 18
        else:
            score += {"standard": 10, "low": 16}.get(tier, 10)
            score += member["editor_rank"] * {"standard": 3, "low": 4}.get(
                tier, 3
            )
    else:
        return None

    if name == director_name:
        score += 40

    return score


def is_strong_editor(name, members):
    return members[name]["editor_rank"] <= 4


def is_lower_tier_editor(name, members):
    return members[name]["editor_rank"] >= 5


def is_strong_sunday_photographer(name, members):
    member = members[name]
    return member["role"] != "red" and member["shoot_rank"] <= 8


def is_development_heavy_sunday_photographer(name, members):
    member = members[name]
    return member["role"] == "red" or (
        member["role"] == "yellow" and member["shoot_rank"] >= 9
    )


def sunday_strength_metrics(photographers, members):
    strong_count = sum(
        1 for name in photographers if is_strong_sunday_photographer(name, members)
    )
    development_heavy_count = sum(
        1
        for name in photographers
        if is_development_heavy_sunday_photographer(name, members)
    )
    return strong_count, development_heavy_count


def photographer_score(name, members, stats, event_name, event_date, tier):
    member = members[name]
    if not member["can_shoot"]:
        return None
    if event_name == "Leaders Meet" and not member.get("leader", False):
        return None
    if member["role"] == "red" and stats[name]["monthly_events"][month_key(event_date)] >= 2:
        return None

    score = fairness_penalty(stats, name, event_date, tier)
    if monthly_role_count(stats, name, "photographer", event_date) >= 2:
        score += 140
    score += role_count_penalty(stats, name, "photographer")
    score += repeated_event_role_penalty(stats, name, event_name, "photographer", event_date)

    if tier == "high":
        score += high_tier_rotation_penalty(stats, name, event_date, "photographer")
        if member["role"] == "green":
            score += high_tier_shoot_strength_penalty(
                member,
                {"green": 5},
            )
            score -= 24
        elif member["role"] == "yellow":
            score += high_tier_shoot_strength_penalty(
                member,
                {"yellow": 6},
            )
            score += member["editor_rank"]
        else:
            score += 40
    elif tier == "low":
        if event_name == "Leaders Meet":
            if member["role"] == "green":
                score += member["shoot_rank"]
            elif member["role"] == "yellow":
                score += member["editor_rank"]
            else:
                return None
        elif member["role"] == "green":
            score += 20
        elif member["role"] == "yellow":
            score += 6 + (member["editor_rank"] // 2)
        else:
            score -= 4
    else:
        if member["role"] == "green":
            score += 8
        elif member["role"] == "yellow":
            score += member["editor_rank"]
        else:
            score += 16

    if event_name == "Sunday Service":
        sunday_count = monthly_event_role_count(stats, name, event_name, "photographer", event_date)
        if sunday_count == 0:
            score -= 35
        else:
            score += sunday_count * 45

    return score


def pick_director(event, members, stats, bad_dates):
    tier = event["requirements"]["tier"]
    candidates = available_names(members, bad_dates, event["date"], used=set())

    return choose_best_candidate(
        candidates,
        lambda name: director_score(name, members, stats, event["event"], event["date"], tier),
        f"Could not find an available director for {event['date'].strftime('%Y-%m-%d')} {event['event']}.",
    )


def pick_assist(event, members, stats, bad_dates, director_name, used):
    if not members[director_name]["director_track"]:
        return ""

    candidates = available_names(members, bad_dates, event["date"], used)
    return choose_best_candidate(
        candidates,
        lambda name: assist_score(name, members, stats, event["event"], event["date"], event["requirements"]["tier"]),
        (
            f"Could not find a green assist for trainee director "
            f"{director_name} on {event['date'].strftime('%Y-%m-%d')} {event['event']}."
        ),
    )


def pick_editors(event, members, stats, bad_dates, director_name, used):
    required = event["requirements"]["editors"]
    if required == 0:
        return []

    tier = event["requirements"]["tier"]
    editors = []

    def candidate_score(name):
        return editor_score(name, members, stats, event["event"], event["date"], tier, director_name)

    unused_candidates = available_names(members, bad_dates, event["date"], used)
    if required >= 2 and tier != "high":
        strong_candidates = [
            name
            for name in unused_candidates
            if members[name]["can_edit"] and is_strong_editor(name, members)
        ]
        lower_tier_candidates = [
            name
            for name in unused_candidates
            if members[name]["can_edit"] and is_lower_tier_editor(name, members)
        ]

        if not strong_candidates:
            raise SchedulingError(
                f"Could not find a stronger editor for {event['date'].strftime('%Y-%m-%d')} {event['event']}."
            )
        if not lower_tier_candidates:
            raise SchedulingError(
                f"Could not find a lower-tier editor for {event['date'].strftime('%Y-%m-%d')} {event['event']}."
            )

        strong_editor = choose_best_candidate(
            strong_candidates,
            candidate_score,
            f"Could not find a stronger editor for {event['date'].strftime('%Y-%m-%d')} {event['event']}.",
        )
        editors.append(strong_editor)

        lower_tier_editor = choose_best_candidate(
            [name for name in lower_tier_candidates if name != strong_editor],
            candidate_score,
            f"Could not find a lower-tier editor for {event['date'].strftime('%Y-%m-%d')} {event['event']}.",
        )
        editors.append(lower_tier_editor)

        return editors

    if tier == "high":
        strong_unused_candidates = [
            name
            for name in unused_candidates
            if members[name]["can_edit"] and members[name]["editor_rank"] <= 4
        ]
        if len(strong_unused_candidates) >= required:
            unused_candidates = strong_unused_candidates

    while len(editors) < required:
        remaining_candidates = [name for name in unused_candidates if name not in editors]
        if not remaining_candidates:
            break

        chosen = choose_best_candidate(
            remaining_candidates,
            candidate_score,
            f"Could not find enough editors for {event['date'].strftime('%Y-%m-%d')} {event['event']}.",
        )
        editors.append(chosen)

    if len(editors) == required:
        return editors

    fallback_candidates = [
        name
        for name in members
        if name not in editors and is_available(name, event["date"], bad_dates)
    ]
    if tier == "high":
        strong_fallback_candidates = [
            name
            for name in fallback_candidates
            if members[name]["can_edit"] and members[name]["editor_rank"] <= 4
        ]
        if len(strong_fallback_candidates) >= required - len(editors):
            fallback_candidates = strong_fallback_candidates

    while len(editors) < required:
        remaining_candidates = [name for name in fallback_candidates if name not in editors]
        chosen = choose_best_candidate(
            remaining_candidates,
            candidate_score,
            f"Could not fill the editor slots for {event['date'].strftime('%Y-%m-%d')} {event['event']}.",
        )
        editors.append(chosen)

    return editors


def choose_required_photographer(candidate_names, members, stats, event_name, event_date, tier, label):
    return choose_best_candidate(
        candidate_names,
        lambda name: photographer_score(name, members, stats, event_name, event_date, tier),
        f"Could not find {label} for {event_date.strftime('%Y-%m-%d')}.",
    )


def pick_photographers(event, members, stats, bad_dates, director_name, assist, used):
    required = event["requirements"]["photographers"]
    if required == 0:
        return []

    tier = event["requirements"]["tier"]
    photographers = []
    event_name = event["event"]
    current_team = list(used)
    current_role_counts = role_counts(current_team, members)
    minimum_green_photographers = 0
    minimum_yellow_photographers = 0
    minimum_red_photographers = 0
    max_red_photographers = required
    target_green_photographers = 0
    target_yellow_photographers = 0
    target_strong_sunday_photographers = 0
    preferred_max_development_heavy_sunday_photographers = required
    preferred_max_green_photographers = required

    if tier == "high":
        minimum_green_photographers = max(minimum_green_photographers, min(2, required))
        target_green_photographers = min(2, required)
        target_yellow_photographers = min(2, max(0, required - target_green_photographers))
    elif tier == "standard" and required > 0:
        minimum_green_photographers = 1

    if event_name == "Sunday Service":
        minimum_yellow_photographers = max(0, 1 - current_role_counts["yellow"])
        minimum_red_photographers = max(0, 1 - current_role_counts["red"])
        target_strong_sunday_photographers = min(2, required)
        preferred_max_development_heavy_sunday_photographers = 2
        preferred_max_green_photographers = 1

    if is_service_event(event_name):
        max_red_photographers = max(0, 2 - current_role_counts["red"])

    def available_shooters():
        return [
            name
            for name in members
            if name not in used
            and name not in photographers
            and is_available(name, event["date"], bad_dates)
            and members[name]["can_shoot"]
        ]

    def can_add_photographer(name):
        if name in RISKY_REDS and any(existing in RISKY_REDS for existing in photographers):
            return False

        current_with_candidate = [*photographers, name]
        remaining_slots_after_choice = required - len(current_with_candidate)
        anchor_present = has_safety_anchor(current_with_candidate, members)
        anchor_available_after_choice = any(
            is_safety_anchor(candidate_name, members)
            for candidate_name in available_shooters()
            if candidate_name != name
        )
        if name in RISKY_REDS and not anchor_present:
            if remaining_slots_after_choice == 0 or not anchor_available_after_choice:
                return False

        return True

    if tier == "high" and required > 0 and minimum_green_photographers == 0:
        green_candidates = [
            name for name in available_shooters() if members[name]["role"] == "green" and can_add_photographer(name)
        ]
        if green_candidates:
            photographers.append(
                choose_required_photographer(
                    green_candidates,
                    members,
                    stats,
                    event["event"],
                    event["date"],
                    tier,
                    "a green photographer",
                )
            )

    while minimum_green_photographers > 0 and len(photographers) < required:
        green_candidates = [
            name for name in available_shooters() if members[name]["role"] == "green" and can_add_photographer(name)
        ]
        chosen = choose_required_photographer(
            green_candidates,
            members,
            stats,
            event["event"],
            event["date"],
            tier,
            "a required green photographer",
        )
        photographers.append(chosen)
        minimum_green_photographers -= 1

    while minimum_yellow_photographers > 0 and len(photographers) < required:
        yellow_candidates = [
            name for name in available_shooters() if members[name]["role"] == "yellow" and can_add_photographer(name)
        ]
        chosen = choose_required_photographer(
            yellow_candidates,
            members,
            stats,
            event["event"],
            event["date"],
            tier,
            "a required yellow photographer",
        )
        photographers.append(chosen)
        minimum_yellow_photographers -= 1

    while minimum_red_photographers > 0 and len(photographers) < required:
        red_candidates = [
            name for name in available_shooters() if members[name]["role"] == "red" and can_add_photographer(name)
        ]
        chosen = choose_required_photographer(
            red_candidates,
            members,
            stats,
            event["event"],
            event["date"],
            tier,
            "a required red photographer",
        )
        photographers.append(chosen)
        minimum_red_photographers -= 1

    while (
        event_name == "Sunday Service"
        and len(photographers) < required
        and sum(
            1 for name in photographers if is_strong_sunday_photographer(name, members)
        ) < target_strong_sunday_photographers
    ):
        strong_candidates = [
            name
            for name in available_shooters()
            if is_strong_sunday_photographer(name, members) and can_add_photographer(name)
        ]
        if not strong_candidates:
            break

        photographers.append(
            choose_required_photographer(
                strong_candidates,
                members,
                stats,
                event["event"],
                event["date"],
                tier,
                "a stronger Sunday photographer",
            )
        )

    while (
        tier == "high"
        and len(photographers) < required
        and role_counts(photographers, members)["green"] < target_green_photographers
    ):
        green_candidates = [
            name for name in available_shooters() if members[name]["role"] == "green" and can_add_photographer(name)
        ]
        if not green_candidates:
            break

        photographers.append(
            choose_required_photographer(
                green_candidates,
                members,
                stats,
                event["event"],
                event["date"],
                tier,
                "an ideal green photographer for a high tier event",
            )
        )

    while (
        tier == "high"
        and len(photographers) < required
        and role_counts(photographers, members)["yellow"] < target_yellow_photographers
    ):
        yellow_candidates = [
            name
            for name in available_shooters()
            if members[name]["role"] == "yellow" and can_add_photographer(name)
        ]
        if not yellow_candidates:
            break

        photographers.append(
            choose_required_photographer(
                yellow_candidates,
                members,
                stats,
                event["event"],
                event["date"],
                tier,
                "a strong yellow photographer for a high tier event",
            )
        )

    if (
        members[director_name]["role"] != "green"
        and director_name != "Dan C"
        and not assist
        and len(photographers) < required
    ):
        anchor_candidates = [
            name for name in available_shooters() if is_safety_anchor(name, members) and can_add_photographer(name)
        ]
        if anchor_candidates:
            photographers.append(
                choose_required_photographer(
                    anchor_candidates,
                    members,
                    stats,
                    event["event"],
                    event["date"],
                    tier,
                    "a support anchor for a trainee director",
                )
            )

    while len(photographers) < required:
        current_reds = current_role_counts["red"] + role_counts(photographers, members)["red"]
        current_green_photographers = role_counts(photographers, members)["green"]
        current_strong_sunday_photographers = sum(
            1 for existing_name in photographers if is_strong_sunday_photographer(existing_name, members)
        )
        current_development_heavy_sunday_photographers = sum(
            1
            for existing_name in photographers
            if is_development_heavy_sunday_photographer(existing_name, members)
        )

        def candidate_score(name):
            if members[name]["role"] == "red" and current_reds >= max_red_photographers:
                return None
            if name in RISKY_REDS and any(existing in RISKY_REDS for existing in photographers):
                return None

            current_with_candidate = [*photographers, name]
            remaining_slots_after_choice = required - len(current_with_candidate)
            anchor_present = has_safety_anchor(current_with_candidate, members)
            anchor_available_after_choice = any(
                is_safety_anchor(candidate_name, members)
                for candidate_name in available_shooters()
                if candidate_name != name
            )
            if name in RISKY_REDS and not anchor_present:
                if remaining_slots_after_choice == 0 or not anchor_available_after_choice:
                    return None

            score = photographer_score(name, members, stats, event["event"], event["date"], tier)
            if score is None:
                return None
            if (
                event_name == "Sunday Service"
                and members[name]["role"] == "green"
                and current_green_photographers >= preferred_max_green_photographers
            ):
                score += 60
            if (
                event_name == "Sunday Service"
                and is_development_heavy_sunday_photographer(name, members)
                and current_development_heavy_sunday_photographers
                >= preferred_max_development_heavy_sunday_photographers
            ):
                score += 160
            if (
                event_name == "Sunday Service"
                and current_strong_sunday_photographers < target_strong_sunday_photographers
                and not is_strong_sunday_photographer(name, members)
            ):
                score += 120
            if tier == "low" and name in RISKY_REDS:
                score += 80
            if name in RISKY_REDS and not anchor_present:
                score += 40
            if tier == "high":
                score += high_tier_rank_spread_penalty(
                    name,
                    photographers,
                    members,
                )
            return score

        candidate_pool = [name for name in available_shooters() if can_add_photographer(name)]
        if tier == "high":
            non_red_candidates = [
                name for name in candidate_pool if members[name]["role"] != "red"
            ]
            if non_red_candidates:
                candidate_pool = non_red_candidates
        if (
            event_name == "Sunday Service"
            and current_green_photographers >= preferred_max_green_photographers
            and current_strong_sunday_photographers >= target_strong_sunday_photographers
            and current_development_heavy_sunday_photographers
            < preferred_max_development_heavy_sunday_photographers
        ):
            non_green_candidates = [
                name for name in candidate_pool if members[name]["role"] != "green"
            ]
            if non_green_candidates:
                candidate_pool = non_green_candidates
        if (
            event_name == "Sunday Service"
            and current_strong_sunday_photographers < target_strong_sunday_photographers
        ):
            strong_candidates = [
                name for name in candidate_pool if is_strong_sunday_photographer(name, members)
            ]
            if strong_candidates:
                candidate_pool = strong_candidates
        elif (
            event_name == "Sunday Service"
            and current_development_heavy_sunday_photographers
            >= preferred_max_development_heavy_sunday_photographers
        ):
            non_development_candidates = [
                name
                for name in candidate_pool
                if not is_development_heavy_sunday_photographer(name, members)
            ]
            if non_development_candidates:
                candidate_pool = non_development_candidates
        elif tier == "low" and event_name != "Leaders Meet":
            non_green_candidates = [
                name for name in candidate_pool if members[name]["role"] != "green"
            ]
            if non_green_candidates:
                candidate_pool = non_green_candidates

        chosen = choose_best_candidate(
            candidate_pool,
            candidate_score,
            f"Could not find enough photographers for {event['date'].strftime('%Y-%m-%d')} {event['event']}.",
        )
        photographers.append(chosen)

    photographers = enforce_safety_rule(
        event,
        members,
        stats,
        bad_dates,
        director_name,
        used,
        photographers,
    )

    if event_name == "Sunday Service":
        photographers = rebalance_sunday_photographers(
            event,
            members,
            stats,
            bad_dates,
            used,
            photographers,
        )

    while visible_photographer_slot_count(photographers, members) < required:
        current_reds = current_role_counts["red"] + role_counts(photographers, members)["red"]
        current_green_photographers = role_counts(photographers, members)["green"]

        def supplemental_candidate_score(name):
            if name in photographers or name in used:
                return None
            if not is_available(name, event["date"], bad_dates):
                return None
            if not members[name]["can_shoot"]:
                return None
            if members[name]["role"] == "red" and current_reds >= max_red_photographers:
                return None
            if name in RISKY_REDS and any(existing in RISKY_REDS for existing in photographers):
                return None

            projected_photographers = [*photographers, name]
            anchor_present = has_safety_anchor(projected_photographers, members)
            if name in RISKY_REDS and not anchor_present:
                return None

            score = photographer_score(
                name,
                members,
                stats,
                event["event"],
                event["date"],
                tier,
            )
            if score is None:
                return None
            if (
                event_name == "Sunday Service"
                and members[name]["role"] == "green"
                and current_green_photographers >= preferred_max_green_photographers
            ):
                score += 60
            if tier == "high":
                score += high_tier_rank_spread_penalty(
                    name,
                    photographers,
                    members,
                )
            return score

        supplemental_pool = [
            name
            for name in members
            if name not in photographers and name not in used
        ]
        if tier == "high":
            non_red_candidates = [
                name for name in supplemental_pool if members[name]["role"] != "red"
            ]
            if non_red_candidates:
                supplemental_pool = non_red_candidates

        chosen = choose_best_candidate(
            supplemental_pool,
            supplemental_candidate_score,
            (
                f"Could not fill the visible photographer slots for "
                f"{event['date'].strftime('%Y-%m-%d')} {event['event']}."
            ),
        )
        photographers.append(chosen)

    if event_name == "Sunday Service":
        photographers = rebalance_sunday_photographers(
            event,
            members,
            stats,
            bad_dates,
            used,
            photographers,
        )

    validate_team_composition(event, members, director_name, used, assist, photographers)
    return photographers


def can_use_sunday_photographer_lineup(event, members, used, photographers):
    assigned_names = [*used, *photographers]
    counts = role_counts(assigned_names, members)
    photographer_counts = role_counts(photographers, members)

    if any(counts[role] < 1 for role in ("green", "yellow", "red")):
        return False
    if photographer_counts["green"] < 1:
        return False
    if is_service_event(event["event"]) and counts["red"] > 2:
        return False
    if len(RISKY_REDS.intersection(photographers)) > 1:
        return False
    if RISKY_REDS.intersection(photographers) and not has_safety_anchor(photographers, members):
        return False
    return True


def rebalance_sunday_photographers(event, members, stats, bad_dates, used, photographers):
    while True:
        strong_count, development_heavy_count = sunday_strength_metrics(photographers, members)
        needs_more_strength = strong_count < 2
        has_too_many_development_slots = development_heavy_count > 2

        if not needs_more_strength and not has_too_many_development_slots:
            return photographers

        current_red_count = role_counts(photographers, members)["red"]
        removable_candidates = [
            name
            for name in photographers
            if members[name]["role"] == "yellow" and is_development_heavy_sunday_photographer(name, members)
        ]
        if current_red_count > 1:
            removable_candidates.extend(
                name for name in photographers if members[name]["role"] == "red"
            )

        removable_candidates = sorted(
            set(removable_candidates),
            key=lambda name: (
                0 if members[name]["role"] == "red" else 1,
                -members[name]["shoot_rank"],
                name,
            ),
        )
        if not removable_candidates:
            return photographers

        replacement_candidates = [
            name
            for name in members
            if name not in used
            and name not in photographers
            and is_available(name, event["date"], bad_dates)
            and members[name]["can_shoot"]
            and not is_development_heavy_sunday_photographer(name, members)
        ]
        if not replacement_candidates:
            return photographers

        best_swap = None
        for removable in removable_candidates:
            for candidate in replacement_candidates:
                proposed = [candidate if name == removable else name for name in photographers]
                if not can_use_sunday_photographer_lineup(event, members, used, proposed):
                    continue

                proposed_strong_count, proposed_development_heavy_count = sunday_strength_metrics(
                    proposed,
                    members,
                )
                score = photographer_score(
                    candidate,
                    members,
                    stats,
                    event["event"],
                    event["date"],
                    event["requirements"]["tier"],
                )
                if score is None:
                    continue

                swap_rank = (
                    0 if proposed_development_heavy_count < development_heavy_count else 1,
                    0 if proposed_strong_count > strong_count else 1,
                    proposed_development_heavy_count,
                    -proposed_strong_count,
                    score,
                    candidate,
                    removable,
                )
                if best_swap is None or swap_rank < best_swap[0]:
                    best_swap = (swap_rank, removable, candidate)

        if best_swap is None:
            return photographers

        _, removable, candidate = best_swap
        photographers = [candidate if name == removable else name for name in photographers]


def validate_editor_pairing(event, members, editors):
    if len(editors) < 2:
        return

    strong_editors = [name for name in editors if is_strong_editor(name, members)]
    lower_tier_editors = [name for name in editors if is_lower_tier_editor(name, members)]

    if event["requirements"]["tier"] == "high":
        if len(strong_editors) < 2:
            raise SchedulingError(
                f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must use stronger editors in both editor slots."
            )
        return

    if not strong_editors or not lower_tier_editors:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include 1 stronger editor and 1 lower-tier editor."
        )
    if len(lower_tier_editors) >= 2:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} cannot schedule 2 lower-tier editors together."
        )


def validate_team_composition(event, members, director_name, used, assist, photographers):
    assigned_names = [*used, *photographers]
    counts = role_counts(assigned_names, members)
    photographer_counts = role_counts(photographers, members)

    if event["event"] == "Leaders Meet":
        non_leaders = sorted({name for name in assigned_names if not members[name].get("leader", False)})
        if non_leaders:
            raise SchedulingError(
                f"Leaders Meet on {event['date'].strftime('%Y-%m-%d')} can only include leaders. Non-leaders: {', '.join(non_leaders)}."
            )

    if len(RISKY_REDS.intersection(photographers)) > 1:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} cannot schedule Issac and Aslvin together."
        )

    if members[director_name]["director_track"]:
        if not assist or members[assist]["role"] != "green":
            raise SchedulingError(
                f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include a green assist when {director_name} is directing."
            )

    if (
        event["requirements"]["tier"] != "low"
        and event["requirements"]["photographers"] > 0
        and photographer_counts["green"] < 1
    ):
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include at least 1 green photographer."
        )

    if event["requirements"]["tier"] == "high" and counts["green"] < 2:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include at least 2 greens."
        )

    if event["requirements"]["tier"] == "high" and photographer_counts["green"] < 2:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include at least 2 green photographers."
        )

    if event["event"] == "Sunday Service":
        missing_roles = [
            role
            for role in ("green", "yellow", "red")
            if counts[role] < 1
        ]
        if missing_roles:
            raise SchedulingError(
                f"Sunday Service on {event['date'].strftime('%Y-%m-%d')} must include at least 1 green, 1 yellow, and 1 red. Missing: {', '.join(missing_roles)}."
            )
        visible_slots = visible_photographer_slot_count(photographers, members)
        if visible_slots < event["requirements"]["photographers"]:
            raise SchedulingError(
                f"Sunday Service on {event['date'].strftime('%Y-%m-%d')} must show 4 photographer slots after red pairings are collapsed. Found {visible_slots}."
            )
        strong_sunday_photographers = sum(
            1 for name in photographers if is_strong_sunday_photographer(name, members)
        )
        if strong_sunday_photographers < 2:
            raise SchedulingError(
                f"Sunday Service on {event['date'].strftime('%Y-%m-%d')} must keep at least 2 stronger photographer assignments when workable."
            )
        development_heavy_sunday_photographers = sum(
            1
            for name in photographers
            if is_development_heavy_sunday_photographer(name, members)
        )
        if development_heavy_sunday_photographers > 2:
            raise SchedulingError(
                f"Sunday Service on {event['date'].strftime('%Y-%m-%d')} has too many development-heavy photographer assignments."
            )

    if is_service_event(event["event"]) and counts["red"] > 2:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} cannot have more than 2 reds."
        )

    if RISKY_REDS.intersection(photographers) and not has_safety_anchor(photographers, members):
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include a guide-capable photographer when Issac or Aslvin are scheduled."
        )



def enforce_safety_rule(
    event, members, stats, bad_dates, director_name, used, photographers
):
    assigned_team = set(photographers)
    if not RISKY_REDS.intersection(assigned_team):
        return photographers

    if has_safety_anchor(assigned_team, members):
        return photographers

    replacement_candidates = [
        name
        for name in members
        if name not in used
        and name not in photographers
        and is_available(name, event["date"], bad_dates)
        and members[name]["can_shoot"]
        and is_safety_anchor(name, members)
    ]

    replacement = choose_best_candidate(
        replacement_candidates,
        lambda name: photographer_score(
            name, members, stats, event["event"], event["date"], event["requirements"]["tier"]
        ),
        (
            f"Could not satisfy the safety rule for {event['date'].strftime('%Y-%m-%d')} "
            f"{event['event']}."
        ),
    )

    removable_candidates = [
        name for name in photographers if name not in RISKY_REDS and not is_safety_anchor(name, members)
    ]
    if not removable_candidates:
        raise SchedulingError(
            f"Could not satisfy the safety rule for {event['date'].strftime('%Y-%m-%d')} {event['event']}."
        )

    removable = max(
        removable_candidates,
        key=lambda name: (
            photographer_score(
                name, members, stats, event["date"], event["requirements"]["tier"]
            ),
            name,
        ),
    )

    photographers = [replacement if name == removable else name for name in photographers]
    return photographers


def build_event_requirements(event_name, event_types):
    config = event_types[event_name]
    return {
        "director": int(config.get("director", 1)),
        "editors": int(config.get("editors", 0)),
        "photographers": int(config.get("photographers", 0)),
        "tier": str(config.get("tier", "standard")).lower(),
    }


def update_stats(stats, event, director, assist, editors, photographers):
    event_date = event["date"]
    month = month_key(event_date)
    quarter = quarter_key(event_date.date())
    tier = event["requirements"]["tier"]
    participants = set([director, *([assist] if assist else []), *editors, *photographers])

    for name in participants:
        stats[name]["total_events"] += 1
        stats[name]["monthly_events"][month] += 1
        stats[name]["last_assigned"] = event_date.date()
        if tier == "high":
            stats[name]["high_tier_events"] += 1
            stats[name]["monthly_high_tier_events"][month] += 1
            stats[name]["last_high_tier_assigned"] = event_date.date()

    stats[director]["role_counts"]["director"] += 1
    stats[director]["monthly_role_counts"][month]["director"] += 1
    stats[director]["monthly_event_role_counts"][month][event["event"]]["director"] += 1
    stats[director]["quarterly_event_role_counts"][quarter][event["event"]]["director"] += 1
    if tier == "high":
        stats[director]["high_tier_role_counts"]["director"] += 1
        stats[director]["monthly_high_tier_role_counts"][month]["director"] += 1
        stats[director]["last_high_tier_role_assigned"]["director"] = event_date.date()
    if assist:
        stats[assist]["role_counts"]["assist"] += 1
        stats[assist]["monthly_role_counts"][month]["assist"] += 1
        stats[assist]["monthly_event_role_counts"][month][event["event"]]["assist"] += 1
        stats[assist]["quarterly_event_role_counts"][quarter][event["event"]]["assist"] += 1
        if tier == "high":
            stats[assist]["high_tier_role_counts"]["assist"] += 1
            stats[assist]["monthly_high_tier_role_counts"][month]["assist"] += 1
            stats[assist]["last_high_tier_role_assigned"]["assist"] = event_date.date()
    for name in editors:
        stats[name]["role_counts"]["editor"] += 1
        stats[name]["monthly_role_counts"][month]["editor"] += 1
        stats[name]["monthly_event_role_counts"][month][event["event"]]["editor"] += 1
        stats[name]["quarterly_event_role_counts"][quarter][event["event"]]["editor"] += 1
        if tier == "high":
            stats[name]["high_tier_role_counts"]["editor"] += 1
            stats[name]["monthly_high_tier_role_counts"][month]["editor"] += 1
            stats[name]["last_high_tier_role_assigned"]["editor"] = event_date.date()
    for name in photographers:
        stats[name]["role_counts"]["photographer"] += 1
        stats[name]["monthly_role_counts"][month]["photographer"] += 1
        stats[name]["monthly_event_role_counts"][month][event["event"]]["photographer"] += 1
        stats[name]["quarterly_event_role_counts"][quarter][event["event"]]["photographer"] += 1
        if tier == "high":
            stats[name]["high_tier_role_counts"]["photographer"] += 1
            stats[name]["monthly_high_tier_role_counts"][month]["photographer"] += 1
            stats[name]["last_high_tier_role_assigned"]["photographer"] = event_date.date()


def generate_schedule():
    sync_universal_scheduler_if_needed()

    team = load_team()
    event_types = load_event_types()
    google_sheets_styles = load_google_sheets_styles()
    google_sheets_layout = load_google_sheets_layout()
    events = parse_events()
    bad_dates = parse_bad_dates()
    members = build_members(team)

    validate_bad_dates(members, bad_dates)
    validate_events(events, event_types)
    validate_google_sheets_styles(google_sheets_styles)
    validate_google_sheets_layout(google_sheets_layout)

    fieldnames = google_sheets_layout["sheet_layout"]["canonical_scheduler_format"][
        "columns"
    ]

    stats = init_stats(members)
    rows = []

    for event in events:
        event["requirements"] = build_event_requirements(event["event"], event_types)
        used = set()

        director = pick_director(event, members, stats, bad_dates)
        used.add(director)

        assist = pick_assist(event, members, stats, bad_dates, director, used)
        if assist:
            used.add(assist)

        editors = pick_editors(event, members, stats, bad_dates, director, used)
        used.update(editors)

        photographers = pick_photographers(
            event, members, stats, bad_dates, director, assist, used
        )
        validate_editor_pairing(event, members, editors)

        unavailable = sorted(
            name for name, dates in bad_dates.items() if event["date"].date() in dates
        )

        update_stats(stats, event, director, assist, editors, photographers)

        row = build_output_row(event, director, assist, editors, photographers, fieldnames, members)
        row["unavailable"] = ", ".join(unavailable)
        rows.append(row)

    return rows, fieldnames


def write_csv(rows, fieldnames):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Schedule written to {OUTPUT_PATH}")


def main():
    try:
        rows, fieldnames = generate_schedule()
        write_csv(rows, fieldnames)
        write_styles_manifest(load_google_sheets_styles())
    except UniversalSchedulerValidationError as exc:
        print("Universal scheduler needs attention:")
        print()
        for issue in exc.issues:
            print(f"- {issue}")
        raise SystemExit(1)
    except (SchedulingError, ValueError) as exc:
        print(f"Could not generate schedule: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
