import argparse
import json
import random
from collections import defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path

import yaml

from generate_schedule import (
    DATE_FORMAT,
    build_members,
    generate_schedule,
    load_event_types,
    load_google_sheets_layout,
    load_google_sheets_styles,
    load_team,
    parse_bad_dates,
    write_csv,
    write_styles_manifest,
)

BASE = Path(__file__).resolve().parents[1]
SYNC_CONFIG_PATH = BASE / "config/google_sheets_sync.yaml"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


def load_sync_config():
    with open(SYNC_CONFIG_PATH) as f:
        data = yaml.safe_load(f) or {}

    config = data.get("google_sheets")
    if not config:
        raise ValueError(
            "Missing 'google_sheets' section in config/google_sheets_sync.yaml."
        )

    required_fields = {
        "spreadsheet_id",
        "worksheet_title",
        "service_account_json",
        "clear_before_write",
        "create_worksheet_if_missing",
    }
    missing_fields = sorted(required_fields - set(config))
    if missing_fields:
        raise ValueError(
            "Missing fields in config/google_sheets_sync.yaml: "
            + ", ".join(missing_fields)
        )

    service_account_path = Path(config["service_account_json"]).expanduser()
    if not service_account_path.exists():
        raise ValueError(
            "Google service account JSON file not found: "
            f"{service_account_path}"
        )
    service_account_data = json.loads(service_account_path.read_text())

    return {
        "spreadsheet_id": str(config["spreadsheet_id"]).strip(),
        "worksheet_title": str(config["worksheet_title"]).strip(),
        "service_account_json": service_account_path,
        "service_account_email": service_account_data.get("client_email", ""),
        "clear_before_write": bool(config["clear_before_write"]),
        "create_worksheet_if_missing": bool(config["create_worksheet_if_missing"]),
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

    red = int(round(color.get("red", 0) * 255))
    green = int(round(color.get("green", 0) * 255))
    blue = int(round(color.get("blue", 0) * 255))
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


def build_event_matrix(schedule_rows, layout):
    event_column = layout["sheet_layout"]["event_column"]
    blank_event_titles = set(layout["sheet_layout"].get("blank_event_titles", []))
    metadata_rows = event_column["metadata_rows"]
    role_rows = event_column["role_rows"]

    labels = [row["label"] for row in metadata_rows] + [
        row["label"] for row in role_rows
    ]
    values = [[label] + [""] * len(schedule_rows) for label in labels]

    row_key_index = {}
    for index, row in enumerate(metadata_rows):
        row_key_index[row["key"]] = index
    offset = len(metadata_rows)
    for index, row in enumerate(role_rows):
        row_key_index[row["key"]] = offset + index

    for column_index, row in enumerate(schedule_rows, start=1):
        event_datetime = datetime.strptime(row["date"], "%Y-%m-%d")
        event_date = f"{event_datetime.day} {event_datetime.strftime('%b')}"
        values[row_key_index["event_name"]][column_index] = (
            "" if row["event"] in blank_event_titles else row["event"]
        )
        values[row_key_index["event_date"]][column_index] = event_date
        values[row_key_index["unavailable"]][column_index] = row.get("unavailable", "")

        for role in role_rows:
            values[row_key_index[role["key"]]][column_index] = row.get(role["key"], "")

    return values


def month_key(date_str):
    event_datetime = datetime.strptime(date_str, "%Y-%m-%d")
    return event_datetime.year, event_datetime.month


def month_color_map(schedule_rows, styles):
    palette = styles["month_palette"]["colors"]
    unique_months = list(OrderedDict((month_key(row["date"]), None) for row in schedule_rows))
    if not unique_months:
        return {}

    rng = random.Random(f"{unique_months[0][0]}-{unique_months[0][1]}")
    start_index = rng.randrange(len(palette))

    colors = {}
    for index, current_month in enumerate(unique_months):
        colors[current_month] = hex_to_rgb(palette[(start_index + index) % len(palette)])

    return colors


def month_column_groups(schedule_rows):
    groups = []
    if not schedule_rows:
        return groups

    current_month = month_key(schedule_rows[0]["date"])
    start_column = 1

    for index, row in enumerate(schedule_rows, start=1):
        row_month = month_key(row["date"])
        if row_month != current_month:
            groups.append((current_month, start_column, index))
            current_month = row_month
            start_column = index

    groups.append((current_month, start_column, len(schedule_rows) + 1))
    return groups


def user_format_for_cell(row_data, row_index, column_index):
    if row_index >= len(row_data):
        return {}

    values = row_data[row_index].get("values", [])
    if column_index >= len(values):
        return {}

    cell = values[column_index]
    return cell.get("userEnteredFormat") or cell.get("effectiveFormat") or {}


def cell_has_value(row_data, row_index, column_index):
    if row_index >= len(row_data):
        return False

    values = row_data[row_index].get("values", [])
    if column_index >= len(values):
        return False

    cell = values[column_index]
    return bool(cell.get("formattedValue"))


def font_weight_from_format(cell_format):
    return "bold" if cell_format.get("textFormat", {}).get("bold") else "normal"


def update_if_changed(target, key, value):
    if value is None or target.get(key) == value:
        return False

    target[key] = value
    return True


def sync_styles_from_sheet(service, spreadsheet_id, worksheet_title, styles):
    response = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[f"'{worksheet_title}'!A1:ZZ20"],
        includeGridData=True,
        fields=(
            "sheets(properties(gridProperties),"
            "data(rowMetadata(pixelSize),rowData(values(formattedValue,userEnteredFormat,effectiveFormat))))"
        ),
    ).execute()

    sheets = response.get("sheets", [])
    if not sheets or not sheets[0].get("data"):
        return False

    sheet = sheets[0]
    row_data = sheet["data"][0].get("rowData", [])
    row_metadata = sheet["data"][0].get("rowMetadata", [])
    grid_properties = sheet.get("properties", {}).get("gridProperties", {})

    pivot_format = user_format_for_cell(row_data, 0, 0)
    event_name_format = user_format_for_cell(row_data, 0, 1)
    date_format = user_format_for_cell(row_data, 1, 1)
    availability_format = user_format_for_cell(row_data, 2, 1)

    changed = False
    changed |= update_if_changed(
        styles["sheet"], "freeze_header_row", grid_properties.get("frozenRowCount", 0) >= 2
    )
    if row_metadata:
        changed |= update_if_changed(
            styles["sheet"], "header_row_height", row_metadata[0].get("pixelSize")
        )
    changed |= update_if_changed(
        styles["sheet"],
        "font_family",
        pivot_format.get("textFormat", {}).get("fontFamily"),
    )
    changed |= update_if_changed(
        styles["sheet"],
        "horizontal_alignment",
        pivot_format.get("horizontalAlignment"),
    )
    changed |= update_if_changed(
        styles["sheet"],
        "vertical_alignment",
        pivot_format.get("verticalAlignment"),
    )

    changed |= update_if_changed(
        styles["pivot_column"],
        "font_weight",
        font_weight_from_format(pivot_format),
    )
    changed |= update_if_changed(
        styles["pivot_column"],
        "background_color",
        rgb_to_hex(pivot_format.get("backgroundColor")),
    )
    changed |= update_if_changed(
        styles["pivot_column"],
        "text_color",
        rgb_to_hex(pivot_format.get("textFormat", {}).get("foregroundColor")),
    )

    changed |= update_if_changed(
        styles["event_name"],
        "font_weight",
        font_weight_from_format(event_name_format),
    )
    changed |= update_if_changed(
        styles["event_name"],
        "text_color",
        rgb_to_hex(event_name_format.get("textFormat", {}).get("foregroundColor")),
    )
    changed |= update_if_changed(
        styles["event_name"],
        "wrap_strategy",
        event_name_format.get("wrapStrategy"),
    )

    changed |= update_if_changed(
        styles["date_column"],
        "font_weight",
        font_weight_from_format(date_format),
    )
    changed |= update_if_changed(
        styles["date_column"],
        "text_color",
        rgb_to_hex(date_format.get("textFormat", {}).get("foregroundColor")),
    )

    changed |= update_if_changed(
        styles["availability_row"],
        "font_weight",
        font_weight_from_format(availability_format),
    )
    changed |= update_if_changed(
        styles["availability_row"],
        "text_color",
        rgb_to_hex(availability_format.get("textFormat", {}).get("foregroundColor")),
    )

    month_colors = []
    seen_colors = set()
    column_index = 1
    while cell_has_value(row_data, 1, column_index):
        current_color = rgb_to_hex(user_format_for_cell(row_data, 1, column_index).get("backgroundColor"))
        if current_color and current_color not in seen_colors:
            month_colors.append(current_color)
            seen_colors.add(current_color)
        column_index += 1

    if month_colors and styles["month_palette"].get("colors") != month_colors:
        styles["month_palette"]["colors"] = month_colors
        changed = True

    month_border = event_name_format.get("borders", {}).get("top", {})
    if month_border.get("style") and month_border.get("style") != "NONE":
        changed |= update_if_changed(
            styles["month_group_border"], "enabled", True
        )
        changed |= update_if_changed(
            styles["month_group_border"], "style", month_border.get("style")
        )
        changed |= update_if_changed(
            styles["month_group_border"],
            "color",
            rgb_to_hex(month_border.get("color")),
        )

    if len(row_data) >= 17:
        odd_row_color = rgb_to_hex(
            user_format_for_cell(row_data, 15, 0).get("backgroundColor")
        )
        even_row_color = rgb_to_hex(
            user_format_for_cell(row_data, 16, 0).get("backgroundColor")
        )
        if odd_row_color and even_row_color:
            changed |= update_if_changed(styles["alternating_rows"], "enabled", True)
            changed |= update_if_changed(
                styles["alternating_rows"], "odd_row_background", odd_row_color
            )
            changed |= update_if_changed(
                styles["alternating_rows"], "even_row_background", even_row_color
            )

    border_color = rgb_to_hex(pivot_format.get("borders", {}).get("bottom", {}).get("color"))
    border_style = pivot_format.get("borders", {}).get("bottom", {}).get("style")
    if border_color and border_style and border_style != "NONE":
        changed |= update_if_changed(styles["borders"], "enabled", True)
        changed |= update_if_changed(styles["borders"], "color", border_color)

    if changed:
        with open(BASE / "config/google_sheets_styles.yaml", "w") as f:
            yaml.safe_dump(styles, f, sort_keys=False)

    return changed


def slot_names(value):
    if not value:
        return set()
    return {part.strip() for part in str(value).split("+") if part.strip()}


def build_summary_values(schedule_rows, members, layout):
    columns = layout["sheet_layout"]["summary_section"]["columns"]
    values = [columns]

    for name in members:
        shoot = 0
        sde = 0
        direct_assist = 0

        for row in schedule_rows:
            if name == row.get("director", ""):
                direct_assist += 1
            if name == row.get("assist", ""):
                direct_assist += 1
            if name == row.get("floor_runner", ""):
                shoot += 1
            photographer_names = set()
            for field in (
                "photographer_1",
                "photographer_2",
                "photographer_3",
                "photographer_4",
                "photographer_5",
            ):
                photographer_names.update(slot_names(row.get(field, "")))
            if name in photographer_names:
                shoot += 1
            editor_names = slot_names(row.get("sde_1", "")) | slot_names(row.get("sde_2", ""))
            if name in editor_names:
                sde += 1

        has_slot = "Yes" if (shoot + sde + direct_assist) > 0 else "No"
        values.append([name, str(shoot), str(sde), str(direct_assist), has_slot])

    return values


def build_bad_dates_values(members, bad_dates, layout):
    columns = layout["sheet_layout"]["bad_dates_section"]["columns"]
    values = [columns]

    for name in members:
        sorted_dates = sorted(bad_dates.get(name, set()))
        rendered_dates = ", ".join(date.strftime(DATE_FORMAT) for date in sorted_dates)
        row = [name, rendered_dates]
        while len(row) < len(columns):
            row.append("")
        values.append(row[: len(columns)])

    return values


def get_or_create_sheet(service, spreadsheet_id, worksheet_title, create_if_missing):
    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title,index,gridProperties))",
    ).execute()

    normalized_target = worksheet_title.strip().casefold()
    for sheet in metadata.get("sheets", []):
        properties = sheet["properties"]
        existing_title = properties["title"].strip()
        if existing_title == worksheet_title or existing_title.casefold() == normalized_target:
            return properties["sheetId"]

    if not create_if_missing:
        raise ValueError(
            f"Worksheet '{worksheet_title}' does not exist and create_worksheet_if_missing is false."
        )

    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": worksheet_title}}}]},
    ).execute()
    return response["replies"][0]["addSheet"]["properties"]["sheetId"]


def style_from_config(style):
    return {
        "backgroundColor": hex_to_rgb(style["background_color"]),
        "textFormat": {
            "foregroundColor": hex_to_rgb(style["text_color"]),
            "bold": style["font_weight"] == "bold",
        },
    }


def repeat_cell_request(sheet_id, start_row, end_row, start_col, end_col, cell_format):
    format_fields = []
    if "backgroundColor" in cell_format:
        format_fields.append("backgroundColor")
    if "horizontalAlignment" in cell_format:
        format_fields.append("horizontalAlignment")
    if "verticalAlignment" in cell_format:
        format_fields.append("verticalAlignment")
    if "wrapStrategy" in cell_format:
        format_fields.append("wrapStrategy")
    if "textFormat" in cell_format:
        for key in cell_format["textFormat"]:
            format_fields.append(f"textFormat.{key}")

    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "cell": {"userEnteredFormat": cell_format},
            "fields": "userEnteredFormat(" + ",".join(format_fields) + ")",
        }
    }


def add_border_request(sheet_id, row_count, col_count, color):
    border = {"style": "SOLID", "color": hex_to_rgb(color)}
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": row_count,
                "startColumnIndex": 0,
                "endColumnIndex": col_count,
            },
            "top": border,
            "bottom": border,
            "left": border,
            "right": border,
            "innerHorizontal": border,
            "innerVertical": border,
        }
    }


def add_border_range_request(
    sheet_id, start_row, end_row, start_col, end_col, color
):
    border = {"style": "SOLID", "color": hex_to_rgb(color)}
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "top": border,
            "bottom": border,
            "left": border,
            "right": border,
            "innerHorizontal": border,
            "innerVertical": border,
        }
    }


def add_outline_border_range_request(
    sheet_id, start_row, end_row, start_col, end_col, color, style
):
    border = {"style": style, "color": hex_to_rgb(color)}
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "top": border,
            "bottom": border,
            "left": border,
            "right": border,
        }
    }


def add_right_border_range_request(
    sheet_id, start_row, end_row, start_col, end_col, color, style
):
    border = {"style": style, "color": hex_to_rgb(color)}
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "right": border,
        }
    }


def add_bottom_border_range_request(
    sheet_id, start_row, end_row, start_col, end_col, color, style
):
    border = {"style": style, "color": hex_to_rgb(color)}
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "bottom": border,
        }
    }


def clear_border_range_request(sheet_id, start_row, end_row, start_col, end_col):
    clear_border = {"style": "NONE"}
    return {
        "updateBorders": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": start_col,
                "endColumnIndex": end_col,
            },
            "top": clear_border,
            "bottom": clear_border,
            "left": clear_border,
            "right": clear_border,
            "innerHorizontal": clear_border,
            "innerVertical": clear_border,
        }
    }


def format_sheet(
    service,
    spreadsheet_id,
    sheet_id,
    schedule_rows,
    event_matrix,
    summary_values,
    bad_dates_values,
    styles,
    event_types,
):
    requests = []
    total_event_columns = len(schedule_rows) + 1
    event_matrix_height = len(event_matrix)
    summary_start_row = event_matrix_height + 2
    bad_dates_start_col = len(summary_values[0]) + 2
    total_cols = max(total_event_columns, bad_dates_start_col - 1 + len(bad_dates_values[0]))
    total_rows = max(
        event_matrix_height,
        summary_start_row - 1 + len(summary_values),
        summary_start_row - 1 + len(bad_dates_values),
    )

    requests.append(
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
        }
    )

    requests.append(
        repeat_cell_request(
            sheet_id,
            0,
            total_rows,
            0,
            total_cols,
            {
                "horizontalAlignment": styles["sheet"]["horizontal_alignment"],
                "verticalAlignment": styles["sheet"]["vertical_alignment"],
                "textFormat": {"fontFamily": styles["sheet"]["font_family"]},
            },
        )
    )

    requests.append(
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": styles["sheet"]["header_row_height"]},
                "fields": "pixelSize",
            }
        }
    )

    requests.append(
        repeat_cell_request(
            sheet_id,
            0,
            1,
            1,
            total_event_columns,
            style_from_config(styles["event_name"]),
        )
    )
    requests.append(
        repeat_cell_request(
            sheet_id,
            0,
            1,
            1,
            total_event_columns,
            {"wrapStrategy": styles["event_name"]["wrap_strategy"]},
        )
    )
    requests.append(
        repeat_cell_request(
            sheet_id,
            1,
            2,
            1,
            total_event_columns,
            style_from_config(styles["date_column"]),
        )
    )
    if styles["header_divider"]["enabled"]:
        requests.append(
            add_bottom_border_range_request(
                sheet_id,
                0,
                1,
                1,
                total_event_columns,
                styles["header_divider"]["color"],
                styles["header_divider"]["style"],
            )
        )
    requests.append(
        repeat_cell_request(
            sheet_id,
            0,
            event_matrix_height,
            0,
            1,
            style_from_config(styles["pivot_column"]),
        )
    )

    requests.append(
        repeat_cell_request(
            sheet_id,
            2,
            3,
            1,
            total_event_columns,
            style_from_config(styles["availability_row"]),
        )
    )
    requests.append(
        repeat_cell_request(
            sheet_id,
            event_matrix_height,
            event_matrix_height + 1,
            0,
            total_cols,
            {"backgroundColor": {"red": 1, "green": 1, "blue": 1}},
        )
    )
    requests.append(
        clear_border_range_request(
            sheet_id,
            0,
            event_matrix_height,
            0,
            total_event_columns,
        )
    )
    requests.append(
        clear_border_range_request(
            sheet_id,
            event_matrix_height,
            event_matrix_height + 1,
            0,
            total_cols,
        )
    )
    requests.append(
        repeat_cell_request(
            sheet_id,
            0,
            2,
            0,
            total_event_columns,
            {"textFormat": {"bold": True}},
        )
    )

    colors_by_month = month_color_map(schedule_rows, styles)
    for column_index, row in enumerate(schedule_rows, start=1):
        color = colors_by_month[month_key(row["date"])]
        requests.append(
            repeat_cell_request(
                sheet_id,
                0,
                event_matrix_height,
                column_index,
                column_index + 1,
                {"backgroundColor": color},
            )
        )

    summary_width = len(summary_values[0])
    requests.append(
        repeat_cell_request(
            sheet_id,
            summary_start_row - 1,
            summary_start_row,
            0,
            summary_width,
            style_from_config(styles["pivot_column"]),
        )
    )
    requests.append(
        repeat_cell_request(
            sheet_id,
            summary_start_row - 1,
            summary_start_row,
            bad_dates_start_col - 1,
            bad_dates_start_col - 1 + len(bad_dates_values[0]),
            style_from_config(styles["pivot_column"]),
        )
    )

    if styles["alternating_rows"]["enabled"] and len(summary_values) > 1:
        odd_color = {"backgroundColor": hex_to_rgb(styles["alternating_rows"]["odd_row_background"])}
        even_color = {"backgroundColor": hex_to_rgb(styles["alternating_rows"]["even_row_background"])}
        for row_offset in range(1, len(summary_values)):
            row_index = summary_start_row - 1 + row_offset
            requests.append(
                repeat_cell_request(
                    sheet_id,
                    row_index,
                    row_index + 1,
                    0,
                    summary_width,
                    odd_color if row_offset % 2 == 1 else even_color,
                )
        )

    if styles["borders"]["enabled"]:
        requests.append(
            add_border_range_request(
                sheet_id,
                0,
                event_matrix_height,
                0,
                total_event_columns,
                styles["borders"]["color"],
            )
        )
        for _, start_column, end_column in month_column_groups(schedule_rows):
            requests.append(
                add_border_range_request(
                    sheet_id,
                    0,
                    event_matrix_height,
                    start_column,
                    end_column,
                    styles["borders"]["color"],
                )
            )
        requests.append(
            add_border_range_request(
                sheet_id,
                summary_start_row - 1,
                summary_start_row - 1 + len(summary_values),
                0,
                summary_width,
                styles["borders"]["color"],
            )
        )
        requests.append(
            add_border_range_request(
                sheet_id,
                summary_start_row - 1,
                summary_start_row - 1 + len(bad_dates_values),
                bad_dates_start_col - 1,
                bad_dates_start_col - 1 + len(bad_dates_values[0]),
                styles["borders"]["color"],
            )
        )

    if styles["month_group_border"]["enabled"]:
        for _, start_column, end_column in month_column_groups(schedule_rows):
            requests.append(
                add_outline_border_range_request(
                    sheet_id,
                    0,
                    event_matrix_height,
                    start_column,
                    end_column,
                    styles["month_group_border"]["color"],
                    styles["month_group_border"]["style"],
                )
            )
        for _, _, end_column in month_column_groups(schedule_rows)[:-1]:
            requests.append(
                add_right_border_range_request(
                    sheet_id,
                    0,
                    event_matrix_height,
                    end_column - 1,
                    end_column,
                    styles["month_group_border"]["color"],
                    styles["month_group_border"]["style"],
                )
            )

    if styles["column_separator"]["enabled"]:
        month_boundary_columns = {
            end_column - 1 for _, _, end_column in month_column_groups(schedule_rows)[:-1]
        }
        for column_index in range(1, total_event_columns):
            if column_index in month_boundary_columns:
                continue
            requests.append(
                add_right_border_range_request(
                    sheet_id,
                    0,
                    event_matrix_height,
                    column_index,
                    column_index + 1,
                    styles["column_separator"]["color"],
                    styles["column_separator"]["style"],
                )
            )

    requests.append(
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": max(total_event_columns, bad_dates_start_col - 1 + len(bad_dates_values[0])),
                }
            }
        }
    )

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def push_schedule_to_google_sheet(
    generate_first=True, apply_formatting=True, sync_styles_first=False
):
    sync_config = load_sync_config()
    layout = load_google_sheets_layout()
    styles = load_google_sheets_styles()
    event_types = load_event_types()
    members = build_members(load_team())
    bad_dates = parse_bad_dates()

    service = get_sheets_service(sync_config["service_account_json"])
    if sync_styles_first:
        sync_styles_from_sheet(
            service,
            sync_config["spreadsheet_id"],
            sync_config["worksheet_title"],
            styles,
        )
        styles = load_google_sheets_styles()

    if generate_first:
        schedule_rows, fieldnames = generate_schedule()
        write_csv(schedule_rows, fieldnames)
        write_styles_manifest(styles)
    else:
        schedule_rows, _ = generate_schedule()

    event_matrix = build_event_matrix(schedule_rows, layout)
    summary_values = build_summary_values(schedule_rows, members, layout)
    bad_dates_values = build_bad_dates_values(members, bad_dates, layout)

    try:
        sheet_id = get_or_create_sheet(
            service,
            sync_config["spreadsheet_id"],
            sync_config["worksheet_title"],
            sync_config["create_worksheet_if_missing"],
        )

        if sync_config["clear_before_write"]:
            service.spreadsheets().values().clear(
                spreadsheetId=sync_config["spreadsheet_id"],
                range=f"'{sync_config['worksheet_title']}'!A:ZZ",
                body={},
            ).execute()

        summary_start_row = len(event_matrix) + 2
        bad_dates_start_col = len(summary_values[0]) + 2

        data = [
            {
                "range": build_range(sync_config["worksheet_title"], 1, 1, event_matrix),
                "values": event_matrix,
            },
            {
                "range": build_range(
                    sync_config["worksheet_title"], summary_start_row, 1, summary_values
                ),
                "values": summary_values,
            },
            {
                "range": build_range(
                    sync_config["worksheet_title"],
                    summary_start_row,
                    bad_dates_start_col,
                    bad_dates_values,
                ),
                "values": bad_dates_values,
            },
        ]

        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sync_config["spreadsheet_id"],
            body={"valueInputOption": "RAW", "data": data},
        ).execute()

        if apply_formatting:
            format_sheet(
                service,
                sync_config["spreadsheet_id"],
                sheet_id,
                schedule_rows,
                event_matrix,
                summary_values,
                bad_dates_values,
                styles,
                event_types,
            )
    except Exception as exc:
        raise translate_google_error(exc, sync_config) from exc

    if apply_formatting:
        print(
            "Schedule pushed to Google Sheets with formatting: "
            f"{sync_config['worksheet_title']} ({sync_config['spreadsheet_id']})"
        )
    else:
        print(
            "Schedule values pushed to Google Sheets without restyling: "
            f"{sync_config['worksheet_title']} ({sync_config['spreadsheet_id']})"
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
        "--sync-styles-from-sheet",
        action="store_true",
        help="Pull the current sheet's managed styles into config/google_sheets_styles.yaml before pushing values.",
    )
    args = parser.parse_args()

    push_schedule_to_google_sheet(
        generate_first=not args.skip_generate,
        apply_formatting=not args.values_only,
        sync_styles_first=args.sync_styles_from_sheet,
    )


if __name__ == "__main__":
    main()
