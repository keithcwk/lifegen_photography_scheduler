"""Regression checks for the scheduler. Run with: python tests/test_scheduler.py

No framework on purpose: plain asserts, one second to run, fails loudly.
"""

import csv
from datetime import date, timedelta
import difflib
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))

import generate_schedule as scheduler  # noqa: E402
from universal_scheduler import build_universal_scheduler_template_text  # noqa: E402

PHOTOGRAPHER_FIELDS = [f"photographer_{index}" for index in range(1, 6)]


def slot_members(value):
    return [part.strip() for part in value.split("+") if part.strip()]


def row_members(row):
    names = []
    for field, value in row.items():
        if field in ("event", "date", "unavailable") or not value:
            continue
        names.extend(slot_members(value))
    return names


def run_in_copy(tmp, args):
    return subprocess.run([sys.executable, *args], cwd=tmp, capture_output=True, text=True)


def copy_repo(tmp, include_universal=True):
    for folder in ("scripts", "config", "data", "rules"):
        shutil.copytree(BASE / folder, tmp / folder, ignore=shutil.ignore_patterns("__pycache__"))
    if include_universal:
        shutil.copy(BASE / "UNIVERSAL_SCHEDULER.md", tmp / "UNIVERSAL_SCHEDULER.md")
    return tmp


def test_committed_schedule_is_reproducible():
    """The committed CSV is exactly the schedule today's data produces."""
    rows, fieldnames = scheduler.generate_schedule()

    rendered = io.StringIO()
    writer = csv.DictWriter(rendered, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    committed = (BASE / "output/schedule.csv").read_text()
    if rendered.getvalue() != committed:
        diff = difflib.unified_diff(
            committed.splitlines(), rendered.getvalue().splitlines(), "committed", "generated", lineterm=""
        )
        raise AssertionError("output/schedule.csv is stale, regenerate it:\n" + "\n".join(list(diff)[:20]))
    return rows


def test_assignments_respect_the_rules(rows):
    bad_dates = scheduler.parse_bad_dates()
    members = scheduler.members
    event_types = scheduler.load_yaml("config/event_types.yaml")["events"]

    for row in rows:
        event_type = scheduler.event_type(row["event"])
        requirements = event_types.get(row["event"], event_types[event_type])
        names = row_members(row)
        date = scheduler.datetime.strptime(row["date"], "%Y-%m-%d").date()

        for name in names:
            assert date not in bad_dates.get(name, set()), f"{name} scheduled on a bad date {row['date']}"

        photographers = [n for field in PHOTOGRAPHER_FIELDS for n in slot_members(row[field])]
        others = [row[field] for field in ("director", "assist", "sde_director", "floor_runner") if row[field]]
        editors = [row[field] for field in ("sde_1", "sde_2") if row[field]]
        assert len(set(others)) == len(others), f"{row['date']} reuses one person across lead roles"
        assert not set(others) & set(photographers), f"{row['date']} puts a lead role in the photo lineup"

        if requirements.get("sde_director"):
            sde_director = row["sde_director"]
            assert sde_director, f"{row['date']} {row['event']} is missing its SDE director"
            assert scheduler.is_sde_director(sde_director, {"requirements": {"tier": requirements["tier"]}}), f"{sde_director} may not oversee editors"
            assert sde_director not in editors, "SDE director must be a separate person from the editors"

        if requirements.get("leaders_only"):
            non_leaders = [n for n in names if not members[n]["leader"]]
            assert not non_leaders, f"{row['event']} is leaders-only but scheduled {non_leaders}"

        if requirements.get("tier") == "high":
            reds = [n for n in photographers if members[n]["role"] == "red"]
            assert not reds, f"{row['date']} {row['event']} is high tier but has reds: {reds}"

        if requirements.get("greens_only"):
            non_greens = [n for n in names if members[n]["role"] != "green"]
            assert not non_greens, f"{row['event']} is greens-only but scheduled {non_greens}"

        if requirements.get("director_edits"):
            assert editors == [row["director"]], f"{row['date']} {row['event']}: the director should edit"

        if requirements.get("sde_director") and requirements.get("tier") == "low":
            assert members[row["sde_director"]]["role"] == "green", f"{row['date']} low tier SDE director not green"

        if "max_red_photographers" in requirements:
            reds = [n for n in photographers if members[n]["role"] == "red"]
            allowed = requirements["max_red_photographers"] + requirements.get("extra_red_photographer", 0)
            assert len(reds) <= allowed, f"{row['date']} {row['event']} has {len(reds)} reds"
            greens = [n for n in photographers if members[n]["role"] == "green"]
            assert len(greens) >= requirements.get("min_green_photographers", 0), f"{row['date']} too few greens"

        director = members[row["director"]]
        if director["director_track"]:
            reds = [n for n in photographers if members[n]["role"] == "red"]
            assert len(reds) <= 1, f"{row['date']} trainee {row['director']} has {len(reds)} reds"
            green_assist = row["assist"] and members[row["assist"]]["role"] == "green"
            core_green = any(scheduler.is_core_green(n) for n in photographers)
            assert green_assist or core_green, f"{row['date']} trainee {row['director']} is unsupervised"

        if requirements.get("floor_runner"):
            assert row["floor_runner"], f"{row['date']} {row['event']} is missing its floor runner"

        if scheduler.is_event_named(event_type, "balanced_service"):
            visible = sum(1 for field in PHOTOGRAPHER_FIELDS if row[field])
            assert visible == requirements["photographers"], f"{row['date']} shows {visible} photographer slots"
            roles = {members[n]["role"] for n in photographers + others + editors}
            assert {"green", "yellow", "red"} <= roles, f"{row['date']} is missing a tier: {sorted(roles)}"

        for risky in scheduler.required_guides():
            if risky in photographers:
                assert scheduler.has_safety_anchor(photographers), f"{risky} has no guide on {row['date']}"


def test_explicit_sunday_service_survives_a_special_event(rows):
    """25 Oct is the last Leaders Retreat day and a Sunday service: both get their own roster."""
    on_the_day = {row["event"]: row for row in rows if row["date"] == "2026-10-25"}
    assert sorted(on_the_day) == ["Leaders Retreat", "Sunday Service"], sorted(on_the_day)
    filled = lambda row: sum(1 for field in PHOTOGRAPHER_FIELDS if row[field])
    assert filled(on_the_day["Sunday Service"]) == 4
    assert filled(on_the_day["Leaders Retreat"]) == 1


def test_importer_reads_a_sheet_grid():
    """Event labels, session suffixes and the continuation row in BAD DATES all parse."""
    import import_sheet_quarter as importer

    settings = scheduler.load_yaml("config/sheet_import.yaml")
    layout = settings["layout"]
    grid = [
        ["", "October"],
        ["", "PCJB", "", "Prayer"],
        ["Date", "", 46306, 46308],
        ["N/A"],
        ["Director"],
        [],
        ["BAD DATES"],
        ["Names", "Dates", "Reason"],
        ["See Qian", "2/10, 3/10", "PCJB"],
        ["", "18/10", "Wedding"],
        ["Janelle", "22/11", "Assignments"],
    ]
    known_types = set(scheduler.load_yaml("config/event_types.yaml")["events"])
    events, unknown = importer.import_events(grid, layout, settings["event_aliases"], known_types)
    assert unknown == [], unknown
    assert events == ["11 Oct 2026 - Sunday Service", "13 Oct 2026 - Lifegen Prayer"], events

    blocked, unknown_members = importer.import_bad_dates(
        grid, layout, settings["member_aliases"], set(scheduler.members)
    )
    assert unknown_members == [], unknown_members
    assert {name: len(dates) for name, dates in blocked.items()} == {"See Qian": 3, "Janelle": 1}

    # The N/A row blocks its column's date; aliases are case-insensitive.
    grid[3] = ["N/A", "", "hc, Janelle"]
    blocked, unknown_members = importer.import_bad_dates(
        grid, layout, settings["member_aliases"], set(scheduler.members)
    )
    assert unknown_members == [], unknown_members
    assert blocked["Huey Chyi"] == {date(2026, 10, 11)}, blocked

    day = lambda text: importer.sheet_dates(text, 2026)
    d = date
    assert day("2/10") == [d(2026, 10, 2)]
    assert day("18/10/2026") == [d(2026, 10, 18)]
    assert day("18 Oct") == [d(2026, 10, 18)]
    assert day("11/10 - 20/10") == [d(2026, 10, 11) + timedelta(days=n) for n in range(10)]
    assert len(day("26/11-2/12")) == 7
    assert day("27") == [] and day("2-4 Oct") == []  # day labels, not dates


def test_template_generates_a_schedule():
    """A brand new ministry can compile the template and generate, with no hand edits."""
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        shutil.copytree(BASE / "scripts", tmp / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        template = build_universal_scheduler_template_text().replace(
            "<!--\nExample\n06 Apr 2026 - Special Service",
            "06 Apr 2026 - Special Service",
        ).replace("19 Apr 2026 - Sunday Service\n-->", "19 Apr 2026 - Sunday Service")
        (tmp / "UNIVERSAL_SCHEDULER.md").write_text(template)

        checked = run_in_copy(tmp, ["scripts/compile_universal_scheduler.py", "--check"])
        assert checked.returncode == 0, f"template failed validation:\n{checked.stdout}"
        generated = run_in_copy(tmp, ["scripts/generate_schedule.py"])
        assert generated.returncode == 0, f"template failed to generate:\n{generated.stdout}"
        assert len((tmp / "output/schedule.csv").read_text().splitlines()) > 1


def test_universal_file_survives_repeated_runs():
    """Generating must not rewrite or corrupt UNIVERSAL_SCHEDULER.md."""
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = copy_repo(Path(raw_tmp))
        before = (tmp / "UNIVERSAL_SCHEDULER.md").read_text()
        for _ in range(2):
            result = run_in_copy(tmp, ["scripts/generate_schedule.py"])
            assert result.returncode == 0, result.stdout
        after = (tmp / "UNIVERSAL_SCHEDULER.md").read_text()
        assert before.count("```") == after.count("```"), "generate added stray code fences"
        assert before == after, "generate rewrote the universal file"


def test_direct_edits_to_generated_files_win():
    """Edit two generated files by hand: both edits must reach the universal file."""
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = copy_repo(Path(raw_tmp))
        old = (tmp / "UNIVERSAL_SCHEDULER.md").stat().st_mtime
        for relative, marker in (("data/team.yaml", "# team edit"), ("data/events.md", "# events edit")):
            path = tmp / relative
            path.write_text(path.read_text() + f"\n{marker}\n")
            os.utime(path, (old + 60, old + 60))

        result = run_in_copy(tmp, ["scripts/compile_universal_scheduler.py", "--check"])
        assert result.returncode == 0, result.stdout
        universal = (tmp / "UNIVERSAL_SCHEDULER.md").read_text()
        assert "# team edit" in universal, "team.yaml edit was lost"
        assert "# events edit" in universal, "events.md edit was lost"


def main():
    rows = test_committed_schedule_is_reproducible()
    test_assignments_respect_the_rules(rows)
    test_explicit_sunday_service_survives_a_special_event(rows)
    test_importer_reads_a_sheet_grid()
    test_template_generates_a_schedule()
    test_universal_file_survives_repeated_runs()
    test_direct_edits_to_generated_files_win()
    print(f"All checks passed ({len(rows)} scheduled events).")


if __name__ == "__main__":
    main()
