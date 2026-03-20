import csv
import calendar
import re
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
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
SCHEDULER_POLICY_PATH = BASE / "config/scheduler_policy.yaml"
OUTPUT_PATH = BASE / "output/schedule.csv"
STYLE_OUTPUT_PATH = BASE / "output/google_sheets_styles.yaml"

DATE_FORMAT = "%d %b %Y"
EVENT_LINE_PATTERN = re.compile(r"(\d{1,2} [A-Za-z]{3} \d{4}) - (.+)")
DEFAULT_SCHEDULER_POLICY = {
    "limits": {
        "max_assignments_per_member_per_month": 3,
        "max_director_track_directs_per_month": 1,
        "max_red_assignments_per_month": 2,
        "max_high_tier_yellow_shoot_rank": 8,
        "max_high_tier_yellow_editor_rank": 4,
        "high_tier_reserve_window_days": 14,
        "high_tier_recent_window_days": 10,
        "max_same_high_tier_event_assignments": 3,
        "creative_team_meet_max_yellow_editor_rank": 4,
        "creative_team_meet_anchor_yellow_shoot_rank": 10,
        "creative_team_meet_editor_soft_cap_per_quarter": 2,
    },
    "penalties": {
        "consecutive_event_penalty": 30,
        "repeated_high_tier_event_penalty": 140,
        "recent_high_tier_window_penalty": 120,
        "repeated_event_editor_pair_penalty": 110,
        "repeated_low_tier_event_penalty": 55,
        "repeated_weekday_low_tier_penalty": 35,
        "creative_team_meet_editor_repeat_penalty": 65,
        "creative_team_meet_editor_overuse_penalty": 140,
        "weekday_late_low_tier_penalty": 80,
        "multi_day_high_tier_early_day_strength_reserve": 10,
        "upcoming_high_tier_reserve_penalty": 35,
        "upcoming_high_tier_preload_penalty": 90,
        "upcoming_high_tier_preload_same_role_penalty": 50,
    },
    "weights": {
        "priority_rank": 10,
        "role_serve_count": 8,
        "total_serve_count": 3,
    },
    "bonuses": {
        "first_monthly_photographer_assignment": 24,
        "yellow_photo_coverage_bonus": 32,
        "green_editor_rotation_bonus": 24,
        "creative_team_meet_green_editor_rotation_bonus": 18,
        "creative_team_meet_lower_yellow_editor_rotation_bonus": 22,
        "weekend_service_for_weekday_late_member": 18,
        "multi_day_high_tier_final_day_strength_boost": 18,
        "creative_team_meet_anchor_bonus": 20,
    },
    "fallbacks": {
        "blank_rank_value": 50,
    },
    "safety": {
        "required_guides_for": ["Isaac", "Aslvin"],
    },
    "special_rules": {
        "use_scoring_only_after_hard_constraints": True,
    },
}
SCHEDULER_POLICY = DEFAULT_SCHEDULER_POLICY.copy()


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


def load_scheduler_policy():
    with open(SCHEDULER_POLICY_PATH) as f:
        raw_data = yaml.safe_load(f) or {}

    policy = {
        section: dict(DEFAULT_SCHEDULER_POLICY.get(section, {}))
        for section in DEFAULT_SCHEDULER_POLICY
    }
    for section, defaults in policy.items():
        if isinstance(raw_data.get(section), dict):
            defaults.update(raw_data[section])
    return policy


def policy_limit(name):
    return int(SCHEDULER_POLICY["limits"][name])


def policy_weight(name):
    return int(SCHEDULER_POLICY["weights"][name])


def policy_penalty(name):
    return int(SCHEDULER_POLICY["penalties"][name])


def policy_bonus(name):
    return int(SCHEDULER_POLICY["bonuses"][name])


def policy_fallback(name):
    return int(SCHEDULER_POLICY["fallbacks"][name])


def required_guides():
    return set(SCHEDULER_POLICY["safety"].get("required_guides_for", []))


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


def annotate_event_series(events):
    index = 0

    while index < len(events):
        series = [events[index]]
        next_index = index + 1

        while next_index < len(events):
            previous_event = events[next_index - 1]
            current_event = events[next_index]
            if current_event["event"] != previous_event["event"]:
                break
            if (current_event["date"].date() - previous_event["date"].date()).days != 1:
                break
            series.append(current_event)
            next_index += 1

        series_length = len(series)
        for series_index, event in enumerate(series, start=1):
            event["series_length"] = series_length
            event["series_day_index"] = series_index
            event["series_is_final_day"] = series_index == series_length

        index = next_index

    return events


def annotate_upcoming_high_tier_events(events):
    next_high_tier_event = None

    for event in reversed(events):
        event["event_key"] = f"{event['event']}@{event['date'].date().isoformat()}"
        event["days_until_next_high_tier"] = None
        event["next_high_tier_event_name"] = None
        event["next_high_tier_event_key"] = None

        if event["requirements"]["tier"] == "high":
            next_high_tier_event = event
            continue

        if next_high_tier_event is None:
            continue

        gap_days = (next_high_tier_event["date"].date() - event["date"].date()).days
        if gap_days <= 0:
            continue

        event["days_until_next_high_tier"] = gap_days
        event["next_high_tier_event_name"] = next_high_tier_event["event"]
        event["next_high_tier_event_key"] = next_high_tier_event["event_key"]

    return events


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
    blank_rank = policy_fallback("blank_rank_value")

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
            "shoot_rank": int(person.get("shoot_rank", blank_rank)),
            "direct_rank": int(person.get("direct_rank", blank_rank)),
            "editor_rank": int(person.get("editor_rank", blank_rank)),
            "director_track": False,
            "leader": bool(person.get("leaders", person.get("leader", True))),
            "can_guide": bool(person.get("guide", person.get("can_guide", True))),
            "weekday_late": bool(person.get("weekday_late", False)),
        }

    for person in team["yellows"]:
        name = person["name"]
        members[name] = {
            "name": name,
            "role": "yellow",
            "can_direct": bool(person.get("director_track", False)),
            "can_edit": True,
            "can_shoot": True,
            "shoot_rank": int(person.get("shoot_rank", person.get("editor_rank", blank_rank))),
            "direct_rank": int(person.get("direct_rank", blank_rank)),
            "editor_rank": int(person.get("editor_rank", blank_rank)),
            "director_track": bool(person.get("director_track", False)),
            "leader": bool(person.get("leaders", person.get("leader", False))),
            "can_guide": bool(person.get("guide", person.get("can_guide", False))),
            "weekday_late": bool(person.get("weekday_late", False)),
        }

    for person in team["reds"]:
        if isinstance(person, dict):
            name = person["name"]
            shoot_rank = int(person.get("shoot_rank", 999))
            can_edit = bool(person.get("can_edit", "editor_rank" in person))
            editor_rank = int(person.get("editor_rank", 999))
            can_guide = bool(person.get("guide", person.get("can_guide", False)))
        else:
            name = str(person)
            shoot_rank = 999
            can_edit = False
            editor_rank = 999
            can_guide = False

        members[name] = {
            "name": name,
            "role": "red",
            "can_direct": False,
            "can_edit": can_edit,
            "can_shoot": True,
            "shoot_rank": shoot_rank,
            "direct_rank": 999,
            "editor_rank": editor_rank,
            "director_track": False,
            "leader": False,
            "can_guide": can_guide,
            "weekday_late": bool(person.get("weekday_late", False)) if isinstance(person, dict) else False,
        }

    for person in team.get("shadows", []):
        if isinstance(person, dict):
            name = person["name"]
        else:
            name = str(person)

        members[name] = {
            "name": name,
            "role": "shadow",
            "can_direct": False,
            "can_edit": False,
            "can_shoot": False,
            "shoot_rank": blank_rank,
            "direct_rank": blank_rank,
            "editor_rank": blank_rank,
            "director_track": False,
            "leader": False,
            "can_guide": False,
            "weekday_late": bool(person.get("weekday_late", False)) if isinstance(person, dict) else False,
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
        "shadow",
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
    risky_members = required_guides()
    risky_names = [name for name in ordered_photographers if name in risky_members]
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
        if name in risky_members:
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
            "quarterly_event_editor_pair_counts": defaultdict(lambda: defaultdict(lambda: defaultdict(int))),
            "event_role_counts_total": defaultdict(lambda: defaultdict(int)),
            "event_editor_pair_counts_total": defaultdict(lambda: defaultdict(int)),
            "quarterly_weekday_low_tier_role_counts": defaultdict(lambda: defaultdict(int)),
            "upcoming_high_tier_preload_counts": defaultdict(int),
            "upcoming_high_tier_preload_role_counts": defaultdict(lambda: defaultdict(int)),
            "last_assigned": None,
            "last_high_tier_assigned": None,
            "last_high_tier_role_assigned": {},
            "last_high_tier_event_name": None,
            "high_tier_dates": [],
        }
        for name in members
    }


def reached_monthly_red_limit(stats, name, event_date, members):
    if members[name]["role"] != "red":
        return False
    limit = policy_limit("max_red_assignments_per_month")
    if limit <= 0:
        return False
    return stats[name]["monthly_events"][month_key(event_date)] >= limit


def reached_monthly_assignment_limit(stats, name, event_date):
    limit = policy_limit("max_assignments_per_member_per_month")
    if limit <= 0:
        return False
    return stats[name]["monthly_events"][month_key(event_date)] > limit


def reached_nonfinal_high_tier_monthly_limit(stats, name, event_date):
    limit = policy_limit("max_assignments_per_member_per_month")
    if limit <= 0:
        return False
    return stats[name]["monthly_events"][month_key(event_date)] > limit


def reached_high_tier_event_repeat_limit(stats, name, event_name, event_date, tier):
    if tier != "high":
        return False

    limit = policy_limit("max_same_high_tier_event_assignments")
    if limit <= 0:
        return False

    quarter = quarter_key(event_date.date())
    event_role_counts = stats[name]["quarterly_event_role_counts"][quarter][event_name]
    return sum(event_role_counts.values()) >= limit


def fairness_penalty(stats, name, event_date, tier):
    person_stats = stats[name]
    monthly_events = person_stats["monthly_events"][month_key(event_date)]
    penalty = person_stats["total_events"] * policy_weight("total_serve_count")
    penalty += monthly_events * (
        policy_weight("total_serve_count") * 2
    )
    monthly_limit = policy_limit("max_assignments_per_member_per_month")
    if monthly_limit > 0 and monthly_events >= monthly_limit:
        overload = monthly_events - monthly_limit + 1
        penalty += overload * (280 if tier == "high" else 220)

    last_assigned = person_stats["last_assigned"]
    if last_assigned is None:
        penalty -= 6
    else:
        gap = (event_date.date() - last_assigned).days
        if gap < 7:
            penalty += (
                policy_penalty("consecutive_event_penalty") // 2
                if tier == "high"
                else policy_penalty("consecutive_event_penalty")
            )
        elif gap < 14:
            penalty += 4 if tier == "high" else max(
                1, policy_penalty("consecutive_event_penalty") - 10
            )
        elif gap < 21:
            penalty += 2 if tier == "high" else 5

    return penalty


def role_count_penalty(stats, name, role):
    return stats[name]["role_counts"][role] * policy_weight("role_serve_count")


def repeated_event_role_penalty(stats, name, event_name, role, event_date):
    if event_name in {"Creative Team Meet", "Lifegen Prayer"}:
        repeats = stats[name]["event_role_counts_total"][event_name][role]
    else:
        quarter = quarter_key(event_date.date())
        repeats = stats[name]["quarterly_event_role_counts"][quarter][event_name][role]
    if repeats == 0:
        return 0

    if event_name in {"Creative Team Meet", "Lifegen Prayer"}:
        return repeats * 45
    if event_name == "Leaders Meet":
        return repeats * 30
    return repeats * 12


def quarterly_event_role_count(stats, name, event_name, role, event_date):
    quarter = quarter_key(event_date.date())
    return stats[name]["quarterly_event_role_counts"][quarter][event_name][role]


def total_event_role_count(stats, name, event_name, role):
    return stats[name]["event_role_counts_total"][event_name][role]


def editor_pair_key(editors):
    return tuple(sorted(editors))


def repeated_event_editor_pair_penalty(stats, editors, event_name, event_date):
    if len(editors) != 2:
        return 0

    repeats = event_editor_pair_repeat_count(stats, editors, event_name, event_date)
    if repeats == 0:
        return 0

    return repeats * policy_penalty("repeated_event_editor_pair_penalty")


def event_editor_pair_repeat_count(stats, editors, event_name, event_date):
    if len(editors) != 2:
        return 0

    pair_key = editor_pair_key(editors)
    anchor_name = pair_key[0]
    if event_name in {"Creative Team Meet", "Lifegen Prayer"}:
        return stats[anchor_name]["event_editor_pair_counts_total"][event_name][pair_key]

    quarter = quarter_key(event_date.date())
    return stats[anchor_name]["quarterly_event_editor_pair_counts"][quarter][event_name][pair_key]


def repeated_low_tier_event_penalty(stats, name, event_name, event_date, tier):
    if tier != "low":
        return 0

    if event_name in {"Creative Team Meet", "Lifegen Prayer"}:
        event_role_counts = stats[name]["event_role_counts_total"][event_name]
    else:
        quarter = quarter_key(event_date.date())
        event_role_counts = stats[name]["quarterly_event_role_counts"][quarter][event_name]
    repeats = sum(event_role_counts.values())
    if repeats == 0:
        return 0

    return repeats * policy_penalty("repeated_low_tier_event_penalty")


def repeated_high_tier_event_penalty(stats, name, event_name, event_date, tier):
    if tier != "high":
        return 0

    quarter = quarter_key(event_date.date())
    event_role_counts = stats[name]["quarterly_event_role_counts"][quarter][event_name]
    repeats = sum(event_role_counts.values())
    if repeats == 0:
        return 0

    return repeats * policy_penalty("repeated_high_tier_event_penalty")


def repeated_weekday_low_tier_role_penalty(stats, name, role, event_name, event_date, tier):
    if not is_weekday_low_tier_event(event_name, event_date, tier):
        return 0

    quarter = quarter_key(event_date.date())
    repeats = stats[name]["quarterly_weekday_low_tier_role_counts"][quarter][role]
    return repeats * policy_penalty("repeated_weekday_low_tier_penalty")


def creative_team_meet_editor_rotation_penalty(stats, name, event_name, event_date):
    if event_name != "Creative Team Meet":
        return 0

    repeats = total_event_role_count(stats, name, event_name, "editor")
    if repeats == 0:
        return 0

    penalty = repeats * policy_penalty("creative_team_meet_editor_repeat_penalty")
    soft_cap = policy_limit("creative_team_meet_editor_soft_cap_per_quarter")
    if soft_cap > 0 and repeats >= soft_cap:
        penalty += (
            repeats - soft_cap + 1
        ) * policy_penalty("creative_team_meet_editor_overuse_penalty")
    return penalty


def monthly_event_role_count(stats, name, event_name, role, event_date):
    return stats[name]["monthly_event_role_counts"][month_key(event_date)][event_name][role]


def monthly_role_count(stats, name, role, event_date):
    return stats[name]["monthly_role_counts"][month_key(event_date)][role]


def recent_high_tier_window_penalty(stats, name, event_date, tier):
    if tier != "high":
        return 0

    window_days = policy_limit("high_tier_recent_window_days")
    if window_days <= 0:
        return 0

    recent_dates = []
    for assigned_date in stats[name]["high_tier_dates"]:
        gap = (event_date.date() - assigned_date).days
        if 0 < gap <= window_days:
            recent_dates.append(gap)

    if not recent_dates:
        return 0

    penalty = len(recent_dates) * policy_penalty("recent_high_tier_window_penalty")
    if any(gap <= 2 for gap in recent_dates):
        penalty += policy_penalty("recent_high_tier_window_penalty")
    return penalty


def has_adjacent_high_tier_same_role_conflict(stats, name, role, event_name, event_date, tier):
    if tier != "high":
        return False

    last_same_role = stats[name]["last_high_tier_role_assigned"].get(role)
    if last_same_role is None:
        return False

    gap = (event_date.date() - last_same_role).days
    if gap <= 0 or gap > 2:
        return False

    if stats[name]["last_high_tier_event_name"] == event_name:
        return False

    return True


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


def is_weekday_low_tier_event(event_name, event_date, tier):
    return tier == "low" and event_date.weekday() < calendar.SATURDAY


def is_creative_team_meet(event_name):
    return event_name == "Creative Team Meet"


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


def upcoming_high_tier_reserve_penalty(event, member, role):
    if event["requirements"]["tier"] == "high":
        return 0

    gap_days = event.get("days_until_next_high_tier")
    if gap_days is None:
        return 0

    reserve_window = policy_limit("high_tier_reserve_window_days")
    if reserve_window <= 0 or gap_days > reserve_window:
        return 0

    if role in {"director", "assist"}:
        if member["role"] != "green":
            return 0
        rank = member["direct_rank"]
        threshold = 6
    elif role == "editor":
        if not member["can_edit"] or member["role"] == "red":
            return 0
        rank = member["editor_rank"]
        threshold = 4 if member["role"] == "yellow" else 6
    elif role == "photographer":
        if member["role"] == "red":
            return 0
        rank = member["shoot_rank"]
        threshold = (
            policy_limit("max_high_tier_yellow_shoot_rank")
            if member["role"] == "yellow"
            else 6
        )
    else:
        return 0

    strength_points = max(0, threshold - rank + 1)
    if strength_points == 0:
        return 0

    proximity_factor = 2 if gap_days <= max(7, reserve_window // 2) else 1
    return (
        strength_points
        * proximity_factor
        * policy_penalty("upcoming_high_tier_reserve_penalty")
    )


def upcoming_high_tier_preload_penalty(stats, name, role, event):
    if event["requirements"]["tier"] == "high":
        reserve_key = event.get("event_key")
    else:
        reserve_key = event.get("next_high_tier_event_key")

    if not reserve_key:
        return 0

    preload_count = stats[name]["upcoming_high_tier_preload_counts"][reserve_key]
    if preload_count == 0:
        return 0

    same_role_count = stats[name]["upcoming_high_tier_preload_role_counts"][reserve_key][
        role
    ]
    penalty = preload_count * policy_penalty("upcoming_high_tier_preload_penalty")
    penalty += (
        same_role_count
        * policy_penalty("upcoming_high_tier_preload_same_role_penalty")
    )
    return penalty


def multi_day_high_tier_strength_adjustment(event, member, role):
    if event["requirements"]["tier"] != "high":
        return 0
    if int(event.get("series_length", 1)) < 2:
        return 0

    if role in {"director", "assist"}:
        rank = member["direct_rank"]
    elif role == "editor":
        rank = member["editor_rank"]
    elif role == "photographer":
        rank = member["shoot_rank"]
    else:
        return 0

    strength_points = max(0, 12 - rank)
    if strength_points == 0:
        return 0

    if event.get("series_is_final_day", False):
        return -(
            strength_points * policy_bonus("multi_day_high_tier_final_day_strength_boost")
        )

    return strength_points * policy_penalty(
        "multi_day_high_tier_early_day_strength_reserve"
    )


def director_score(name, members, stats, event_name, event_date, tier, event=None):
    member = members[name]
    if not member["can_direct"]:
        return None

    if event_name == "Leaders Meet" and not member.get("leader", False):
        return None

    if tier == "high" and member["role"] != "green":
        return None
    if (
        tier == "high"
        and member["role"] != "green"
        and has_adjacent_high_tier_same_role_conflict(
            stats,
            name,
            "director",
            event_name,
            event_date,
            tier,
        )
    ):
        return None
    if tier != "high" and reached_monthly_assignment_limit(stats, name, event_date):
        return None

    score = fairness_penalty(stats, name, event_date, tier)
    score += role_count_penalty(stats, name, "director")
    score += repeated_event_role_penalty(stats, name, event_name, "director", event_date)
    score += repeated_low_tier_event_penalty(stats, name, event_name, event_date, tier)
    score += repeated_weekday_low_tier_role_penalty(
        stats, name, "director", event_name, event_date, tier
    )
    if tier == "high":
        score += high_tier_rotation_penalty(stats, name, event_date, "director")
        score += repeated_high_tier_event_penalty(stats, name, event_name, event_date, tier)
        score += recent_high_tier_window_penalty(stats, name, event_date, tier)
    elif event is not None:
        score += upcoming_high_tier_reserve_penalty(event, member, "director")
    if event is not None:
        score += upcoming_high_tier_preload_penalty(stats, name, "director", event)

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
        if (
            monthly_role_count(stats, name, "director", event_date)
            >= policy_limit("max_director_track_directs_per_month")
        ):
            return None
        if tier == "low":
            score -= 18
        else:
            score += 35
    else:
        return None

    if event is not None:
        score += multi_day_high_tier_strength_adjustment(event, member, "director")

    return score


def assist_score(name, members, stats, event_name, event_date, tier="standard", event=None):
    member = members[name]
    if member["role"] != "green":
        return None
    if event_name == "Leaders Meet" and not member.get("leader", False):
        return None
    if (
        tier == "high"
        and member["role"] != "green"
        and has_adjacent_high_tier_same_role_conflict(
            stats,
            name,
            "assist",
            event_name,
            event_date,
            tier,
        )
    ):
        return None
    if tier != "high" and reached_monthly_assignment_limit(stats, name, event_date):
        return None

    score = fairness_penalty(stats, name, event_date, tier)
    score += repeated_event_role_penalty(stats, name, event_name, "assist", event_date)
    score += repeated_low_tier_event_penalty(stats, name, event_name, event_date, tier)
    score += repeated_weekday_low_tier_role_penalty(
        stats, name, "assist", event_name, event_date, tier
    )
    score += role_count_penalty(stats, name, "assist")
    score += monthly_role_count(stats, name, "assist", event_date) * 8
    if tier == "high":
        score += high_tier_rotation_penalty(stats, name, event_date, "assist")
        score += repeated_high_tier_event_penalty(stats, name, event_name, event_date, tier)
        score += recent_high_tier_window_penalty(stats, name, event_date, tier)
        score += high_tier_shoot_strength_penalty(
            member,
            {"green": 3},
        )
    elif event is not None:
        score += upcoming_high_tier_reserve_penalty(event, member, "assist")
    if event is not None:
        score += upcoming_high_tier_preload_penalty(stats, name, "assist", event)
    score -= max(0, 14 - (member["direct_rank"] * 2))
    if event is not None:
        score += multi_day_high_tier_strength_adjustment(event, member, "assist")
    return score


def editor_score(name, members, stats, event_name, event_date, tier, director_name, event=None):
    member = members[name]
    if not member["can_edit"]:
        return None
    if event_name == "Leaders Meet" and not member.get("leader", False):
        return None
    if (
        tier == "high"
        and member["role"] != "green"
        and has_adjacent_high_tier_same_role_conflict(
            stats,
            name,
            "editor",
            event_name,
            event_date,
            tier,
        )
    ):
        return None
    if tier != "high" and reached_monthly_assignment_limit(stats, name, event_date):
        return None
    if member["role"] == "red" and not (
        is_creative_team_meet(event_name) and is_creative_team_meet_red_editor(name, members)
    ):
        return None
    if (
        tier == "high"
        and member["role"] == "yellow"
        and member["editor_rank"] > policy_limit("max_high_tier_yellow_editor_rank")
    ):
        return None

    score = fairness_penalty(stats, name, event_date, tier)
    score += role_count_penalty(stats, name, "editor")
    score += repeated_event_role_penalty(stats, name, event_name, "editor", event_date)
    score += repeated_low_tier_event_penalty(stats, name, event_name, event_date, tier)
    score += repeated_weekday_low_tier_role_penalty(
        stats, name, "editor", event_name, event_date, tier
    )
    score += creative_team_meet_editor_rotation_penalty(
        stats,
        name,
        event_name,
        event_date,
    )

    if member["role"] == "yellow":
        if tier == "high":
            score += high_tier_rotation_penalty(stats, name, event_date, "editor")
            score += repeated_high_tier_event_penalty(stats, name, event_name, event_date, tier)
            score += recent_high_tier_window_penalty(stats, name, event_date, tier)
            score += member["editor_rank"] * (policy_weight("priority_rank") + 4)
            if member["editor_rank"] > 4:
                score += (member["editor_rank"] - 4) * 24
        else:
            rank_weight = {"standard": 3, "low": 1}.get(tier, 3)
            score += member["editor_rank"] * rank_weight
            if event is not None:
                score += upcoming_high_tier_reserve_penalty(event, member, "editor")
            if monthly_role_count(stats, name, "photographer", event_date) == 0:
                score += policy_bonus("first_monthly_photographer_assignment")
                if monthly_role_count(stats, name, "editor", event_date) > 0:
                    score += policy_bonus("yellow_photo_coverage_bonus")
            if event_name == "Creative Team Meet" and member["editor_rank"] >= 5:
                score -= policy_bonus("creative_team_meet_lower_yellow_editor_rotation_bonus")
    elif member["role"] == "green":
        if tier == "high":
            score += high_tier_rotation_penalty(stats, name, event_date, "editor")
            score += repeated_high_tier_event_penalty(stats, name, event_name, event_date, tier)
            score += recent_high_tier_window_penalty(stats, name, event_date, tier)
            score += member["editor_rank"] * policy_weight("priority_rank")
            if member["editor_rank"] > 4:
                score += (member["editor_rank"] - 4) * 18
        else:
            score += {"standard": 10, "low": 16}.get(tier, 10)
            score += member["editor_rank"] * {"standard": 3, "low": 4}.get(
                tier, 3
            )
            if event is not None:
                score += upcoming_high_tier_reserve_penalty(event, member, "editor")
            if (
                member["editor_rank"] >= 4
                and monthly_role_count(stats, name, "editor", event_date) == 0
            ):
                score -= policy_bonus("green_editor_rotation_bonus")
            if event_name == "Creative Team Meet":
                score -= policy_bonus("creative_team_meet_green_editor_rotation_bonus")
    elif member["role"] == "red":
        if not is_creative_team_meet(event_name):
            return None
        score -= 10
        score += member["editor_rank"] * 2
    else:
        return None

    if name == director_name:
        score += 40

    if event is not None:
        score += upcoming_high_tier_preload_penalty(stats, name, "editor", event)
    if event is not None:
        score += multi_day_high_tier_strength_adjustment(event, member, "editor")

    return score


def is_strong_editor(name, members):
    return members[name]["editor_rank"] <= 4


def is_lower_tier_editor(name, members):
    return members[name]["editor_rank"] >= 5


def is_creative_team_meet_mentor_editor(name, members):
    member = members[name]
    return (
        member["can_edit"]
        and member["role"] != "red"
        and member["can_guide"]
        and member["editor_rank"]
        <= policy_limit("creative_team_meet_max_yellow_editor_rank")
    )


def is_creative_team_meet_decent_yellow_editor(name, members):
    member = members[name]
    return (
        member["role"] == "yellow"
        and member["can_edit"]
        and member["editor_rank"]
        <= policy_limit("creative_team_meet_max_yellow_editor_rank")
    )


def is_creative_team_meet_red_editor(name, members):
    member = members[name]
    return member["role"] == "red" and member["can_edit"]


def is_creative_team_meet_anchor_yellow_photographer(name, members):
    member = members[name]
    return (
        member["role"] == "yellow"
        and member["shoot_rank"]
        <= policy_limit("creative_team_meet_anchor_yellow_shoot_rank")
    )


def is_valid_creative_team_meet_editor_pair(editors, members):
    if len(editors) != 2:
        return False
    if any(not members[name]["can_edit"] for name in editors):
        return False

    if all(is_creative_team_meet_decent_yellow_editor(name, members) for name in editors):
        return True

    red_editors = [name for name in editors if is_creative_team_meet_red_editor(name, members)]
    if red_editors:
        if len(red_editors) != 1:
            return False
        mentor_name = next(name for name in editors if name not in red_editors)
        return members[mentor_name]["role"] == "green" and is_creative_team_meet_mentor_editor(
            mentor_name,
            members,
        )

    if not any(members[name]["role"] == "yellow" for name in editors):
        return False

    return any(is_creative_team_meet_mentor_editor(name, members) for name in editors)


def creative_team_meet_editor_pair_priority(editors, members):
    if all(is_creative_team_meet_decent_yellow_editor(name, members) for name in editors):
        return 0
    if any(is_creative_team_meet_red_editor(name, members) for name in editors):
        return 2
    return 1


def is_high_tier_eligible_yellow_photographer(name, members):
    member = members[name]
    return (
        member["role"] == "yellow"
        and member["shoot_rank"] <= policy_limit("max_high_tier_yellow_shoot_rank")
    )


def is_disallowed_high_tier_photographer(name, members):
    member = members[name]
    return member["role"] == "red" or (
        member["role"] == "yellow"
        and member["shoot_rank"] > policy_limit("max_high_tier_yellow_shoot_rank")
    )


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


def photographer_score(name, members, stats, event_name, event_date, tier, event=None):
    member = members[name]
    if not member["can_shoot"]:
        return None
    if event_name == "Leaders Meet" and not member.get("leader", False):
        return None
    if (
        tier == "high"
        and member["role"] != "green"
        and has_adjacent_high_tier_same_role_conflict(
            stats,
            name,
            "photographer",
            event_name,
            event_date,
            tier,
        )
    ):
        return None
    if tier != "high" and reached_monthly_assignment_limit(stats, name, event_date):
        return None
    if reached_monthly_red_limit(stats, name, event_date, members):
        return None
    if tier == "high" and is_disallowed_high_tier_photographer(name, members):
        return None

    score = fairness_penalty(stats, name, event_date, tier)
    if monthly_role_count(stats, name, "photographer", event_date) >= 2:
        score += 140
    score += role_count_penalty(stats, name, "photographer")
    score += repeated_event_role_penalty(stats, name, event_name, "photographer", event_date)
    score += repeated_low_tier_event_penalty(stats, name, event_name, event_date, tier)
    score += repeated_weekday_low_tier_role_penalty(
        stats, name, "photographer", event_name, event_date, tier
    )

    if tier == "high":
        score += high_tier_rotation_penalty(stats, name, event_date, "photographer")
        score += repeated_high_tier_event_penalty(stats, name, event_name, event_date, tier)
        score += recent_high_tier_window_penalty(stats, name, event_date, tier)
        if member["role"] == "green":
            score += high_tier_shoot_strength_penalty(
                member,
                {"green": 5},
            )
            score -= policy_weight("priority_rank") * 2
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

    if tier != "high" and event is not None:
        score += upcoming_high_tier_reserve_penalty(event, member, "photographer")
    if event is not None:
        score += upcoming_high_tier_preload_penalty(stats, name, "photographer", event)

    if member["role"] == "yellow" and monthly_role_count(stats, name, "photographer", event_date) == 0:
        score -= policy_bonus("first_monthly_photographer_assignment")
        if monthly_role_count(stats, name, "editor", event_date) > 0:
            score -= policy_bonus("yellow_photo_coverage_bonus")

    if (
        is_creative_team_meet(event_name)
        and is_creative_team_meet_anchor_yellow_photographer(name, members)
    ):
        score -= policy_bonus("creative_team_meet_anchor_bonus")

    if event_name == "Sunday Service":
        sunday_count = monthly_event_role_count(stats, name, event_name, "photographer", event_date)
        if sunday_count == 0:
            score -= 35
        else:
            score += sunday_count * 45
        if member.get("weekday_late", False):
            score -= policy_bonus("weekend_service_for_weekday_late_member")

    if is_weekday_low_tier_event(event_name, event_date, tier) and member.get("weekday_late", False):
        score += policy_penalty("weekday_late_low_tier_penalty")

    if event is not None:
        score += multi_day_high_tier_strength_adjustment(event, member, "photographer")

    return score


def pick_director(event, members, stats, bad_dates):
    tier = event["requirements"]["tier"]
    candidates = available_names(members, bad_dates, event["date"], used=set())

    return choose_best_candidate(
        candidates,
        lambda name: director_score(
            name, members, stats, event["event"], event["date"], tier, event=event
        ),
        f"Could not find an available director for {event['date'].strftime('%Y-%m-%d')} {event['event']}.",
    )


def pick_assist(event, members, stats, bad_dates, director_name, used):
    if not members[director_name]["director_track"]:
        return ""

    candidates = available_names(members, bad_dates, event["date"], used)
    return choose_best_candidate(
        candidates,
        lambda name: assist_score(
            name,
            members,
            stats,
            event["event"],
            event["date"],
            event["requirements"]["tier"],
            event=event,
        ),
        (
            f"Could not find a green assist for trainee director "
            f"{director_name} on {event['date'].strftime('%Y-%m-%d')} {event['event']}."
        ),
    )


def pick_editors(event, members, stats, bad_dates, director_name, used):
    required = event["requirements"]["editors"]
    if required == 0:
        return []

    if is_creative_team_meet(event["event"]):
        return pick_creative_team_meet_editors(
            event,
            members,
            stats,
            bad_dates,
            director_name,
            used,
        )

    if required == 2:
        unused_candidates = available_names(members, bad_dates, event["date"], used)
        try:
            return choose_best_editor_pair(
                unused_candidates,
                event,
                members,
                stats,
                director_name,
                lambda pair: is_valid_default_editor_pair(pair, event, members),
                (
                    f"Could not find enough editors for "
                    f"{event['date'].strftime('%Y-%m-%d')} {event['event']}."
                ),
            )
        except SchedulingError:
            fallback_candidates = [
                name for name in members if is_available(name, event["date"], bad_dates)
            ]
            return choose_best_editor_pair(
                fallback_candidates,
                event,
                members,
                stats,
                director_name,
                lambda pair: is_valid_default_editor_pair(pair, event, members),
                (
                    f"Could not fill the editor slots for "
                    f"{event['date'].strftime('%Y-%m-%d')} {event['event']}."
                ),
            )

    tier = event["requirements"]["tier"]
    editors = []

    def candidate_score(name):
        return editor_score(
            name,
            members,
            stats,
            event["event"],
            event["date"],
            tier,
            director_name,
            event=event,
        )

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


def pick_creative_team_meet_editors(event, members, stats, bad_dates, director_name, used):
    required = event["requirements"]["editors"]
    if required == 0:
        return []
    if required != 2:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must use exactly 2 editor slots."
        )

    available_candidates = available_names(members, bad_dates, event["date"], used)
    try:
        return choose_best_editor_pair(
            available_candidates,
            event,
            members,
            stats,
            director_name,
            lambda pair: is_valid_creative_team_meet_editor_pair(pair, members),
            (
                f"Could not find a valid Creative Team Meet editor pair for "
                f"{event['date'].strftime('%Y-%m-%d')}. "
                f"Use either 2 decent yellow editors, a guide-capable mentor plus a yellow editor, "
                f"or a guide-capable green plus a red editor."
            ),
            pair_priority_fn=creative_team_meet_editor_pair_priority,
        )
    except SchedulingError:
        fallback_candidates = [
            name for name in members if is_available(name, event["date"], bad_dates)
        ]
        return choose_best_editor_pair(
            fallback_candidates,
            event,
            members,
            stats,
            director_name,
            lambda pair: is_valid_creative_team_meet_editor_pair(pair, members),
            (
                f"Could not find a valid Creative Team Meet editor pair for "
                f"{event['date'].strftime('%Y-%m-%d')}. "
                f"Use either 2 decent yellow editors, a guide-capable mentor plus a yellow editor, "
                f"or a guide-capable green plus a red editor."
            ),
            pair_priority_fn=creative_team_meet_editor_pair_priority,
        )


def choose_required_photographer(candidate_names, members, stats, event_name, event_date, tier, label, event=None):
    return choose_best_candidate(
        candidate_names,
        lambda name: photographer_score(
            name, members, stats, event_name, event_date, tier, event=event
        ),
        f"Could not find {label} for {event_date.strftime('%Y-%m-%d')}.",
    )


def is_valid_default_editor_pair(editors, event, members):
    if len(editors) != 2:
        return False
    if any(not members[name]["can_edit"] for name in editors):
        return False

    tier = event["requirements"]["tier"]
    if tier == "high":
        return all(is_strong_editor(name, members) for name in editors)

    strong_editors = [name for name in editors if is_strong_editor(name, members)]
    lower_tier_editors = [name for name in editors if is_lower_tier_editor(name, members)]
    return bool(strong_editors) and bool(lower_tier_editors) and len(lower_tier_editors) < 2


def choose_best_editor_pair(
    candidate_names,
    event,
    members,
    stats,
    director_name,
    pair_validator,
    failure_message,
    pair_priority_fn=None,
):
    def candidate_score(name):
        return editor_score(
            name,
            members,
            stats,
            event["event"],
            event["date"],
            event["requirements"]["tier"],
            director_name,
            event=event,
        )

    for avoid_repeated_pairs in (True, False):
        best_pair = None

        for pair in combinations(candidate_names, 2):
            if not pair_validator(pair):
                continue
            if avoid_repeated_pairs and event_editor_pair_repeat_count(
                stats,
                pair,
                event["event"],
                event["date"],
            ):
                continue

            scores = []
            for name in pair:
                score = candidate_score(name)
                if score is None:
                    break
                scores.append(score)
            else:
                pair_penalty = repeated_event_editor_pair_penalty(
                    stats,
                    pair,
                    event["event"],
                    event["date"],
                )
                pair_event_load = sum(
                    quarterly_event_role_count(
                        stats,
                        name,
                        event["event"],
                        "editor",
                        event["date"],
                    )
                    for name in pair
                )
                priority = pair_priority_fn(pair, members) if pair_priority_fn else 0
                sort_key = (
                    pair_penalty + sum(scores),
                    pair_event_load,
                    priority,
                    pair_penalty,
                    max(scores),
                    tuple(sorted(pair)),
                )
                if best_pair is None or sort_key < best_pair[0]:
                    best_pair = (sort_key, list(pair))

        if best_pair is not None:
            return best_pair[1]

    raise SchedulingError(failure_message)


def pick_photographers(event, members, stats, bad_dates, director_name, assist, editors, used):
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
    risky_members = required_guides()

    minimum_green_photographers = max(
        minimum_green_photographers,
        int(event["requirements"].get("min_green_photographers", 0)),
    )
    minimum_yellow_photographers = max(
        minimum_yellow_photographers,
        int(event["requirements"].get("min_yellow_photographers", 0)),
    )
    minimum_red_photographers = max(
        minimum_red_photographers,
        int(event["requirements"].get("min_red_photographers", 0)),
    )
    max_red_photographers = min(
        max_red_photographers,
        int(event["requirements"].get("max_red_photographers", required)),
    )

    if tier == "high":
        minimum_green_photographers = max(minimum_green_photographers, min(2, required))
        target_green_photographers = min(3, required)
        target_yellow_photographers = min(1, max(0, required - target_green_photographers))
    elif tier == "standard" and required > 0:
        minimum_green_photographers = 1

    if is_creative_team_meet(event_name):
        minimum_yellow_photographers = max(minimum_yellow_photographers, 1)
        max_red_photographers = min(max_red_photographers, 2)

    if event_name == "Sunday Service":
        minimum_yellow_photographers = max(
            minimum_yellow_photographers,
            max(0, 1 - current_role_counts["yellow"]),
        )
        minimum_red_photographers = max(
            minimum_red_photographers,
            max(0, 1 - current_role_counts["red"]),
        )
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
        if name in risky_members and any(existing in risky_members for existing in photographers):
            return False

        current_with_candidate = [*photographers, name]
        remaining_slots_after_choice = required - len(current_with_candidate)
        anchor_present = has_safety_anchor(current_with_candidate, members)
        anchor_available_after_choice = any(
            is_safety_anchor(candidate_name, members)
            for candidate_name in available_shooters()
            if candidate_name != name
        )
        if name in risky_members and not anchor_present:
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
                    event=event,
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
            event=event,
        )
        photographers.append(chosen)
        minimum_green_photographers -= 1

    while minimum_yellow_photographers > 0 and len(photographers) < required:
        yellow_candidates = [
            name
            for name in available_shooters()
            if members[name]["role"] == "yellow"
            and can_add_photographer(name)
            and (tier != "high" or is_high_tier_eligible_yellow_photographer(name, members))
        ]
        chosen = choose_required_photographer(
            yellow_candidates,
            members,
            stats,
            event["event"],
            event["date"],
            tier,
            "a required yellow photographer",
            event=event,
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
            event=event,
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
                event=event,
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
        green_candidates = [
            name
            for name in green_candidates
            if photographer_score(
                name,
                members,
                stats,
                event["event"],
                event["date"],
                tier,
                event=event,
            )
            is not None
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
                event=event,
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
            if members[name]["role"] == "yellow"
            and can_add_photographer(name)
            and is_high_tier_eligible_yellow_photographer(name, members)
        ]
        yellow_candidates = [
            name
            for name in yellow_candidates
            if photographer_score(
                name,
                members,
                stats,
                event["event"],
                event["date"],
                tier,
                event=event,
            )
            is not None
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
                event=event,
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
                    event=event,
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
            if name in risky_members and any(existing in risky_members for existing in photographers):
                return None

            current_with_candidate = [*photographers, name]
            remaining_slots_after_choice = required - len(current_with_candidate)
            anchor_present = has_safety_anchor(current_with_candidate, members)
            anchor_available_after_choice = any(
                is_safety_anchor(candidate_name, members)
                for candidate_name in available_shooters()
                if candidate_name != name
            )
            if name in risky_members and not anchor_present:
                if remaining_slots_after_choice == 0 or not anchor_available_after_choice:
                    return None

            score = photographer_score(
                name,
                members,
                stats,
                event["event"],
                event["date"],
                tier,
                event=event,
            )
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
            if tier == "low" and name in risky_members:
                score += 80
            if name in risky_members and not anchor_present:
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
        photographers = trim_sunday_photographers_to_visible_limit(
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
            if name in risky_members and any(existing in risky_members for existing in photographers):
                return None

            projected_photographers = [*photographers, name]
            anchor_present = has_safety_anchor(projected_photographers, members)
            if name in risky_members and not anchor_present:
                return None

            score = photographer_score(
                name,
                members,
                stats,
                event["event"],
                event["date"],
                tier,
                event=event,
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
        photographers = trim_sunday_photographers_to_visible_limit(
            event,
            members,
            stats,
            bad_dates,
            used,
            photographers,
        )

    validate_team_composition(
        event, members, director_name, used, assist, editors, photographers
    )
    return photographers


def can_use_sunday_photographer_lineup(event, members, used, photographers):
    assigned_names = [*used, *photographers]
    counts = role_counts(assigned_names, members)
    photographer_counts = role_counts(photographers, members)
    risky_members = required_guides()
    minimum_green_photographers = int(event["requirements"].get("min_green_photographers", 0))
    minimum_yellow_photographers = int(event["requirements"].get("min_yellow_photographers", 0))
    minimum_red_photographers = int(event["requirements"].get("min_red_photographers", 0))
    max_red_photographers = int(
        event["requirements"].get("max_red_photographers", event["requirements"]["photographers"])
    )

    if any(counts[role] < 1 for role in ("green", "yellow", "red")):
        return False
    if photographer_counts["green"] < max(1, minimum_green_photographers):
        return False
    if photographer_counts["yellow"] < minimum_yellow_photographers:
        return False
    if photographer_counts["red"] < minimum_red_photographers:
        return False
    if photographer_counts["red"] > max_red_photographers:
        return False
    if is_service_event(event["event"]) and counts["red"] > 2:
        return False
    if len(risky_members.intersection(photographers)) > 1:
        return False
    if risky_members.intersection(photographers) and not has_safety_anchor(photographers, members):
        return False
    return True


def trim_sunday_photographers_to_visible_limit(
    event, members, stats, bad_dates, used, photographers
):
    required_visible_slots = int(event["requirements"]["photographers"])

    for require_balanced_shape in (True, False):
        while visible_photographer_slot_count(photographers, members) > required_visible_slots:
            current_visible_slots = visible_photographer_slot_count(photographers, members)
            best_removal = None

            for removable in photographers:
                proposed = [name for name in photographers if name != removable]
                proposed_visible_slots = visible_photographer_slot_count(proposed, members)
                if proposed_visible_slots < required_visible_slots:
                    continue
                if proposed_visible_slots >= current_visible_slots:
                    continue
                if not can_use_sunday_photographer_lineup(event, members, used, proposed):
                    continue

                strong_count, development_heavy_count = sunday_strength_metrics(
                    proposed,
                    members,
                )
                if require_balanced_shape and (
                    strong_count < 2 or development_heavy_count > 2
                ):
                    continue

                removal_score = photographer_score(
                    removable,
                    members,
                    stats,
                    event["event"],
                    event["date"],
                    event["requirements"]["tier"],
                    event=event,
                )
                if removal_score is None:
                    removal_score = 0

                removal_rank = (
                    proposed_visible_slots,
                    development_heavy_count,
                    -strong_count,
                    -removal_score,
                    members[removable]["shoot_rank"],
                    removable,
                )
                if best_removal is None or removal_rank < best_removal[0]:
                    best_removal = (removal_rank, proposed)

            if best_removal is None:
                break

            _, photographers = best_removal

        if visible_photographer_slot_count(photographers, members) <= required_visible_slots:
            break

    return photographers


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
                    event=event,
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
    if is_creative_team_meet(event["event"]):
        if not is_valid_creative_team_meet_editor_pair(editors, members):
            raise SchedulingError(
                (
                    f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must use "
                    f"either 2 decent yellow editors, a guide-capable mentor plus a yellow editor, "
                    f"or a guide-capable green plus a red editor."
                )
            )
        return

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


def validate_team_composition(event, members, director_name, used, assist, editors, photographers):
    assigned_names = [*used, *photographers]
    counts = role_counts(assigned_names, members)
    photographer_counts = role_counts(photographers, members)
    risky_members = required_guides()

    if event["requirements"].get("leaders_only"):
        non_leaders = sorted({name for name in assigned_names if not members[name].get("leader", False)})
        if non_leaders:
            raise SchedulingError(
                f"Leaders Meet on {event['date'].strftime('%Y-%m-%d')} can only include leaders. Non-leaders: {', '.join(non_leaders)}."
            )

    if len(risky_members.intersection(photographers)) > 1:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} cannot schedule Isaac and Aslvin together."
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

    if event["requirements"]["tier"] == "high":
        disallowed_photographers = [
            name for name in photographers if is_disallowed_high_tier_photographer(name, members)
        ]
        if disallowed_photographers:
            raise SchedulingError(
                f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} cannot include low-tier yellows or reds. Found: {', '.join(disallowed_photographers)}."
            )

        disallowed_editors = [
            name
            for name in editors
            if members[name]["role"] == "yellow"
            and members[name]["editor_rank"] > policy_limit("max_high_tier_yellow_editor_rank")
        ]
        if disallowed_editors:
            raise SchedulingError(
                f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} cannot include lower-tier yellow editors. Found: {', '.join(disallowed_editors)}."
            )

    minimum_green_photographers = int(event["requirements"].get("min_green_photographers", 0))
    if event["requirements"]["tier"] == "high":
        minimum_green_photographers = max(2, minimum_green_photographers)
    if minimum_green_photographers and photographer_counts["green"] < minimum_green_photographers:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include at least {minimum_green_photographers} green photographers."
        )

    minimum_yellow_photographers = int(event["requirements"].get("min_yellow_photographers", 0))
    if minimum_yellow_photographers and photographer_counts["yellow"] < minimum_yellow_photographers:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include at least {minimum_yellow_photographers} yellow photographers."
        )

    minimum_red_photographers = int(event["requirements"].get("min_red_photographers", 0))
    if minimum_red_photographers and photographer_counts["red"] < minimum_red_photographers:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include at least {minimum_red_photographers} red photographers."
        )

    max_red_photographers = int(event["requirements"].get("max_red_photographers", event["requirements"]["photographers"]))
    if photographer_counts["red"] > max_red_photographers:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} cannot have more than {max_red_photographers} red photographers."
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
        if visible_slots != event["requirements"]["photographers"]:
            raise SchedulingError(
                f"Sunday Service on {event['date'].strftime('%Y-%m-%d')} must show exactly 4 photographer slots after red pairings are collapsed. Found {visible_slots}."
            )

    if is_service_event(event["event"]) and counts["red"] > 2:
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} cannot have more than 2 reds."
        )

    if risky_members.intersection(photographers) and not has_safety_anchor(photographers, members):
        raise SchedulingError(
            f"{event['event']} on {event['date'].strftime('%Y-%m-%d')} must include a guide-capable photographer when Isaac or Aslvin are scheduled."
        )



def enforce_safety_rule(
    event, members, stats, bad_dates, director_name, used, photographers
):
    assigned_team = set(photographers)
    risky_members = required_guides()
    if not risky_members.intersection(assigned_team):
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
            name,
            members,
            stats,
            event["event"],
            event["date"],
            event["requirements"]["tier"],
            event=event,
        ),
        (
            f"Could not satisfy the safety rule for {event['date'].strftime('%Y-%m-%d')} "
            f"{event['event']}."
        ),
    )

    removable_candidates = [
        name for name in photographers if name not in risky_members and not is_safety_anchor(name, members)
    ]
    if not removable_candidates:
        raise SchedulingError(
            f"Could not satisfy the safety rule for {event['date'].strftime('%Y-%m-%d')} {event['event']}."
        )

    removable = max(
        removable_candidates,
        key=lambda name: (
            photographer_score(
                name,
                members,
                stats,
                event["event"],
                event["date"],
                event["requirements"]["tier"],
                event=event,
            ),
            name,
        ),
    )

    photographers = [replacement if name == removable else name for name in photographers]
    return photographers


def build_event_requirements(event_name, event_types):
    config = event_types[event_name]
    return {
        "director": int(config.get("directors", config.get("director", 1))),
        "assist": int(config.get("assist", 0)),
        "editors": int(config.get("editors", 0)),
        "photographers": int(config.get("photographers", 0)),
        "floor_runner": int(config.get("floor_runner", 0)),
        "shadow": int(config.get("shadow", 0)),
        "tier": str(config.get("tier", "standard")).lower(),
        "leaders_only": bool(config.get("leaders_only", False)),
        "min_green_photographers": int(config.get("min_green_photographers", 0)),
        "min_yellow_photographers": int(config.get("min_yellow_photographers", 0)),
        "min_red_photographers": int(config.get("min_red_photographers", 0)),
        "max_red_photographers": int(config.get("max_red_photographers", config.get("photographers", 0))),
    }


def update_stats(stats, event, director, assist, editors, photographers):
    event_date = event["date"]
    month = month_key(event_date)
    quarter = quarter_key(event_date.date())
    tier = event["requirements"]["tier"]
    is_weekday_low_tier = is_weekday_low_tier_event(event["event"], event_date, tier)
    upcoming_high_tier_key = event.get("next_high_tier_event_key")
    participants = set([director, *([assist] if assist else []), *editors, *photographers])

    for name in participants:
        stats[name]["total_events"] += 1
        stats[name]["monthly_events"][month] += 1
        stats[name]["last_assigned"] = event_date.date()
        if tier == "high":
            stats[name]["high_tier_events"] += 1
            stats[name]["monthly_high_tier_events"][month] += 1
            stats[name]["last_high_tier_assigned"] = event_date.date()
            stats[name]["last_high_tier_event_name"] = event["event"]
            stats[name]["high_tier_dates"].append(event_date.date())

    stats[director]["role_counts"]["director"] += 1
    stats[director]["monthly_role_counts"][month]["director"] += 1
    stats[director]["monthly_event_role_counts"][month][event["event"]]["director"] += 1
    stats[director]["quarterly_event_role_counts"][quarter][event["event"]]["director"] += 1
    stats[director]["event_role_counts_total"][event["event"]]["director"] += 1
    if is_weekday_low_tier:
        stats[director]["quarterly_weekday_low_tier_role_counts"][quarter]["director"] += 1
    if tier != "high" and upcoming_high_tier_key:
        stats[director]["upcoming_high_tier_preload_counts"][upcoming_high_tier_key] += 1
        stats[director]["upcoming_high_tier_preload_role_counts"][upcoming_high_tier_key]["director"] += 1
    if tier == "high":
        stats[director]["high_tier_role_counts"]["director"] += 1
        stats[director]["monthly_high_tier_role_counts"][month]["director"] += 1
        stats[director]["last_high_tier_role_assigned"]["director"] = event_date.date()
    if assist:
        stats[assist]["role_counts"]["assist"] += 1
        stats[assist]["monthly_role_counts"][month]["assist"] += 1
        stats[assist]["monthly_event_role_counts"][month][event["event"]]["assist"] += 1
        stats[assist]["quarterly_event_role_counts"][quarter][event["event"]]["assist"] += 1
        stats[assist]["event_role_counts_total"][event["event"]]["assist"] += 1
        if is_weekday_low_tier:
            stats[assist]["quarterly_weekday_low_tier_role_counts"][quarter]["assist"] += 1
        if tier != "high" and upcoming_high_tier_key:
            stats[assist]["upcoming_high_tier_preload_counts"][upcoming_high_tier_key] += 1
            stats[assist]["upcoming_high_tier_preload_role_counts"][upcoming_high_tier_key]["assist"] += 1
        if tier == "high":
            stats[assist]["high_tier_role_counts"]["assist"] += 1
            stats[assist]["monthly_high_tier_role_counts"][month]["assist"] += 1
            stats[assist]["last_high_tier_role_assigned"]["assist"] = event_date.date()
    for name in editors:
        stats[name]["role_counts"]["editor"] += 1
        stats[name]["monthly_role_counts"][month]["editor"] += 1
        stats[name]["monthly_event_role_counts"][month][event["event"]]["editor"] += 1
        stats[name]["quarterly_event_role_counts"][quarter][event["event"]]["editor"] += 1
        stats[name]["event_role_counts_total"][event["event"]]["editor"] += 1
        if is_weekday_low_tier:
            stats[name]["quarterly_weekday_low_tier_role_counts"][quarter]["editor"] += 1
        if tier != "high" and upcoming_high_tier_key:
            stats[name]["upcoming_high_tier_preload_counts"][upcoming_high_tier_key] += 1
            stats[name]["upcoming_high_tier_preload_role_counts"][upcoming_high_tier_key]["editor"] += 1
        if tier == "high":
            stats[name]["high_tier_role_counts"]["editor"] += 1
            stats[name]["monthly_high_tier_role_counts"][month]["editor"] += 1
            stats[name]["last_high_tier_role_assigned"]["editor"] = event_date.date()
    if len(editors) == 2:
        pair_key = editor_pair_key(editors)
        for name in editors:
            stats[name]["quarterly_event_editor_pair_counts"][quarter][event["event"]][
                pair_key
            ] += 1
            stats[name]["event_editor_pair_counts_total"][event["event"]][pair_key] += 1
    for name in photographers:
        stats[name]["role_counts"]["photographer"] += 1
        stats[name]["monthly_role_counts"][month]["photographer"] += 1
        stats[name]["monthly_event_role_counts"][month][event["event"]]["photographer"] += 1
        stats[name]["quarterly_event_role_counts"][quarter][event["event"]]["photographer"] += 1
        stats[name]["event_role_counts_total"][event["event"]]["photographer"] += 1
        if is_weekday_low_tier:
            stats[name]["quarterly_weekday_low_tier_role_counts"][quarter]["photographer"] += 1
        if tier != "high" and upcoming_high_tier_key:
            stats[name]["upcoming_high_tier_preload_counts"][upcoming_high_tier_key] += 1
            stats[name]["upcoming_high_tier_preload_role_counts"][upcoming_high_tier_key]["photographer"] += 1
        if tier == "high":
            stats[name]["high_tier_role_counts"]["photographer"] += 1
            stats[name]["monthly_high_tier_role_counts"][month]["photographer"] += 1
            stats[name]["last_high_tier_role_assigned"]["photographer"] = event_date.date()


def generate_schedule():
    global SCHEDULER_POLICY
    sync_universal_scheduler_if_needed()

    SCHEDULER_POLICY = load_scheduler_policy()
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

    for event in events:
        event["requirements"] = build_event_requirements(event["event"], event_types)
    annotate_event_series(events)
    annotate_upcoming_high_tier_events(events)

    fieldnames = google_sheets_layout["sheet_layout"]["canonical_scheduler_format"][
        "columns"
    ]

    stats = init_stats(members)
    rows = []

    for event in events:
        used = set()

        director = pick_director(event, members, stats, bad_dates)
        used.add(director)

        assist = pick_assist(event, members, stats, bad_dates, director, used)
        if assist:
            used.add(assist)

        editors = pick_editors(event, members, stats, bad_dates, director, used)
        used.update(editors)

        photographers = pick_photographers(
            event, members, stats, bad_dates, director, assist, editors, used
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
