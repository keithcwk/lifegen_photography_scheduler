import argparse
import json
import random
from collections import OrderedDict
from datetime import date, datetime, timedelta
from itertools import groupby
from pathlib import Path

import yaml

from universal_scheduler import event_type

from generate_schedule import (
    DATE_FORMAT,
    build_members,
    generate_schedule,
    load_yaml,
    parse_bad_dates,
    write_csv,
    write_styles_manifest,
)

BASE = Path(__file__).resolve().parents[1]
STYLES_PATH = "config/google_sheets_styles.yaml"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEET_EPOCH = date(1899, 12, 30)
PHOTOGRAPHER_FIELDS = tuple(f"photographer_{index}" for index in range(1, 6))
# Per-month summary block columns: rank, Name, Shoot, SDE, Direct/Assist, Has Slot, Total
SUMMARY_BLOCK_WIDTH = 7
ALL_SIDES = ("top", "bottom", "left", "right", "innerHorizontal", "innerVertical")
OUTLINE_SIDES = ("top", "bottom", "left", "right")


def load_sync_config(target=None):
    settings = load_yaml("config/google_sheets_sync.yaml")
    config = settings.get("google_sheets")
    if not config:
        raise ValueError("Missing 'google_sheets' section in config/google_sheets_sync.yaml.")

    if target:
        overrides = settings.get("targets", {}).get(target)
        if overrides is None:
            raise ValueError(
                f"Unknown target '{target}'. Known targets: "
                + ", ".join(sorted(settings.get("targets", {})))
            )
        config = {**config, **overrides}

    missing_fields = sorted(
        {
            "spreadsheet_id",
            "worksheet_title",
            "service_account_json",
            "clear_before_write",
            "create_worksheet_if_missing",
        }
        - set(config)
    )
    if missing_fields:
        raise ValueError(
            "Missing fields in config/google_sheets_sync.yaml: " + ", ".join(missing_fields)
        )

    service_account_path = Path(config["service_account_json"]).expanduser()
    if not service_account_path.exists():
        raise ValueError(f"Google service account JSON file not found: {service_account_path}")

    return {
        "spreadsheet_id": str(config["spreadsheet_id"]).strip(),
        "worksheet_title": str(config["worksheet_title"]).strip(),
        "service_account_json": service_account_path,
        "service_account_email": json.loads(service_account_path.read_text()).get("client_email", ""),
        "clear_before_write": bool(config["clear_before_write"]),
        "create_worksheet_if_missing": bool(config["create_worksheet_if_missing"]),
        "mode": str(config.get("mode", "full")),
        "layout_profile": config.get("layout_profile"),
        "date_window": config.get("date_window"),
        "keep_existing": bool(config.get("keep_existing", True)),
        "only_event_types": list(config.get("only_event_types", [])),
        "exclude_event_types": list(config.get("exclude_event_types", [])),
    }


def get_sheets_service(service_account_json):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Sheets dependencies are missing. Install "
            "'google-api-python-client' and 'google-auth'."
        ) from exc

    credentials = service_account.Credentials.from_service_account_file(
        str(service_account_json),
        scopes=[SHEETS_SCOPE],
    )
    return build("sheets", "v4", credentials=credentials)


# --------------------------------------------------------------------------- cells and ranges


def hex_to_rgb(color):
    color = color.lstrip("#")
    return {
        "red": int(color[0:2], 16) / 255,
        "green": int(color[2:4], 16) / 255,
        "blue": int(color[4:6], 16) / 255,
    }


def rgb_to_hex(color):
    if not color:
        return None

    red, green, blue = (int(round(color.get(key, 0) * 255)) for key in ("red", "green", "blue"))
    return f"#{red:02X}{green:02X}{blue:02X}"


def column_letter(index):
    label = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def build_range(sheet_title, start_row, start_col, values):
    end_row = start_row + len(values) - 1
    end_col = start_col + len(values[0]) - 1
    return (
        f"'{sheet_title}'!"
        f"{column_letter(start_col)}{start_row}:"
        f"{column_letter(end_col)}{end_row}"
    )


def max_row_width(values):
    return max((len(row) for row in values), default=0)


def cell(values, row_index, column_index):
    """Sheet reads drop trailing blanks, so treat anything past a row's end as empty."""
    if row_index >= len(values) or column_index >= len(values[row_index]):
        return ""
    return values[row_index][column_index]


def block_width(values, row_count, start_col):
    return max((max(0, len(row) - (start_col - 1)) for row in values[:row_count]), default=0)


def managed_height(values, start_row, column_ranges):
    """How many rows from `start_row` down still hold data in the managed column ranges."""
    height = 0
    for row_index in range(start_row - 1, len(values)):
        row = values[row_index]
        if any(
            value != ""
            for start_col, width in column_ranges
            for value in row[start_col - 1 : start_col - 1 + width]
        ):
            height = row_index - (start_row - 2)
    return height


def build_block_updates(sheet_title, start_row, start_col, target, current, row_count, col_count):
    """Write only the cells that changed, one update per run of changed cells."""
    updates = []
    changed_cells = 0

    for row_offset in range(row_count):
        def changed(column_offset):
            return cell(target, row_offset, column_offset) != cell(
                current, start_row - 1 + row_offset, start_col - 1 + column_offset
            )

        column_offset = 0
        while column_offset < col_count:
            if not changed(column_offset):
                column_offset += 1
                continue

            segment_start = column_offset
            while column_offset < col_count and changed(column_offset):
                column_offset += 1

            segment = [cell(target, row_offset, offset) for offset in range(segment_start, column_offset)]
            changed_cells += len(segment)
            updates.append(
                {
                    "range": build_range(
                        sheet_title, start_row + row_offset, start_col + segment_start, [segment]
                    ),
                    "values": [segment],
                }
            )

    return updates, changed_cells


def build_incremental_value_updates(
    worksheet_title, current_sheet_values, event_matrix, summary_values, bad_dates_values
):
    matrix_height = len(event_matrix)
    summary_start_row = matrix_height + 2
    summary_width = max_row_width(summary_values)
    bad_dates_start_col = summary_width + 2
    bad_dates_width = max_row_width(bad_dates_values)
    shared_height = max(
        len(summary_values),
        len(bad_dates_values),
        managed_height(
            current_sheet_values,
            summary_start_row,
            [(1, summary_width), (bad_dates_start_col, bad_dates_width)],
        ),
    )

    updates = []
    changed_cells = 0
    for start_row, start_col, target, row_count, col_count in (
        (
            1,
            1,
            event_matrix,
            matrix_height,
            max(max_row_width(event_matrix), block_width(current_sheet_values, matrix_height, 1)),
        ),
        (summary_start_row, 1, summary_values, shared_height, summary_width),
        (summary_start_row, bad_dates_start_col, bad_dates_values, shared_height, bad_dates_width),
    ):
        block_updates, block_changes = build_block_updates(
            worksheet_title, start_row, start_col, target, current_sheet_values, row_count, col_count
        )
        updates.extend(block_updates)
        changed_cells += block_changes

    return updates, changed_cells


def fetch_sheet_values(service, spreadsheet_id, worksheet_title):
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{worksheet_title}'!A:ZZZ")
        .execute()
    )
    return response.get("values", [])


# --------------------------------------------------------------------------- sheet content


def month_key(date_str):
    event_datetime = datetime.strptime(date_str, "%Y-%m-%d")
    return event_datetime.year, event_datetime.month


def month_column_groups(schedule_rows):
    """(month, first column, one past last column) per month block, over 1-based event columns."""
    groups = []
    column = 1
    for month, rows in groupby(schedule_rows, key=lambda row: month_key(row["date"])):
        column_count = len(list(rows))
        groups.append((month, column, column + column_count))
        column += column_count
    return groups


def build_event_matrix(schedule_rows, layout):
    event_column = layout["sheet_layout"]["event_column"]
    blank_event_titles = set(layout["sheet_layout"].get("blank_event_titles", []))
    rows = [*event_column["metadata_rows"], *event_column["role_rows"]]
    row_index = {row["key"]: index for index, row in enumerate(rows)}

    values = [[row["label"]] + [""] * len(schedule_rows) for row in rows]
    for column_index, row in enumerate(schedule_rows, start=1):
        event_datetime = datetime.strptime(row["date"], "%Y-%m-%d")
        values[row_index["event_name"]][column_index] = (
            "" if row["event"] in blank_event_titles else row["event"]
        )
        values[row_index["event_date"]][column_index] = f"{event_datetime.day} {event_datetime.strftime('%b')}"
        values[row_index["unavailable"]][column_index] = row.get("unavailable", "")
        for role in event_column["role_rows"]:
            values[row_index[role["key"]]][column_index] = row.get(role["key"], "")

    return values


def slot_names(value):
    if not value:
        return set()
    return {part.strip() for part in str(value).split("+") if part.strip()}


def count_member_role_frequency(name, rows):
    """Return (shoot, sde, direct_assist) counts for a member; SDE director counts as oversight."""
    shoot = sde = direct_assist = 0
    for row in rows:
        direct_assist += sum(
            name == row.get(field, "") for field in ("director", "assist", "sde_director")
        )
        photographers = set().union(*(slot_names(row.get(field, "")) for field in PHOTOGRAPHER_FIELDS))
        shoot += (name == row.get("floor_runner", "")) + (name in photographers)
        sde += name in slot_names(row.get("sde_1", "")) | slot_names(row.get("sde_2", ""))
    return shoot, sde, direct_assist


def build_summary_values(schedule_rows, members, layout):
    """Tile one per-month frequency block under each month's matrix columns.

    Each block lists every member's Shoot / SDE / Direct-Assist / Has Slot / Total
    counted from that month's events only (mirrors the Q2 2026 reference sheet).
    """
    if not schedule_rows:
        return [["Shoot", "SDE", "Direct/Assist", "Has Slot"]]

    # Align each block to its month's start column, shifting right only to avoid overlap.
    placements = []
    cursor = 1
    for month, start_col, _end_col in month_column_groups(schedule_rows):
        column = max(start_col, cursor)
        placements.append((month, column))
        cursor = column + SUMMARY_BLOCK_WIDTH

    member_names = list(members)
    width = placements[-1][1] - 1 + SUMMARY_BLOCK_WIDTH
    grid = [["" for _ in range(width)] for _ in range(1 + len(member_names))]

    for month, column in placements:
        base = column - 1  # 0-indexed grid column
        for offset, header in enumerate(("Shoot", "SDE", "Direct/Assist", "Has Slot"), start=2):
            grid[0][base + offset] = header

        month_rows = [row for row in schedule_rows if month_key(row["date"]) == month]
        for index, name in enumerate(member_names):
            shoot, sde, direct_assist = count_member_role_frequency(name, month_rows)
            total = shoot + sde + direct_assist
            grid[1 + index][base : base + SUMMARY_BLOCK_WIDTH] = [
                str(index + 1),
                name,
                str(shoot),
                str(sde),
                str(direct_assist),
                "Yes" if total > 0 else "No",
                str(total),
            ]

    return grid


def build_bad_dates_values(members, bad_dates, layout):
    columns = layout["sheet_layout"]["bad_dates_section"]["columns"]
    values = [columns]

    for name in members:
        rendered = ", ".join(blocked.strftime(DATE_FORMAT) for blocked in sorted(bad_dates.get(name, set())))
        values.append(([name, rendered] + [""] * len(columns))[: len(columns)])

    return values


def get_or_create_sheet(service, spreadsheet_id, worksheet_title, create_if_missing):
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title,index,gridProperties))")
        .execute()
    )

    wanted = worksheet_title.strip().casefold()
    for sheet in metadata.get("sheets", []):
        if sheet["properties"]["title"].strip().casefold() == wanted:
            return sheet["properties"]["sheetId"]

    if not create_if_missing:
        raise ValueError(
            f"Worksheet '{worksheet_title}' does not exist and create_worksheet_if_missing is false."
        )

    response = (
        service.spreadsheets()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": worksheet_title}}}]},
        )
        .execute()
    )
    return response["replies"][0]["addSheet"]["properties"]["sheetId"]


# --------------------------------------------------------------------------- reading styles back


def user_format_for_cell(row_data, row_index, column_index):
    if row_index >= len(row_data):
        return {}

    values = row_data[row_index].get("values", [])
    if column_index >= len(values):
        return {}
    return values[column_index].get("userEnteredFormat") or values[column_index].get("effectiveFormat") or {}


def cell_has_value(row_data, row_index, column_index):
    if row_index >= len(row_data):
        return False

    values = row_data[row_index].get("values", [])
    return column_index < len(values) and bool(values[column_index].get("formattedValue"))


def font_weight_from_format(cell_format):
    return "bold" if cell_format.get("textFormat", {}).get("bold") else "normal"


def text_color_from_format(cell_format):
    return rgb_to_hex(cell_format.get("textFormat", {}).get("foregroundColor"))


def update_if_changed(target, key, value):
    if value is None or target.get(key) == value:
        return False

    target[key] = value
    return True


def sheet_month_colors(row_data):
    colors = []
    column_index = 1
    while cell_has_value(row_data, 1, column_index):
        color = rgb_to_hex(user_format_for_cell(row_data, 1, column_index).get("backgroundColor"))
        if color and color not in colors:
            colors.append(color)
        column_index += 1
    return colors


def sync_styles_from_sheet(service, spreadsheet_id, worksheet_title, styles):
    """Adopt the styling the live sheet already uses so pushes stop fighting manual edits."""
    response = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            ranges=[f"'{worksheet_title}'!A1:ZZ20"],
            includeGridData=True,
            fields=(
                "sheets(properties(gridProperties),"
                "data(rowMetadata(pixelSize),rowData(values(formattedValue,userEnteredFormat,effectiveFormat))))"
            ),
        )
        .execute()
    )

    sheets = response.get("sheets", [])
    if not sheets or not sheets[0].get("data"):
        return False

    row_data = sheets[0]["data"][0].get("rowData", [])
    row_metadata = sheets[0]["data"][0].get("rowMetadata", [])
    grid_properties = sheets[0].get("properties", {}).get("gridProperties", {})

    pivot = user_format_for_cell(row_data, 0, 0)
    event_name = user_format_for_cell(row_data, 0, 1)
    date_format = user_format_for_cell(row_data, 1, 1)
    availability = user_format_for_cell(row_data, 2, 1)

    changed = False
    for section, key, value in (
        ("sheet", "freeze_header_row", grid_properties.get("frozenRowCount", 0) >= 2),
        ("sheet", "header_row_height", row_metadata[0].get("pixelSize") if row_metadata else None),
        ("sheet", "font_family", pivot.get("textFormat", {}).get("fontFamily")),
        ("sheet", "horizontal_alignment", pivot.get("horizontalAlignment")),
        ("sheet", "vertical_alignment", pivot.get("verticalAlignment")),
        ("pivot_column", "font_weight", font_weight_from_format(pivot)),
        ("pivot_column", "background_color", rgb_to_hex(pivot.get("backgroundColor"))),
        ("pivot_column", "text_color", text_color_from_format(pivot)),
        ("event_name", "font_weight", font_weight_from_format(event_name)),
        ("event_name", "text_color", text_color_from_format(event_name)),
        ("event_name", "wrap_strategy", event_name.get("wrapStrategy")),
        ("date_column", "font_weight", font_weight_from_format(date_format)),
        ("date_column", "text_color", text_color_from_format(date_format)),
        ("availability_row", "font_weight", font_weight_from_format(availability)),
        ("availability_row", "text_color", text_color_from_format(availability)),
    ):
        changed |= update_if_changed(styles[section], key, value)

    month_colors = sheet_month_colors(row_data)
    if month_colors and styles["month_palette"].get("colors") != month_colors:
        styles["month_palette"]["colors"] = month_colors
        changed = True

    month_border = event_name.get("borders", {}).get("top", {})
    if month_border.get("style") and month_border["style"] != "NONE":
        for key, value in (
            ("enabled", True),
            ("style", month_border["style"]),
            ("color", rgb_to_hex(month_border.get("color"))),
        ):
            changed |= update_if_changed(styles["month_group_border"], key, value)

    if len(row_data) >= 17:
        odd = rgb_to_hex(user_format_for_cell(row_data, 15, 0).get("backgroundColor"))
        even = rgb_to_hex(user_format_for_cell(row_data, 16, 0).get("backgroundColor"))
        if odd and even:
            for key, value in (("enabled", True), ("odd_row_background", odd), ("even_row_background", even)):
                changed |= update_if_changed(styles["alternating_rows"], key, value)

    bottom_border = pivot.get("borders", {}).get("bottom", {})
    border_color = rgb_to_hex(bottom_border.get("color"))
    if border_color and bottom_border.get("style") not in (None, "NONE"):
        changed |= update_if_changed(styles["borders"], "enabled", True)
        changed |= update_if_changed(styles["borders"], "color", border_color)

    if changed:
        with open(BASE / STYLES_PATH, "w") as f:
            yaml.safe_dump(styles, f, sort_keys=False)

    return changed


# --------------------------------------------------------------------------- formatting requests


def grid_range(sheet_id, rows, columns):
    return {
        "sheetId": sheet_id,
        "startRowIndex": rows[0],
        "endRowIndex": rows[1],
        "startColumnIndex": columns[0],
        "endColumnIndex": columns[1],
    }


def repeat_cell_request(sheet_id, rows, columns, cell_format):
    fields = [
        key
        for key in ("backgroundColor", "horizontalAlignment", "verticalAlignment", "wrapStrategy")
        if key in cell_format
    ]
    fields += [f"textFormat.{key}" for key in cell_format.get("textFormat", {})]
    return {
        "repeatCell": {
            "range": grid_range(sheet_id, rows, columns),
            "cell": {"userEnteredFormat": cell_format},
            "fields": "userEnteredFormat(" + ",".join(fields) + ")",
        }
    }


def border_request(sheet_id, rows, columns, sides, color=None, style="SOLID"):
    border = {"style": style, "color": hex_to_rgb(color)} if color else {"style": "NONE"}
    return {
        "updateBorders": {
            "range": grid_range(sheet_id, rows, columns),
            **{side: border for side in sides},
        }
    }


def style_from_config(style):
    return {
        "backgroundColor": hex_to_rgb(style["background_color"]),
        "textFormat": {
            "foregroundColor": hex_to_rgb(style["text_color"]),
            "bold": style["font_weight"] == "bold",
        },
    }


def month_color_map(schedule_rows, styles):
    palette = styles["month_palette"]["colors"]
    months = list(OrderedDict((month_key(row["date"]), None) for row in schedule_rows))
    if not months:
        return {}

    start_index = random.Random(f"{months[0][0]}-{months[0][1]}").randrange(len(palette))
    return {
        month: hex_to_rgb(palette[(start_index + index) % len(palette)])
        for index, month in enumerate(months)
    }


def format_sheet(
    service, spreadsheet_id, sheet_id, schedule_rows, event_matrix, summary_values, bad_dates_values, styles
):
    event_columns = len(schedule_rows) + 1
    matrix_height = len(event_matrix)
    matrix_rows = (0, matrix_height)
    summary_start_row = matrix_height + 2
    summary_width = len(summary_values[0])
    bad_dates_start_col = summary_width + 2
    bad_dates_columns = (bad_dates_start_col - 1, bad_dates_start_col - 1 + len(bad_dates_values[0]))
    total_cols = max(event_columns, bad_dates_columns[1])
    total_rows = max(
        matrix_height,
        summary_start_row - 1 + len(summary_values),
        summary_start_row - 1 + len(bad_dates_values),
    )
    groups = month_column_groups(schedule_rows)
    pivot_style = style_from_config(styles["pivot_column"])

    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 2 if styles["sheet"]["freeze_header_row"] else 0,
                        "frozenColumnCount": 1,
                    },
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        },
        repeat_cell_request(
            sheet_id,
            (0, total_rows),
            (0, total_cols),
            {
                "horizontalAlignment": styles["sheet"]["horizontal_alignment"],
                "verticalAlignment": styles["sheet"]["vertical_alignment"],
                "textFormat": {"fontFamily": styles["sheet"]["font_family"]},
            },
        ),
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": styles["sheet"]["header_row_height"]},
                "fields": "pixelSize",
            }
        },
        repeat_cell_request(sheet_id, (0, 1), (1, event_columns), style_from_config(styles["event_name"])),
        repeat_cell_request(
            sheet_id, (0, 1), (1, event_columns), {"wrapStrategy": styles["event_name"]["wrap_strategy"]}
        ),
        repeat_cell_request(sheet_id, (1, 2), (1, event_columns), style_from_config(styles["date_column"])),
    ]

    if styles["header_divider"]["enabled"]:
        requests.append(
            border_request(
                sheet_id,
                (0, 1),
                (1, event_columns),
                ("bottom",),
                styles["header_divider"]["color"],
                styles["header_divider"]["style"],
            )
        )

    requests += [
        repeat_cell_request(sheet_id, matrix_rows, (0, 1), pivot_style),
        repeat_cell_request(sheet_id, (2, 3), (1, event_columns), style_from_config(styles["availability_row"])),
        repeat_cell_request(
            sheet_id,
            (matrix_height, matrix_height + 1),
            (0, total_cols),
            {"backgroundColor": {"red": 1, "green": 1, "blue": 1}},
        ),
        border_request(sheet_id, matrix_rows, (0, event_columns), ALL_SIDES),
        border_request(sheet_id, (matrix_height, matrix_height + 1), (0, total_cols), ALL_SIDES),
        repeat_cell_request(sheet_id, (0, 2), (0, event_columns), {"textFormat": {"bold": True}}),
    ]

    colors_by_month = month_color_map(schedule_rows, styles)
    requests += [
        repeat_cell_request(
            sheet_id,
            matrix_rows,
            (column_index, column_index + 1),
            {"backgroundColor": colors_by_month[month_key(row["date"])]},
        )
        for column_index, row in enumerate(schedule_rows, start=1)
    ]

    summary_header_rows = (summary_start_row - 1, summary_start_row)
    requests += [
        repeat_cell_request(sheet_id, summary_header_rows, (0, summary_width), pivot_style),
        repeat_cell_request(sheet_id, summary_header_rows, bad_dates_columns, pivot_style),
    ]

    if styles["alternating_rows"]["enabled"] and len(summary_values) > 1:
        backgrounds = (
            {"backgroundColor": hex_to_rgb(styles["alternating_rows"]["even_row_background"])},
            {"backgroundColor": hex_to_rgb(styles["alternating_rows"]["odd_row_background"])},
        )
        requests += [
            repeat_cell_request(
                sheet_id,
                (summary_start_row - 1 + row_offset, summary_start_row + row_offset),
                (0, summary_width),
                backgrounds[row_offset % 2],
            )
            for row_offset in range(1, len(summary_values))
        ]

    if styles["borders"]["enabled"]:
        color = styles["borders"]["color"]
        requests.append(border_request(sheet_id, matrix_rows, (0, event_columns), ALL_SIDES, color))
        requests += [
            border_request(sheet_id, matrix_rows, (start_column, end_column), ALL_SIDES, color)
            for _, start_column, end_column in groups
        ]
        requests += [
            border_request(
                sheet_id,
                (summary_start_row - 1, summary_start_row - 1 + len(summary_values)),
                (0, summary_width),
                ALL_SIDES,
                color,
            ),
            border_request(
                sheet_id,
                (summary_start_row - 1, summary_start_row - 1 + len(bad_dates_values)),
                bad_dates_columns,
                ALL_SIDES,
                color,
            ),
        ]

    if styles["month_group_border"]["enabled"]:
        color, style = styles["month_group_border"]["color"], styles["month_group_border"]["style"]
        requests += [
            border_request(sheet_id, matrix_rows, (start_column, end_column), OUTLINE_SIDES, color, style)
            for _, start_column, end_column in groups
        ]
        requests += [
            border_request(sheet_id, matrix_rows, (end_column - 1, end_column), ("right",), color, style)
            for _, _, end_column in groups[:-1]
        ]

    if styles["column_separator"]["enabled"]:
        month_boundaries = {end_column - 1 for _, _, end_column in groups[:-1]}
        requests += [
            border_request(
                sheet_id,
                matrix_rows,
                (column_index, column_index + 1),
                ("right",),
                styles["column_separator"]["color"],
                styles["column_separator"]["style"],
            )
            for column_index in range(1, event_columns)
            if column_index not in month_boundaries
        ]

    requests.append(
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": max(event_columns, bad_dates_columns[1]),
                }
            }
        }
    )

    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()



# --------------------------------------------------------------------------- hand-built quarter tabs


def parse_sheet_date(value):
    """Row 3 holds date serials once read unformatted."""
    text = str(value).strip()
    if not text:
        return None
    try:
        return SHEET_EPOCH + timedelta(days=int(float(text)))
    except ValueError:
        return None


def fetch_sheet_grid(service, spreadsheet_id, worksheet_title):
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{worksheet_title}'!A:BZ",
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    return response.get("values", [])


def quarter_tab_plan(schedule_rows, current, profile):
    """Map each event onto a sheet column, keeping hand-typed label columns at the front of a month.

    Returns (months, columns) where months is [(label, start_col, end_col)] and columns is
    [(col, kind, payload)] with kind 'keep' (preserve an existing column) or 'event'.
    """
    month_row = profile["month_row"] - 1
    date_row = next(row["row"] for row in profile["metadata_rows"] if row["key"] == "event_date") - 1

    header = current[month_row] if month_row < len(current) else []
    starts = [index for index, value in enumerate(header) if str(value).strip()]
    old_blocks = []
    for position, start in enumerate(starts):
        end = starts[position + 1] - 1 if position + 1 < len(starts) else max(len(header), len(current[date_row]) if date_row < len(current) else 0) - 1
        old_blocks.append((str(header[start]).strip(), start, max(end, start)))

    existing_by_date = {}
    extras_by_block = {start: [] for _, start, _ in old_blocks}
    for _, start, end in old_blocks:
        for column in range(start, end + 1):
            event_date = parse_sheet_date(cell(current, date_row, column))
            if event_date:
                existing_by_date[event_date] = column
            elif any(str(cell(current, row, column)).strip() for row in range(month_row + 1, 17)):
                extras_by_block[start].append(column)

    events_by_month = OrderedDict()
    for row in schedule_rows:
        events_by_month.setdefault(month_key(row["date"]), []).append(row)

    months, columns = [], []
    cursor = 1
    for position, (month, rows) in enumerate(events_by_month.items()):
        label = datetime(month[0], month[1], 1).strftime("%B")
        start = cursor
        for column in extras_by_block.get(old_blocks[position][1], []) if position < len(old_blocks) else []:
            columns.append((cursor, "keep", column))
            cursor += 1
        for row in rows:
            columns.append((cursor, "event", row))
            cursor += 1
        months.append((label, start, cursor - 1))

    return months, columns, existing_by_date


def quarter_tab_values(schedule_rows, current, profile, keep_existing):
    """Full rows 1..last-role grid for the quarter tab, hand-typed cells preserved."""
    months, columns, existing_by_date = quarter_tab_plan(schedule_rows, current, profile)
    metadata = {row["key"]: row["row"] for row in profile["metadata_rows"]}
    roles = {row["key"]: row["row"] for row in profile["role_rows"]}
    last_row = max([profile["month_row"], *metadata.values(), *roles.values()])
    width = max(len(row) for row in current[:last_row]) if current else 0
    grid = [["" for _ in range(max(width, columns[-1][0] + 1 if columns else 1))] for _ in range(last_row)]

    for row_index in range(last_row):  # keep the pivot column labels as they are
        grid[row_index][0] = cell(current, row_index, 0)

    for label, start, end in months:
        grid[profile["month_row"] - 1][start] = label

    reused = set()
    for column, kind, payload in columns:
        if kind == "keep":
            for row_index in range(1, last_row):
                grid[row_index][column] = cell(current, row_index, payload)
            continue

        row = payload
        event_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        # One existing column feeds one event: a second event on the same date starts clean.
        source = existing_by_date.get(event_date)
        source = None if source in reused else source
        reused.add(source)
        typed = lambda sheet_row: cell(current, sheet_row - 1, source) if source is not None else ""

        grid[metadata["event_name"] - 1][column] = typed(metadata["event_name"]) or row["event"]
        grid[metadata["event_date"] - 1][column] = str((event_date - SHEET_EPOCH).days)
        grid[metadata["unavailable"] - 1][column] = typed(metadata["unavailable"]) or row.get("unavailable", "")
        for key, sheet_row in roles.items():
            generated = row.get(key, "")
            existing = typed(sheet_row)
            grid[sheet_row - 1][column] = existing if (keep_existing and existing) else generated

    return grid, months


def quarter_summary_updates(worksheet_title, months, members, profile):
    """Rebuild each month's COUNTIF summary block under its new column span."""
    summary = profile["summary"]
    templates = summary["formulas"]
    data = []
    for label, start, end in months:
        name_col = column_letter(start + 1)
        letters = {key: column_letter(start + 2 + index) for index, key in enumerate(templates)}
        header = [summary["headers"]]
        rows = []
        for index, member in enumerate(members):
            row_number = summary["first_row"] + index
            cells = [member]
            for key, template in templates.items():
                cells.append(
                    template.format(
                        start=column_letter(start + 1),
                        end=column_letter(end + 1),
                        name=name_col,
                        row=row_number,
                        **letters,
                    )
                )
            rows.append(cells)

        data.append(
            {
                # Headers sit beside the name column, which is the month's first column.
                "range": build_range(worksheet_title, summary["header_row"], start + 2, header),
                "values": header,
            }
        )
        data.append(
            {
                "range": build_range(worksheet_title, summary["first_row"], start + 1, rows),
                "values": rows,
            }
        )
    return data


def old_summary_ranges(worksheet_title, current, members, profile):
    """Where the summary blocks sit today, so a move leaves nothing behind."""
    month_row = profile["month_row"] - 1
    summary = profile["summary"]
    last_row = summary["first_row"] + len(members) - 1
    header = current[month_row] if month_row < len(current) else []
    return [
        f"'{worksheet_title}'!{column_letter(start + 1)}{summary['header_row']}:"
        f"{column_letter(start + 7)}{last_row}"
        for start, value in enumerate(header)
        if str(value).strip()
    ]


def push_quarter_tab(service, sync_config, layout, schedule_rows, members, dry_run, restructure):
    profile = layout[sync_config["layout_profile"]]
    spreadsheet_id = sync_config["spreadsheet_id"]
    worksheet_title = sync_config["worksheet_title"]
    window = sync_config.get("date_window")
    if window:
        schedule_rows = [row for row in schedule_rows if window[0] <= row["date"] <= window[1]]
    only = sync_config["only_event_types"]
    excluded = sync_config["exclude_event_types"]
    schedule_rows = [
        row
        for row in schedule_rows
        if (not only or event_type(row["event"]) in only) and event_type(row["event"]) not in excluded
    ]
    if not schedule_rows:
        raise ValueError("No scheduled events left after date_window and event type filters.")

    current = fetch_sheet_grid(service, spreadsheet_id, worksheet_title)
    grid, months = quarter_tab_values(schedule_rows, current, profile, sync_config.get("keep_existing", True))
    updates, changed_cells = build_block_updates(
        worksheet_title, 1, 1, grid, current, len(grid), max_row_width(grid)
    )

    print(f"Column plan for '{worksheet_title}':")
    for label, start, end in months:
        print(f"  {label}: {column_letter(start + 1)}:{column_letter(end + 1)}")
    print(f"Roster rows 1-{len(grid)}: {changed_cells} cell(s) to write in {len(updates)} range(s)")

    summary_data, stale_ranges = [], []
    if restructure:
        summary_data = quarter_summary_updates(worksheet_title, months, members, profile)
        stale_ranges = old_summary_ranges(worksheet_title, current, members, profile)
        print(f"Summary blocks: clear {len(stale_ranges)} old range(s), write {len(summary_data)}")

    if dry_run:
        for stale in stale_ranges:
            print(f"  clear {stale}")
        for update in updates[:10] + summary_data:
            print(f"  {update['range']}")
        if len(updates) > 10:
            print(f"  ... and {len(updates) - 10} more roster ranges")
        print("Dry run: nothing written.")
        return

    if updates:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": updates},
        ).execute()
    if stale_ranges:
        service.spreadsheets().values().batchClear(
            spreadsheetId=spreadsheet_id, body={"ranges": stale_ranges}
        ).execute()
    if summary_data:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": summary_data},
        ).execute()
        remerge_month_headers(service, sync_config, months, profile, len(grid))

    print(
        f"Roster written to '{worksheet_title}': {changed_cells} changed cells"
        + (", summary blocks and month headers rebuilt" if summary_data else "")
    )


def remerge_month_headers(service, sync_config, months, profile, last_row):
    """Re-merge the month headers over their new spans, and unmerge the roster rows.

    A merged roster cell would swallow writes to every column but its first.
    """
    sheet_id = get_or_create_sheet(
        service, sync_config["spreadsheet_id"], sync_config["worksheet_title"], False
    )
    row = profile["month_row"] - 1
    existing = (
        service.spreadsheets()
        .get(
            spreadsheetId=sync_config["spreadsheet_id"],
            ranges=[f"'{sync_config['worksheet_title']}'!A1:ZZ{last_row}"],
            fields="sheets(merges)",
        )
        .execute()
    )
    # Unmerge by each merge's own range: a partial range is rejected by the API.
    requests = [
        {"unmergeCells": {"range": {**merge, "sheetId": sheet_id}}}
        for merge in existing["sheets"][0].get("merges", [])
        if merge["startRowIndex"] < last_row
    ]
    requests += [
        {
            "mergeCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row,
                    "endRowIndex": row + 1,
                    "startColumnIndex": start,
                    "endColumnIndex": end + 1,
                },
                "mergeType": "MERGE_ALL",
            }
        }
        for _, start, end in months
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=sync_config["spreadsheet_id"], body={"requests": requests}
    ).execute()


# --------------------------------------------------------------------------- push


def push_schedule_to_google_sheet(
    generate_first=True, apply_formatting=False, sync_styles_first=False, dry_run=False,
    restructure=False, target=None,
):
    sync_config = load_sync_config(target)
    layout = load_yaml("config/google_sheets_layout.yaml")
    styles = load_yaml(STYLES_PATH)

    service = get_sheets_service(sync_config["service_account_json"])
    if sync_styles_first:
        sync_styles_from_sheet(service, sync_config["spreadsheet_id"], sync_config["worksheet_title"], styles)
        styles = load_yaml(STYLES_PATH)

    schedule_rows, fieldnames = generate_schedule()
    members = build_members(load_yaml("data/team.yaml"))
    bad_dates = parse_bad_dates()
    if generate_first:
        write_csv(schedule_rows, fieldnames)
        write_styles_manifest(styles)

    if sync_config["mode"] == "matrix_only":
        try:
            push_quarter_tab(service, sync_config, layout, schedule_rows, list(members), dry_run, restructure)
        except Exception as exc:
            raise translate_google_error(exc, sync_config) from exc
        return

    event_matrix = build_event_matrix(schedule_rows, layout)
    summary_values = build_summary_values(schedule_rows, members, layout)
    bad_dates_values = build_bad_dates_values(members, bad_dates, layout)
    spreadsheet_id = sync_config["spreadsheet_id"]
    worksheet_title = sync_config["worksheet_title"]

    try:
        sheet_id = get_or_create_sheet(
            service, spreadsheet_id, worksheet_title, sync_config["create_worksheet_if_missing"]
        )

        if sync_config["clear_before_write"]:
            data = [
                {"range": build_range(worksheet_title, start_row, start_col, values), "values": values}
                for start_row, start_col, values in (
                    (1, 1, event_matrix),
                    (len(event_matrix) + 2, 1, summary_values),
                    (len(event_matrix) + 2, len(summary_values[0]) + 2, bad_dates_values),
                )
            ]
            changed_cells = sum(len(row) for block in data for row in block["values"])
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id, range=f"'{worksheet_title}'!A:ZZZ", body={}
            ).execute()
        else:
            data, changed_cells = build_incremental_value_updates(
                worksheet_title,
                fetch_sheet_values(service, spreadsheet_id, worksheet_title),
                event_matrix,
                summary_values,
                bad_dates_values,
            )

        if data:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id, body={"valueInputOption": "RAW", "data": data}
            ).execute()

        if apply_formatting:
            format_sheet(
                service,
                spreadsheet_id,
                sheet_id,
                schedule_rows,
                event_matrix,
                summary_values,
                bad_dates_values,
                styles,
            )
    except Exception as exc:
        raise translate_google_error(exc, sync_config) from exc

    if apply_formatting:
        print(f"Schedule pushed to Google Sheets with formatting: {worksheet_title} ({spreadsheet_id})")
    else:
        print(
            "Schedule values synced incrementally without restyling: "
            f"{changed_cells} changed cells in {worksheet_title} ({spreadsheet_id})"
        )


def translate_google_error(error, sync_config):
    content = getattr(error, "content", b"")
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="ignore")

    if "SERVICE_DISABLED" in content or "Google Sheets API has not been used" in content:
        return RuntimeError(
            "Google Sheets API is not enabled for the service account project yet. "
            "Open the activation link from the error, enable the API, wait a few minutes, "
            "and retry."
        )

    if "PERMISSION_DENIED" in content or "The caller does not have permission" in content:
        return RuntimeError(
            "Google authenticated successfully, but the spreadsheet is not accessible to "
            f"the service account. Share the sheet with {sync_config['service_account_email']} "
            "as an editor and retry."
        )

    return error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Push using freshly computed values without writing local output files first.",
    )
    parser.add_argument(
        "--values-only",
        action="store_true",
        help="Update cell contents only and preserve existing Google Sheets styling.",
    )
    parser.add_argument(
        "--with-formatting",
        action="store_true",
        help="Restyle the managed schedule ranges after pushing values.",
    )
    parser.add_argument(
        "--target",
        help="Named tab from config/google_sheets_sync.yaml targets (e.g. pcjb).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the ranges that would be written and write nothing.",
    )
    parser.add_argument(
        "--restructure",
        action="store_true",
        help="Quarter tabs: also rebuild the month header merges and the summary formulas.",
    )
    parser.add_argument(
        "--sync-styles-from-sheet",
        action="store_true",
        help="Pull the current sheet's managed styles into config/google_sheets_styles.yaml before pushing values.",
    )
    args = parser.parse_args()

    push_schedule_to_google_sheet(
        generate_first=not args.skip_generate,
        apply_formatting=args.with_formatting and not args.values_only,
        sync_styles_first=args.sync_styles_from_sheet,
        dry_run=args.dry_run,
        restructure=args.restructure,
        target=args.target,
    )


if __name__ == "__main__":
    main()
