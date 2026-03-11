# AGENTS.md

## Purpose

This repository is a church photography scheduling system.

Codex should treat descriptive user updates as actionable instructions that modify the project and keep the schedule valid under all defined constraints.

When `UNIVERSAL_SCHEDULER.md` exists, prefer editing that file as the source of truth and compiling it back into the repo instead of editing the generated `data/`, `config/`, and `rules/` files directly.

Managed files such as `rules/rulebook.md`, `data/team.yaml`, `data/events.md`, `data/bad_dates.md`, and the scheduler config files are automatically synced with their matching sections inside `UNIVERSAL_SCHEDULER.md`; the more recently edited copy wins.

`UNIVERSAL_SCHEDULER.template.md` is the reusable starter for new ministries.
For non-dev usage, prefer the universal file plus the one-click `.command` launchers instead of direct file-by-file edits.

The system supports:

- Event scheduling
- Team roster management
- Bad date tracking
- Automatic schedule generation
- Replacement suggestions when conflicts occur
- Automatic roster suggestions for new events

---

# Default Behavior

When the user describes a change in plain English, infer the most likely file edits and perform them.

Examples:

User:
Add event 12 Sep 2026 - Youth Camp

Action:

1. Update `data/events.md`
2. Generate a roster suggestion for the event
3. Update `output/schedule.csv`

User:
Keith unavailable 10 May 2026

Action:

1. Update `data/bad_dates.md`
2. Recompute the schedule
3. Suggest a replacement candidate that satisfies constraints.

Ask a follow-up question only if the request is ambiguous enough that editing the wrong file would be risky.

Prefer completing the change end-to-end, including documentation updates when behavior or file formats change.

---

# Schedule Reasoning Mode

When handling availability changes, new events, or replacements, Codex should:

1. Load team roster (`data/team.yaml`)
2. Load scheduling rules (`rules/rulebook.md`)
3. Load event requirements (`config/event_types.yaml`)
4. Load bad date constraints (`data/bad_dates.md`)
5. Load event schedule (`data/events.md`)
6. Inspect generated schedule (`output/schedule.csv`)

Then evaluate which candidate assignments best satisfy all constraints.

---

# Adding New Events

Users may add new events.

Example:

Add event 14 Jun 2026 - Youth Camp

Codex should:

1. Insert the event into `data/events.md`
2. Keep events sorted by date
3. Determine event staffing requirements from `config/event_types.yaml`

If the event type does not exist in `event_types.yaml`, treat it as a **standard event** unless the user specifies otherwise.

Then:

4. Generate a roster suggestion using scheduling constraints
5. Update `output/schedule.csv`
6. Return the suggested team roster in the response

Example output:

Event added:
14 Jun 2026 - Youth Camp

Suggested roster:

Director: Dennis
Photographers: Patrick, Alvin, Joseph, Cindy
Editors: Charites, Jia En

---

# Ad-Hoc Replacement Requests

Users may report last-minute availability changes.

Example:

Felise cannot make it for 10/3 prayer
suggest replacement

Codex should:

1. Identify the event from `data/events.md`
2. Check the assigned role in `output/schedule.csv`
3. Record the conflict in `data/bad_dates.md` if not already present
4. Evaluate replacement candidates

Candidate selection must consider:

- Skill tier compatibility
- Safety constraints defined in `rulebook.md`
- Event tier requirements
- Existing bad dates
- Current workload distribution

Return a ranked list of candidates and recommend the best option.

Example response:

Felise unavailable on 03 Oct 2026.

Suggested replacements:

1. Patrick — similar skill level, available
2. Janelle — available but less experienced
3. Alvin — acceptable but requires supervision

Recommended: Patrick.

---

# Fast Bad-Date Updates

Users may provide short availability inputs.

Examples:

Nic 12 Sep
Huey Chyi 10 Oct

Interpret this as:

Member unavailable on that date.

Codex should update `data/bad_dates.md`.

Example transformation:

Input:

Nic 12 Sep

Output:

## 2026 Q3

### Nic

- 12 Sep 2026

---

# Multiple Bad-Date Updates

Users may submit multiple entries.

Example:

Nic 12 Sep
Huey Chyi 10 Oct
Keith 15 Nov

Codex should:

1. Parse each entry
2. Insert dates under the correct member
3. Place dates in the correct quarter section
4. Avoid duplicates
5. Keep dates sorted

---

# Replacement Candidate Ranking

When selecting a replacement, prefer candidates who:

1. Match the same skill tier (green/yellow/red)
2. Maintain safety constraints
3. Have the lowest recent assignment count
4. Preserve leadership development goals
5. Do not violate existing bad dates

If no perfect candidate exists, choose the closest match and explain the tradeoff.

---

# Roster Generation Rules

When generating a roster for an event:

1. Determine staffing requirements from `config/event_types.yaml`
2. Assign roles in the following order:
   - Director
   - Editors
   - Photographers

Constraints:

- Directors must be green or director-track members
- Reds cannot direct
- Editors should follow editor ranking priority
- Safety rules must be respected (example: supervised members)
- Bad dates must not be violated

Prefer candidates who:

- Have the lowest recent workload
- Maintain skill balance within the team
- Support leadership development goals

---

# Constraint Sources

Codex must consider constraints defined in:

- `rules/rulebook.md`
- `data/team.yaml`
- `config/event_types.yaml`
- `data/bad_dates.md`

Examples of constraints:

- Certain members require supervision
- Some events require stronger teams
- Editors must follow rank priority
- Reds cannot direct

---

# How To Map User Updates To Files

Use these defaults unless the user says otherwise:

Universal scheduler source of truth:
`UNIVERSAL_SCHEDULER.md`

Event date additions, removals, or renames:
`data/events.md`

Event-specific exclusions for recurring or explicit dates:
`data/events.md` under `## Exclusions`

Member unavailability or bad dates:
`data/bad_dates.md`

Team member roster or role changes:
`data/team.yaml`

Green ranking changes (`shoot_rank`, `direct_rank`, `editor_rank`):
`data/team.yaml`

Event staffing requirements or tiers:
`config/event_types.yaml`

Recurring monthly event rules:
`config/recurring_events.yaml`

Google Sheets style tokens:
`config/google_sheets_styles.yaml`

Google Sheets structural layout:
`config/google_sheets_layout.yaml`

Google Sheets target spreadsheet sync settings:
`config/google_sheets_sync.yaml`

Human scheduling rules or policy:
`rules/rulebook.md`

Parser or scheduler logic:
`scripts/generate_schedule.py`

Usage instructions or documentation:
`README.md`

---

# Markdown File Rules

## data/events.md

Active lines must use:

DD Mon YYYY - Event Name

Example:

12 Sep 2026 - Mother's Day

Examples should remain commented out using:

<!-- Example Event -->

---

## data/bad_dates.md

Use quarter headings:

## 2026 Q2

Member headings:

### Keith

Bullet dates:

- 06 Apr 2026

Example:

## 2026 Q2

### Keith

- 06 Apr 2026
- 20 Apr 2026

Keep examples commented out when used as templates.

---

# Google Sheets Layout Rules

The Google Sheets schedule is column-based, not row-based.

Use this structure when the user refers to the Q1 draft sheet or asks for sheet-compatible output:

- each event occupies one column
- row 1 stores the event name
- row 2 stores the event date
- subsequent rows store role assignments

Default role row order:

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

There is also:

- a member summary section for workload tracking
- a bad dates section for availability notes

The machine-readable source of truth for this layout is:

`config/google_sheets_layout.yaml`

Codex may keep a simpler canonical scheduler table internally, but should map it to this event-matrix structure for Google Sheets output.

---

# Date Normalization

User inputs may include partial or alternative formats.

Examples:

12 Sep
Sep 12
12/9
12-09

Normalize all dates to:

DD Mon YYYY

If the year is missing, assume the current scheduling year unless specified.

---

# Working Style

When the user gives a descriptive update:

1. Infer which file(s) should change
2. Modify files directly
3. Preserve project conventions
4. Avoid unnecessary redesign
5. Update documentation if formats change

---

# Verification

After modifying code, run lightweight verification.

Minimum:

python3 -m py_compile scripts/generate_schedule.py

If runtime verification cannot run due to missing dependencies such as `PyYAML`, state this clearly in the final response.

---

# Response Expectations

Be concise and practical.

In the final response summarize:

- What changed
- Which files were edited
- Suggested roster or replacements
- Verification performed
- Any blockers encountered
