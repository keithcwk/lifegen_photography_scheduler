import calendar
import csv
import re
from collections import Counter
from datetime import datetime, timedelta
from functools import partial
from itertools import combinations
from pathlib import Path

import yaml

from universal_scheduler import (
    DATE_FORMAT,
    EVENT_LINE_PATTERN,
    UniversalSchedulerValidationError,
    iter_active_lines,
    normalize_quarter,
    quarter_key,
    sync_universal_scheduler_if_needed,
)

BASE = Path(__file__).resolve().parents[1]
EVENTS_PATH = BASE / "data/events.md"
BAD_DATES_PATH = BASE / "data/bad_dates.md"
OUTPUT_PATH = BASE / "output/schedule.csv"
STYLE_OUTPUT_PATH = BASE / "output/google_sheets_styles.yaml"

CREATIVE_TEAM_MEET_PAIR_RULE = (
    "either 2 decent yellow editors, a guide-capable mentor plus a yellow editor, "
    "or a guide-capable green plus a red editor."
)
SESSION_SEPARATOR = "|"
ROLES = ("director", "assist", "sde_director", "editor", "photographer", "floor_runner")
ROLE_ORDER = {"green": 0, "yellow": 1, "red": 2}
RANK_FIELD = {
    "director": "direct_rank",
    "assist": "direct_rank",
    "sde_director": "editor_rank",
    "editor": "editor_rank",
    "photographer": "shoot_rank",
    "floor_runner": "shoot_rank",
}
WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
BORDER_STYLES = {"SOLID", "SOLID_MEDIUM", "SOLID_THICK"}
STYLE_SECTIONS = (
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
)
CANONICAL_COLUMNS = {
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
    "sde_director",
    "sde_1",
    "sde_2",
    "shadow",
}
DEFAULT_SCHEDULER_POLICY = {
    "limits": {
        "max_assignments_per_member_per_month": 3,
        # Per-tier monthly caps; 0 falls back to max_assignments_per_member_per_month.
        "max_green_assignments_per_month": 0,
        "max_yellow_assignments_per_month": 0,
        "max_director_track_directs_per_month": 1,
        "max_red_assignments_per_month": 2,
        "max_high_tier_yellow_shoot_rank": 8,
        "max_high_tier_yellow_editor_rank": 4,
        "high_tier_reserve_window_days": 14,
        "high_tier_recent_window_days": 10,
        "max_same_high_tier_event_assignments": 3,
        "creative_team_meet_max_yellow_editor_rank": 4,
        "creative_team_meet_anchor_yellow_shoot_rank": 10,
        "creative_team_meet_editor_soft_cap_per_run": 2,
        "red_idle_days": 28,
        "core_green_max_direct_rank": 5,
        # Yellows up to this editor rank may oversee editors below high tier (growth slot).
        "max_sde_director_yellow_editor_rank": 6,
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
        "repeated_monthly_director_penalty": 200,
        "same_high_tier_event_overuse_penalty": 200,
        "multi_day_high_tier_early_day_strength_reserve": 10,
        "upcoming_high_tier_reserve_penalty": 35,
        "upcoming_high_tier_preload_penalty": 90,
        "upcoming_high_tier_preload_same_role_penalty": 50,
    },
    "weights": {
        # Below high tier, extra cost per green SDE director (raise it to hand the slot to yellows).
        "green_sde_director": 0,
        # Below high tier, cost per direct_rank step so stronger greens direct more often.
        "green_direct_rank": 8,
        # Green SDE directors below high tier skip the monthly cap and are scored on these alone:
        # cost per SDE director turn so far, and per event already served this month.
        "green_sde_director_turn": 48,
        "green_sde_director_month": 12,
        # Greens/strong editors under an SDE director stack the team; this cost per such editor.
        "strong_editor_under_sde_director": 60,
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
    "fallbacks": {"blank_rank_value": 50},
    "safety": {"required_guides_for": ["Isaac", "Aslvin"]},
    "event_roles": {
        # Which event name carries each built-in behaviour; rename here for another ministry.
        "balanced_service": "Sunday Service",
        "mentor_editor_pair": ["Creative Team Meet", "Creative Team Advance"],
        "mid_tier_editor": "Lifegen Prayer",
        "leaders_meet": "Leaders Meet",
        "service_marker": "service",
        "run_balanced": ["Creative Team Meet", "Creative Team Advance", "Lifegen Prayer"],
    },
    "special_rules": {
        "trainee_service_directing_from": "2026-08-01",
        "frequency_exempt_events": [
            "Power Conference KL",
            "Power Conference JB",
            "Power Festival",
        ],
    },
}
SCHEDULER_POLICY = DEFAULT_SCHEDULER_POLICY

# Per-run state, (re)built by generate_schedule().
members = {}
stats = {}
bad_dates = {}
pair_counts = Counter()


class SchedulingError(Exception):
    pass


def check(condition, message):
    if not condition:
        raise ValueError(message)


def load_yaml(relative_path):
    return yaml.safe_load((BASE / relative_path).read_text()) or {}


def load_scheduler_policy():
    raw = load_yaml("config/scheduler_policy.yaml")
    return {
        section: {**defaults, **raw[section]} if isinstance(raw.get(section), dict) else dict(defaults)
        for section, defaults in DEFAULT_SCHEDULER_POLICY.items()
    }


def ensure_scheduler_policy():
    """Load the policy file for callers (push, CLI) that use helpers before generate_schedule()."""
    global SCHEDULER_POLICY
    if SCHEDULER_POLICY is DEFAULT_SCHEDULER_POLICY:
        SCHEDULER_POLICY = load_scheduler_policy()


def _policy(section, name):
    return int(SCHEDULER_POLICY[section][name])


policy_limit = partial(_policy, "limits")
policy_weight = partial(_policy, "weights")
policy_penalty = partial(_policy, "penalties")
policy_bonus = partial(_policy, "bonuses")
policy_fallback = partial(_policy, "fallbacks")


def required_guides():
    return set(SCHEDULER_POLICY["safety"].get("required_guides_for", []))


def event_role_name(key):
    return SCHEDULER_POLICY["event_roles"][key]


def is_event_named(event_name, key):
    names = event_role_name(key)
    return event_name in names if isinstance(names, list) else event_name == names


def is_run_balanced_event(event_name):
    return is_event_named(event_name, "run_balanced")


def trainee_may_direct_services(event):
    """Trainee directors get standard services from the configured date onward."""
    starts_on = SCHEDULER_POLICY["special_rules"].get("trainee_service_directing_from")
    if not starts_on:
        return True
    if isinstance(starts_on, str):
        starts_on = datetime.strptime(starts_on, "%Y-%m-%d").date()
    return event["date"].date() >= starts_on


def is_frequency_exempt_event(event_name):
    """Special events (e.g. Power Conferences) whose slots ignore frequency fairness."""
    return event_name in set(SCHEDULER_POLICY["special_rules"].get("frequency_exempt_events", []))


# --------------------------------------------------------------------------- input files


def event_type(event_name):
    """'Power Conference KL | Night 1' is a session of the 'Power Conference KL' event type."""
    return event_name.split(SESSION_SEPARATOR, 1)[0].strip()


def parse_event_file():
    explicit_events = []
    exclusions = set()
    section = "events"

    for _, line in iter_active_lines(EVENTS_PATH.read_text()):
        if line.startswith("#"):
            section = {"## exclusions": "exclusions", "## events": "events"}.get(line.lower(), section)
            continue

        match = EVENT_LINE_PATTERN.fullmatch(line)
        if not match:
            continue

        date_str, event_name = match.groups()
        event_date = datetime.strptime(date_str, DATE_FORMAT)
        event_name = event_name.strip()
        if section == "exclusions":
            exclusions.add((event_date.date(), event_name))
        else:
            explicit_events.append(
                {"date": event_date, "event": event_name, "type": event_type(event_name), "explicit": True}
            )

    return explicit_events, exclusions


def parse_events():
    explicit_events, exclusions = parse_event_file()

    deduped = {}
    for event in [*explicit_events, *build_recurring_events(explicit_events)]:
        key = (event["date"].date(), event["event"])
        if key in exclusions:
            continue
        event["explicit"] = event["explicit"] or key in deduped and deduped[key]["explicit"]
        deduped[key] = event

    events = sorted(deduped.values(), key=lambda event: event["date"])
    # A special event on a Sunday replaces the recurring Sunday Service; an explicitly listed one stays.
    replaced = {
        event["date"].date()
        for event in events
        if not is_event_named(event["type"], "balanced_service") and event["date"].weekday() == calendar.SUNDAY
    }
    return [
        event
        for event in events
        if event["explicit"]
        or not (is_event_named(event["type"], "balanced_service") and event["date"].date() in replaced)
    ]


def nth_weekday_of_month(year, month, weekday_index, occurrence):
    if occurrence not in ("first", "last"):
        raise ValueError(f"Unsupported recurring occurrence: {occurrence}")

    days = [week[weekday_index] for week in calendar.monthcalendar(year, month) if week[weekday_index]]
    return days[0] if occurrence == "first" else days[-1]


def recurring_event(event_date, rule):
    event_name = str(rule["event"]).strip()
    return {"date": event_date, "event": event_name, "type": event_type(event_name), "explicit": False}


def build_recurring_events(base_events):
    config = load_yaml("config/recurring_events.yaml")
    rules = config.get("recurring_events", [])
    if not base_events or not rules:
        return []

    extra_months = int(config.get("generation_window", {}).get("months_after_last_explicit_event", 0))
    dates = [event["date"] for event in base_events]
    start, last = min(dates), max(dates)
    last_month_index = last.year * 12 + last.month - 1 + extra_months
    months = range(start.year * 12 + start.month - 1, last_month_index + 1)

    events = []
    for year, month_index in (divmod(index, 12) for index in months):
        for rule in rules:
            frequency = str(rule.get("frequency", "")).lower()
            if frequency == "weekly":
                continue
            if frequency != "monthly":
                raise ValueError(f"Unsupported recurring event frequency: {rule.get('frequency')}")

            weekday = str(rule["weekday"]).lower()
            occurrence = str(rule["occurrence"]).lower()
            if weekday not in WEEKDAY_NAMES:
                raise ValueError(f"Unsupported recurring event weekday: {rule['weekday']}")

            month = month_index + 1
            day = nth_weekday_of_month(year, month, WEEKDAY_NAMES.index(weekday), occurrence)
            events.append(recurring_event(datetime(year, month, day), rule))

    end_year, end_month_index = divmod(last_month_index, 12)
    end_month = end_month_index + 1
    current = start
    end = datetime(end_year, end_month, calendar.monthrange(end_year, end_month)[1])
    while current <= end:
        for rule in rules:
            if str(rule.get("frequency", "")).lower() != "weekly":
                continue
            if str(rule["weekday"]).lower() == WEEKDAY_NAMES[current.weekday()]:
                events.append(recurring_event(current, rule))
        current += timedelta(days=1)

    return events


def parse_bad_dates():
    if not BAD_DATES_PATH.exists():
        return {}

    blocked_by_member = {}
    quarter = None
    member = None

    for line_number, line in iter_active_lines(BAD_DATES_PATH.read_text()):
        where = f"{BAD_DATES_PATH}:{line_number}"
        if not line or line.startswith("# "):
            continue

        if line.startswith("## "):
            quarter, member = normalize_quarter(line[3:]), None
        elif line.startswith("### "):
            check(quarter is not None, f"{where} member heading appears before a quarter heading.")
            member = line[4:].strip()
            blocked_by_member.setdefault(member, set())
        elif line.startswith("- "):
            check(member is not None, f"{where} date entry must be under a quarter and member heading.")
            blocked_date = datetime.strptime(line[2:].strip(), DATE_FORMAT).date()
            check(
                quarter_key(blocked_date) == quarter,
                f"{where} date {blocked_date} does not belong to {quarter}.",
            )
            blocked_by_member[member].add(blocked_date)
        elif quarter is not None:
            raise ValueError(
                f"{where} invalid line '{line}'. "
                f"Use quarter headings, member headings, and bullet dates."
            )

    return blocked_by_member


def build_members(team):
    """Flatten the team file into one lookup of member -> capabilities and ranks."""
    ensure_scheduler_policy()
    blank_rank = policy_fallback("blank_rank_value")
    built = {}

    def add(person, role, **fields):
        person = person if isinstance(person, dict) else {"name": str(person)}
        built[person["name"]] = {
            "role": role,
            "can_direct": False,
            "can_edit": False,
            "can_shoot": True,
            "director_track": False,
            "leader": False,
            "can_guide": False,
            "weekday_late": bool(person.get("weekday_late", False)),
            **fields,
        }
        return person

    def flag(person, key, alias, default):
        return bool(person.get(key, person.get(alias, default)))

    for person in team["greens"]:
        add(
            person,
            "green",
            can_direct=True,
            can_edit=True,
            shoot_rank=int(person.get("shoot_rank", blank_rank)),
            direct_rank=int(person.get("direct_rank", blank_rank)),
            editor_rank=int(person.get("editor_rank", blank_rank)),
            leader=flag(person, "leaders", "leader", True),
            can_guide=flag(person, "guide", "can_guide", True),
        )

    for person in team["yellows"]:
        director_track = bool(person.get("director_track", False))
        add(
            person,
            "yellow",
            can_direct=director_track,
            can_edit=True,
            director_track=director_track,
            shoot_rank=int(person.get("shoot_rank", person.get("editor_rank", blank_rank))),
            direct_rank=int(person.get("direct_rank", blank_rank)),
            editor_rank=int(person.get("editor_rank", blank_rank)),
            leader=flag(person, "leaders", "leader", False),
            can_guide=flag(person, "guide", "can_guide", False),
        )

    for person in team["reds"]:
        person = person if isinstance(person, dict) else {"name": str(person)}
        add(
            person,
            "red",
            can_edit=bool(person.get("can_edit", "editor_rank" in person)),
            shoot_rank=int(person.get("shoot_rank", 999)),
            direct_rank=999,
            editor_rank=int(person.get("editor_rank", 999)),
            can_guide=flag(person, "guide", "can_guide", False),
        )

    for person in team.get("shadows", []):
        add(
            person,
            "shadow",
            can_shoot=False,
            shoot_rank=blank_rank,
            direct_rank=blank_rank,
            editor_rank=blank_rank,
        )

    return built


def build_event_requirements(config):
    photographers = int(config.get("photographers", 0))
    return {
        "editors": int(config.get("editors", 0)),
        "photographers": photographers,
        "assist": int(config.get("assist", 0)),
        "sde_director": int(config.get("sde_director", 0)),
        "floor_runner": int(config.get("floor_runner", 0)),
        "tier": str(config.get("tier", "standard")).lower(),
        "leaders_only": bool(config.get("leaders_only", False)),
        "greens_only": bool(config.get("greens_only", False)),
        "min_green_photographers": int(config.get("min_green_photographers", 0)),
        "min_yellow_photographers": int(config.get("min_yellow_photographers", 0)),
        "target_yellow_photographers": int(config.get("target_yellow_photographers", 0)),
        "min_red_photographers": int(config.get("min_red_photographers", 0)),
        "max_red_photographers": int(config.get("max_red_photographers", photographers)),
        "director_edits": bool(config.get("director_edits", False)),
        "extra_red_photographer": int(config.get("extra_red_photographer", 0)),
    }


def annotate_event_series(events):
    """Group consecutive same-name dates into runs (multi-day camps, conferences)."""
    runs = []
    for event in events:
        previous = runs[-1][-1] if runs else None
        # Sessions on one date and consecutive dates of the same event type are one run.
        same_run = (
            previous is not None
            and previous["type"] == event["type"]
            and (event["date"].date() - previous["date"].date()).days in (0, 1)
        )
        if same_run:
            runs[-1].append(event)
        else:
            runs.append([event])

    for run in runs:
        for index, event in enumerate(run, start=1):
            event["series_length"] = len(run)
            event["series_is_final_day"] = index == len(run)


def annotate_upcoming_high_tier_events(events):
    """Tell each normal event which high tier event is coming up next, and how soon."""
    upcoming = None

    for event in reversed(events):
        event["event_key"] = f"{event['event']}@{event['date'].date().isoformat()}"
        event["days_until_next_high_tier"] = None
        event["next_high_tier_event_key"] = None

        if tier(event) == "high":
            upcoming = event
            continue
        if upcoming is None:
            continue

        gap_days = (upcoming["date"].date() - event["date"].date()).days
        if gap_days > 0:
            event["days_until_next_high_tier"] = gap_days
            event["next_high_tier_event_key"] = upcoming["event_key"]


# --------------------------------------------------------------------------- config validation


def validate_hex_color(value, field_name):
    check(
        isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value),
        f"Invalid color for {field_name}: {value!r}. Use hex like '#D9EAF4'.",
    )


def validate_boolean(value, field_name):
    check(isinstance(value, bool), f"Invalid boolean for {field_name}: {value!r}.")


def validate_google_sheets_styles(styles):
    where = "in config/google_sheets_styles.yaml."
    missing_sections = sorted(set(STYLE_SECTIONS) - set(styles))
    check(
        not missing_sections,
        "Missing sections in config/google_sheets_styles.yaml: " + ", ".join(missing_sections),
    )

    sheet = styles["sheet"]
    validate_boolean(sheet["freeze_header_row"], "sheet.freeze_header_row")
    height = sheet["header_row_height"]
    check(
        isinstance(height, int) and height >= 1,
        f"Invalid integer for sheet.header_row_height: {height!r}. Must be >= 1.",
    )
    check(
        isinstance(sheet["font_family"], str) and sheet["font_family"].strip(),
        f"Invalid sheet.font_family {where}",
    )
    check(sheet["horizontal_alignment"] in {"LEFT", "CENTER", "RIGHT"}, f"Invalid sheet.horizontal_alignment {where}")
    check(sheet["vertical_alignment"] in {"TOP", "MIDDLE", "BOTTOM"}, f"Invalid sheet.vertical_alignment {where}")

    for section_name in ("pivot_column", "event_name", "date_column", "availability_row"):
        section = styles[section_name]
        check(
            section["font_weight"] in {"normal", "bold"},
            f"Invalid font weight for {section_name}.font_weight: {section['font_weight']!r}. "
            f"Use one of ['bold', 'normal'].",
        )
        validate_hex_color(section["background_color"], f"{section_name}.background_color")
        validate_hex_color(section["text_color"], f"{section_name}.text_color")

    check(
        styles["event_name"].get("wrap_strategy") in {"OVERFLOW_CELL", "LEGACY_WRAP", "CLIP", "WRAP"},
        f"Invalid event_name.wrap_strategy {where}",
    )

    palette = styles["month_palette"].get("colors", [])
    check(isinstance(palette, list) and palette, "month_palette.colors must be a non-empty list.")
    for index, color in enumerate(palette):
        validate_hex_color(color, f"month_palette.colors[{index}]")

    for section_name in ("month_group_border", "column_separator", "header_divider"):
        section = styles[section_name]
        validate_boolean(section["enabled"], f"{section_name}.enabled")
        validate_hex_color(section["color"], f"{section_name}.color")
        check(section["style"] in BORDER_STYLES, f"Invalid {section_name}.style {where}")

    validate_boolean(styles["alternating_rows"]["enabled"], "alternating_rows.enabled")
    for field_name in ("odd_row_background", "even_row_background"):
        validate_hex_color(styles["alternating_rows"][field_name], f"alternating_rows.{field_name}")

    validate_boolean(styles["borders"]["enabled"], "borders.enabled")
    validate_hex_color(styles["borders"]["color"], "borders.color")


def validate_google_sheets_layout(layout):
    sheet_layout = layout.get("sheet_layout")
    check(sheet_layout, "Missing 'sheet_layout' in config/google_sheets_layout.yaml.")

    columns = sheet_layout.get("canonical_scheduler_format", {}).get("columns")
    check(columns, "Missing canonical_scheduler_format.columns in config/google_sheets_layout.yaml.")

    missing_columns = sorted(CANONICAL_COLUMNS - set(columns))
    check(
        not missing_columns,
        "Missing canonical scheduler columns in config/google_sheets_layout.yaml: "
        + ", ".join(missing_columns),
    )


def write_styles_manifest(styles):
    STYLE_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STYLE_OUTPUT_PATH, "w") as f:
        yaml.safe_dump(styles, f, sort_keys=False)


# --------------------------------------------------------------------------- small lookups


def tier(event):
    return event["requirements"]["tier"]


def day(event):
    return event["date"].strftime("%Y-%m-%d")


def label(event):
    return f"{day(event)} {event['event']}"


def month_key(event_date):
    return event_date.year, event_date.month


def is_available(name, event):
    return event["date"].date() not in bad_dates.get(name, set())


def is_safety_anchor(name):
    return members[name]["can_guide"]


def has_safety_anchor(names):
    return any(is_safety_anchor(name) for name in names)


def role_counts(names):
    return Counter(members[name]["role"] for name in names)


def is_service_event(event_name):
    return event_role_name("service_marker").lower() in event_name.lower()


def is_weekday_low_tier_event(event):
    return tier(event) == "low" and event["date"].weekday() < calendar.SATURDAY


def blocked_by_event_rules(name, event, relax_monthly_limit=False):
    """Event-level gates every role shares: leaders-only, greens-only, monthly cap."""
    member, requirements = members[name], event["requirements"]
    return (
        (requirements["leaders_only"] and not member["leader"])
        or (requirements["greens_only"] and member["role"] != "green")
        or (not relax_monthly_limit and over_monthly_cap(name, event))
    )


def is_sde_director(name, event=None):
    """Greens and capable yellow editors may oversee the editors; high tier keeps the stricter rank."""
    member = members[name]
    limit_key = (
        "max_high_tier_yellow_editor_rank"
        if event is None or tier(event) == "high"
        else "max_sde_director_yellow_editor_rank"
    )
    return member["can_edit"] and (member["role"] == "green" or member["editor_rank"] <= policy_limit(limit_key))


def is_stacking_editor(name):
    """A green or strong editor: under an SDE director they make the editing team too strong."""
    return members[name]["role"] == "green" or is_strong_editor(name)


def is_strong_editor(name):
    return members[name]["editor_rank"] <= 4


def is_high_tier_eligible_yellow_photographer(name):
    member = members[name]
    return member["role"] == "yellow" and member["shoot_rank"] <= policy_limit("max_high_tier_yellow_shoot_rank")


def is_disallowed_high_tier_photographer(name):
    member = members[name]
    return member["role"] == "red" or (
        member["role"] == "yellow" and member["shoot_rank"] > policy_limit("max_high_tier_yellow_shoot_rank")
    )


def is_strong_sunday_photographer(name):
    member = members[name]
    return member["role"] != "red" and member["shoot_rank"] <= 8


def is_development_heavy_sunday_photographer(name):
    member = members[name]
    return member["role"] == "red" or (member["role"] == "yellow" and member["shoot_rank"] >= 9)


def sunday_strength_metrics(photographers):
    return (
        sum(1 for name in photographers if is_strong_sunday_photographer(name)),
        sum(1 for name in photographers if is_development_heavy_sunday_photographer(name)),
    )


def prefer(names, keep):
    """Narrow a candidate pool, unless that would empty it."""
    return [name for name in names if keep(name)] or names


def available_names(event, used):
    return [name for name in members if name not in used and is_available(name, event)]


def choose_under_cap_first(candidate_names, score_fn, failure_message):
    """Prefer members still under the monthly cap; go over it only when nobody else can serve."""
    try:
        return choose_best_candidate(candidate_names, lambda name: score_fn(name, False), failure_message)
    except SchedulingError:
        return choose_best_candidate(candidate_names, lambda name: score_fn(name, True), failure_message)


def choose_best_candidate(candidate_names, score_fn, failure_message):
    scored = [(score, name) for name in candidate_names if (score := score_fn(name)) is not None]
    if not scored:
        raise SchedulingError(failure_message)
    return min(scored)[1]


# --------------------------------------------------------------------------- display order


def photographer_display_rank(name):
    member = members[name]
    return (ROLE_ORDER.get(member["role"], 2), member["shoot_rank"], name)


def editor_display_rank(name):
    member = members[name]
    return (member["editor_rank"], ROLE_ORDER[member["role"]], name)


def guide_display_rank(name):
    member = members[name]
    return (0 if member["role"] == "green" else 1, member["shoot_rank"], name)


def format_photographer_slots(photographers):
    """Collapse each supervised member and their guide into one `Name + Guide` slot."""
    ordered = sorted(photographers, key=photographer_display_rank)
    risky_members = required_guides()
    guides = []

    for risky_name in [name for name in ordered if name in risky_members]:
        options = [
            name
            for name in ordered
            if name != risky_name and name not in guides and is_safety_anchor(name)
        ]
        if options:
            guides.append(min(options, key=guide_display_rank))

    slots = []
    for name in ordered:
        if name in guides:
            continue
        paired = [guide for guide in ordered if guide in guides and guide != name] if name in risky_members else []
        slots.append(f"{name} + {paired[0]}" if paired else name)
    return slots


def visible_photographer_slot_count(photographers):
    return len(format_photographer_slots(photographers))


def build_output_row(event, crew, fieldnames):
    row = dict.fromkeys(fieldnames, "")
    row["event"] = event["event"]
    row["date"] = day(event)
    for role in ("director", "assist", "sde_director", "floor_runner"):
        row[role] = crew[role][0] if crew[role] else ""

    for index, photographer in enumerate(format_photographer_slots(crew["photographer"])[:5], start=1):
        row[f"photographer_{index}"] = photographer
    for index, editor in enumerate(sorted(crew["editor"], key=editor_display_rank)[:2], start=1):
        row[f"sde_{index}"] = editor

    return row


# --------------------------------------------------------------------------- assignment history


def new_member_stats():
    return {
        "counts": Counter(),
        "last_assigned": None,
        "last_high_tier_assigned": None,
        "last_high_tier_event": None,
        "last_high_tier_role_assigned": {},
        "high_tier_dates": [],
    }


def counts_of(name):
    return stats[name]["counts"]


def event_role_repeats(name, event, roles=ROLES, whole_run=None):
    """How often `name` already served this event: whole run for run-balanced events, else this quarter."""
    counts, event_name = counts_of(name), event["type"]
    if whole_run is None:
        whole_run = is_run_balanced_event(event_name)
    if whole_run:
        return sum(counts["event_role", event_name, role] for role in roles)

    quarter = quarter_key(event["date"])
    return sum(counts["quarter_event_role", quarter, event_name, role] for role in roles)


def editor_pair_repeats(editors, event):
    if len(editors) != 2:
        return 0

    pair = tuple(sorted(editors))
    if is_run_balanced_event(event["type"]):
        return pair_counts["run", event["type"], pair]
    return pair_counts["quarter", quarter_key(event["date"]), event["type"], pair]


def update_stats(event, crew):
    event_name, assigned_date = event["type"], event["date"].date()
    month, quarter = month_key(event["date"]), quarter_key(event["date"])
    high_tier, exempt = tier(event) == "high", is_frequency_exempt_event(event_name)
    weekday_low_tier = is_weekday_low_tier_event(event)
    preload_key = None if high_tier else event["next_high_tier_event_key"]

    # Frequency-exempt special events skip normal-load fairness, but high-tier ones still
    # track high-tier/per-event counters so the same crew rotates across the event's days.
    participants = {name for names in crew.values() for name in names}
    for name in participants:
        person = stats[name]
        if not exempt:
            person["counts"].update(["total", ("month", month)])
            person["last_assigned"] = assigned_date
        if high_tier:
            person["counts"].update(["high", ("high_month", month)])
            person["last_high_tier_assigned"] = assigned_date
            person["last_high_tier_event"] = event_name
            person["high_tier_dates"].append(assigned_date)

    def bump(name, role):
        person = stats[name]
        keys = [("quarter_event_role", quarter, event_name, role)]
        if not exempt:
            keys += [
                ("role", role),
                ("month_role", month, role),
                ("month_event_role", month, event_name, role),
                ("event_role", event_name, role),
            ]
            if weekday_low_tier:
                keys.append(("weekday_low_role", quarter, role))
            if preload_key:
                keys += [("preload", preload_key), ("preload_role", preload_key, role)]
        if high_tier:
            keys += [("high_role", role), ("high_month_role", month, role)]
            person["last_high_tier_role_assigned"][role] = assigned_date
        person["counts"].update(keys)

    for role, names in crew.items():
        for name in names:
            bump(name, role)

    editors = crew["editor"]
    if not exempt and len(editors) == 2:
        pair = tuple(sorted(editors))
        pair_counts.update([("run", event_name, pair), ("quarter", quarter, event_name, pair)])


# --------------------------------------------------------------------------- scoring


def fairness_penalty(name, event, capped=True):
    person = stats[name]
    high_tier = tier(event) == "high"
    monthly_events = person["counts"]["month", month_key(event["date"])]
    serve_weight = policy_weight("total_serve_count")
    penalty = person["counts"]["total"] * serve_weight + monthly_events * serve_weight * 2

    monthly_limit = monthly_cap(name)
    if capped and monthly_limit > 0 and monthly_events >= monthly_limit:
        penalty += (monthly_events - monthly_limit + 1) * (280 if high_tier else 220)

    if person["last_assigned"] is None:
        return penalty - 6

    gap = (event["date"].date() - person["last_assigned"]).days
    consecutive = policy_penalty("consecutive_event_penalty")
    if gap < 7:
        penalty += consecutive // 2 if high_tier else consecutive
    elif gap < 14:
        penalty += 4 if high_tier else max(1, consecutive - 10)
    elif gap < 21:
        penalty += 2 if high_tier else 5
    return penalty


def monthly_cap(name):
    """Greens carry more than yellows, reds least; a tier without its own cap uses the general one."""
    tier_key = f"max_{members[name]['role']}_assignments_per_month"
    if SCHEDULER_POLICY["limits"].get(tier_key):
        return policy_limit(tier_key)
    return policy_limit("max_assignments_per_member_per_month")


def is_core_green(name):
    member = members[name]
    return member["role"] == "green" and member["direct_rank"] <= policy_limit("core_green_max_direct_rank")


def is_idle_red(name, event):
    last = stats[name]["last_assigned"]
    return members[name]["role"] == "red" and (
        last is None or (event["date"].date() - last).days >= policy_limit("red_idle_days")
    )


def over_monthly_cap(name, event):
    limit = monthly_cap(name)
    return (
        tier(event) != "high"
        and not is_frequency_exempt_event(event["event"])
        and limit > 0
        and counts_of(name)["month", month_key(event["date"])] >= limit
    )


def reached_monthly_red_limit(name, event):
    limit = policy_limit("max_red_assignments_per_month")
    return (
        members[name]["role"] == "red"
        and limit > 0
        and counts_of(name)["month", month_key(event["date"])] >= limit
    )


def has_adjacent_high_tier_same_role_conflict(name, event, role):
    person = stats[name]
    last_same_role = person["last_high_tier_role_assigned"].get(role)
    return (
        last_same_role is not None
        and 0 < (event["date"].date() - last_same_role).days <= 2
        and person["last_high_tier_event"] != event["type"]
    )


def high_tier_role_penalties(name, event, role):
    """Combined high-tier rotation + repeat + recency penalties for a role."""
    person, counts = stats[name], counts_of(name)
    event_date, month = event["date"].date(), month_key(event["date"])

    penalty = (
        counts["high"] * 18
        + counts["high_month", month] * 28
        + counts["high_role", role] * 10
        + counts["high_month_role", month, role] * 18
    )
    for last_assigned, near, close in (
        (person["last_high_tier_assigned"], 45, 24),
        (person["last_high_tier_role_assigned"].get(role), 65, 32),
    ):
        if last_assigned is not None:
            gap = (event_date - last_assigned).days
            penalty += near if gap < 3 else close if gap < 8 else 0

    repeats = event_role_repeats(name, event, whole_run=False)
    penalty += repeats * policy_penalty("repeated_high_tier_event_penalty")
    run_cap = policy_limit("max_same_high_tier_event_assignments")
    if 0 < run_cap <= repeats:
        # Soft cap: strong people may still repeat across a multi-day run, but it costs.
        penalty += (repeats - run_cap + 1) * policy_penalty("same_high_tier_event_overuse_penalty")

    window_days = policy_limit("high_tier_recent_window_days")
    if window_days > 0:
        gaps = [
            gap
            for assigned in person["high_tier_dates"]
            if 0 < (gap := (event_date - assigned).days) <= window_days
        ]
        penalty += (len(gaps) + any(gap <= 2 for gap in gaps)) * policy_penalty(
            "recent_high_tier_window_penalty"
        )
    return penalty


def upcoming_high_tier_reserve_penalty(event, member, role):
    """Keep strong members free in the run-up to a high tier event."""
    gap_days = event["days_until_next_high_tier"]
    reserve_window = policy_limit("high_tier_reserve_window_days")
    if tier(event) == "high" or gap_days is None or reserve_window <= 0 or gap_days > reserve_window:
        return 0

    if role in ("director", "assist"):
        if member["role"] != "green":
            return 0
        threshold = 6
    elif role in ("editor", "sde_director"):
        if not member["can_edit"] or member["role"] == "red":
            return 0
        threshold = 4 if member["role"] == "yellow" else 6
    else:  # photographer, floor runner
        if member["role"] == "red":
            return 0
        threshold = (
            policy_limit("max_high_tier_yellow_shoot_rank") if member["role"] == "yellow" else 6
        )

    strength_points = max(0, threshold - member[RANK_FIELD[role]] + 1)
    proximity_factor = 2 if gap_days <= max(7, reserve_window // 2) else 1
    return strength_points * proximity_factor * policy_penalty("upcoming_high_tier_reserve_penalty")


def upcoming_high_tier_preload_penalty(name, event, role):
    """Discourage reusing whoever already served in the lead-up to the same high tier event."""
    reserve_key = event["event_key"] if tier(event) == "high" else event["next_high_tier_event_key"]
    if not reserve_key:
        return 0

    counts = counts_of(name)
    return counts["preload", reserve_key] * policy_penalty("upcoming_high_tier_preload_penalty") + counts[
        "preload_role", reserve_key, role
    ] * policy_penalty("upcoming_high_tier_preload_same_role_penalty")


def multi_day_high_tier_strength_adjustment(event, member, role):
    """Hold the strongest people back for the final day of a multi-day high tier run."""
    if tier(event) != "high" or event["series_length"] < 2:
        return 0

    strength_points = max(0, 12 - member[RANK_FIELD[role]])
    if event["series_is_final_day"]:
        return -strength_points * policy_bonus("multi_day_high_tier_final_day_strength_boost")
    return strength_points * policy_penalty("multi_day_high_tier_early_day_strength_reserve")


def shared_score(name, event, role, capped=True):
    """Load, repeat and high-tier planning penalties that every role shares."""
    member, event_name = members[name], event["type"]
    score = 0 if is_frequency_exempt_event(event_name) else fairness_penalty(name, event, capped)
    score += counts_of(name)["role", role] * policy_weight("role_serve_count")

    repeat_weight = (
        45 if is_run_balanced_event(event_name) else 30 if is_event_named(event_name, "leaders_meet") else 12
    )
    score += event_role_repeats(name, event, (role,)) * repeat_weight
    if tier(event) == "low":
        score += event_role_repeats(name, event) * policy_penalty("repeated_low_tier_event_penalty")
    if is_weekday_low_tier_event(event):
        score += counts_of(name)["weekday_low_role", quarter_key(event["date"]), role] * policy_penalty(
            "repeated_weekday_low_tier_penalty"
        )
    if tier(event) == "high" and member["role"] != "red":
        score += high_tier_role_penalties(name, event, role)

    return (
        score
        + upcoming_high_tier_reserve_penalty(event, member, role)
        + upcoming_high_tier_preload_penalty(name, event, role)
        + multi_day_high_tier_strength_adjustment(event, member, role)
    )


def director_score(name, event, relax_monthly_limit=False):
    member = members[name]
    event_tier = tier(event)
    if (
        not member["can_direct"]
        or (event_tier == "high" and member["role"] != "green")
        or blocked_by_event_rules(name, event, relax_monthly_limit)
    ):
        return None

    monthly_directs = counts_of(name)["month_role", month_key(event["date"]), "director"]
    score = shared_score(name, event, "director")
    if not is_frequency_exempt_event(event["event"]):
        # Spread directing across the team: strongly discourage directing twice in one month
        score += monthly_directs * policy_penalty("repeated_monthly_director_penalty")

    if member["role"] == "green":
        if event_tier == "high":
            score += member["shoot_rank"] * 2 - max(0, 14 - member["direct_rank"] * 2)
        else:
            score += member["direct_rank"] * policy_weight("green_direct_rank")
            if event_tier == "low":
                score += 10
        return score

    if monthly_directs >= policy_limit("max_director_track_directs_per_month"):
        return None
    if event_tier == "low":
        return score - 18
    # From the configured date on, trainees may direct services (still under green-assist supervision)
    return score + (8 if event_tier == "standard" and trainee_may_direct_services(event) else 35)


def assist_score(name, event, relax_monthly_limit=False, require_green=True):
    member = members[name]
    if (
        (member["role"] != "green" and (require_green or not member["director_track"]))
        or blocked_by_event_rules(name, event, relax_monthly_limit)
    ):
        return None

    score = shared_score(name, event, "assist")
    if member["role"] != "green":
        score += 25
    score += counts_of(name)["month_role", month_key(event["date"]), "assist"] * 8
    if tier(event) == "high":
        score += member["shoot_rank"] * 3
    return score - max(0, 14 - member["direct_rank"] * 2)


def creative_team_meet_editor_rotation_penalty(name, event):
    if not is_event_named(event["type"], "mentor_editor_pair"):
        return 0

    repeats = event_role_repeats(name, event, ("editor",))
    soft_cap = policy_limit("creative_team_meet_editor_soft_cap_per_run")
    overuse = repeats - soft_cap + 1 if 0 < soft_cap <= repeats else 0
    return repeats * policy_penalty("creative_team_meet_editor_repeat_penalty") + overuse * policy_penalty(
        "creative_team_meet_editor_overuse_penalty"
    )


def editor_score(name, event, director_name, relax_monthly_limit=False):
    member, event_name, event_tier = members[name], event["type"], tier(event)
    role, rank = member["role"], member["editor_rank"]
    if (
        not member["can_edit"]
        or blocked_by_event_rules(name, event, relax_monthly_limit)
        or (
            event_tier == "high"
            and role != "green"
            and has_adjacent_high_tier_same_role_conflict(name, event, "editor")
        )
        or (role == "red" and not is_event_named(event_name, "mentor_editor_pair"))
        or (event_tier == "high" and role == "yellow" and rank > policy_limit("max_high_tier_yellow_editor_rank"))
    ):
        return None

    month = month_key(event["date"])
    monthly_edits = counts_of(name)["month_role", month, "editor"]
    score = shared_score(name, event, "editor") + creative_team_meet_editor_rotation_penalty(name, event)

    if role == "yellow":
        if event_tier == "high":
            score += rank * (policy_weight("priority_rank") + 4) + max(0, rank - 4) * 24
        else:
            score += rank * {"standard": 3, "low": 1}.get(event_tier, 3)
            if counts_of(name)["month_role", month, "photographer"] == 0:
                score += policy_bonus("first_monthly_photographer_assignment")
                if monthly_edits > 0:
                    score += policy_bonus("yellow_photo_coverage_bonus")
            if is_event_named(event_name, "mentor_editor_pair") and rank >= 5:
                score -= policy_bonus("creative_team_meet_lower_yellow_editor_rotation_bonus")
    elif role == "green":
        if event_tier == "high":
            score += rank * policy_weight("priority_rank") + max(0, rank - 4) * 18
        else:
            score += {"standard": 10, "low": 16}.get(event_tier, 10)
            score += rank * {"standard": 3, "low": 4}.get(event_tier, 3)
            if rank >= 4 and monthly_edits == 0:
                score -= policy_bonus("green_editor_rotation_bonus")
            if is_event_named(event_name, "mentor_editor_pair"):
                score -= policy_bonus("creative_team_meet_green_editor_rotation_bonus")
    else:  # red editors only ever appear at Creative Team Meet
        score += rank * 2 - 10

    if name == director_name:
        score += 40

    if event_tier != "high" and event["requirements"]["sde_director"] and is_stacking_editor(name):
        score += policy_weight("strong_editor_under_sde_director")

    if is_event_named(event_name, "mid_tier_editor"):
        # Prayer editor should lean yellow / mid-low tier, not a top-strength editor
        if role == "green":
            score += 18
        if rank <= 3:
            score += 15
        elif rank >= 5:
            score -= 12

    return score


def photographer_score(name, event, relax_monthly_limit=False):
    member, event_name, event_tier = members[name], event["type"], tier(event)
    role = member["role"]
    if (
        not member["can_shoot"]
        or blocked_by_event_rules(name, event, relax_monthly_limit)
        or (
            event_tier == "high"
            and role != "green"
            and has_adjacent_high_tier_same_role_conflict(name, event, "photographer")
        )
        or (
            not relax_monthly_limit
            and not is_frequency_exempt_event(event_name)
            and reached_monthly_red_limit(name, event)
        )
        or (event_tier == "high" and is_disallowed_high_tier_photographer(name))
    ):
        return None

    month = month_key(event["date"])
    monthly_shoots = counts_of(name)["month_role", month, "photographer"]
    score = shared_score(name, event, "photographer")
    if monthly_shoots >= 2:
        score += 140

    if event_tier == "high":
        if role == "green":
            score += member["shoot_rank"] * 5 - policy_weight("priority_rank") * 2
        else:
            score += member["shoot_rank"] * 6 + member["editor_rank"]
    elif event_tier == "low":
        if event["requirements"]["leaders_only"]:
            score += member["shoot_rank"] if role == "green" else member["editor_rank"]
        elif role == "green":
            score += 20
        elif role == "yellow":
            score += 6 + member["editor_rank"] // 2
        else:
            score -= 4
    elif role == "green":
        score += 8
    elif role == "yellow":
        score += member["editor_rank"]
    else:
        score += 16

    if role == "yellow" and monthly_shoots == 0:
        score -= policy_bonus("first_monthly_photographer_assignment")
        if counts_of(name)["month_role", month, "editor"] > 0:
            score -= policy_bonus("yellow_photo_coverage_bonus")

    if (
        is_event_named(event_name, "mentor_editor_pair")
        and role == "yellow"
        and member["shoot_rank"] <= policy_limit("creative_team_meet_anchor_yellow_shoot_rank")
    ):
        score -= policy_bonus("creative_team_meet_anchor_bonus")

    if is_event_named(event_name, "balanced_service"):
        monthly_sundays = counts_of(name)["month_event_role", month, event_name, "photographer"]
        score += monthly_sundays * 45 if monthly_sundays else -35
        if member["weekday_late"]:
            score -= policy_bonus("weekend_service_for_weekday_late_member")

    if is_weekday_low_tier_event(event) and member["weekday_late"]:
        score += policy_penalty("weekday_late_low_tier_penalty")

    return score


def sde_director_score(name, event, relax_monthly_limit=False):
    member = members[name]
    # Overseeing editors is light work: greens may take it past their monthly cap (as in the Q4 sheet).
    capped = member["role"] != "green"
    if (
        not is_sde_director(name, event)
        or (tier(event) == "low" and member["role"] != "green")
        or blocked_by_event_rules(name, event, relax_monthly_limit or not capped)
    ):
        return None

    if tier(event) == "high":
        score = shared_score(name, event, "sde_director", capped)
        score += member["editor_rank"] * policy_weight("priority_rank")
        return score + (12 if member["role"] != "green" else 0)
    if capped:
        score = shared_score(name, event, "sde_director")
    else:
        # A green's shooting/directing load says little about whether they can also oversee
        # editing, so only their SDE director turns count (the Q4 sheet leans on greens here).
        person = counts_of(name)
        score = person["role", "sde_director"] * policy_weight("green_sde_director_turn")
        score += person["month", month_key(event["date"])] * policy_weight("green_sde_director_month")
    # Rotate the slot instead of always giving it to the top editor.
    return score + member["editor_rank"] * 5 + (policy_weight("green_sde_director") if member["role"] == "green" else 0)


def floor_runner_score(name, event, photographers, relax_monthly_limit=False):
    member = members[name]
    if not member["can_shoot"] or blocked_by_event_rules(name, event, relax_monthly_limit):
        return None
    if name in required_guides() and not has_safety_anchor(photographers):
        return None

    score = shared_score(name, event, "floor_runner")
    # Floor running is a development slot: reds first, greens only if nobody else is free.
    score += {"red": 0, "yellow": 30}.get(member["role"], 70)
    return score


def high_tier_rank_spread_penalty(candidate_name, selected_photographers):
    """Keep a high tier lineup tight in shoot rank."""
    if not selected_photographers:
        return 0

    ranks = [members[name]["shoot_rank"] for name in selected_photographers]
    candidate_rank = members[candidate_name]["shoot_rank"]
    spread = max(*ranks, candidate_rank) - min(*ranks, candidate_rank)
    average_rank = sum(ranks) / len(ranks)
    return max(0, spread - 4) * 35 + int(abs(candidate_rank - average_rank) * 8)


# --------------------------------------------------------------------------- picking


def pick_director(event):
    return choose_under_cap_first(
        available_names(event, used=set()),
        lambda name, relax: director_score(name, event, relax),
        f"Could not find an available director for {label(event)}.",
    )


def pick_assist(event, director_name, used):
    """A green assist for a trainee director, plus wherever the event asks for one.

    Trainees lead low tier events alone. On other events a trainee with no green free may still
    direct alone; pick_photographers then puts a core green in the lineup instead.
    """
    trainee_director = members[director_name]["director_track"] and tier(event) != "low"
    if not trainee_director and event["requirements"]["assist"] < 1:
        return ""
    if trainee_director and event["requirements"]["assist"] < 1:
        try:
            return choose_under_cap_first(
                available_names(event, used),
                lambda name, relax: assist_score(name, event, relax, require_green=True),
                "",
            )
        except SchedulingError:
            return ""

    message = (
        f"Could not find a green assist for trainee director {director_name} on {label(event)}."
        if trainee_director
        else f"Could not find an assist director for {label(event)}."
    )
    return choose_under_cap_first(
        available_names(event, used),
        lambda name, relax: assist_score(name, event, relax, require_green=trainee_director),
        message,
    )


def pick_sde_director(event, used):
    if event["requirements"]["sde_director"] < 1:
        return ""

    return choose_under_cap_first(
        available_names(event, used),
        lambda name, relax: sde_director_score(name, event, relax),
        f"Could not find an SDE director for {label(event)}.",
    )


def pick_floor_runner(event, used, photographers):
    if event["requirements"]["floor_runner"] < 1:
        return ""

    return choose_under_cap_first(
        available_names(event, used),
        lambda name, relax: floor_runner_score(name, event, photographers, relax),
        f"Could not find a floor runner for {label(event)}.",
    )


def is_creative_team_meet_mentor_editor(name):
    member = members[name]
    return (
        member["can_edit"]
        and member["role"] != "red"
        and member["can_guide"]
        and member["editor_rank"] <= policy_limit("creative_team_meet_max_yellow_editor_rank")
    )


def is_creative_team_meet_decent_yellow_editor(name):
    member = members[name]
    return (
        member["role"] == "yellow"
        and member["can_edit"]
        and member["editor_rank"] <= policy_limit("creative_team_meet_max_yellow_editor_rank")
    )


def is_valid_creative_team_meet_editor_pair(editors):
    if len(editors) != 2 or any(not members[name]["can_edit"] for name in editors):
        return False
    if all(is_creative_team_meet_decent_yellow_editor(name) for name in editors):
        return True

    red_editors = [name for name in editors if members[name]["role"] == "red"]
    if red_editors:
        if len(red_editors) != 1:
            return False
        mentor = next(name for name in editors if name not in red_editors)
        return members[mentor]["role"] == "green" and is_creative_team_meet_mentor_editor(mentor)

    if not any(members[name]["role"] == "yellow" for name in editors):
        return False
    return any(is_creative_team_meet_mentor_editor(name) for name in editors)


def creative_team_meet_editor_pair_priority(editors):
    if all(is_creative_team_meet_decent_yellow_editor(name) for name in editors):
        return 0
    if any(members[name]["role"] == "red" for name in editors):
        return 2
    return 1


def is_valid_default_editor_pair(editors, event):
    if len(editors) != 2 or any(not members[name]["can_edit"] for name in editors):
        return False

    strong = [name for name in editors if is_strong_editor(name)]
    if tier(event) == "high":
        return len(strong) == 2
    if event["requirements"]["sde_director"]:
        # The SDE director is the strong editor; any pair works and editor_score steers it to
        # developing editors (strong_editor_under_sde_director), so small teams still fill it.
        return True
    return len(strong) == 1


def choose_best_editor_pair(
    candidate_names, event, director_name, is_valid_pair, failure_message, priority_fn=None,
    relax_monthly_limit=False,
):
    """Pick the cheapest valid editor duo, avoiding pairs that already worked this event together."""
    for avoid_repeated_pairs in (True, False):
        options = []
        for pair in combinations(candidate_names, 2):
            repeats = editor_pair_repeats(pair, event)
            if not is_valid_pair(pair) or (avoid_repeated_pairs and repeats):
                continue

            scores = [editor_score(name, event, director_name, relax_monthly_limit) for name in pair]
            if any(score is None for score in scores):
                continue

            pair_penalty = repeats * policy_penalty("repeated_event_editor_pair_penalty")
            sort_key = (
                pair_penalty + sum(scores),
                sum(event_role_repeats(name, event, ("editor",), whole_run=False) for name in pair),
                priority_fn(pair) if priority_fn else 0,
                pair_penalty,
                max(scores),
                tuple(sorted(pair)),
            )
            options.append((sort_key, list(pair)))

        if options:
            return min(options, key=lambda option: option[0])[1]

    raise SchedulingError(failure_message)


def pick_editors(event, director_name, used, blocked=frozenset()):
    if event["requirements"]["editors"] == 0:
        return []
    try:
        return pick_editors_under_cap(event, director_name, used, blocked, relax_monthly_limit=False)
    except SchedulingError:
        return pick_editors_under_cap(event, director_name, used, blocked, relax_monthly_limit=True)


def pick_editors_under_cap(event, director_name, used, blocked, relax_monthly_limit):
    required = event["requirements"]["editors"]
    event_tier = tier(event)
    score = lambda name: editor_score(name, event, director_name, relax_monthly_limit)

    if is_event_named(event["type"], "mentor_editor_pair"):
        if required != 2:
            raise SchedulingError(f"{event['event']} on {day(event)} must use exactly 2 editor slots.")
        failure = (
            f"Could not find a valid Creative Team Meet editor pair for {day(event)}. "
            f"Use {CREATIVE_TEAM_MEET_PAIR_RULE}"
        )
        return pick_editor_pair(
            event, director_name, used, blocked, is_valid_creative_team_meet_editor_pair, failure,
            creative_team_meet_editor_pair_priority, relax_monthly_limit,
        )

    if required == 2:
        return pick_editor_pair(
            event, director_name, used, blocked, lambda pair: is_valid_default_editor_pair(pair, event),
            f"Could not fill the editor slots for {label(event)}.", relax_monthly_limit=relax_monthly_limit,
        )

    if required > 2 and event_tier != "high":
        # Keep the 1 strong + 1 lower-tier split even when more slots are configured.
        candidates = [name for name in available_names(event, used) if members[name]["can_edit"]]
        strong = [name for name in candidates if is_strong_editor(name)]
        lower = [name for name in candidates if not is_strong_editor(name)]
        strong_failure = f"Could not find a stronger editor for {label(event)}."
        lower_failure = f"Could not find a lower-tier editor for {label(event)}."
        if not strong:
            raise SchedulingError(strong_failure)
        if not lower:
            raise SchedulingError(lower_failure)
        return [
            choose_best_candidate(strong, score, strong_failure),
            choose_best_candidate(lower, score, lower_failure),
        ]

    editors = []

    def fill(candidate_names, failure_message):
        if event_tier == "high":
            strong = [
                name for name in candidate_names if members[name]["can_edit"] and is_strong_editor(name)
            ]
            if len(strong) >= required - len(editors):
                candidate_names = strong
        while len(editors) < required:
            remaining = [name for name in candidate_names if name not in editors]
            if not remaining:
                return
            editors.append(choose_best_candidate(remaining, score, failure_message))

    fill(available_names(event, used), f"Could not find enough editors for {label(event)}.")
    if len(editors) < required:
        failure = f"Could not fill the editor slots for {label(event)}."
        fill(available_names(event, set(editors) | set(blocked)), failure)
        if len(editors) < required:
            raise SchedulingError(failure)
    return editors


def pick_editor_pair(
    event, director_name, used, blocked, is_valid_pair, failure_message, priority_fn=None,
    relax_monthly_limit=False,
):
    """Try the unused members first, then fall back to everyone available but the blocked names."""
    for candidates in (available_names(event, used), available_names(event, set(blocked))):
        try:
            return choose_best_editor_pair(
                candidates, event, director_name, is_valid_pair, failure_message, priority_fn,
                relax_monthly_limit,
            )
        except SchedulingError:
            failure = SchedulingError(failure_message)
    raise failure


def choose_required_photographer(candidate_names, event, wanted):
    message = f"Could not find {wanted} for {day(event)}."
    try:
        return choose_best_candidate(candidate_names, lambda name: photographer_score(name, event), message)
    except SchedulingError:
        # A hard role requirement could not be met under the monthly cap; relax it
        # rather than fail (fairness still applies as a penalty everywhere else).
        return choose_best_candidate(
            candidate_names, lambda name: photographer_score(name, event, relax_monthly_limit=True), message
        )


def pick_photographers(event, crew, used):
    director_name = crew["director"][0]
    requirements = event["requirements"]
    required = requirements["photographers"]
    if required == 0:
        return []

    event_name, event_tier = event["type"], tier(event)
    is_sunday_service = is_event_named(event_name, "balanced_service")
    used_roles = role_counts(used)
    risky_members = required_guides()
    photographers = []

    min_green = max(0, requirements["min_green_photographers"])
    min_yellow = max(0, requirements["min_yellow_photographers"])
    min_red = max(0, requirements["min_red_photographers"])
    max_red = min(required, requirements["max_red_photographers"])
    target_green = target_yellow = target_strong = 0
    max_development_heavy = max_green = required

    if event_tier == "high":
        min_green = max(min_green, min(2, required))
        target_green = min(3, required)
        target_yellow = min(1, max(0, required - target_green))
    elif event_tier == "standard":
        min_green = max(min_green, 1)

    if members[director_name]["director_track"]:
        # Trainee directors get a steadier lineup: never more than 1 red
        max_red = min(max_red, 1)
    if is_event_named(event_name, "mentor_editor_pair"):
        min_yellow = max(min_yellow, 1)
        max_red = min(max_red, 2)
    if is_sunday_service:
        min_yellow = max(min_yellow, 1 - used_roles["yellow"])
        min_red = max(min_red, 1 - used_roles["red"])
        target_strong = min(2, required)
        max_development_heavy = 2
        max_green = 1
    if is_service_event(event_name):
        max_red = min(max_red, max(0, 2 - used_roles["red"]))

    def available_shooters():
        return [
            name
            for name in members
            if name not in used
            and name not in photographers
            and is_available(name, event)
            and members[name]["can_shoot"]
        ]

    def can_add(name):
        if name not in risky_members:
            return True
        if any(existing in risky_members for existing in photographers):
            return False
        if has_safety_anchor([*photographers, name]):
            return True
        # Only take the risk when a guide can still fill one of the remaining slots.
        return len(photographers) + 1 < required and any(
            is_safety_anchor(other) for other in available_shooters() if other != name
        )

    def pool(eligible):
        return [name for name in available_shooters() if eligible(name) and can_add(name)]

    def top_up(below_target, eligible, wanted):
        while len(photographers) < required and below_target():
            candidates = pool(eligible)
            if not candidates:
                return
            photographers.append(choose_required_photographer(candidates, event, wanted))

    if trainee_directing_alone(event, crew):
        photographers.append(
            choose_required_photographer(pool(is_core_green), event, "a core green for a trainee director")
        )

    high_tier_yellow_ok = lambda name: event_tier != "high" or is_high_tier_eligible_yellow_photographer(name)
    for role, needed, also in (
        ("green", min_green, None),
        ("yellow", min_yellow, high_tier_yellow_ok),
        ("red", min_red, None),
    ):
        for _ in range(max(0, needed - role_counts(photographers)[role])):
            if len(photographers) >= required:
                break
            candidates = pool(
                lambda name, role=role, also=also: members[name]["role"] == role and (also is None or also(name))
            )
            photographers.append(
                choose_required_photographer(candidates, event, f"a required {role} photographer")
            )

    if is_sunday_service:
        top_up(
            lambda: sunday_strength_metrics(photographers)[0] < target_strong,
            is_strong_sunday_photographer,
            "a stronger Sunday photographer",
        )
    if event_tier == "high":
        scorable = lambda name: photographer_score(name, event) is not None
        top_up(
            lambda: role_counts(photographers)["green"] < target_green,
            lambda name: members[name]["role"] == "green" and scorable(name),
            "an ideal green photographer for a high tier event",
        )
        top_up(
            lambda: role_counts(photographers)["yellow"] < target_yellow,
            lambda name: is_high_tier_eligible_yellow_photographer(name) and scorable(name),
            "a strong yellow photographer for a high tier event",
        )

    # Soft target: more yellows where someone under the cap can take it, never forced.
    top_up(
        lambda: role_counts(photographers)["yellow"] < requirements["target_yellow_photographers"],
        lambda name: members[name]["role"] == "yellow" and photographer_score(name, event) is not None,
        "a target yellow photographer",
    )

    while len(photographers) < required:
        chosen_roles = role_counts(photographers)
        reds = used_roles["red"] + chosen_roles["red"]
        strong_count, development_heavy_count = sunday_strength_metrics(photographers)

        def candidate_score(name, relax_monthly_limit=False):
            if members[name]["role"] == "red" and reds >= max_red:
                return None
            score = photographer_score(name, event, relax_monthly_limit)
            if score is None:
                return None
            if is_sunday_service:
                if members[name]["role"] == "green" and chosen_roles["green"] >= max_green:
                    score += 60
                if is_development_heavy_sunday_photographer(name) and development_heavy_count >= max_development_heavy:
                    score += 160
                if strong_count < target_strong and not is_strong_sunday_photographer(name):
                    score += 120
            if name in risky_members:
                if event_tier == "low":
                    score += 80
                if not has_safety_anchor([*photographers, name]):
                    score += 40
            if event_tier == "high":
                score += high_tier_rank_spread_penalty(name, photographers)
            return score

        candidates = pool(lambda name: True)
        if event_tier == "high":
            candidates = prefer(candidates, lambda name: members[name]["role"] != "red")
        if (
            is_sunday_service
            and chosen_roles["green"] >= max_green
            and strong_count >= target_strong
            and development_heavy_count < max_development_heavy
        ):
            candidates = prefer(candidates, lambda name: members[name]["role"] != "green")
        if is_sunday_service and strong_count < target_strong:
            candidates = prefer(candidates, is_strong_sunday_photographer)
        elif is_sunday_service and development_heavy_count >= max_development_heavy:
            candidates = prefer(candidates, lambda name: not is_development_heavy_sunday_photographer(name))
        elif event_tier == "low" and not requirements["leaders_only"]:
            candidates = prefer(candidates, lambda name: members[name]["role"] != "green")

        photographers.append(
            choose_under_cap_first(
                candidates, candidate_score, f"Could not find enough photographers for {label(event)}."
            )
        )

    def balance_sunday(lineup):
        if not is_sunday_service:
            return lineup
        return trim_sunday_photographers(event, used, rebalance_sunday_photographers(event, used, lineup))

    photographers = balance_sunday(enforce_safety_rule(event, used, photographers))

    # Supervised pairings collapse two members into one visible slot; refill what they hide.
    while visible_photographer_slot_count(photographers) < required:
        chosen_roles = role_counts(photographers)
        reds = used_roles["red"] + chosen_roles["red"]

        def supplemental_score(name, relax_monthly_limit=False):
            member = members[name]
            if not is_available(name, event) or not member["can_shoot"]:
                return None
            if member["role"] == "red" and reds >= max_red:
                return None
            if name in risky_members and (
                any(existing in risky_members for existing in photographers)
                or not has_safety_anchor([*photographers, name])
            ):
                return None
            score = photographer_score(name, event, relax_monthly_limit)
            if score is None:
                return None
            if is_sunday_service and member["role"] == "green" and chosen_roles["green"] >= max_green:
                score += 60
            if event_tier == "high":
                score += high_tier_rank_spread_penalty(name, photographers)
            return score

        candidates = [name for name in members if name not in photographers and name not in used]
        if event_tier == "high":
            candidates = prefer(candidates, lambda name: members[name]["role"] != "red")
        photographers.append(
            choose_under_cap_first(
                candidates,
                supplemental_score,
                f"Could not fill the visible photographer slots for {label(event)}.",
            )
        )

    photographers = balance_sunday(photographers)
    validate_team_composition(event, crew, used, photographers)
    if members[director_name]["director_track"]:
        return photographers  # no extra recruit slot under a trainee director
    return photographers + pick_idle_reds(event, used, photographers)


def pick_idle_reds(event, used, photographers):
    """Extra slots, beyond the event's normal shape, for reds who have not served in a while."""
    extra = []
    for _ in range(event["requirements"]["extra_red_photographer"]):
        lineup = [*photographers, *extra]
        candidates = [
            name
            for name in members
            if name not in used
            and name not in lineup
            and is_available(name, event)
            and is_idle_red(name, event)
            and (name not in required_guides() or has_safety_anchor([*lineup, name]))
        ]
        try:
            extra.append(choose_best_candidate(candidates, lambda name: photographer_score(name, event), ""))
        except SchedulingError:
            break
    return extra


def trainee_directing_alone(event, crew):
    assist = crew["assist"]
    return members[crew["director"][0]]["director_track"] and not (
        assist and members[assist[0]]["role"] == "green"
    )


def enforce_safety_rule(event, used, photographers):
    """Isaac and Aslvin need a guide in the lineup; if no guide can join, they give up the slot."""
    risky_members = required_guides()
    unsupervised = [name for name in photographers if name in risky_members]
    if not unsupervised or has_safety_anchor(photographers):
        return photographers

    message = f"Could not satisfy the safety rule for {label(event)}."
    score = lambda name, relax=False: photographer_score(name, event, relax)
    free = [
        name
        for name in members
        if name not in used
        and name not in photographers
        and is_available(name, event)
        and members[name]["can_shoot"]
    ]
    anchors = [name for name in free if is_safety_anchor(name)]
    removable = [
        name for name in photographers if name not in risky_members and not is_safety_anchor(name)
    ]

    if anchors and removable:
        replacement = choose_under_cap_first(anchors, score, message)
        removed = max(removable, key=lambda name: (photographer_score(name, event) or 0, name))
    else:
        replacement = choose_under_cap_first([n for n in free if n not in risky_members], score, message)
        removed = unsupervised[0]

    return [replacement if name == removed else name for name in photographers]


def can_use_sunday_photographer_lineup(event, used, photographers):
    requirements = event["requirements"]
    everyone = role_counts([*used, *photographers])
    chosen = role_counts(photographers)
    risky_members = required_guides().intersection(photographers)

    return (
        all(everyone[role] >= 1 for role in ("green", "yellow", "red"))
        and chosen["green"] >= max(1, requirements["min_green_photographers"])
        and chosen["yellow"] >= requirements["min_yellow_photographers"]
        and requirements["min_red_photographers"] <= chosen["red"] <= requirements["max_red_photographers"]
        and not (is_service_event(event["type"]) and everyone["red"] > 2)
        and len(risky_members) <= 1
        and (not risky_members or has_safety_anchor(photographers))
    )


def trim_sunday_photographers(event, used, photographers):
    """Drop extra members until the visible slot count matches the requirement."""
    required = event["requirements"]["photographers"]

    for require_balanced_shape in (True, False):
        while (visible := visible_photographer_slot_count(photographers)) > required:
            options = []
            for removed in photographers:
                proposed = [name for name in photographers if name != removed]
                proposed_visible = visible_photographer_slot_count(proposed)
                strong_count, development_heavy_count = sunday_strength_metrics(proposed)
                if (
                    not required <= proposed_visible < visible
                    or not can_use_sunday_photographer_lineup(event, used, proposed)
                    or (require_balanced_shape and (strong_count < 2 or development_heavy_count > 2))
                ):
                    continue

                options.append(
                    (
                        (
                            proposed_visible,
                            development_heavy_count,
                            -strong_count,
                            -(photographer_score(removed, event) or 0),
                            members[removed]["shoot_rank"],
                            removed,
                        ),
                        proposed,
                    )
                )

            if not options:
                break
            photographers = min(options, key=lambda option: option[0])[1]

    return photographers


def rebalance_sunday_photographers(event, used, photographers):
    """Swap development-heavy slots out until the lineup has enough strength."""
    while True:
        strong_count, development_heavy_count = sunday_strength_metrics(photographers)
        if strong_count >= 2 and development_heavy_count <= 2:
            return photographers

        many_reds = role_counts(photographers)["red"] > 1
        removable = sorted(
            {
                name
                for name in photographers
                if (members[name]["role"] == "yellow" and is_development_heavy_sunday_photographer(name))
                or (many_reds and members[name]["role"] == "red")
            },
            key=lambda name: (members[name]["role"] != "red", -members[name]["shoot_rank"], name),
        )
        replacements = [
            name
            for name in members
            if name not in used
            and name not in photographers
            and is_available(name, event)
            and members[name]["can_shoot"]
            and not is_development_heavy_sunday_photographer(name)
        ]

        options = []
        for removed in removable:
            for candidate in replacements:
                proposed = [candidate if name == removed else name for name in photographers]
                score = photographer_score(candidate, event)
                if score is None or not can_use_sunday_photographer_lineup(event, used, proposed):
                    continue

                proposed_strong, proposed_development_heavy = sunday_strength_metrics(proposed)
                options.append(
                    (
                        (
                            proposed_development_heavy >= development_heavy_count,
                            proposed_strong <= strong_count,
                            proposed_development_heavy,
                            -proposed_strong,
                            score,
                            candidate,
                            removed,
                        ),
                        removed,
                        candidate,
                    )
                )

        if not options:
            return photographers
        _, removed, candidate = min(options, key=lambda option: option[0])
        photographers = [candidate if name == removed else name for name in photographers]


# --------------------------------------------------------------------------- result checks


def validate_editor_pairing(event, editors):
    def fail(problem):
        return SchedulingError(f"{event['event']} on {day(event)} {problem}")

    if is_event_named(event["type"], "mentor_editor_pair"):
        if not is_valid_creative_team_meet_editor_pair(editors):
            raise fail(f"must use {CREATIVE_TEAM_MEET_PAIR_RULE}")
        return

    if len(editors) < 2:
        return

    strong = [name for name in editors if is_strong_editor(name)]
    lower_tier = [name for name in editors if not is_strong_editor(name)]

    if tier(event) == "high":
        if len(strong) < 2:
            raise fail("must use stronger editors in both editor slots.")
    elif event["requirements"]["sde_director"]:
        return
    elif not strong or not lower_tier:
        raise fail("must include 1 stronger editor and 1 lower-tier editor.")
    elif len(lower_tier) >= 2:
        raise fail("cannot schedule 2 lower-tier editors together.")


def validate_team_composition(event, crew, used, photographers):
    director_name, assist, editors = crew["director"][0], crew["assist"], crew["editor"]
    requirements = event["requirements"]
    everyone = [*used, *photographers]
    counts = role_counts(everyone)
    chosen = role_counts(photographers)
    risky_members = required_guides()

    def fail(problem):
        return SchedulingError(f"{event['event']} on {day(event)} {problem}")

    if requirements["leaders_only"]:
        non_leaders = sorted({name for name in everyone if not members[name]["leader"]})
        if non_leaders:
            raise fail(f"can only include leaders. Non-leaders: {', '.join(non_leaders)}.")

    if len(risky_members.intersection(photographers)) > 1:
        raise fail("cannot schedule Isaac and Aslvin together.")

    if trainee_directing_alone(event, crew) and not any(is_core_green(name) for name in photographers):
        raise fail(f"must include a green assist or a core green photographer when {director_name} is directing.")

    if requirements["greens_only"]:
        non_greens = sorted({name for name in everyone if members[name]["role"] != "green"})
        if non_greens:
            raise fail(f"can only include greens. Found: {', '.join(non_greens)}.")

    if requirements["tier"] != "low" and requirements["photographers"] > 0 and chosen["green"] < 1:
        raise fail("must include at least 1 green photographer.")

    min_green = requirements["min_green_photographers"]
    if requirements["tier"] == "high":
        min_green = max(2, min_green)
        if counts["green"] < 2:
            raise fail("must include at least 2 greens.")

        disallowed = [name for name in photographers if is_disallowed_high_tier_photographer(name)]
        if disallowed:
            raise fail(f"cannot include low-tier yellows or reds. Found: {', '.join(disallowed)}.")

        weak_editors = [
            name
            for name in editors
            if members[name]["role"] == "yellow"
            and members[name]["editor_rank"] > policy_limit("max_high_tier_yellow_editor_rank")
        ]
        if weak_editors:
            raise fail(f"cannot include lower-tier yellow editors. Found: {', '.join(weak_editors)}.")

    for role, minimum in (
        ("green", min_green),
        ("yellow", requirements["min_yellow_photographers"]),
        ("red", requirements["min_red_photographers"]),
    ):
        if minimum and chosen[role] < minimum:
            raise fail(f"must include at least {minimum} {role} photographers.")

    if chosen["red"] > requirements["max_red_photographers"]:
        raise fail(f"cannot have more than {requirements['max_red_photographers']} red photographers.")

    if is_event_named(event["type"], "balanced_service"):
        missing = [role for role in ("green", "yellow", "red") if counts[role] < 1]
        if missing:
            raise fail(
                f"must include at least 1 green, 1 yellow, and 1 red. Missing: {', '.join(missing)}."
            )
        visible_slots = visible_photographer_slot_count(photographers)
        if visible_slots != requirements["photographers"]:
            raise fail(
                "must show exactly 4 photographer slots after red pairings are collapsed. "
                f"Found {visible_slots}."
            )

    if is_service_event(event["type"]) and counts["red"] > 2:
        raise fail("cannot have more than 2 reds.")

    if risky_members.intersection(photographers) and not has_safety_anchor(photographers):
        raise fail("must include a guide-capable photographer when Isaac or Aslvin are scheduled.")


# --------------------------------------------------------------------------- run


def generate_schedule():
    global SCHEDULER_POLICY, members, stats, bad_dates, pair_counts
    sync_universal_scheduler_if_needed()

    SCHEDULER_POLICY = load_scheduler_policy()
    team = load_yaml("data/team.yaml")
    event_types = load_yaml("config/event_types.yaml").get("events", {})
    styles = load_yaml("config/google_sheets_styles.yaml")
    layout = load_yaml("config/google_sheets_layout.yaml")
    events = parse_events()
    bad_dates = parse_bad_dates()
    members = build_members(team)

    unknown_members = sorted(set(bad_dates) - set(members))
    check(not unknown_members, "Unknown members in data/bad_dates.md: " + ", ".join(unknown_members))
    unknown_events = sorted({event["type"] for event in events} - set(event_types))
    check(not unknown_events, "Unknown event types in data/events.md: " + ", ".join(unknown_events))
    validate_google_sheets_styles(styles)
    validate_google_sheets_layout(layout)

    for event in events:
        event["requirements"] = build_event_requirements(
            event_types.get(event["event"], event_types[event["type"]])
        )
    annotate_event_series(events)
    annotate_upcoming_high_tier_events(events)

    fieldnames = layout["sheet_layout"]["canonical_scheduler_format"]["columns"]
    stats = {name: new_member_stats() for name in members}
    pair_counts = Counter()
    rows = []

    for event in events:
        crew = {role: [] for role in ROLES}
        used = set()

        def assign(role, name):
            if name:
                crew[role].append(name)
                used.add(name)

        assign("director", pick_director(event))
        director = crew["director"][0]
        assign("assist", pick_assist(event, director, used))
        assign("sde_director", pick_sde_director(event, used))
        # The editor fallback may reuse the director, but not when an SDE director oversees them.
        blocked = set(crew["sde_director"])
        if event["requirements"]["sde_director"]:
            blocked.add(director)
        if event["requirements"]["director_edits"]:
            # ponytail: the director covers every editor slot; split it out if such an event needs 2 editors.
            crew["editor"].append(director)
        else:
            for editor in pick_editors(event, director, used, blocked=blocked):
                assign("editor", editor)

        photographers = pick_photographers(event, crew, used)
        crew["photographer"] = photographers
        used.update(photographers)
        assign("floor_runner", pick_floor_runner(event, used, photographers))

        validate_editor_pairing(event, crew["editor"])
        update_stats(event, crew)

        row = build_output_row(event, crew, fieldnames)
        row["unavailable"] = ", ".join(
            sorted(name for name, dates in bad_dates.items() if event["date"].date() in dates)
        )
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
        write_styles_manifest(load_yaml("config/google_sheets_styles.yaml"))
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
