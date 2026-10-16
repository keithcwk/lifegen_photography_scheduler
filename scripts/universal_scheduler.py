import re
import textwrap
from datetime import datetime
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[1]
UNIVERSAL_SCHEDULER_PATH = BASE / "UNIVERSAL_SCHEDULER.md"
UNIVERSAL_TEMPLATE_PATH = BASE / "UNIVERSAL_SCHEDULER.template.md"
SECTION_SPECS = [
    ("rules/rulebook.md", "md"),
    ("data/team.yaml", "yaml"),
    ("data/events.md", "md"),
    ("data/bad_dates.md", "md"),
    ("config/event_types.yaml", "yaml"),
    ("config/recurring_events.yaml", "yaml"),
    ("config/google_sheets_styles.yaml", "yaml"),
    ("config/google_sheets_layout.yaml", "yaml"),
    ("config/google_sheets_sync.yaml", "yaml"),
    ("config/scheduler_policy.yaml", "yaml"),
]
SECTION_TARGETS = {path for path, _ in SECTION_SPECS}
TEAM_FILE = "data/team.yaml"
DATE_FORMAT = "%d %b %Y"
EVENT_LINE_PATTERN = re.compile(r"(\d{1,2} [A-Za-z]{3} \d{4}) - (.+)")
WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
SESSION_SEPARATOR = "|"

DOCUMENT_HEADER_LINES = [
    "# UNIVERSAL_SCHEDULER.md",
    "",
    "This file is the single human-edited source of truth for the scheduler.",
    "Only edit inside the fenced code blocks.",
    "Do not rename the `## file/path` headings.",
    "After editing, run the validator or the generate script.",
    "If this file is newer than the generated repo files, schedule generation auto-syncs from it.",
    "",
    "Safe workflow for non-dev users:",
    "1. Edit the content inside the code block for the section you want to change.",
    "2. Run `Validate Universal Scheduler.command` or `python scripts/compile_universal_scheduler.py --check`.",
    "3. Run `Generate Schedule.command` or `python scripts/generate_schedule.py`.",
    "4. If needed, run `Push Schedule To Google Sheets.command`.",
]

TEMPLATE_HEADER_LINES = [
    "# UNIVERSAL_SCHEDULER.md",
    "",
    "This is a starter template for a new ministry.",
    "Only edit inside the fenced code blocks.",
    "Do not rename the `## file/path` headings.",
    "Replace the example names, dates, and sheet settings with your own.",
    "Use `python scripts/compile_universal_scheduler.py --check` before generating a schedule.",
]

TEMPLATE_SECTION_CONTENTS = {
    "rules/rulebook.md": textwrap.dedent(
        """\
        # Ministry Photography Scheduling Rulebook

        ## Team Roles

        Each main service usually needs:

        - 1 Director
        - 4 Photographers
        - 2 Editors

        Directors may also serve as editors when needed.

        ## Team Categories

        Green: Experienced photographers who can direct, edit, and shoot.
        Yellow: Developing photographers who can shoot and are learning editing.
        Red: New photographers who cannot direct or edit yet.

        ## Team Composition Rules

        - High tier events should be covered by stronger teams
        - Low tier events can be used for development opportunities
        - Sunday Service should balance experience and development
        - Reds must never direct

        ## Recurring Planning Rules

        - Every Sunday is Sunday Service
        - The first Tuesday of every month is Prayer Meeting
        - The first Friday of every month is Leaders Meeting

        ## Schedule Sheet Rules

        - Photographer slots should appear in tier order: Green, then Yellow, then Red
        - `SDE 1` and `SDE 2` should appear in editor-strength order
        """
    ),
    "data/team.yaml": textwrap.dedent(
        """\
        greens:
          - name: Example Green 1
            shoot_rank: 1
            direct_rank: 1
            editor_rank: 1

          - name: Example Green 2
            shoot_rank: 2
            direct_rank: 2
            editor_rank: 2

          - name: Example Green 3
            shoot_rank: 3
            direct_rank: 3
            editor_rank: 3

          - name: Example Green 4
            shoot_rank: 4
            direct_rank: 4
            editor_rank: 4

          - name: Example Green 5
            shoot_rank: 5
            direct_rank: 5
            editor_rank: 5

          - name: Example Green 6
            shoot_rank: 6
            direct_rank: 6
            editor_rank: 6

        yellows:
          - name: Example Yellow 1
            shoot_rank: 7
            editor_rank: 1
            director_track: true

          - name: Example Yellow 2
            shoot_rank: 8
            editor_rank: 2

          - name: Example Yellow 3
            shoot_rank: 9
            editor_rank: 3

          - name: Example Yellow 4
            shoot_rank: 10
            editor_rank: 4

        reds:
          - name: Example Red 1
            shoot_rank: 11
          - name: Example Red 2
            shoot_rank: 12
          - name: Example Red 3
            shoot_rank: 13

        shadows: []
        """
    ),
    "data/events.md": textwrap.dedent(
        """\
        # Events

        Add one event per line using `DD Mon YYYY - Event Name`.
        Keep examples commented out.

        <!--
        Example
        06 Apr 2026 - Special Service
        12 Apr 2026 - Sunday Service
        19 Apr 2026 - Sunday Service
        -->

        ## Exclusions
        <!--
        Example
        31 May 2026 - Sunday Service
        -->
        """
    ),
    "data/bad_dates.md": textwrap.dedent(
        """\
        # Bad Dates

        Use quarter headings, then member headings, then bullet dates.
        Keep examples commented out.

        <!--
        Example
        ## 2026 Q2

        ### Example Green 1
        - 06 Apr 2026

        ### Example Yellow 1
        - 13 Apr 2026
        -->
        """
    ),
    "config/event_types.yaml": textwrap.dedent(
        """\
        events:
          Sunday Service:
            photographers: 4
            editors: 2
            sde_director: 1
            tier: standard
            min_green_photographers: 1

          Prayer Meeting:
            photographers: 2
            editors: 1
            tier: low

          Leaders Meeting:
            photographers: 2
            editors: 1
            tier: low

          Special Service:
            photographers: 4
            editors: 2
            assist: 1
            sde_director: 1
            floor_runner: 1
            tier: high
            min_green_photographers: 2
            max_red_photographers: 0
        """
    ),
    "config/recurring_events.yaml": textwrap.dedent(
        """\
        recurring_events:
          - event: Sunday Service
            frequency: weekly
            weekday: sunday

          - event: Prayer Meeting
            frequency: monthly
            occurrence: first
            weekday: tuesday

          - event: Leaders Meeting
            frequency: monthly
            occurrence: first
            weekday: friday

        generation_window:
          months_after_last_explicit_event: 1
        """
    ),
    "config/google_sheets_sync.yaml": textwrap.dedent(
        """\
        # Replace these values before pushing to Google Sheets.
        google_sheets:
          spreadsheet_id: "YOUR_SPREADSHEET_ID"
          worksheet_title: "Schedule"
          service_account_json: "/absolute/path/to/google_credentials.json"
          clear_before_write: false
          create_worksheet_if_missing: true
        """
    ),
    "config/scheduler_policy.yaml": textwrap.dedent(
        """\
        limits:
          max_assignments_per_member_per_month: 2
          max_director_track_directs_per_month: 1
          max_red_assignments_per_month: 2
          max_high_tier_yellow_shoot_rank: 10
          max_high_tier_yellow_editor_rank: 4
          high_tier_reserve_window_days: 14

        penalties:
          consecutive_event_penalty: 30
          repeated_weekday_low_tier_penalty: 35
          weekday_late_low_tier_penalty: 80
          multi_day_high_tier_early_day_strength_reserve: 10
          upcoming_high_tier_reserve_penalty: 18
          upcoming_high_tier_preload_penalty: 55
          upcoming_high_tier_preload_same_role_penalty: 30

        bonuses:
          first_monthly_photographer_assignment: 24
          yellow_photo_coverage_bonus: 32
          green_editor_rotation_bonus: 24
          weekend_service_for_weekday_late_member: 18
          multi_day_high_tier_final_day_strength_boost: 18

        weights:
          priority_rank: 10
          role_serve_count: 8
          total_serve_count: 3

        fallbacks:
          blank_rank_value: 50

        safety:
          required_guides_for:
            - Example Red 1

        event_roles:
          balanced_service: Sunday Service
          mid_tier_editor: Prayer Meeting
          leaders_meet: Leaders Meeting
          service_marker: service

        special_rules:
          frequency_exempt_events: []
        """
    ),
}


class UniversalSchedulerValidationError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("Universal scheduler validation failed:\n- " + "\n- ".join(issues))


def iter_active_lines(text):
    """Yield (line number, stripped line), skipping HTML comment blocks."""
    in_comment_block = False

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if in_comment_block:
            in_comment_block = "-->" not in line
        elif "<!--" in line:
            in_comment_block = "-->" not in line
        else:
            yield line_number, line


def event_type(event_name):
    """'Power Conference KL | Night 1' is a session of the 'Power Conference KL' event type."""
    return event_name.split(SESSION_SEPARATOR, 1)[0].strip()


def normalize_quarter(label):
    match = re.fullmatch(r"(\d{4})\s+Q([1-4])|Q([1-4])\s+(\d{4})", label.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid quarter heading '{label.strip()}'. Use '2026 Q2' or 'Q2 2026'.")

    year, quarter, flipped_quarter, flipped_year = match.groups()
    return f"{int(year or flipped_year)} Q{int(quarter or flipped_quarter)}"


def quarter_key(date_value):
    return f"{date_value.year} Q{(date_value.month - 1) // 3 + 1}"


# --------------------------------------------------------------------------- document building


def _build_document(section_texts, header_lines):
    lines = list(header_lines)
    for target, language in SECTION_SPECS:
        lines += ["", f"## {target}", f"```{language}", section_texts[target].rstrip(), "```"]
    return "\n".join(lines) + "\n"


def build_universal_scheduler_text():
    return _build_document(
        {target: (BASE / target).read_text() for target, _ in SECTION_SPECS},
        DOCUMENT_HEADER_LINES,
    )


def build_universal_scheduler_template_text():
    # Styles and layout carry no ministry-specific data, so the template reuses the live files
    # instead of a copy that can drift out of schema.
    sections = dict(TEMPLATE_SECTION_CONTENTS)
    for target in ("config/google_sheets_styles.yaml", "config/google_sheets_layout.yaml"):
        sections[target] = (BASE / target).read_text()
    return _build_document(sections, TEMPLATE_HEADER_LINES)


def write_universal_scheduler(path=UNIVERSAL_SCHEDULER_PATH):
    path.write_text(build_universal_scheduler_text())
    return path


def write_universal_scheduler_template(path=UNIVERSAL_TEMPLATE_PATH):
    path.write_text(build_universal_scheduler_template_text())
    return path


def replace_section_in_universal_text(document_text, target, language, content):
    pattern = re.compile(
        rf"(^## {re.escape(target)}\n\n*```{re.escape(language)}\n)(.*?)(\n```\n?)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(document_text)
    if not match:
        raise ValueError(f"Could not find section '{target}' in {UNIVERSAL_SCHEDULER_PATH}.")

    closing_fence = document_text[match.end() - len(match.group(3)) :]
    return document_text[: match.start()] + match.group(1) + content.rstrip() + closing_fence


def parse_universal_scheduler(path=UNIVERSAL_SCHEDULER_PATH):
    if not path.exists():
        raise FileNotFoundError(f"Universal scheduler file not found: {path}")

    sections = {}
    current_target = None
    in_code_block = False
    buffer = []

    for line in path.read_text().splitlines():
        if current_target is not None and line.startswith("```"):
            if not in_code_block:
                in_code_block = True
                continue

            sections[current_target] = "\n".join(buffer).rstrip() + "\n"
            current_target = None
            in_code_block = False
            buffer = []
        elif current_target is not None and in_code_block:
            buffer.append(line)
        elif line.startswith("## "):
            if current_target is not None:
                raise ValueError(f"Section '{current_target}' is missing a closing code fence.")

            heading = line[3:].strip()
            current_target = heading if heading in SECTION_TARGETS else None
            buffer = []

    if current_target is not None:
        raise ValueError(f"Section '{current_target}' is missing a closing code fence.")

    missing_sections = sorted(SECTION_TARGETS - set(sections))
    if missing_sections:
        raise ValueError("Universal scheduler file is missing sections: " + ", ".join(missing_sections))

    return sections


def sync_rulebook_with_team_sections(sections):
    """Rewrite the rulebook's roster lists from the team section, and return it."""
    team_data = yaml.safe_load(sections["data/team.yaml"]) or {}
    yellows = sorted(
        team_data.get("yellows", []),
        key=lambda person: (int(person.get("editor_rank", 999)), str(person.get("name", ""))),
    )
    reds = [
        name
        for name in (
            str(person.get("name", "") if isinstance(person, dict) else person).strip()
            for person in team_data.get("reds", [])
        )
        if name
    ]

    blocks = (
        (
            r"(## Yellows \(Editor Rank\)\n\n)(.*?)(\n\nDirector Development Track:)",
            "\n".join(f"{index}. {person['name']}" for index, person in enumerate(yellows, start=1))
            or "No yellow members defined.",
        ),
        (
            r"(Director Development Track:\n\n)(.*?)(\n\nDirector-track members may)",
            "\n".join(f"- {person['name']}" for person in yellows if person.get("director_track")) or "- None",
        ),
        (r"(## Reds\n\n)(.*?)(\n\n## Safety Rule)", "\n".join(reds) or "None"),
    )

    rulebook = sections["rules/rulebook.md"]
    for pattern, block in blocks:
        rulebook = re.sub(
            pattern,
            lambda match, block=block: match.group(1) + block + match.group(3),
            rulebook,
            flags=re.DOTALL,
        )
    return rulebook.rstrip() + "\n"


def sync_sections_if_needed(path=UNIVERSAL_SCHEDULER_PATH):
    """Keep the universal file and the generated repo files in step; the newer copy wins."""
    if not path.exists():
        return []

    sections = parse_universal_scheduler(path)
    universal_text = path.read_text()
    # Snapshot once: writing the universal file below must not make other edited files look stale.
    universal_mtime = path.stat().st_mtime
    updated_paths = []

    for target, language in SECTION_SPECS:
        output_path = BASE / target
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(sections[target])
            updated_paths.append(output_path)
            continue

        universal_content = sections[target].rstrip() + "\n"
        file_content = output_path.read_text().rstrip() + "\n"
        if universal_content == file_content:
            continue

        if output_path.stat().st_mtime > universal_mtime:
            universal_text = replace_section_in_universal_text(universal_text, target, language, file_content)
            path.write_text(universal_text)
            if path not in updated_paths:
                updated_paths.append(path)
        else:
            output_path.write_text(universal_content)
            updated_paths.append(output_path)

    rulebook = sync_rulebook_with_team_sections(parse_universal_scheduler(path))
    rulebook_path = BASE / "rules/rulebook.md"
    current_rulebook = rulebook_path.read_text().rstrip() + "\n" if rulebook_path.exists() else ""
    if rulebook != current_rulebook:
        rulebook_path.write_text(rulebook)
        updated_paths.append(rulebook_path)

    refreshed_universal = replace_section_in_universal_text(path.read_text(), "rules/rulebook.md", "md", rulebook)
    if refreshed_universal != path.read_text():
        path.write_text(refreshed_universal)
        if path not in updated_paths:
            updated_paths.append(path)

    return updated_paths


# --------------------------------------------------------------------------- validation


def _load_yaml_section(target, text, issues):
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        issues.append(f"{target}: YAML could not be read: {exc}")
        return None


def _check_positive_int(value, target, field_name, issues, member_name=None):
    if not isinstance(value, int) or value < 1:
        owner = f" for '{member_name}'" if member_name else ""
        issues.append(f"{target}: '{field_name}' must be a positive integer{owner}.")


def _validate_team(team_data, issues):
    """Collect every member name, flagging malformed entries as it goes."""
    member_names = set()
    if not isinstance(team_data, dict):
        issues.append(f"{TEAM_FILE}: top level must be a YAML map.")
        return member_names

    for key in ("greens", "yellows", "reds", "shadows"):
        if key not in team_data:
            issues.append(f"{TEAM_FILE}: missing top-level key '{key}'.")

    def add_name(name):
        if name in member_names:
            issues.append(f"{TEAM_FILE}: duplicate member name '{name}'.")
        member_names.add(name)

    def entries(group):
        people = team_data.get(group, [])
        if not isinstance(people, list):
            issues.append(f"{TEAM_FILE}: '{group}' must be a list.")
            return []
        return list(enumerate(people, start=1))

    for group, shape, required_ranks, optional_ranks in (
        ("greens", "a map with name and ranks", ("shoot_rank", "direct_rank", "editor_rank"), ()),
        ("yellows", "a map with a name", ("editor_rank",), ("shoot_rank", "direct_rank")),
    ):
        for index, person in entries(group):
            if not isinstance(person, dict):
                issues.append(f"{TEAM_FILE}: {group} entry #{index} must be {shape}.")
                continue

            name = str(person.get("name", "")).strip()
            if not name:
                issues.append(f"{TEAM_FILE}: {group} entry #{index} is missing 'name'.")
                continue

            add_name(name)
            for field in required_ranks:
                _check_positive_int(person.get(field), TEAM_FILE, field, issues, name)
            for field in optional_ranks:
                if field in person:
                    _check_positive_int(person.get(field), TEAM_FILE, field, issues, name)
            flags = ("guide", "leader", "leaders", "can_guide")
            if group == "yellows":
                flags = ("director_track", *flags)
            for field in flags:
                if field in person and not isinstance(person[field], bool):
                    issues.append(f"{TEAM_FILE}: '{field}' must be true or false for '{name}'.")

    for index, person in entries("reds"):
        if isinstance(person, dict):
            name = str(person.get("name", "")).strip()
            if not name:
                issues.append(f"{TEAM_FILE}: reds entry #{index} is missing 'name'.")
                continue
            if "shoot_rank" in person:
                _check_positive_int(person["shoot_rank"], TEAM_FILE, "shoot_rank", issues, name)
        elif isinstance(person, str) and person.strip():
            name = person.strip()
        else:
            issues.append(
                f"{TEAM_FILE}: reds entry #{index} must be a member name string or a map with 'name'."
            )
            continue
        add_name(name)

    for index, person in entries("shadows"):
        name = str(person.get("name", "") if isinstance(person, dict) else person).strip()
        if not name:
            issues.append(
                f"{TEAM_FILE}: shadows entry #{index} must be a member name string or a map with 'name'."
            )
            continue
        add_name(name)

    return member_names


def _validate_event_types(event_types_data, issues):
    target = "config/event_types.yaml"
    event_names = set()
    if not isinstance(event_types_data, dict):
        issues.append(f"{target}: top level must be a YAML map.")
        return event_names

    events = event_types_data.get("events")
    if not isinstance(events, dict) or not events:
        issues.append(f"{target}: add an 'events' map with at least one event type.")
        return event_names

    for event_name, spec in events.items():
        event_names.add(str(event_name).strip())
        if not isinstance(spec, dict):
            issues.append(f"{target}: '{event_name}' must map to a settings block.")
            continue

        for field, minimum in (("photographers", 1), ("editors", 0)):
            if not isinstance(spec.get(field), int) or spec[field] < minimum:
                issues.append(f"{target}: '{field}' must be an integer >= {minimum} for '{event_name}'.")

        for field in (
            "assist",
            "floor_runner",
            "sde_director",
            "min_green_photographers",
            "min_yellow_photographers",
            "target_yellow_photographers",
            "min_red_photographers",
            "max_red_photographers",
            "extra_red_photographer",
        ):
            if field in spec and (not isinstance(spec[field], int) or spec[field] < 0):
                issues.append(f"{target}: '{field}' must be an integer >= 0 for '{event_name}'.")

        for field in ("leaders_only", "director_edits"):
            if field in spec and not isinstance(spec[field], bool):
                issues.append(f"{target}: '{field}' must be true or false for '{event_name}'.")
        if str(spec.get("tier", "")).strip().lower() not in {"low", "standard", "high"}:
            issues.append(
                f"{target}: '{event_name}' has invalid tier '{spec.get('tier')}'. Use low, standard, or high."
            )

    return event_names


def _validate_recurring_events(recurring_data, event_names, issues):
    target = "config/recurring_events.yaml"
    if not isinstance(recurring_data, dict):
        issues.append(f"{target}: top level must be a YAML map.")
        return

    rules = recurring_data.get("recurring_events", [])
    if rules and not isinstance(rules, list):
        issues.append(f"{target}: 'recurring_events' must be a list.")
    elif isinstance(rules, list):
        for index, rule in enumerate(rules, start=1):
            if not isinstance(rule, dict):
                issues.append(f"{target}: rule #{index} must be a YAML map.")
                continue

            event_name = str(rule.get("event", "")).strip()
            if not event_name:
                issues.append(f"{target}: rule #{index} is missing 'event'.")
            elif event_names and event_name not in event_names:
                issues.append(
                    f"{target}: recurring event '{event_name}' is not defined in config/event_types.yaml."
                )

            frequency = str(rule.get("frequency", "")).strip().lower()
            if frequency not in {"weekly", "monthly"}:
                issues.append(f"{target}: rule #{index} has invalid frequency '{rule.get('frequency')}'.")
            if str(rule.get("weekday", "")).strip().lower() not in WEEKDAYS:
                issues.append(f"{target}: rule #{index} has invalid weekday '{rule.get('weekday')}'.")
            if frequency == "monthly" and str(rule.get("occurrence", "")).strip().lower() not in {"first", "last"}:
                issues.append(f"{target}: monthly rule #{index} must use occurrence 'first' or 'last'.")

    window = recurring_data.get("generation_window", {})
    if window and not isinstance(window, dict):
        issues.append(f"{target}: 'generation_window' must be a map.")
    elif isinstance(window, dict) and "months_after_last_explicit_event" in window:
        value = window["months_after_last_explicit_event"]
        if not isinstance(value, int) or value < 0:
            issues.append(f"{target}: 'months_after_last_explicit_event' must be 0 or greater.")


def _validate_events_file(text, event_names, issues):
    target = "data/events.md"
    in_exclusions = False
    seen = set()
    saw_event_content = False

    for line_number, line in iter_active_lines(text):
        if not line:
            continue
        if line.startswith("#"):
            in_exclusions = in_exclusions or line.lower().strip() == "## exclusions"
            continue

        match = EVENT_LINE_PATTERN.fullmatch(line)
        if not match:
            if saw_event_content:
                issues.append(
                    f"{target}:{line_number}: use '{DATE_FORMAT} - Event Name'. Could not read '{line}'."
                )
            continue

        date_str, event_name = match.groups()
        try:
            event_date = datetime.strptime(date_str, DATE_FORMAT)
        except ValueError:
            issues.append(f"{target}:{line_number}: '{date_str}' is not a valid date.")
            continue

        saw_event_content = True
        event_name = event_name.strip()
        entry = (event_date.date().isoformat(), event_name, in_exclusions)
        if entry in seen:
            kind = "exclusion" if in_exclusions else "event"
            issues.append(f"{target}:{line_number}: duplicate {kind} '{date_str} - {event_name}'.")
        seen.add(entry)

        if event_names and event_name not in event_names and event_type(event_name) not in event_names:
            issues.append(
                f"{target}:{line_number}: unknown event type '{event_name}'. Add it to config/event_types.yaml."
            )


def _validate_bad_dates_file(text, member_names, issues):
    target = "data/bad_dates.md"
    quarter = None
    member = None
    saw_content = False

    for line_number, line in iter_active_lines(text):
        if not line or line.startswith("# "):
            continue

        if line.startswith("## "):
            saw_content = True
            member = None
            try:
                quarter = normalize_quarter(line[3:])
            except ValueError as exc:
                issues.append(f"{target}:{line_number}: {exc}")
                quarter = None
        elif line.startswith("### "):
            saw_content = True
            if quarter is None:
                issues.append(f"{target}:{line_number}: member heading must come after a quarter heading.")
                continue
            member = line[4:].strip()
            if member_names and member not in member_names:
                issues.append(
                    f"{target}:{line_number}: unknown member '{member}'. Add them to data/team.yaml first."
                )
        elif line.startswith("- "):
            saw_content = True
            if quarter is None or member is None:
                issues.append(
                    f"{target}:{line_number}: dates must be under a quarter heading and member heading."
                )
                continue

            date_str = line[2:].strip()
            try:
                blocked_date = datetime.strptime(date_str, DATE_FORMAT).date()
            except ValueError:
                issues.append(f"{target}:{line_number}: '{date_str}' is not a valid date.")
                continue
            if quarter_key(blocked_date) != quarter:
                issues.append(f"{target}:{line_number}: date '{date_str}' does not belong to {quarter}.")
        elif saw_content:
            issues.append(
                f"{target}:{line_number}: unrecognized line '{line}'. "
                f"Use quarter headings, member headings, and bullet dates."
            )


def _validate_sheets_sync(sync_data, issues):
    target = "config/google_sheets_sync.yaml"
    if not isinstance(sync_data, dict):
        issues.append(f"{target}: top level must be a YAML map.")
        return

    google_sheets = sync_data.get("google_sheets")
    if not isinstance(google_sheets, dict):
        issues.append(f"{target}: add a top-level 'google_sheets' map.")
        return

    for field in ("spreadsheet_id", "worksheet_title", "service_account_json"):
        value = google_sheets.get(field)
        if value is None or str(value).strip() == "":
            issues.append(f"{target}: '{field}' cannot be blank.")


def _validate_scheduler_policy(policy_data, member_names, event_names, issues):
    target = "config/scheduler_policy.yaml"
    if not isinstance(policy_data, dict):
        issues.append(f"{target}: top level must be a YAML map.")
        return

    sections = {
        name: policy_data.get(name, {})
        for name in ("limits", "penalties", "weights", "bonuses", "fallbacks", "safety", "special_rules")
    }
    for name, section in sections.items():
        if section and not isinstance(section, dict):
            issues.append(f"{target}: '{name}' must be a YAML map.")

    for name in ("limits", "penalties", "weights", "bonuses", "fallbacks"):
        section = sections[name]
        if not isinstance(section, dict):
            continue
        for field, value in section.items():
            if not isinstance(value, int) or value < 0:
                issues.append(f"{target}: '{field}' must be an integer >= 0.")

    event_roles = policy_data.get("event_roles", {})
    if event_roles and not isinstance(event_roles, dict):
        issues.append(f"{target}: 'event_roles' must be a YAML map.")
    elif isinstance(event_roles, dict):
        for key, value in event_roles.items():
            if key == "service_marker":
                continue
            for name in value if isinstance(value, list) else [value]:
                if event_names and str(name).strip() not in event_names:
                    issues.append(
                        f"{target}: event_roles.{key} names '{name}', which is not in config/event_types.yaml."
                    )

    required_guides = sections["safety"].get("required_guides_for", [])
    if required_guides and not isinstance(required_guides, list):
        issues.append(f"{target}: 'safety.required_guides_for' must be a list.")
    elif isinstance(required_guides, list):
        for name in required_guides:
            name = str(name).strip()
            if not name:
                issues.append(f"{target}: 'safety.required_guides_for' cannot contain blank names.")
            elif member_names and name not in member_names:
                issues.append(f"{target}: unknown member '{name}' in safety.required_guides_for.")

    special_rules = sections["special_rules"]
    if "use_scoring_only_after_hard_constraints" in special_rules and not isinstance(
        special_rules["use_scoring_only_after_hard_constraints"], bool
    ):
        issues.append(
            f"{target}: 'special_rules.use_scoring_only_after_hard_constraints' must be true or false."
        )


def validate_universal_scheduler_sections(sections):
    issues = []
    loaded = {
        target: _load_yaml_section(target, sections[target], issues)
        for target, language in SECTION_SPECS
        if language == "yaml"
    }

    member_names = _validate_team(loaded["data/team.yaml"], issues)
    event_names = _validate_event_types(loaded["config/event_types.yaml"], issues)
    _validate_recurring_events(loaded["config/recurring_events.yaml"], event_names, issues)
    _validate_events_file(sections["data/events.md"], event_names, issues)
    _validate_bad_dates_file(sections["data/bad_dates.md"], member_names, issues)
    _validate_sheets_sync(loaded["config/google_sheets_sync.yaml"], issues)
    _validate_scheduler_policy(loaded["config/scheduler_policy.yaml"], member_names, event_names, issues)

    if issues:
        raise UniversalSchedulerValidationError(issues)

    return {"member_names": sorted(member_names), "event_names": sorted(event_names)}


# --------------------------------------------------------------------------- entry points


def validate_universal_scheduler(path=UNIVERSAL_SCHEDULER_PATH):
    sync_sections_if_needed(path)
    return validate_universal_scheduler_sections(parse_universal_scheduler(path))


def compile_universal_scheduler(path=UNIVERSAL_SCHEDULER_PATH, validate=True):
    sync_sections_if_needed(path)
    sections = parse_universal_scheduler(path)
    if validate:
        validate_universal_scheduler_sections(sections)

    written_paths = []
    for target, _ in SECTION_SPECS:
        output_path = BASE / target
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(sections[target])
        written_paths.append(output_path)

    return written_paths


def universal_scheduler_needs_sync(path=UNIVERSAL_SCHEDULER_PATH):
    if not path.exists():
        return False

    universal_mtime = path.stat().st_mtime
    return any(
        not (BASE / target).exists() or universal_mtime > (BASE / target).stat().st_mtime
        for target, _ in SECTION_SPECS
    )


def sync_universal_scheduler_if_needed(path=UNIVERSAL_SCHEDULER_PATH, force=False):
    if not path.exists():
        return []

    synced_paths = sync_sections_if_needed(path)
    if force or universal_scheduler_needs_sync(path):
        return [*synced_paths, *compile_universal_scheduler(path)]
    return synced_paths
