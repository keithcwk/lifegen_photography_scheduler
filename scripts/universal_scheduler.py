from datetime import datetime
from pathlib import Path
import re
import textwrap

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
DATE_FORMAT = "%d %b %Y"
EVENT_LINE_PATTERN = re.compile(r"(\d{1,2} [A-Za-z]{3} \d{4}) - (.+)")

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

        yellows:
          - name: Example Yellow 1
            shoot_rank: 3
            editor_rank: 1
            director_track: true

          - name: Example Yellow 2
            shoot_rank: 4
            editor_rank: 2

        reds:
          - name: Example Red 1
            shoot_rank: 5
          - name: Example Red 2
            shoot_rank: 6

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
            directors: 1
            editors: 2
            tier: standard

          Prayer Meeting:
            photographers: 2
            directors: 1
            editors: 1
            tier: low

          Leaders Meeting:
            photographers: 2
            directors: 1
            editors: 1
            tier: low

          Special Service:
            photographers: 4
            directors: 1
            editors: 2
            tier: high
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
    "config/google_sheets_styles.yaml": textwrap.dedent(
        """\
        google_sheets_styles:
          font_family: Montserrat
          pivot_column:
            background_color: "#F3F4F6"
          header_rows:
            bold: true
          borders:
            color: "#D0D7DE"
          month_palette:
            colors:
              - "#D9EAD3"
              - "#D0E0E3"
              - "#FCE5CD"
              - "#EAD1DC"
        """
    ),
    "config/google_sheets_layout.yaml": textwrap.dedent(
        """\
        sheet_layout:
          event_matrix:
            pivot_column_label: Role
            event_name_row: 1
            event_date_row: 2
            unavailable_row: 3
          role_rows:
            - Director
            - Assist
            - Photographer 1
            - Photographer 2
            - Photographer 3
            - Photographer 4
            - Photographer 5
            - Floor runner
            - SDE 1
            - SDE 2
          summary_section:
            title: Summary
            headers:
              - Name
              - Shoot
              - SDE
              - Direct/Assist
              - Has Slot
          bad_dates_section:
            title: Bad Dates
            headers:
              - Name
              - Bad Dates
          canonical_scheduler_format:
            columns:
              - event
              - date
              - unavailable
              - director
              - assist
              - photographer_1
              - photographer_2
              - photographer_3
              - photographer_4
              - photographer_5
              - floor_runner
              - sde_1
              - sde_2
              - shadow
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
          max_high_tier_yellow_shoot_rank: 8
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

        special_rules:
          use_scoring_only_after_hard_constraints: true
        """
    ),
}


class UniversalSchedulerValidationError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        message = "Universal scheduler validation failed:\n- " + "\n- ".join(issues)
        super().__init__(message)


def _build_document(section_texts, header_lines):
    lines = list(header_lines)

    for target, language in SECTION_SPECS:
        content = section_texts[target].rstrip() + "\n"
        lines.extend(
            [
                "",
                f"## {target}",
                f"```{language}",
                content.rstrip(),
                "```",
            ]
        )

    return "\n".join(lines) + "\n"


def build_universal_scheduler_text():
    section_texts = {}
    for target, _ in SECTION_SPECS:
        section_texts[target] = (BASE / target).read_text().rstrip() + "\n"
    return _build_document(section_texts, DOCUMENT_HEADER_LINES)


def build_universal_scheduler_template_text():
    return _build_document(TEMPLATE_SECTION_CONTENTS, TEMPLATE_HEADER_LINES)


def write_universal_scheduler(path=UNIVERSAL_SCHEDULER_PATH):
    path.write_text(build_universal_scheduler_text())
    return path


def write_universal_scheduler_template(path=UNIVERSAL_TEMPLATE_PATH):
    path.write_text(build_universal_scheduler_template_text())
    return path


def replace_section_in_universal_text(document_text, target, language, content):
    pattern = re.compile(
        rf"(^## {re.escape(target)}\n(?:\n)*```{re.escape(language)}\n)(.*?)(\n```\n?)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(document_text)
    if not match:
        raise ValueError(f"Could not find section '{target}' in {UNIVERSAL_SCHEDULER_PATH}.")

    normalized_content = content.rstrip() + "\n"
    return document_text[: match.start()] + match.group(1) + normalized_content + "```" + document_text[match.end() - len(match.group(3)) :]



def sync_sections_if_needed(path=UNIVERSAL_SCHEDULER_PATH):
    if not path.exists():
        return []

    sections = parse_universal_scheduler(path)
    universal_text = path.read_text()
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

        if output_path.stat().st_mtime > path.stat().st_mtime:
            universal_text = replace_section_in_universal_text(
                universal_text,
                target,
                language,
                file_content,
            )
            path.write_text(universal_text)
            sections[target] = file_content
            if path not in updated_paths:
                updated_paths.append(path)
        else:
            output_path.write_text(universal_content)
            updated_paths.append(output_path)

    sections = parse_universal_scheduler(path)
    synced_sections = sync_rulebook_with_team_sections(sections)
    synced_rulebook = synced_sections["rules/rulebook.md"]
    current_rulebook_path = BASE / "rules/rulebook.md"
    current_rulebook = current_rulebook_path.read_text().rstrip() + "\n" if current_rulebook_path.exists() else ""
    if synced_rulebook != current_rulebook:
        current_rulebook_path.write_text(synced_rulebook)
        updated_paths.append(current_rulebook_path)

    refreshed_universal = replace_section_in_universal_text(
        path.read_text(),
        "rules/rulebook.md",
        "md",
        synced_rulebook,
    )
    if refreshed_universal != path.read_text():
        path.write_text(refreshed_universal)
        if path not in updated_paths:
            updated_paths.append(path)

    return updated_paths

def parse_universal_scheduler(path=UNIVERSAL_SCHEDULER_PATH):
    if not path.exists():
        raise FileNotFoundError(f"Universal scheduler file not found: {path}")

    lines = path.read_text().splitlines()
    sections = {}
    current_target = None
    in_code_block = False
    buffer = []

    for line in lines:
        if current_target is not None and line.startswith("```"):
            if not in_code_block:
                in_code_block = True
                continue

            sections[current_target] = "\n".join(buffer).rstrip() + "\n"
            current_target = None
            in_code_block = False
            buffer = []
            continue

        if current_target is not None and in_code_block:
            buffer.append(line)
            continue

        if line.startswith("## "):
            if current_target is not None:
                raise ValueError(f"Section '{current_target}' is missing a closing code fence.")

            heading = line[3:].strip()
            current_target = heading if heading in SECTION_TARGETS else None
            in_code_block = False
            buffer = []
            continue

        if current_target is None:
            continue

    if current_target is not None:
        raise ValueError(f"Section '{current_target}' is missing a closing code fence.")

    missing_sections = sorted(SECTION_TARGETS - set(sections))
    if missing_sections:
        raise ValueError(
            "Universal scheduler file is missing sections: " + ", ".join(missing_sections)
        )

    return sections


def _iter_active_lines(text):
    in_comment_block = False

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        if in_comment_block:
            if "-->" in line:
                in_comment_block = False
            continue

        if "<!--" in line:
            if "-->" not in line:
                in_comment_block = True
            continue

        yield line_number, line


def _load_yaml_section(target, text, issues):
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        issues.append(f"{target}: YAML could not be read: {exc}")
        return None


def sync_rulebook_with_team_sections(sections):
    team_data = yaml.safe_load(sections["data/team.yaml"]) or {}
    yellows = sorted(
        team_data.get("yellows", []),
        key=lambda person: (int(person.get("editor_rank", 999)), str(person.get("name", ""))),
    )
    director_track = [
        person["name"]
        for person in yellows
        if bool(person.get("director_track", False))
    ]
    reds = []
    for person in team_data.get("reds", []):
        if isinstance(person, dict):
            name = str(person.get("name", "")).strip()
        else:
            name = str(person).strip()
        if name:
            reds.append(name)

    rulebook = sections["rules/rulebook.md"]
    yellow_block = "\n".join(
        f"{index}. {person['name']}" for index, person in enumerate(yellows, start=1)
    ) or "No yellow members defined."
    director_track_block = "\n".join(f"- {name}" for name in director_track) or "- None"
    reds_block = "\n".join(reds) or "None"

    rulebook = re.sub(
        r"(## Yellows \(Editor Rank\)\n\n)(.*?)(\n\nDirector Development Track:)",
        lambda match: match.group(1) + yellow_block + match.group(3),
        rulebook,
        flags=re.DOTALL,
    )
    rulebook = re.sub(
        r"(Director Development Track:\n\n)(.*?)(\n\nDirector-track members may)",
        lambda match: match.group(1) + director_track_block + match.group(3),
        rulebook,
        flags=re.DOTALL,
    )
    rulebook = re.sub(
        r"(## Reds\n\n)(.*?)(\n\n## Safety Rule)",
        lambda match: match.group(1) + reds_block + match.group(3),
        rulebook,
        flags=re.DOTALL,
    )

    sections["rules/rulebook.md"] = rulebook.rstrip() + "\n"
    return sections

def _check_positive_int(value, target, field_name, issues, member_name=None):
    if not isinstance(value, int) or value < 1:
        owner = f" for '{member_name}'" if member_name else ""
        issues.append(f"{target}: '{field_name}' must be a positive integer{owner}.")


def _normalize_quarter(label):
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

    raise ValueError(f"Use '2026 Q2' or 'Q2 2026', not '{label}'.")


def _quarter_key(date_value):
    quarter = ((date_value.month - 1) // 3) + 1
    return f"{date_value.year} Q{quarter}"


def validate_universal_scheduler_sections(sections):
    issues = []

    team_data = _load_yaml_section("data/team.yaml", sections["data/team.yaml"], issues)
    event_types_data = _load_yaml_section(
        "config/event_types.yaml", sections["config/event_types.yaml"], issues
    )
    recurring_data = _load_yaml_section(
        "config/recurring_events.yaml", sections["config/recurring_events.yaml"], issues
    )
    _load_yaml_section(
        "config/google_sheets_styles.yaml", sections["config/google_sheets_styles.yaml"], issues
    )
    _load_yaml_section(
        "config/google_sheets_layout.yaml", sections["config/google_sheets_layout.yaml"], issues
    )
    sync_data = _load_yaml_section(
        "config/google_sheets_sync.yaml", sections["config/google_sheets_sync.yaml"], issues
    )
    scheduler_policy_data = _load_yaml_section(
        "config/scheduler_policy.yaml", sections["config/scheduler_policy.yaml"], issues
    )

    member_names = set()
    if isinstance(team_data, dict):
        for key in ("greens", "yellows", "reds", "shadows"):
            if key not in team_data:
                issues.append(f"data/team.yaml: missing top-level key '{key}'.")

        greens = team_data.get("greens", [])
        yellows = team_data.get("yellows", [])
        reds = team_data.get("reds", [])
        shadows = team_data.get("shadows", [])

        if not isinstance(greens, list):
            issues.append("data/team.yaml: 'greens' must be a list.")
        else:
            for index, person in enumerate(greens, start=1):
                if not isinstance(person, dict):
                    issues.append(f"data/team.yaml: greens entry #{index} must be a map with name and ranks.")
                    continue
                name = str(person.get("name", "")).strip()
                if not name:
                    issues.append(f"data/team.yaml: greens entry #{index} is missing 'name'.")
                    continue
                if name in member_names:
                    issues.append(f"data/team.yaml: duplicate member name '{name}'.")
                member_names.add(name)
                _check_positive_int(person.get("shoot_rank"), "data/team.yaml", "shoot_rank", issues, name)
                _check_positive_int(person.get("direct_rank"), "data/team.yaml", "direct_rank", issues, name)
                _check_positive_int(person.get("editor_rank"), "data/team.yaml", "editor_rank", issues, name)
                for bool_field in ("guide", "leader", "leaders", "can_guide"):
                    if bool_field in person and not isinstance(person.get(bool_field), bool):
                        issues.append(f"data/team.yaml: '{bool_field}' must be true or false for '{name}'.")

        if not isinstance(yellows, list):
            issues.append("data/team.yaml: 'yellows' must be a list.")
        else:
            for index, person in enumerate(yellows, start=1):
                if not isinstance(person, dict):
                    issues.append(f"data/team.yaml: yellows entry #{index} must be a map with a name.")
                    continue
                name = str(person.get("name", "")).strip()
                if not name:
                    issues.append(f"data/team.yaml: yellows entry #{index} is missing 'name'.")
                    continue
                if name in member_names:
                    issues.append(f"data/team.yaml: duplicate member name '{name}'.")
                member_names.add(name)
                _check_positive_int(person.get("editor_rank"), "data/team.yaml", "editor_rank", issues, name)
                if "shoot_rank" in person:
                    _check_positive_int(person.get("shoot_rank"), "data/team.yaml", "shoot_rank", issues, name)
                if "direct_rank" in person:
                    _check_positive_int(person.get("direct_rank"), "data/team.yaml", "direct_rank", issues, name)
                if "director_track" in person and not isinstance(person.get("director_track"), bool):
                    issues.append(f"data/team.yaml: 'director_track' must be true or false for '{name}'.")
                for bool_field in ("guide", "leader", "leaders", "can_guide"):
                    if bool_field in person and not isinstance(person.get(bool_field), bool):
                        issues.append(f"data/team.yaml: '{bool_field}' must be true or false for '{name}'.")

        if not isinstance(reds, list):
            issues.append("data/team.yaml: 'reds' must be a list.")
        else:
            for index, person in enumerate(reds, start=1):
                if isinstance(person, dict):
                    normalized_name = str(person.get("name", "")).strip()
                    if not normalized_name:
                        issues.append(f"data/team.yaml: reds entry #{index} is missing 'name'.")
                        continue
                    if "shoot_rank" in person:
                        _check_positive_int(
                            person.get("shoot_rank"),
                            "data/team.yaml",
                            "shoot_rank",
                            issues,
                            normalized_name,
                        )
                elif isinstance(person, str) and person.strip():
                    normalized_name = person.strip()
                else:
                    issues.append(
                        f"data/team.yaml: reds entry #{index} must be a member name string or a map with 'name'."
                    )
                    continue
                if normalized_name in member_names:
                    issues.append(f"data/team.yaml: duplicate member name '{normalized_name}'.")
                member_names.add(normalized_name)
        if not isinstance(shadows, list):
            issues.append("data/team.yaml: 'shadows' must be a list.")
        else:
            for index, person in enumerate(shadows, start=1):
                if isinstance(person, dict):
                    normalized_name = str(person.get("name", "")).strip()
                else:
                    normalized_name = str(person).strip()
                if not normalized_name:
                    issues.append(
                        f"data/team.yaml: shadows entry #{index} must be a member name string or a map with 'name'."
                    )
                    continue
                if normalized_name in member_names:
                    issues.append(f"data/team.yaml: duplicate member name '{normalized_name}'.")
                member_names.add(normalized_name)
    else:
        issues.append("data/team.yaml: top level must be a YAML map.")

    event_names = set()
    if isinstance(event_types_data, dict):
        events_map = event_types_data.get("events")
        if not isinstance(events_map, dict) or not events_map:
            issues.append("config/event_types.yaml: add an 'events' map with at least one event type.")
        else:
            for event_name, spec in events_map.items():
                event_names.add(str(event_name).strip())
                if not isinstance(spec, dict):
                    issues.append(f"config/event_types.yaml: '{event_name}' must map to a settings block.")
                    continue
                for field in ("photographers", "directors", "editors"):
                    value = spec.get(field)
                    minimum = 1
                    if field == "directors":
                        value = spec.get("directors", spec.get("director"))
                    if field == "editors":
                        minimum = 0
                    if not isinstance(value, int) or value < minimum:
                        issues.append(
                            f"config/event_types.yaml: '{field}' must be an integer >= {minimum} for '{event_name}'."
                        )
                for optional_int_field in (
                    "assist",
                    "floor_runner",
                    "shadow",
                    "min_green_photographers",
                    "min_yellow_photographers",
                    "min_red_photographers",
                    "max_red_photographers",
                ):
                    if optional_int_field in spec and (
                        not isinstance(spec.get(optional_int_field), int)
                        or spec.get(optional_int_field) < 0
                    ):
                        issues.append(
                            f"config/event_types.yaml: '{optional_int_field}' must be an integer >= 0 for '{event_name}'."
                        )
                if "leaders_only" in spec and not isinstance(spec.get("leaders_only"), bool):
                    issues.append(
                        f"config/event_types.yaml: 'leaders_only' must be true or false for '{event_name}'."
                    )
                tier = str(spec.get("tier", "")).strip().lower()
                if tier not in {"low", "standard", "high"}:
                    issues.append(
                        f"config/event_types.yaml: '{event_name}' has invalid tier '{spec.get('tier')}'. Use low, standard, or high."
                    )
    else:
        issues.append("config/event_types.yaml: top level must be a YAML map.")

    if isinstance(recurring_data, dict):
        recurring_events = recurring_data.get("recurring_events", [])
        if recurring_events and not isinstance(recurring_events, list):
            issues.append("config/recurring_events.yaml: 'recurring_events' must be a list.")
        elif isinstance(recurring_events, list):
            for index, rule in enumerate(recurring_events, start=1):
                if not isinstance(rule, dict):
                    issues.append(f"config/recurring_events.yaml: rule #{index} must be a YAML map.")
                    continue
                event_name = str(rule.get("event", "")).strip()
                if not event_name:
                    issues.append(f"config/recurring_events.yaml: rule #{index} is missing 'event'.")
                elif event_names and event_name not in event_names:
                    issues.append(
                        f"config/recurring_events.yaml: recurring event '{event_name}' is not defined in config/event_types.yaml."
                    )
                frequency = str(rule.get("frequency", "")).strip().lower()
                if frequency not in {"weekly", "monthly"}:
                    issues.append(
                        f"config/recurring_events.yaml: rule #{index} has invalid frequency '{rule.get('frequency')}'."
                    )
                weekday = str(rule.get("weekday", "")).strip().lower()
                if weekday not in {
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                }:
                    issues.append(f"config/recurring_events.yaml: rule #{index} has invalid weekday '{rule.get('weekday')}'.")
                if frequency == "monthly":
                    occurrence = str(rule.get("occurrence", "")).strip().lower()
                    if occurrence not in {"first", "last"}:
                        issues.append(
                            f"config/recurring_events.yaml: monthly rule #{index} must use occurrence 'first' or 'last'."
                        )
        generation_window = recurring_data.get("generation_window", {})
        if generation_window and not isinstance(generation_window, dict):
            issues.append("config/recurring_events.yaml: 'generation_window' must be a map.")
        elif isinstance(generation_window, dict) and "months_after_last_explicit_event" in generation_window:
            value = generation_window.get("months_after_last_explicit_event")
            if not isinstance(value, int) or value < 0:
                issues.append(
                    "config/recurring_events.yaml: 'months_after_last_explicit_event' must be 0 or greater."
                )
    else:
        issues.append("config/recurring_events.yaml: top level must be a YAML map.")

    exclusions_started = False
    seen_events = set()
    saw_event_content = False
    for line_number, line in _iter_active_lines(sections["data/events.md"]):
        if not line:
            continue
        if line.startswith("#"):
            if line.lower().strip() == "## exclusions":
                exclusions_started = True
            continue
        match = EVENT_LINE_PATTERN.fullmatch(line)
        if not match:
            if not saw_event_content:
                continue
            issues.append(
                f"data/events.md:{line_number}: use '{DATE_FORMAT} - Event Name'. Could not read '{line}'."
            )
            continue
        date_str, event_name = match.groups()
        try:
            event_date = datetime.strptime(date_str, DATE_FORMAT)
        except ValueError:
            issues.append(f"data/events.md:{line_number}: '{date_str}' is not a valid date.")
            continue
        saw_event_content = True
        normalized = (event_date.date().isoformat(), event_name.strip(), exclusions_started)
        if normalized in seen_events:
            issues.append(
                f"data/events.md:{line_number}: duplicate {'exclusion' if exclusions_started else 'event'} '{date_str} - {event_name.strip()}'."
            )
        seen_events.add(normalized)
        if event_names and event_name.strip() not in event_names:
            issues.append(
                f"data/events.md:{line_number}: unknown event type '{event_name.strip()}'. Add it to config/event_types.yaml."
            )

    current_quarter = None
    current_member = None
    saw_bad_dates_content = False
    for line_number, line in _iter_active_lines(sections["data/bad_dates.md"]):
        if not line or line.startswith("# "):
            continue
        if line.startswith("## "):
            saw_bad_dates_content = True
            try:
                current_quarter = _normalize_quarter(line[3:])
            except ValueError as exc:
                issues.append(f"data/bad_dates.md:{line_number}: {exc}")
                current_quarter = None
            current_member = None
            continue
        if line.startswith("### "):
            saw_bad_dates_content = True
            if current_quarter is None:
                issues.append(
                    f"data/bad_dates.md:{line_number}: member heading must come after a quarter heading."
                )
                continue
            current_member = line[4:].strip()
            if member_names and current_member not in member_names:
                issues.append(
                    f"data/bad_dates.md:{line_number}: unknown member '{current_member}'. Add them to data/team.yaml first."
                )
            continue
        if line.startswith("- "):
            saw_bad_dates_content = True
            if current_quarter is None or current_member is None:
                issues.append(
                    f"data/bad_dates.md:{line_number}: dates must be under a quarter heading and member heading."
                )
                continue
            date_str = line[2:].strip()
            try:
                blocked_date = datetime.strptime(date_str, DATE_FORMAT).date()
            except ValueError:
                issues.append(f"data/bad_dates.md:{line_number}: '{date_str}' is not a valid date.")
                continue
            if _quarter_key(blocked_date) != current_quarter:
                issues.append(
                    f"data/bad_dates.md:{line_number}: date '{date_str}' does not belong to {current_quarter}."
                )
            continue
        if not saw_bad_dates_content:
            continue
        issues.append(
            f"data/bad_dates.md:{line_number}: unrecognized line '{line}'. Use quarter headings, member headings, and bullet dates."
        )

    if isinstance(sync_data, dict):
        google_sheets = sync_data.get("google_sheets")
        if not isinstance(google_sheets, dict):
            issues.append("config/google_sheets_sync.yaml: add a top-level 'google_sheets' map.")
        else:
            for field in ("spreadsheet_id", "worksheet_title", "service_account_json"):
                value = google_sheets.get(field)
                if value is None or str(value).strip() == "":
                    issues.append(f"config/google_sheets_sync.yaml: '{field}' cannot be blank.")
    else:
        issues.append("config/google_sheets_sync.yaml: top level must be a YAML map.")

    if isinstance(scheduler_policy_data, dict):
        limits = scheduler_policy_data.get("limits", {})
        penalties = scheduler_policy_data.get("penalties", {})
        weights = scheduler_policy_data.get("weights", {})
        bonuses = scheduler_policy_data.get("bonuses", {})
        fallbacks = scheduler_policy_data.get("fallbacks", {})
        safety = scheduler_policy_data.get("safety", {})
        special_rules = scheduler_policy_data.get("special_rules", {})

        for section_name, section_data in (
            ("limits", limits),
            ("penalties", penalties),
            ("weights", weights),
            ("bonuses", bonuses),
            ("fallbacks", fallbacks),
            ("safety", safety),
            ("special_rules", special_rules),
        ):
            if section_data and not isinstance(section_data, dict):
                issues.append(f"config/scheduler_policy.yaml: '{section_name}' must be a YAML map.")

        for field_name in (
            "max_assignments_per_member_per_month",
            "max_director_track_directs_per_month",
            "max_red_assignments_per_month",
            "max_high_tier_yellow_shoot_rank",
            "max_high_tier_yellow_editor_rank",
            "high_tier_reserve_window_days",
            "high_tier_recent_window_days",
            "max_same_high_tier_event_assignments",
            "creative_team_meet_max_yellow_editor_rank",
            "creative_team_meet_anchor_yellow_shoot_rank",
        ):
            if field_name in limits and (
                not isinstance(limits.get(field_name), int) or limits.get(field_name) < 0
            ):
                issues.append(
                    f"config/scheduler_policy.yaml: '{field_name}' must be an integer >= 0."
                )

        for field_name, source in (
            ("consecutive_event_penalty", penalties),
            ("repeated_high_tier_event_penalty", penalties),
            ("recent_high_tier_window_penalty", penalties),
            ("repeated_event_editor_pair_penalty", penalties),
            ("repeated_low_tier_event_penalty", penalties),
            ("repeated_weekday_low_tier_penalty", penalties),
            ("weekday_late_low_tier_penalty", penalties),
            ("multi_day_high_tier_early_day_strength_reserve", penalties),
            ("upcoming_high_tier_reserve_penalty", penalties),
            ("upcoming_high_tier_preload_penalty", penalties),
            ("upcoming_high_tier_preload_same_role_penalty", penalties),
            ("priority_rank", weights),
            ("role_serve_count", weights),
            ("total_serve_count", weights),
            ("first_monthly_photographer_assignment", bonuses),
            ("yellow_photo_coverage_bonus", bonuses),
            ("green_editor_rotation_bonus", bonuses),
            ("weekend_service_for_weekday_late_member", bonuses),
            ("multi_day_high_tier_final_day_strength_boost", bonuses),
            ("creative_team_meet_anchor_bonus", bonuses),
            ("blank_rank_value", fallbacks),
        ):
            if field_name in source and (
                not isinstance(source.get(field_name), int) or source.get(field_name) < 0
            ):
                issues.append(
                    f"config/scheduler_policy.yaml: '{field_name}' must be an integer >= 0."
                )

        required_guides_for = safety.get("required_guides_for", [])
        if required_guides_for and not isinstance(required_guides_for, list):
            issues.append("config/scheduler_policy.yaml: 'safety.required_guides_for' must be a list.")
        elif isinstance(required_guides_for, list):
            for name in required_guides_for:
                normalized_name = str(name).strip()
                if not normalized_name:
                    issues.append(
                        "config/scheduler_policy.yaml: 'safety.required_guides_for' cannot contain blank names."
                    )
                elif member_names and normalized_name not in member_names:
                    issues.append(
                        f"config/scheduler_policy.yaml: unknown member '{normalized_name}' in safety.required_guides_for."
                    )

        if (
            "use_scoring_only_after_hard_constraints" in special_rules
            and not isinstance(special_rules.get("use_scoring_only_after_hard_constraints"), bool)
        ):
            issues.append(
                "config/scheduler_policy.yaml: 'special_rules.use_scoring_only_after_hard_constraints' must be true or false."
            )
    else:
        issues.append("config/scheduler_policy.yaml: top level must be a YAML map.")

    if issues:
        raise UniversalSchedulerValidationError(issues)

    return {
        "member_names": sorted(member_names),
        "event_names": sorted(event_names),
    }


def validate_universal_scheduler(path=UNIVERSAL_SCHEDULER_PATH):
    sync_sections_if_needed(path)
    sections = parse_universal_scheduler(path)
    return validate_universal_scheduler_sections(sections)


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
    for target, _ in SECTION_SPECS:
        output_path = BASE / target
        if not output_path.exists() or universal_mtime > output_path.stat().st_mtime:
            return True

    return False


def sync_universal_scheduler_if_needed(path=UNIVERSAL_SCHEDULER_PATH, force=False):
    if not path.exists():
        return []

    synced_paths = sync_sections_if_needed(path)

    if force or universal_scheduler_needs_sync(path):
        return [*synced_paths, *compile_universal_scheduler(path)]

    return synced_paths
