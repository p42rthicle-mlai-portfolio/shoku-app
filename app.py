# Shoku (Food Tracker) (Streamlit v0)
# MVP: meals, units, foods+dishes, per-day goal locking, calendar view, mandatory list, dashboard

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import io
import calendar
from contextlib import contextmanager
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Tuple

import shutil
import os
import tempfile
import zipfile

# --- 1. SECURITY LAYER ---
def check_password():
    """Returns `True` if the user has the correct password."""
    def password_entered():
        # Compares entered password against the secret stored on the server
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Remove password from session state for security
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    return True

# Stop the app from loading the rest of the code if the password is wrong
if not check_password():
    st.stop()


# --- YOUR EXISTING APP.PY CODE STARTS HERE ---
# (Keep all your original logic below this line)

if "allow_edit_past" not in st.session_state:
    st.session_state.allow_edit_past = False

DATA_DIR = Path(__file__).parent / "data"
FOODS_CSV = DATA_DIR / "foods.csv"
DISHES_CSV = DATA_DIR / "dishes.csv"
DISH_ING_CSV = DATA_DIR / "dish_ingredients.csv"
GOALS_CSV = DATA_DIR / "goals.csv"
LOGS_CSV = DATA_DIR / "logs.csv"
BATCHES_CSV = DATA_DIR / "batches.csv"
BATCH_ING_CSV = DATA_DIR / "batch_ingredients.csv"
BACKUP_ZIP = Path(__file__).parent / "backup_data.zip"

TRACKED_NUTRIENTS = [
    {
        "key": "calories",
        "label": "Calories",
        "unit": "kcal",
        "decimals": 0,
        "food_base_col": "calories_base",
        "food_per_unit_col": "cal_per_unit",
        "dish_override_col": "cal_override",
        "log_col": "calories",
        "batch_total_col": "total_calories",
    },
    {
        "key": "protein",
        "label": "Protein",
        "unit": "g",
        "decimals": 1,
        "food_base_col": "protein_base",
        "food_per_unit_col": "protein_per_unit",
        "dish_override_col": "protein_override",
        "log_col": "protein",
        "batch_total_col": "total_protein",
    },
    {
        "key": "fiber",
        "label": "Fiber",
        "unit": "g",
        "decimals": 1,
        "food_base_col": "fiber_base",
        "food_per_unit_col": "fiber_per_unit",
        "dish_override_col": "fiber_override",
        "log_col": "fiber",
        "batch_total_col": "total_fiber",
    },
]
NUTRIENT_BY_KEY = {spec["key"]: spec for spec in TRACKED_NUTRIENTS}
FOOD_NUMERIC_COLUMNS = ["base_qty"] + [
    col
    for spec in TRACKED_NUTRIENTS
    for col in [spec["food_base_col"], spec["food_per_unit_col"]]
]
DISH_NUMERIC_COLUMNS = ["servings", "yield_qty"] + [
    spec["dish_override_col"] for spec in TRACKED_NUTRIENTS
]
LOG_NUMERIC_COLUMNS = ["qty"] + [spec["log_col"] for spec in TRACKED_NUTRIENTS]
BATCH_NUMERIC_COLUMNS = ["servings", "final_qty"] + [
    spec["batch_total_col"] for spec in TRACKED_NUTRIENTS
]

FOOD_COLUMNS = [
    "food_name",
    "unit",
    "base_qty",
    "calories_base",
    "protein_base",
    "fiber_base",
    "cal_per_unit",
    "protein_per_unit",
    "fiber_per_unit",
]
DISH_COLUMNS = [
    "dish_name",
    "cal_override",
    "protein_override",
    "fiber_override",
    "servings",
    "yield_qty",
    "yield_unit",
]
DISH_INGREDIENT_COLUMNS = [
    "dish_name",
    "ingredient_type",
    "ingredient_food_name",
    "ingredient_unit",
    "ingredient_qty_per_serving",
    "ingredient_batch_id",
]
GOAL_COLUMNS = ["date", "calorie_goal", "protein_goal"]
LOG_COLUMNS = [
    "log_id",
    "date",
    "meal",
    "type",
    "name",
    "batch_id",
    "unit",
    "qty",
    "calories",
    "protein",
    "fiber",
    "checked",
]
BATCH_COLUMNS = [
    "batch_id",
    "dish_name",
    "batch_date",
    "servings",
    "final_qty",
    "final_unit",
    "yield_source",
    "total_calories",
    "total_protein",
    "total_fiber",
    "notes",
]
BATCH_INGREDIENT_COLUMNS = [
    "batch_id",
    "ingredient_type",
    "ingredient_food_name",
    "ingredient_unit",
    "ingredient_qty",
    "ingredient_batch_id",
]
DATE_INPUT_FORMAT = "DD/MM/YYYY"
MEAL_OPTIONS = ["Breakfast", "Lunch", "Snacks", "Dinner"]
REQUIRED_BACKUP_FILES = {
    "foods.csv": FOOD_COLUMNS,
    "dishes.csv": DISH_COLUMNS,
    "dish_ingredients.csv": DISH_INGREDIENT_COLUMNS,
    "goals.csv": GOAL_COLUMNS,
    "logs.csv": LOG_COLUMNS,
}
OPTIONAL_BACKUP_FILES = {
    "batches.csv": BATCH_COLUMNS,
    "batch_ingredients.csv": BATCH_INGREDIENT_COLUMNS,
}

# ---------- Utilities ----------


def ensure_csv(path: Path, columns: list):
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)
    df = pd.read_csv(path)
    # Make sure all expected columns exist
    for c in columns:
        if c not in df.columns:
            df[c] = None
    # Keep only expected columns (order)
    df = df[columns]
    df.to_csv(path, index=False)  # normalize
    return df


def load_all():
    foods = ensure_csv(
        # FOODS_CSV, ["food_name", "unit", "cal_per_unit", "protein_per_unit"]
        FOODS_CSV, FOOD_COLUMNS
    )
    dishes = ensure_csv(DISHES_CSV, DISH_COLUMNS)
    dings = ensure_csv(DISH_ING_CSV, DISH_INGREDIENT_COLUMNS)
    goals = ensure_csv(GOALS_CSV, GOAL_COLUMNS)
    logs = ensure_csv(LOGS_CSV, LOG_COLUMNS)
    batches = ensure_csv(BATCHES_CSV, BATCH_COLUMNS)
    batch_ings = ensure_csv(BATCH_ING_CSV, BATCH_INGREDIENT_COLUMNS)
    # Coerce types
    for col in FOOD_NUMERIC_COLUMNS:
        if col in foods.columns:
            foods[col] = pd.to_numeric(foods[col], errors="coerce")
    for col in DISH_NUMERIC_COLUMNS:
        if col in dishes.columns:
            dishes[col] = pd.to_numeric(dishes[col], errors="coerce")
    for col in ["ingredient_qty_per_serving"]:
        if col in dings.columns:
            dings[col] = pd.to_numeric(dings[col], errors="coerce")
    for col in ["calorie_goal", "protein_goal"]:
        if col in goals.columns:
            goals[col] = pd.to_numeric(goals[col], errors="coerce")
    for col in LOG_NUMERIC_COLUMNS:
        if col in logs.columns:
            logs[col] = pd.to_numeric(logs[col], errors="coerce")
    logs = ensure_log_ids(logs)
    if "checked" in logs.columns:
        logs["checked"] = to_bool_series(logs["checked"])
    for col in BATCH_NUMERIC_COLUMNS:
        if col in batches.columns:
            batches[col] = pd.to_numeric(batches[col], errors="coerce")
    for col in ["ingredient_qty"]:
        if col in batch_ings.columns:
            batch_ings[col] = pd.to_numeric(batch_ings[col], errors="coerce")
    return foods, dishes, dings, goals, logs, batches, batch_ings


def save_df(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False)


def to_bool_series(values: pd.Series) -> pd.Series:
    return (
        values.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y"])
    )


def make_log_id(log_day: date) -> str:
    return f"log_{log_day.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S%f')}"


def ensure_log_ids(logs: pd.DataFrame) -> pd.DataFrame:
    if "log_id" not in logs.columns:
        logs["log_id"] = None

    seen_ids = set()
    updates_made = False
    for idx in logs.index:
        current_id = as_text(logs.at[idx, "log_id"])
        if not current_id or current_id in seen_ids:
            log_day = parse_date_value(logs.at[idx, "date"]) or date.today()
            current_id = make_log_id(log_day)
            while current_id in seen_ids:
                current_id = make_log_id(log_day)
            logs.at[idx, "log_id"] = current_id
            updates_made = True
        seen_ids.add(current_id)

    if updates_made:
        save_df(logs, LOGS_CSV)
    return logs


def empty_df(columns: list) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def reset_csv(path: Path, columns: list):
    empty_df(columns).to_csv(path, index=False)


def reset_all_data():
    reset_csv(FOODS_CSV, FOOD_COLUMNS)
    reset_csv(DISHES_CSV, DISH_COLUMNS)
    reset_csv(DISH_ING_CSV, DISH_INGREDIENT_COLUMNS)
    reset_csv(GOALS_CSV, GOAL_COLUMNS)
    reset_csv(LOGS_CSV, LOG_COLUMNS)
    reset_csv(BATCHES_CSV, BATCH_COLUMNS)
    reset_csv(BATCH_ING_CSV, BATCH_INGREDIENT_COLUMNS)


def normalize_import_df(df: pd.DataFrame, columns: list) -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = None
    return df[columns]


def get_backup_sources():
    return {
        "foods.csv": FOODS_CSV,
        "dishes.csv": DISHES_CSV,
        "dish_ingredients.csv": DISH_ING_CSV,
        "goals.csv": GOALS_CSV,
        "logs.csv": LOGS_CSV,
        "batches.csv": BATCHES_CSV,
        "batch_ingredients.csv": BATCH_ING_CSV,
    }


def build_backup_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, path in get_backup_sources().items():
            if path.exists():
                zf.writestr(filename, path.read_bytes())
    return buffer.getvalue()


def find_backup_member(extracted_dir: Path, filename: str) -> Path | None:
    direct = extracted_dir / filename
    nested = extracted_dir / "data" / filename
    if direct.exists():
        return direct
    if nested.exists():
        return nested
    return None


def format_backup_timestamp(path: Path) -> str:
    if not path.exists():
        return "Backup ZIP not found yet."
    modified_at = datetime.fromtimestamp(path.stat().st_mtime)
    return "Backup ZIP last updated: " + modified_at.strftime("%d/%m/%Y %H:%M")


def import_backup_zip_bytes(zip_bytes: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            members = [name for name in zf.namelist() if not name.endswith("/")]
            required_names = set(REQUIRED_BACKUP_FILES.keys())
            present_names = {Path(name).name for name in members}
            missing = sorted(required_names - present_names)
            if missing:
                raise ValueError(
                    "Backup is missing required files: " + ", ".join(missing)
                )

            with tempfile.TemporaryDirectory(prefix="shoku_import_") as tmp_dir:
                extracted_dir = Path(tmp_dir)
                zf.extractall(extracted_dir)

                for filename, columns in REQUIRED_BACKUP_FILES.items():
                    source = find_backup_member(extracted_dir, filename)
                    if source is None:
                        raise ValueError(f"Could not find {filename} in the backup ZIP.")
                    imported_df = pd.read_csv(source)
                    normalize_import_df(imported_df, columns).to_csv(
                        get_backup_sources()[filename],
                        index=False,
                    )

                for filename, columns in OPTIONAL_BACKUP_FILES.items():
                    source = find_backup_member(extracted_dir, filename)
                    if source is None:
                        pd.DataFrame(columns=columns).to_csv(
                            get_backup_sources()[filename],
                            index=False,
                        )
                    else:
                        imported_df = pd.read_csv(source)
                        normalize_import_df(imported_df, columns).to_csv(
                            get_backup_sources()[filename],
                            index=False,
                        )
    except zipfile.BadZipFile as exc:
        raise ValueError("Uploaded file is not a valid ZIP archive.") from exc


# --- 2. BACKUP UTILITY ---
st.sidebar.header("System Admin")
st.sidebar.caption(format_backup_timestamp(BACKUP_ZIP))
st.sidebar.download_button(
    label="Download CSV Backup",
    data=build_backup_zip_bytes(),
    file_name="shoku_data_backup.zip",
    mime="application/zip",
)
backup_upload = st.sidebar.file_uploader(
    "Import backup ZIP",
    type=["zip"],
    key="backup_import_zip",
    help="Imports a backup ZIP and rewrites all app CSV data after confirmation.",
)
confirm_backup_import = st.sidebar.text_input(
    "Type IMPORT BACKUP to confirm",
    key="confirm_backup_import",
)
if st.sidebar.button("Import backup and replace data", key="import_backup_button"):
    if backup_upload is None:
        st.sidebar.error("Upload a backup ZIP first.")
    elif confirm_backup_import.strip() != "IMPORT BACKUP":
        st.sidebar.error("Confirmation did not match. Import was cancelled.")
    else:
        try:
            import_backup_zip_bytes(backup_upload.getvalue())
            st.session_state.pop("backup_import_zip", None)
            st.session_state.pop("confirm_backup_import", None)
            st.sidebar.success("Backup imported. Local CSV data was replaced.")
            st.rerun()
        except ValueError as exc:
            st.sidebar.error(str(exc))


def food_key(row) -> str:
    return f"{row['food_name']} [{row['unit']}]"


def as_float(value, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def ingredient_type_for_row(row) -> str:
    ingredient_type = as_text(row.get("ingredient_type")).lower()
    return ingredient_type if ingredient_type in {"food", "batch", "dish"} else "food"


def format_nutrient_value(nutrient_key: str, value, with_unit: bool = False) -> str:
    spec = NUTRIENT_BY_KEY[nutrient_key]
    if pd.isna(value):
        return "—"
    fmt = f"{{:.{spec['decimals']}f}}"
    text = fmt.format(as_float(value, 0.0))
    return f"{text} {spec['unit']}" if with_unit else text


def get_missing_food_nutrients(food_row) -> list[str]:
    if food_row is None:
        return [spec["key"] for spec in TRACKED_NUTRIENTS]
    return [
        spec["key"]
        for spec in TRACKED_NUTRIENTS
        if pd.isna(food_row.get(spec["food_base_col"]))
    ]


def describe_missing_nutrients(nutrient_keys: list[str]) -> str:
    if not nutrient_keys:
        return ""
    labels = [NUTRIENT_BY_KEY[key]["label"].lower() for key in nutrient_keys]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def parse_date_value(value):
    if isinstance(value, date):
        return value
    if pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def format_day(day_value) -> str:
    parsed = parse_date_value(day_value)
    if parsed is None:
        return ""
    return parsed.strftime("%d/%m/%Y")


def format_date_series(values: pd.Series) -> pd.Series:
    return values.apply(format_day)


def apply_effective_goals(
    df: pd.DataFrame, goals: pd.DataFrame, date_col: str = "date"
) -> pd.DataFrame:
    result = df.copy()
    if "calorie_goal" not in result.columns:
        result["calorie_goal"] = None
    if "protein_goal" not in result.columns:
        result["protein_goal"] = None
    if result.empty:
        return result

    result["_goal_lookup_date"] = pd.to_datetime(result[date_col], errors="coerce")
    if goals.empty:
        result = result.drop(columns=["_goal_lookup_date"])
        return result

    goal_lookup = goals[["date", "calorie_goal", "protein_goal"]].copy()
    goal_lookup["_goal_lookup_date"] = pd.to_datetime(goal_lookup["date"], errors="coerce")
    goal_lookup = goal_lookup.dropna(subset=["_goal_lookup_date"]).sort_values("_goal_lookup_date")
    result = result.sort_values("_goal_lookup_date")

    merged = pd.merge_asof(
        result,
        goal_lookup[["_goal_lookup_date", "calorie_goal", "protein_goal"]],
        on="_goal_lookup_date",
        direction="backward",
        suffixes=("", "_effective"),
    )
    for col in ["calorie_goal", "protein_goal"]:
        effective_col = f"{col}_effective"
        if effective_col in merged.columns:
            merged[col] = merged[effective_col].combine_first(merged[col])
            merged = merged.drop(columns=[effective_col])
    return merged.drop(columns=["_goal_lookup_date"])


def month_start(day_value: date) -> date:
    return day_value.replace(day=1)


def shift_month(day_value: date, delta_months: int) -> date:
    year = day_value.year + ((day_value.month - 1 + delta_months) // 12)
    month = ((day_value.month - 1 + delta_months) % 12) + 1
    return date(year, month, 1)


def month_end(day_value: date) -> date:
    return date(
        day_value.year,
        day_value.month,
        calendar.monthrange(day_value.year, day_value.month)[1],
    )


def calorie_status_for_day(calories, goal):
    if pd.isna(calories) or pd.isna(goal):
        return "#e5e7eb", "No goal"
    calories = as_float(calories, 0.0)
    goal = as_float(goal, 0.0)
    if goal <= 0:
        return "#e5e7eb", "No goal"
    if calories <= goal * 1.04:
        return "#2e7d32", f"{calories:.0f} / {goal:.0f} kcal"
    return "#c62828", f"{calories:.0f} / {goal:.0f} kcal"


def protein_status_for_day(protein, goal):
    if pd.isna(protein) or pd.isna(goal):
        return "#e5e7eb", "No goal"
    protein = as_float(protein, 0.0)
    goal = as_float(goal, 0.0)
    if goal <= 0:
        return "#e5e7eb", "No goal"
    if protein >= goal:
        return "#2e7d32", f"{protein:.1f} / {goal:.1f}g"
    if protein >= goal * 0.9:
        return "#9ca3af", f"{protein:.1f} / {goal:.1f}g"
    return "#c62828", f"{protein:.1f} / {goal:.1f}g"


def classify_calorie_progress(consumed: float, goal: float) -> tuple[str, str]:
    if goal <= 0:
        return "none", "No goal"
    if consumed <= goal:
        return "good", "Under budget"
    if consumed <= goal * 1.04:
        return "close", "Within range"
    return "bad", "Over budget"


def classify_protein_progress(consumed: float, goal: float) -> tuple[str, str]:
    if goal <= 0:
        return "none", "No goal"
    if consumed >= goal:
        return "good", "Goal met"
    if consumed >= goal * 0.9:
        return "close", "Close"
    return "bad", "Not met"


def classify_overall_goal_status(
    calories_consumed: float,
    calorie_goal: float | None,
    protein_consumed: float,
    protein_goal: float | None,
) -> tuple[str, str, str]:
    if calorie_goal is None or protein_goal is None:
        return "#6b7280", "Goal status unavailable", "Add calorie and protein goals"

    calorie_state, _ = classify_calorie_progress(calories_consumed, float(calorie_goal))
    protein_state, _ = classify_protein_progress(protein_consumed, float(protein_goal))

    if "bad" in {calorie_state, protein_state}:
        return "#c62828", "Needs attention", "Outside target range"
    if calorie_state == "good" and protein_state == "good":
        return "#2e7d32", "On track", "Within target range"
    return "#6b7280", "Within range", "Inside tolerance band"


def render_month_heatmap(title: str, month_value: date, values_by_day: dict, status_fn):
    weeks = calendar.monthcalendar(month_value.year, month_value.month)
    weekday_labels = ["M", "T", "W", "T", "F", "S", "S"]

    columns_html = []
    for week in weeks:
        week_cells = []
        for weekday_index, day_num in enumerate(week):
            if day_num == 0:
                week_cells.append(
                    '<div style="width:12px;height:12px;border-radius:2px;background:transparent;"></div>'
                )
                continue

            stats = values_by_day.get(day_num)
            if stats is None:
                bg = "#ebedf0"
                detail = "No log"
            else:
                bg, detail = status_fn(stats["value"], stats["goal"])

            week_cells.append(
                f"""
                <div
                    title="{month_value.strftime('%B')} {day_num}: {detail}"
                    aria-label="{title} {month_value.strftime('%B')} {day_num}: {detail}"
                    style="
                        width:12px;
                        height:12px;
                        border-radius:2px;
                        background:{bg};
                        border:1px solid rgba(27,31,35,0.06);
                        box-sizing:border-box;
                    "
                ></div>
                """
            )

        first_day = next((day_num for day_num in week if day_num != 0), 0)
        week_label = (
            f"{first_day}"
            if first_day
            else ""
        )
        columns_html.append(
            f"""
            <div style="display:flex;flex-direction:column;gap:4px;align-items:center;">
                <div style="height:12px;line-height:12px;font-size:0.62rem;color:#6b7280;white-space:nowrap;">
                    {week_label}
                </div>
                {''.join(week_cells)}
            </div>
            """
        )

    label_cells = []
    for weekday_label in weekday_labels:
        label_cells.append(
            f'<div style="height:12px;line-height:12px;font-size:0.65rem;color:#6b7280;">{weekday_label}</div>'
        )

    st.markdown(f"#### {title}")
    components.html(
        f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#111827;">
            <div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px;">
                <div style="display:flex;flex-direction:column;gap:4px;padding-top:16px;min-width:24px;">
                    {''.join(label_cells)}
                </div>
                <div style="display:flex;gap:4px;">
                    {''.join(columns_html)}
                </div>
            </div>
        <div style="display:flex;gap:8px;align-items:center;font-size:0.72rem;color:#6b7280;">
            <span>Worse</span>
            <div style="display:flex;gap:4px;align-items:center;">
                <div style="width:10px;height:10px;border-radius:2px;background:#c62828;border:1px solid rgba(27,31,35,0.06);"></div>
                <div style="width:10px;height:10px;border-radius:2px;background:#9ca3af;border:1px solid rgba(27,31,35,0.06);"></div>
                <div style="width:10px;height:10px;border-radius:2px;background:#2e7d32;border:1px solid rgba(27,31,35,0.06);"></div>
                <div style="width:10px;height:10px;border-radius:2px;background:#ebedf0;border:1px solid rgba(27,31,35,0.06);"></div>
            </div>
            <span>Better</span>
        </div>
        </div>
        """,
        height=190,
    )


def short_batch_id(batch_id: str) -> str:
    batch_text = as_text(batch_id)
    if not batch_text:
        return ""
    return batch_text[-6:]


def batch_key(row) -> str:
    batch_date = format_day(row.get("batch_date"))
    servings = as_float(row.get("servings"), 1.0)
    final_qty = as_float(row.get("final_qty"), 0.0)
    final_unit = as_text(row.get("final_unit"))
    final_text = ""
    if final_qty > 0 and final_unit:
        final_text = f" | {final_qty:g} {final_unit}"
    return (
        f"{row['dish_name']} | {batch_date or 'No date'} | "
        f"{servings:g} servings{final_text} | {short_batch_id(row.get('batch_id'))}"
    )


def batch_ref_label(batch_row) -> str:
    if batch_row is None:
        return "Missing batch"
    return batch_key(batch_row)


def ingredient_ref_label(row, batches: pd.DataFrame | None = None) -> str:
    if ingredient_type_for_row(row) == "dish":
        return f"Dish: {as_text(row.get('ingredient_food_name'))} [{as_text(row.get('ingredient_unit'))}]"
    if ingredient_type_for_row(row) == "batch":
        batch_id = as_text(row.get("ingredient_batch_id"))
        batch_row = get_batch_row(batches, batch_id) if batches is not None and batch_id else None
        label = batch_ref_label(batch_row) if batch_row is not None else (
            f"{as_text(row.get('ingredient_food_name'))} [{short_batch_id(batch_id)}]"
            if batch_id
            else "Missing batch"
        )
        return f"Batch: {label}"
    return f"{as_text(row.get('ingredient_food_name'))} [{as_text(row.get('ingredient_unit'))}]"


def get_food_row(foods: pd.DataFrame, food_name: str, unit: str):
    m = (foods["food_name"] == food_name) & (foods["unit"] == unit)
    if not m.any():
        return None
    return foods[m].iloc[0]


def compute_ingredient_totals(
    ingredients: pd.DataFrame,
    foods: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    batches: pd.DataFrame,
    qty_column: str,
    dish_stack: set[str] | None = None,
):
    totals = {spec["key"]: 0.0 for spec in TRACKED_NUTRIENTS}
    missing_nutrients = set()
    active_dish_stack = set(dish_stack or set())
    for _, ing in ingredients.iterrows():
        ingredient_type = ingredient_type_for_row(ing)
        qty = as_float(ing[qty_column], 0.0)
        if ingredient_type == "dish":
            ingredient_dish_name = as_text(ing.get("ingredient_food_name"))
            unit = as_text(ing.get("ingredient_unit")) or "serving"
            if not ingredient_dish_name or ingredient_dish_name in active_dish_stack:
                missing_nutrients.update(spec["key"] for spec in TRACKED_NUTRIENTS)
                continue
            base_values = compute_dish_base(
                ingredient_dish_name,
                dishes,
                dings,
                foods,
                batches,
                unit,
                dish_stack=active_dish_stack | {ingredient_dish_name},
            )
            valid_units = {basis for basis, _ in get_dish_log_options(
                ingredient_dish_name, dishes, dings, foods, batches, dish_stack=active_dish_stack | {ingredient_dish_name}
            )}
            if unit not in valid_units:
                missing_nutrients.update(spec["key"] for spec in TRACKED_NUTRIENTS)
                continue
            for spec in TRACKED_NUTRIENTS:
                per_unit_value = base_values.get(spec["key"])
                if pd.isna(per_unit_value):
                    missing_nutrients.add(spec["key"])
                else:
                    totals[spec["key"]] += qty * as_float(per_unit_value, 0.0)
            continue
        if ingredient_type == "batch":
            batch_id = as_text(ing.get("ingredient_batch_id"))
            batch_row = get_batch_row(batches, batch_id) if batch_id else None
            if batch_row is None:
                missing_nutrients.update(spec["key"] for spec in TRACKED_NUTRIENTS)
                continue
            unit = as_text(ing.get("ingredient_unit"))
            batch_metrics = get_batch_metrics(batch_row)
            valid_unit = unit == "serving" or (
                batch_metrics["has_weight_basis"] and unit == batch_metrics["final_unit"]
            )
            if not valid_unit:
                missing_nutrients.update(spec["key"] for spec in TRACKED_NUTRIENTS)
                continue
            base_values = compute_batch_base(batch_row, unit)
            for spec in TRACKED_NUTRIENTS:
                per_unit_value = base_values.get(spec["key"])
                if pd.isna(per_unit_value):
                    missing_nutrients.add(spec["key"])
                else:
                    totals[spec["key"]] += qty * as_float(per_unit_value, 0.0)
            continue

        frow = get_food_row(foods, ing["ingredient_food_name"], ing["ingredient_unit"])
        if frow is None:
            missing_nutrients.update(spec["key"] for spec in TRACKED_NUTRIENTS)
            continue
        for spec in TRACKED_NUTRIENTS:
            per_unit_value = frow.get(spec["food_per_unit_col"])
            if pd.isna(per_unit_value):
                missing_nutrients.add(spec["key"])
            else:
                totals[spec["key"]] += qty * as_float(per_unit_value, 0.0)
    for nutrient_key in missing_nutrients:
        totals[nutrient_key] = None
    return totals, sorted(missing_nutrients)


def get_auto_yield_from_ingredients(
    ingredients: pd.DataFrame, qty_column: str
) -> Tuple[float, str]:
    use = ingredients.copy()
    if use.empty:
        return 0.0, ""

    use["ingredient_unit"] = use["ingredient_unit"].fillna("").astype(str).str.strip()
    use[qty_column] = pd.to_numeric(use[qty_column], errors="coerce")
    use = use[(use["ingredient_unit"] != "") & use[qty_column].notna()]
    if use.empty:
        return 0.0, ""

    units = use["ingredient_unit"].unique().tolist()
    if len(units) != 1:
        return 0.0, ""

    return float(use[qty_column].sum()), units[0]


def build_portion_metrics(
    servings: float,
    nutrient_totals: dict,
    manual_qty: float,
    manual_unit: str,
    auto_qty: float = 0.0,
    auto_unit: str = "",
    missing_nutrients: list[str] | None = None,
):
    final_qty = 0.0
    final_unit = ""
    yield_source = "none"
    if manual_qty > 0 and manual_unit:
        final_qty = manual_qty
        final_unit = manual_unit
        yield_source = "manual"
    elif auto_qty > 0 and auto_unit:
        final_qty = auto_qty
        final_unit = auto_unit
        yield_source = "auto"

    has_weight_basis = final_qty > 0 and bool(final_unit)
    safe_servings = servings if servings > 0 else 1.0
    metrics = {
        "servings": safe_servings,
        "final_qty": final_qty,
        "final_unit": final_unit,
        "yield_source": yield_source,
        "has_weight_basis": has_weight_basis,
        "missing_nutrients": missing_nutrients or [],
        "has_complete_nutrients": not bool(missing_nutrients),
    }
    for spec in TRACKED_NUTRIENTS:
        total_value = nutrient_totals.get(spec["key"])
        total_col = spec["batch_total_col"]
        per_serving_col = f"per_serving_{spec['key']}"
        per_weight_col = f"per_weight_{spec['key']}"
        metrics[total_col] = total_value
        metrics[per_serving_col] = (
            total_value / safe_servings if pd.notna(total_value) else None
        )
        metrics[per_weight_col] = (
            total_value / final_qty if has_weight_basis and pd.notna(total_value) else None
        )
    return metrics


def normalize_food_row(row):
    base_qty = as_float(row.get("base_qty"), 0.0)

    if base_qty <= 0:
        base_qty = 1.0

    row["base_qty"] = base_qty
    for spec in TRACKED_NUTRIENTS:
        per_unit_col = spec["food_per_unit_col"]
        base_col = spec["food_base_col"]
        per_unit_value = row.get(per_unit_col)
        base_value = row.get(base_col)
        if pd.isna(base_value):
            if pd.isna(per_unit_value):
                row[base_col] = None
                row[per_unit_col] = None
            else:
                row[base_col] = as_float(per_unit_value, 0.0) * base_qty
                row[per_unit_col] = as_float(per_unit_value, 0.0)
        else:
            row[base_col] = as_float(base_value, 0.0)
            row[per_unit_col] = row[base_col] / base_qty
    return row


def clear_add_food_form():
    clear_session_keys(
        [
            "add_food_name",
            "add_food_unit",
            "add_base_qty",
            "add_cal_base",
            "add_prot_base",
            "add_fiber_base",
        ]
    )


def clear_add_dish_form():
    clear_session_keys(
        [
            "add_dish_name",
            "add_dish_override",
            "add_dish_cal",
            "add_dish_prot",
            "add_dish_fiber",
            "add_dish_servings",
            "add_dish_yield_qty",
            "add_dish_yield_unit",
        ]
    )


def clear_duplicate_dish_form():
    clear_session_keys(["duplicate_dish_source", "duplicate_dish_name"])


def clear_create_batch_form():
    for key in list(st.session_state.keys()):
        if key.startswith("create_batch_"):
            st.session_state.pop(key, None)


def clear_log_form():
    clear_session_keys(
        [
            "log_date",
            "log_meal",
            "log_type",
            "log_qty",
            "log_food_name",
            "log_food_unit",
            "log_dish_name",
            "log_dish_basis",
            "log_batch_sel",
            "log_batch_basis",
        ]
    )


def clear_add_ingredient_form():
    clear_session_keys(
        [
            "add_ing_type",
            "add_ing_food",
            "add_ing_dish_ref",
            "add_ing_unit",
            "add_ing_batch",
            "add_ing_batch_unit_label",
            "add_ing_qty",
        ]
    )


def clear_single_goal_form():
    clear_session_keys(["goal_date", "cal_goal2", "prot_goal2"])


def clear_bulk_goal_form():
    clear_session_keys(["bulk_start", "bulk_end", "bulk_cal", "bulk_prot"])


def set_view_date_today():
    st.session_state.view_date = date.today()


def shift_view_date(days: int):
    current_view_date = st.session_state.get("view_date", date.today())
    parsed_view_date = parse_date_value(current_view_date) or date.today()
    st.session_state.view_date = parsed_view_date + timedelta(days=days)


def load_food_into_edit_form(food_row, food_key_value: str):
    st.session_state.edit_food_name = as_text(food_row["food_name"])
    st.session_state.edit_food_unit = as_text(food_row["unit"])
    st.session_state.edit_base_qty = float(as_float(food_row["base_qty"], 1.0))
    st.session_state.edit_cal_base = float(as_float(food_row["calories_base"], 0.0))
    st.session_state.edit_prot_base = float(as_float(food_row["protein_base"], 0.0))
    st.session_state.edit_fiber_base = (
        "" if pd.isna(food_row["fiber_base"]) else format_nutrient_value("fiber", food_row["fiber_base"])
    )
    st.session_state.edit_food_propagate = True
    st.session_state.edit_food_loaded_for = food_key_value


def log_entry_label(row) -> str:
    item_name = row["name"]
    if row.get("type") == "batch" and as_text(row.get("batch_id")):
        item_name = f"{item_name} [{short_batch_id(row.get('batch_id'))}]"
    short_log_id = as_text(row.get("log_id"))[-6:]
    return (
        f"{row['meal']} - {row['type']} - {item_name} "
        f"({as_float(row['qty'], 0.0):g} {row['unit']}, "
        f"{as_float(row['calories'], 0.0):.0f} kcal, "
        f"{as_float(row['protein'], 0.0):.1f}g protein, "
        f"{format_nutrient_value('fiber', row.get('fiber'), with_unit=True)} fiber)"
        f" [{short_log_id}]"
    )


def clear_session_keys(keys):
    for key in keys:
        st.session_state.pop(key, None)


def initialize_batch_ingredient_rows(
    batch_dish_name: str, template_ings: pd.DataFrame, force_reload: bool = False
):
    row_state_key = f"create_batch_rows_{batch_dish_name}"
    row_seq_key = f"create_batch_row_seq_{batch_dish_name}"
    if row_state_key in st.session_state and not force_reload:
        return row_state_key, row_seq_key

    for key in list(st.session_state.keys()):
        if key.startswith(f"{row_state_key}_"):
            st.session_state.pop(key, None)

    rows = []
    next_row_id = 0
    for _, ing in template_ings.iterrows():
        rows.append(
            {
                "row_id": next_row_id,
                "ingredient_type": ingredient_type_for_row(ing),
                "ingredient_food_name": ing["ingredient_food_name"],
                "ingredient_unit": ing["ingredient_unit"],
                "ingredient_qty": float(ing["ingredient_qty_per_serving"]),
                "ingredient_batch_id": as_text(ing.get("ingredient_batch_id")),
            }
        )
        next_row_id += 1

    st.session_state[row_state_key] = rows
    st.session_state[row_seq_key] = next_row_id
    return row_state_key, row_seq_key


def add_batch_ingredient_row(batch_dish_name: str, foods: pd.DataFrame):
    row_state_key = f"create_batch_rows_{batch_dish_name}"
    row_seq_key = f"create_batch_row_seq_{batch_dish_name}"
    rows = list(st.session_state.get(row_state_key, []))
    next_row_id = int(st.session_state.get(row_seq_key, 0))

    default_food = ""
    default_unit = ""
    if not foods.empty:
        default_food = sorted(foods["food_name"].unique().tolist())[0]
        food_units = sorted(
            foods[foods["food_name"] == default_food]["unit"].dropna().astype(str).tolist()
        )
        if food_units:
            default_unit = food_units[0]

    rows.append(
        {
            "row_id": next_row_id,
            "ingredient_type": "food",
            "ingredient_food_name": default_food,
            "ingredient_unit": default_unit,
            "ingredient_qty": 0.0,
            "ingredient_batch_id": "",
        }
    )
    st.session_state[row_state_key] = rows
    st.session_state[row_seq_key] = next_row_id + 1


def remove_batch_ingredient_row(batch_dish_name: str, row_id: int):
    row_state_key = f"create_batch_rows_{batch_dish_name}"
    rows = list(st.session_state.get(row_state_key, []))
    st.session_state[row_state_key] = [row for row in rows if row["row_id"] != row_id]


def render_goal_progress(
    label: str, consumed: float, goal: float, good_when_under: bool
):
    green = "#2e7d32"
    neutral = "#6b7280"
    red = "#c62828"
    track = "#ebedf0"
    if goal <= 0:
        fill_pct = 0.0
        state = "none"
        status = "No goal"
    else:
        fill_pct = min(consumed / goal, 1.0) * 100
        if good_when_under:
            state, status = classify_calorie_progress(consumed, goal)
        else:
            state, status = classify_protein_progress(consumed, goal)
    color = (
        green if state == "good"
        else neutral if state == "close"
        else red if state == "bad"
        else "#9ca3af"
    )

    st.markdown(
        f"""
        <div style="margin-top:6px;">
            <div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">
                <div style="font-size:0.92rem;font-weight:700;color:#1f2937;">{label}</div>
                <div style="font-size:0.85rem;font-weight:700;color:{color};">{status}</div>
            </div>
            <div style="
                margin-top:6px;
                width:100%;
                height:12px;
                border-radius:999px;
                background:{track};
                overflow:hidden;
            ">
                <div style="
                    width:{fill_pct:.1f}%;
                    height:100%;
                    background:{color};
                    border-radius:999px;
                "></div>
            </div>
            <div style="margin-top:6px;font-size:0.82rem;color:#666;">
                {consumed:.1f} consumed / {goal:.1f} goal
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_heading(title: str, help_text: str, level: int = 4):
    c1, c2 = st.columns([0.96, 0.04])
    with c1:
        st.markdown(f"{'#' * level} {title}")
    with c2:
        st.button("i", key=f"help_{title.lower().replace(' ', '_')}", help=help_text)


@contextmanager
def collapsible_panel(title: str, panel_key: str, default_open: bool = False):
    state_key = f"panel_open_{panel_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = default_open
    is_open = bool(st.session_state[state_key])
    label = f"{'▼' if is_open else '▶'} {title}"
    if st.button(label, key=f"{state_key}_toggle", use_container_width=True):
        st.session_state[state_key] = not is_open
        st.rerun()
    if is_open:
        with st.container(border=True):
            yield True
    else:
        yield False


def is_override_dish(row) -> bool:
    return pd.notna(row.get("cal_override")) and pd.notna(row.get("protein_override"))


def get_dish_yield(row) -> Tuple[float, str]:
    yield_qty = as_float(row.get("yield_qty"), 0.0)
    yield_unit = as_text(row.get("yield_unit"))
    if yield_qty > 0 and yield_unit:
        return yield_qty, yield_unit
    return 0.0, ""


def get_dish_servings(row) -> float:
    servings = as_float(row.get("servings"), 1.0)
    return servings if servings > 0 else 1.0


def compute_dish_totals(
    dish_name: str,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batches: pd.DataFrame,
    dish_stack: set[str] | None = None,
):
    md = dishes[dishes["dish_name"] == dish_name]
    if md.empty:
        return {spec["key"]: 0.0 for spec in TRACKED_NUTRIENTS}, []
    row = md.iloc[0]
    if is_override_dish(row):
        servings = get_dish_servings(row)
        totals = {}
        missing_nutrients = []
        for spec in TRACKED_NUTRIENTS:
            override_value = row.get(spec["dish_override_col"])
            if pd.isna(override_value):
                totals[spec["key"]] = None
                missing_nutrients.append(spec["key"])
            else:
                totals[spec["key"]] = as_float(override_value, 0.0) * servings
        return totals, missing_nutrients

    use = dings[dings["dish_name"] == dish_name]
    active_dish_stack = set(dish_stack or set()) | {dish_name}
    return compute_ingredient_totals(
        use,
        foods,
        dishes,
        dings,
        batches,
        "ingredient_qty_per_serving",
        dish_stack=active_dish_stack,
    )


def get_auto_dish_yield(
    dish_name: str, dings: pd.DataFrame
) -> Tuple[float, str]:
    use = dings[dings["dish_name"] == dish_name].copy()
    return get_auto_yield_from_ingredients(use, "ingredient_qty_per_serving")


def get_effective_dish_yield(
    dish_name: str, row, dings: pd.DataFrame
) -> Tuple[float, str, str]:
    manual_qty, manual_unit = get_dish_yield(row)
    if manual_qty > 0 and manual_unit:
        return manual_qty, manual_unit, "manual"

    auto_qty, auto_unit = get_auto_dish_yield(dish_name, dings)
    if auto_qty > 0 and auto_unit:
        return auto_qty, auto_unit, "auto"

    return 0.0, "", "none"


def get_dish_metrics(
    dish_name: str,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batches: pd.DataFrame,
    dish_stack: set[str] | None = None,
):
    md = dishes[dishes["dish_name"] == dish_name]
    if md.empty:
        return build_portion_metrics(
            1.0,
            {spec["key"]: 0.0 for spec in TRACKED_NUTRIENTS},
            0.0,
            "",
        )

    row = md.iloc[0]
    servings = get_dish_servings(row)
    nutrient_totals, missing_nutrients = compute_dish_totals(
        dish_name, dishes, dings, foods, batches, dish_stack=dish_stack
    )
    manual_qty, manual_unit = get_dish_yield(row)
    auto_qty, auto_unit = get_auto_dish_yield(dish_name, dings)
    return build_portion_metrics(
        servings,
        nutrient_totals,
        manual_qty,
        manual_unit,
        auto_qty,
        auto_unit,
        missing_nutrients,
    )


def get_dish_log_options(
    dish_name: str,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batches: pd.DataFrame,
    dish_stack: set[str] | None = None,
):
    metrics = get_dish_metrics(dish_name, dishes, dings, foods, batches, dish_stack=dish_stack)
    options = [("serving", "Serving")]
    if metrics["has_weight_basis"]:
        source = "manual final weight" if metrics["yield_source"] == "manual" else "auto final weight"
        options.append(
            (
                metrics["final_unit"],
                f"Weight ({metrics['final_unit']}, {source})",
            )
        )
    return options


def get_dish_basis_label(log_unit: str) -> str:
    return f"per {log_unit}"


def compute_dish_base(
    dish_name: str,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batches: pd.DataFrame,
    log_unit: str = "serving",
    dish_stack: set[str] | None = None,
):
    metrics = get_dish_metrics(dish_name, dishes, dings, foods, batches, dish_stack=dish_stack)
    if log_unit == "serving":
        return {
            spec["key"]: metrics[f"per_serving_{spec['key']}"]
            for spec in TRACKED_NUTRIENTS
        }
    if metrics["has_weight_basis"] and log_unit == metrics["final_unit"]:
        return {
            spec["key"]: metrics[f"per_weight_{spec['key']}"]
            for spec in TRACKED_NUTRIENTS
        }
    return {spec["key"]: 0.0 for spec in TRACKED_NUTRIENTS}


def make_batch_id(batch_day: date) -> str:
    return f"batch_{batch_day.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S%f')}"


def get_batch_row(batches: pd.DataFrame, batch_id: str):
    match = batches[batches["batch_id"] == batch_id]
    if match.empty:
        return None
    return match.iloc[0]


def get_batch_metrics(batch_row):
    if batch_row is None:
        return build_portion_metrics(
            1.0, {spec["key"]: 0.0 for spec in TRACKED_NUTRIENTS}, 0.0, ""
        )
    return build_portion_metrics(
        as_float(batch_row.get("servings"), 1.0),
        {
            spec["key"]: batch_row.get(spec["batch_total_col"])
            for spec in TRACKED_NUTRIENTS
        },
        as_float(batch_row.get("final_qty"), 0.0),
        as_text(batch_row.get("final_unit")),
        missing_nutrients=[
            spec["key"]
            for spec in TRACKED_NUTRIENTS
            if pd.isna(batch_row.get(spec["batch_total_col"]))
        ],
    )


def get_batch_log_options(batch_row):
    metrics = get_batch_metrics(batch_row)
    options = [("serving", "Serving")]
    if metrics["has_weight_basis"]:
        source = as_text(batch_row.get("yield_source")) or "manual"
        source_label = "manual final weight" if source == "manual" else "auto final weight"
        options.append(
            (
                metrics["final_unit"],
                f"Weight ({metrics['final_unit']}, {source_label})",
            )
        )
    return options


def compute_batch_base(batch_row, log_unit: str = "serving"):
    metrics = get_batch_metrics(batch_row)
    if log_unit == "serving":
        return {
            spec["key"]: metrics[f"per_serving_{spec['key']}"]
            for spec in TRACKED_NUTRIENTS
        }
    if metrics["has_weight_basis"] and log_unit == metrics["final_unit"]:
        return {
            spec["key"]: metrics[f"per_weight_{spec['key']}"]
            for spec in TRACKED_NUTRIENTS
        }
    return {spec["key"]: 0.0 for spec in TRACKED_NUTRIENTS}


def get_batch_basis_options(batch_row) -> list[tuple[str, str]]:
    options = [("serving", "Serving")]
    metrics = get_batch_metrics(batch_row)
    if metrics["has_weight_basis"]:
        options.append((metrics["final_unit"], f"Weight ({metrics['final_unit']})"))
    return options


def get_dish_basis_options(
    dish_name: str,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batches: pd.DataFrame,
) -> list[tuple[str, str]]:
    return get_dish_log_options(dish_name, dishes, dings, foods, batches)


def get_batch_select_options(batches: pd.DataFrame) -> list[tuple[str, str]]:
    if batches.empty:
        return []
    batch_rows = batches.sort_values(["batch_date", "dish_name", "batch_id"], ascending=[False, True, False])
    return [(batch_ref_label(row), as_text(row["batch_id"])) for _, row in batch_rows.iterrows()]


def get_ingredient_unit_choices(
    ingredient_type: str,
    foods: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    batches: pd.DataFrame,
    food_name: str = "",
    batch_id: str = "",
    dish_name: str = "",
) -> list[str]:
    if ingredient_type == "batch":
        batch_row = get_batch_row(batches, batch_id) if batch_id else None
        return [unit for unit, _ in get_batch_basis_options(batch_row)] if batch_row is not None else ["serving"]
    if ingredient_type == "dish":
        if not dish_name:
            return ["serving"]
        return [unit for unit, _ in get_dish_basis_options(dish_name, dishes, dings, foods, batches)]
    if not food_name:
        return [""]
    unit_choices = sorted(
        foods[foods["food_name"] == food_name]["unit"].dropna().astype(str).tolist()
    )
    return unit_choices or [""]


def estimate_ingredient_row(
    row,
    foods: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    batches: pd.DataFrame,
):
    qty_value = as_float(row.get("ingredient_qty"), 0.0)
    ingredient_type = ingredient_type_for_row(row)
    if ingredient_type == "dish":
        dish_name = as_text(row.get("ingredient_food_name"))
        unit_value = as_text(row.get("ingredient_unit")) or "serving"
        if not dish_name:
            return None, None, None, "Dish missing"
        base_values = compute_dish_base(
            dish_name,
            dishes,
            dings,
            foods,
            batches,
            unit_value,
            dish_stack={dish_name},
        )
        valid_units = {
            unit for unit, _ in get_dish_basis_options(dish_name, dishes, dings, foods, batches)
        }
        if unit_value not in valid_units:
            return None, None, None, "Basis missing"
        est_c = qty_value * as_float(base_values["calories"], 0.0)
        est_p = qty_value * as_float(base_values["protein"], 0.0)
        est_f = (
            qty_value * as_float(base_values["fiber"], 0.0)
            if pd.notna(base_values["fiber"])
            else None
        )
        return est_c, est_p, est_f, None
    if ingredient_type == "batch":
        batch_id = as_text(row.get("ingredient_batch_id"))
        batch_row = get_batch_row(batches, batch_id) if batch_id else None
        if batch_row is None:
            return None, None, None, "Batch missing"
        unit_value = as_text(row.get("ingredient_unit"))
        base_values = compute_batch_base(batch_row, unit_value)
        valid_units = {unit for unit, _ in get_batch_basis_options(batch_row)}
        if unit_value not in valid_units:
            return None, None, None, "Basis missing"
        est_c = qty_value * as_float(base_values["calories"], 0.0)
        est_p = qty_value * as_float(base_values["protein"], 0.0)
        est_f = (
            qty_value * as_float(base_values["fiber"], 0.0)
            if pd.notna(base_values["fiber"])
            else None
        )
        return est_c, est_p, est_f, None

    food_name = as_text(row.get("ingredient_food_name"))
    unit_value = as_text(row.get("ingredient_unit"))
    frow = get_food_row(foods, food_name, unit_value)
    if frow is None:
        return None, None, None, "Food missing"
    est_c = qty_value * as_float(frow["cal_per_unit"], 0.0)
    est_p = qty_value * as_float(frow["protein_per_unit"], 0.0)
    est_f = (
        qty_value * as_float(frow["fiber_per_unit"], 0.0)
        if pd.notna(frow.get("fiber_per_unit"))
        else None
    )
    return est_c, est_p, est_f, None


def get_batch_consumption_summary(logs: pd.DataFrame, batch_row) -> dict:
    metrics = get_batch_metrics(batch_row)
    batch_id = as_text(batch_row.get("batch_id")) if batch_row is not None else ""
    final_unit = metrics["final_unit"]
    consumed_servings = 0.0
    consumed_weight = 0.0

    if batch_id:
        batch_logs = logs[
            (logs["type"] == "batch") & (logs["batch_id"] == batch_id)
        ].copy()
        for _, row in batch_logs.iterrows():
            qty = as_float(row.get("qty"), 0.0)
            unit = as_text(row.get("unit"))
            if qty <= 0:
                continue
            if unit == "serving":
                consumed_servings += qty
                if metrics["has_weight_basis"] and metrics["servings"] > 0:
                    consumed_weight += qty * metrics["final_qty"] / metrics["servings"]
            elif metrics["has_weight_basis"] and unit == final_unit:
                consumed_weight += qty
                if metrics["final_qty"] > 0:
                    consumed_servings += qty * metrics["servings"] / metrics["final_qty"]

    return {
        "consumed_servings": consumed_servings,
        "remaining_servings": max(metrics["servings"] - consumed_servings, 0.0),
        "consumed_weight": consumed_weight,
        "remaining_weight": (
            max(metrics["final_qty"] - consumed_weight, 0.0)
            if metrics["has_weight_basis"]
            else 0.0
        ),
        "over_servings": max(consumed_servings - metrics["servings"], 0.0),
        "over_weight": (
            max(consumed_weight - metrics["final_qty"], 0.0)
            if metrics["has_weight_basis"]
            else 0.0
        ),
    }


def get_goal_for_date(goals: pd.DataFrame, day: date):
    effective = apply_effective_goals(
        pd.DataFrame({"date": [day.isoformat()]}), goals, "date"
    )
    if effective.empty:
        return None, None
    r = effective.iloc[0]
    if pd.isna(r["calorie_goal"]) or pd.isna(r["protein_goal"]):
        return None, None
    return float(r["calorie_goal"]), float(r["protein_goal"])


def upsert_goal(
    goals: pd.DataFrame, day: date, cal_goal: float, prot_goal: float
) -> pd.DataFrame:
    idx = goals.index[goals["date"] == day.isoformat()].tolist()
    if idx:
        goals.loc[idx[0], "calorie_goal"] = cal_goal
        goals.loc[idx[0], "protein_goal"] = prot_goal
    else:
        goals.loc[len(goals)] = [day.isoformat(), cal_goal, prot_goal]
    return goals


def add_log_entry(
    logs: pd.DataFrame,
    day: date,
    meal: str,
    typ: str,
    name: str,
    unit: str,
    qty: float,
    cal: float,
    prot: float,
    fiber: float | None,
    batch_id: str = "",
) -> pd.DataFrame:
    logs.loc[len(logs)] = [
        make_log_id(day),
        day.isoformat(),
        meal,
        typ,
        name,
        batch_id,
        unit,
        qty,
        cal,
        prot,
        fiber,
        False,
    ]
    return logs


def daily_totals(logs: pd.DataFrame, day: date):
    d = logs[logs["date"] == day.isoformat()]
    return (
        float(d["calories"].sum()),
        float(d["protein"].sum()),
        float(pd.to_numeric(d["fiber"], errors="coerce").fillna(0.0).sum()),
    )


# --- Recalc helpers ---
def recalc_logs_for_food(
    logs: pd.DataFrame, foods: pd.DataFrame, food_name: str, unit: str
) -> pd.DataFrame:
    frow = get_food_row(foods, food_name, unit)
    if frow is None:
        return logs
    mask = (
        (logs["type"] == "food") & (logs["name"] == food_name) & (logs["unit"] == unit)
    )
    qty = logs.loc[mask, "qty"].fillna(0).astype(float)
    for spec in TRACKED_NUTRIENTS:
        per_unit_value = frow.get(spec["food_per_unit_col"])
        logs.loc[mask, spec["log_col"]] = (
            qty * as_float(per_unit_value, 0.0) if pd.notna(per_unit_value) else None
        )
    return logs


def recalc_logs_for_dishes(
    logs: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batches: pd.DataFrame,
    dish_names: list,
) -> pd.DataFrame:
    for dn in dish_names:
        metrics = get_dish_metrics(dn, dishes, dings, foods, batches)

        serving_mask = (
            (logs["type"] == "dish")
            & (logs["name"] == dn)
            & (logs["unit"] == "serving")
        )
        serving_qty = logs.loc[serving_mask, "qty"].fillna(0).astype(float)
        for spec in TRACKED_NUTRIENTS:
            per_serving_value = metrics[f"per_serving_{spec['key']}"]
            logs.loc[serving_mask, spec["log_col"]] = (
                serving_qty * as_float(per_serving_value, 0.0)
                if pd.notna(per_serving_value)
                else None
            )

        if metrics["has_weight_basis"]:
            weight_mask = (
                (logs["type"] == "dish")
                & (logs["name"] == dn)
                & (logs["unit"] == metrics["final_unit"])
            )
            weight_qty = logs.loc[weight_mask, "qty"].fillna(0).astype(float)
            for spec in TRACKED_NUTRIENTS:
                per_weight_value = metrics[f"per_weight_{spec['key']}"]
                logs.loc[weight_mask, spec["log_col"]] = (
                    weight_qty * as_float(per_weight_value, 0.0)
                    if pd.notna(per_weight_value)
                    else None
                )
    return logs


def recalc_logs_for_batch(logs: pd.DataFrame, batch_row: pd.Series):
    if batch_row is None:
        return logs
    metrics = get_batch_metrics(batch_row)
    mask = (logs["type"] == "batch") & (logs["batch_id"] == batch_row["batch_id"])
    if not mask.any():
        return logs

    serving_mask = mask & (logs["unit"] == "serving")
    serving_qty = pd.to_numeric(logs.loc[serving_mask, "qty"], errors="coerce").fillna(0.0)
    for spec in TRACKED_NUTRIENTS:
        per_serving_value = metrics[f"per_serving_{spec['key']}"]
        logs.loc[serving_mask, spec["log_col"]] = (
            serving_qty * as_float(per_serving_value, 0.0)
            if pd.notna(per_serving_value)
            else None
        )

    non_serving_mask = mask & (logs["unit"] != "serving")
    if metrics["has_weight_basis"]:
        weight_qty = pd.to_numeric(logs.loc[non_serving_mask, "qty"], errors="coerce").fillna(0.0)
        logs.loc[non_serving_mask, "unit"] = metrics["final_unit"]
        for spec in TRACKED_NUTRIENTS:
            per_weight_value = metrics[f"per_weight_{spec['key']}"]
            logs.loc[non_serving_mask, spec["log_col"]] = (
                weight_qty * as_float(per_weight_value, 0.0)
                if pd.notna(per_weight_value)
                else None
            )

    return logs


def rebuild_batch_from_snapshot(
    batches: pd.DataFrame,
    batch_ings: pd.DataFrame,
    logs: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batch_id: str,
):
    batch_match = batches[batches["batch_id"] == batch_id]
    if batch_match.empty:
        return batches, logs
    batch_index = batch_match.index[0]
    batch_row = batch_match.iloc[0]
    batch_snapshot = batch_ings[batch_ings["batch_id"] == batch_id].copy()
    if batch_snapshot.empty:
        return batches, logs

    nutrient_totals, missing_nutrients = compute_ingredient_totals(
        batch_snapshot,
        foods,
        dishes,
        dings,
        batches,
        "ingredient_qty",
    )
    auto_qty, auto_unit = get_auto_yield_from_ingredients(batch_snapshot, "ingredient_qty")
    manual_qty = (
        as_float(batch_row["final_qty"], 0.0)
        if as_text(batch_row.get("yield_source")) == "manual"
        else 0.0
    )
    manual_unit = (
        as_text(batch_row["final_unit"])
        if as_text(batch_row.get("yield_source")) == "manual"
        else ""
    )
    metrics = build_portion_metrics(
        as_float(batch_row.get("servings"), 1.0),
        nutrient_totals,
        manual_qty,
        manual_unit,
        auto_qty,
        auto_unit,
        missing_nutrients,
    )

    batches.loc[batch_index, "final_qty"] = (
        metrics["final_qty"] if metrics["has_weight_basis"] else None
    )
    batches.loc[batch_index, "final_unit"] = (
        metrics["final_unit"] if metrics["has_weight_basis"] else None
    )
    batches.loc[batch_index, "yield_source"] = metrics["yield_source"]
    for spec in TRACKED_NUTRIENTS:
        batches.loc[batch_index, spec["batch_total_col"]] = metrics[spec["batch_total_col"]]

    updated_batch_row = get_batch_row(batches, batch_id)
    logs = recalc_logs_for_batch(logs, updated_batch_row)
    return batches, logs


def recalc_recipe_dependents(
    logs: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batches: pd.DataFrame,
    batch_ings: pd.DataFrame,
    seed_dish_names: list[str] | None = None,
    seed_batch_ids: list[str] | None = None,
):
    pending_dishes = {as_text(name) for name in (seed_dish_names or []) if as_text(name)}
    pending_batches = {as_text(batch_id) for batch_id in (seed_batch_ids or []) if as_text(batch_id)}
    processed_dishes = set()
    processed_batches = set()

    while pending_dishes or pending_batches:
        if pending_dishes:
            current_dishes = set()
            queue = list(pending_dishes)
            pending_dishes.clear()
            while queue:
                dish_name = queue.pop(0)
                if not dish_name or dish_name in current_dishes:
                    continue
                current_dishes.add(dish_name)
                direct_dependents = (
                    dings[
                        dings.apply(
                            lambda row: ingredient_type_for_row(row) == "dish"
                            and as_text(row.get("ingredient_food_name")) == dish_name,
                            axis=1,
                        )
                    ]["dish_name"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
                for dependent_name in direct_dependents:
                    if dependent_name not in current_dishes:
                        queue.append(dependent_name)

            current_dishes -= processed_dishes
            if current_dishes:
                logs = recalc_logs_for_dishes(
                    logs,
                    dishes,
                    dings,
                    foods,
                    batches,
                    sorted(current_dishes),
                )
                impacted_batch_ids = (
                    batch_ings[
                        batch_ings.apply(
                            lambda row: ingredient_type_for_row(row) == "dish"
                            and as_text(row.get("ingredient_food_name")) in current_dishes,
                            axis=1,
                        )
                    ]["batch_id"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )
                for impacted_batch_id in impacted_batch_ids:
                    batches, logs = rebuild_batch_from_snapshot(
                        batches,
                        batch_ings,
                        logs,
                        dishes,
                        dings,
                        foods,
                        impacted_batch_id,
                    )
                pending_batches.update(impacted_batch_ids)
                processed_dishes.update(current_dishes)

        if pending_batches:
            current_batch_ids = {
                as_text(batch_id)
                for batch_id in pending_batches
                if as_text(batch_id) and as_text(batch_id) not in processed_batches
            }
            pending_batches.clear()
            if not current_batch_ids:
                continue

            dependent_dishes = (
                dings[
                    dings.apply(
                        lambda row: ingredient_type_for_row(row) == "batch"
                        and as_text(row.get("ingredient_batch_id")) in current_batch_ids,
                        axis=1,
                    )
                ]["dish_name"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
            pending_dishes.update(dependent_dishes)

            dependent_batch_ids = (
                batch_ings[
                    batch_ings.apply(
                        lambda row: ingredient_type_for_row(row) == "batch"
                        and as_text(row.get("ingredient_batch_id")) in current_batch_ids,
                        axis=1,
                    )
                ]["batch_id"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
            for dependent_batch_id in dependent_batch_ids:
                batches, logs = rebuild_batch_from_snapshot(
                    batches,
                    batch_ings,
                    logs,
                    dishes,
                    dings,
                    foods,
                    dependent_batch_id,
                )
            pending_batches.update(dependent_batch_ids)
            processed_batches.update(current_batch_ids)

    return batches, logs


def recalc_batches_for_food_refs(
    batches: pd.DataFrame,
    batch_ings: pd.DataFrame,
    logs: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    impacted_food_refs: list[tuple[str, str]],
):
    if not impacted_food_refs or batch_ings.empty or batches.empty:
        return batches, logs

    impacted_ref_set = {(name, unit) for name, unit in impacted_food_refs}
    impacted_batch_ids = batch_ings[
        batch_ings.apply(
            lambda row: (
                ingredient_type_for_row(row) == "food"
                and (
                as_text(row["ingredient_food_name"]),
                as_text(row["ingredient_unit"]),
                )
                in impacted_ref_set
            ),
            axis=1,
        )
    ]["batch_id"].dropna().astype(str).unique().tolist()

    if not impacted_batch_ids:
        return batches, logs

    for batch_id in impacted_batch_ids:
        batches, logs = rebuild_batch_from_snapshot(
            batches,
            batch_ings,
            logs,
            dishes,
            dings,
            foods,
            batch_id,
        )

    return batches, logs


def recalc_logs_for_batch_refs(
    logs: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    batches: pd.DataFrame,
    impacted_batch_ids: list[str],
) -> pd.DataFrame:
    impacted_ids = {as_text(batch_id) for batch_id in impacted_batch_ids if as_text(batch_id)}
    if not impacted_ids or dings.empty:
        return logs
    impacted_dishes = sorted(
        dings[
            dings.apply(
                lambda row: ingredient_type_for_row(row) == "batch"
                and as_text(row.get("ingredient_batch_id")) in impacted_ids,
                axis=1,
            )
        ]["dish_name"].dropna().astype(str).unique().tolist()
    )
    if impacted_dishes:
        logs = recalc_logs_for_dishes(logs, dishes, dings, foods, batches, impacted_dishes)
    return logs


def get_dependent_dish_names(dings: pd.DataFrame, source_dish_names: list[str]) -> list[str]:
    queue = [as_text(name) for name in source_dish_names if as_text(name)]
    seen = set(queue)
    dependents = set()
    while queue:
        source_name = queue.pop(0)
        direct = dings[
            dings.apply(
                lambda row: ingredient_type_for_row(row) == "dish"
                and as_text(row.get("ingredient_food_name")) == source_name,
                axis=1,
            )
        ]["dish_name"].dropna().astype(str).unique().tolist()
        for dish_name in direct:
            if dish_name not in dependents:
                dependents.add(dish_name)
            if dish_name not in seen:
                seen.add(dish_name)
                queue.append(dish_name)
    return sorted(dependents)


def recalc_batches_for_dish_refs(
    batches: pd.DataFrame,
    batch_ings: pd.DataFrame,
    logs: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    impacted_dish_names: list[str],
):
    queue = [as_text(name) for name in impacted_dish_names if as_text(name)]
    seen = set()
    while queue:
        source_dish_name = queue.pop(0)
        if source_dish_name in seen:
            continue
        seen.add(source_dish_name)
        impacted_batch_ids = batch_ings[
            batch_ings.apply(
                lambda row: ingredient_type_for_row(row) == "dish"
                and as_text(row.get("ingredient_food_name")) == source_dish_name,
                axis=1,
            )
        ]["batch_id"].dropna().astype(str).unique().tolist()
        for batch_id in impacted_batch_ids:
            batch_match = batches[batches["batch_id"] == batch_id]
            if batch_match.empty:
                continue
            batch_index = batch_match.index[0]
            batch_row = batch_match.iloc[0]
            batch_snapshot = batch_ings[batch_ings["batch_id"] == batch_id].copy()
            if batch_snapshot.empty:
                continue
            nutrient_totals, missing_nutrients = compute_ingredient_totals(
                batch_snapshot, foods, dishes, dings, batches, "ingredient_qty"
            )
            auto_qty, auto_unit = get_auto_yield_from_ingredients(
                batch_snapshot, "ingredient_qty"
            )
            manual_qty = (
                as_float(batch_row["final_qty"], 0.0)
                if as_text(batch_row.get("yield_source")) == "manual"
                else 0.0
            )
            manual_unit = (
                as_text(batch_row["final_unit"])
                if as_text(batch_row.get("yield_source")) == "manual"
                else ""
            )
            metrics = build_portion_metrics(
                as_float(batch_row.get("servings"), 1.0),
                nutrient_totals,
                manual_qty,
                manual_unit,
                auto_qty,
                auto_unit,
                missing_nutrients,
            )
            batches.loc[batch_index, "final_qty"] = (
                metrics["final_qty"] if metrics["has_weight_basis"] else None
            )
            batches.loc[batch_index, "final_unit"] = (
                metrics["final_unit"] if metrics["has_weight_basis"] else None
            )
            batches.loc[batch_index, "yield_source"] = metrics["yield_source"]
            for spec in TRACKED_NUTRIENTS:
                batches.loc[batch_index, spec["batch_total_col"]] = metrics[spec["batch_total_col"]]
            updated_batch_row = get_batch_row(batches, batch_id)
            logs = recalc_logs_for_batch(logs, updated_batch_row)
        dependent_dishes = get_dependent_dish_names(dings, [source_dish_name])
        for dish_name in dependent_dishes:
            if dish_name not in seen:
                queue.append(dish_name)
    return batches, logs


def recalc_batches_for_batch_refs(
    batches: pd.DataFrame,
    batch_ings: pd.DataFrame,
    logs: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    impacted_batch_ids: list[str],
):
    queue = [as_text(batch_id) for batch_id in impacted_batch_ids if as_text(batch_id)]
    seen = set()
    while queue:
        source_batch_id = queue.pop(0)
        if source_batch_id in seen:
            continue
        seen.add(source_batch_id)
        dependent_batch_ids = batch_ings[
            batch_ings.apply(
                lambda row: ingredient_type_for_row(row) == "batch"
                and as_text(row.get("ingredient_batch_id")) == source_batch_id,
                axis=1,
            )
        ]["batch_id"].dropna().astype(str).unique().tolist()
        for dependent_batch_id in dependent_batch_ids:
            batch_match = batches[batches["batch_id"] == dependent_batch_id]
            if batch_match.empty:
                continue
            batch_index = batch_match.index[0]
            batch_row = batch_match.iloc[0]
            batch_snapshot = batch_ings[batch_ings["batch_id"] == dependent_batch_id].copy()
            if batch_snapshot.empty:
                continue
            batches, logs = rebuild_batch_from_snapshot(
                batches,
                batch_ings,
                logs,
                dishes,
                dings,
                foods,
                dependent_batch_id,
            )
            queue.append(dependent_batch_id)

    return batches, logs


# ---------- UI ----------
st.set_page_config(page_title="Shoku", page_icon="🍱", layout="wide")

components.html(
    """
    <script>
    (function () {
      const parentWindow = window.parent;
      const parentDocument = parentWindow.document;
      if (parentWindow.__shokuKeyboardFixInstalled) {
        return;
      }
      parentWindow.__shokuKeyboardFixInstalled = true;

      function hasTextSelection() {
        try {
          const selection = parentWindow.getSelection();
          return !!selection && String(selection).length > 0;
        } catch (error) {
          return false;
        }
      }

      function isEditableTarget(target) {
        if (!target) {
          return false;
        }
        const tagName = (target.tagName || "").toLowerCase();
        if (target.isContentEditable || tagName === "input" || tagName === "textarea") {
          return true;
        }
        if (typeof target.closest === "function") {
          return !!target.closest(
            "[contenteditable='true'], input, textarea, [role='textbox'], [role='combobox']"
          );
        }
        return false;
      }

      function shouldProtectShortcut(event) {
        const key = (event.key || "").toLowerCase();
        const hasModifier = event.metaKey || event.ctrlKey;
        if (!hasModifier) {
          return false;
        }
        if (!["a", "c", "v", "x", "z", "y"].includes(key)) {
          return false;
        }
        return isEditableTarget(event.target) || hasTextSelection();
      }

      function stopForStreamlit(event) {
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === "function") {
          event.stopImmediatePropagation();
        }
      }

      function handler(event) {
        if (shouldProtectShortcut(event)) {
          stopForStreamlit(event);
        }
      }

      parentDocument.addEventListener("keydown", handler, true);
      parentDocument.addEventListener("keyup", handler, true);
      parentDocument.addEventListener("keypress", handler, true);
    })();
    </script>
    """,
    height=0,
)


# Force light theme
st.markdown(
    """
    <style>
    body {
        background-color: white !important;
        color: black !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

foods, dishes, dings, goals, logs, batches, batch_ings = load_all()

if not foods.empty:
    foods = foods.apply(normalize_food_row, axis=1)

st.title("Shoku 🍱")

tabs = st.tabs(["Log", "Day View", "Dashboard", "Master Data"])

# --------- Tab 1: Log ---------
with tabs[0]:
    log_message = st.session_state.pop("log_message", None)
    if log_message:
        st.success(log_message)
    st.subheader("Add entry")
    c1, c2 = st.columns([1, 1])
    with c1:
        log_date = st.date_input(
            "Date",
            value=date.today(),
            format=DATE_INPUT_FORMAT,
            key="log_date",
        )
        meal = st.selectbox("Meal", MEAL_OPTIONS, index=0, key="log_meal")
        entry_type = st.radio("Type", ["Food", "Dish", "Batch"], horizontal=True, key="log_type")
    with c2:
        qty = st.number_input(
            "Quantity", min_value=0.0, step=1.0, value=1.0, key="log_qty"
        )

    if entry_type == "Food":
        food_names = sorted(foods["food_name"].unique().tolist())
        if not food_names:
            st.info("Add foods in Master Data first.")
        else:
            f_name = st.selectbox("Food", food_names, key="log_food_name")
            units = sorted(
                foods[foods["food_name"] == f_name]["unit"].unique().tolist()
            )
            unit = st.selectbox("Unit", units, key="log_food_unit")
            frow = get_food_row(foods, f_name, unit)
            if frow is not None:
                missing_nutrients = get_missing_food_nutrients(frow)
                est_c = qty * as_float(frow["cal_per_unit"], 0.0)
                est_p = qty * as_float(frow["protein_per_unit"], 0.0)
                est_f = (
                    qty * as_float(frow["fiber_per_unit"], 0.0)
                    if pd.notna(frow.get("fiber_per_unit"))
                    else None
                )
                n1, n2, n3 = st.columns(3)
                n1.metric("Calories (est.)", f"{est_c:.0f}")
                n2.metric("Protein (g, est.)", f"{est_p:.1f}")
                n3.metric("Fiber (g, est.)", format_nutrient_value("fiber", est_f))
                if missing_nutrients:
                    st.warning(
                        f"This food cannot be logged until its {describe_missing_nutrients(missing_nutrients)} value is set."
                    )
                if st.button(
                    "Add to log",
                    type="primary",
                    use_container_width=True,
                    key="add_food_log",
                    disabled=bool(missing_nutrients),
                ):
                    logs = add_log_entry(
                        logs, log_date, meal, "food", f_name, unit, qty, est_c, est_p, est_f
                    )
                    save_df(logs, LOGS_CSV)
                    clear_log_form()
                    st.session_state.log_message = "Entry added."
                    st.rerun()
            else:
                st.warning("Food+unit not found.")

    elif entry_type == "Dish":
        dish_names = sorted(dishes["dish_name"].unique().tolist())
        if not dish_names:
            st.info("Add dishes in Master Data first.")
        else:
            d_name = st.selectbox("Dish", dish_names, key="log_dish_name")
            dish_metrics = get_dish_metrics(d_name, dishes, dings, foods, batches)
            log_options = get_dish_log_options(d_name, dishes, dings, foods, batches)
            option_labels = [label for _, label in log_options]
            option_map = {label: unit for unit, label in log_options}
            selected_label = st.selectbox("Log by", option_labels, key="log_dish_basis")
            log_unit = option_map[selected_label]
            base_values = compute_dish_base(d_name, dishes, dings, foods, batches, log_unit)
            basis_label = get_dish_basis_label(log_unit)
            est_c = qty * as_float(base_values["calories"], 0.0)
            est_p = qty * as_float(base_values["protein"], 0.0)
            est_f = (
                qty * as_float(base_values["fiber"], 0.0)
                if pd.notna(base_values["fiber"])
                else None
            )

            info_cols = st.columns(3)
            with info_cols[0]:
                st.metric("Calories per serving", f"{dish_metrics['per_serving_calories']:.1f}")
                st.metric("Protein per serving (g)", f"{dish_metrics['per_serving_protein']:.2f}")
            with info_cols[1]:
                st.metric(
                    "Fiber per serving (g)",
                    format_nutrient_value("fiber", dish_metrics["per_serving_fiber"]),
                )
            with info_cols[2]:
                if dish_metrics["has_weight_basis"]:
                    source_label = (
                        "Manual final weight"
                        if dish_metrics["yield_source"] == "manual"
                        else "Auto final weight"
                    )
                    st.metric(
                        f"Calories per {dish_metrics['final_unit']}",
                        f"{dish_metrics['per_weight_calories']:.2f}",
                    )
                    st.metric(
                        f"Protein per {dish_metrics['final_unit']} (g)",
                        f"{dish_metrics['per_weight_protein']:.3f}",
                    )
                    st.metric(
                        f"Fiber per {dish_metrics['final_unit']} (g)",
                        format_nutrient_value("fiber", dish_metrics["per_weight_fiber"]),
                    )
                    st.caption(
                        f"{source_label}: {dish_metrics['final_qty']:.0f} {dish_metrics['final_unit']} total, "
                        f"{dish_metrics['servings']:.0f} servings, "
                        f"{dish_metrics['final_qty'] / dish_metrics['servings']:.1f} {dish_metrics['final_unit']} per serving."
                    )
                else:
                    st.caption(
                        "Weight logging becomes available when you add a manual final dish quantity or when all ingredient quantities share the same unit and can be auto-summed."
                    )

            base_cols = st.columns(3)
            base_cols[0].metric(f"Calories {basis_label}", f"{as_float(base_values['calories'], 0.0):.2f}")
            base_cols[1].metric(f"Protein {basis_label} (g)", f"{as_float(base_values['protein'], 0.0):.3f}")
            base_cols[2].metric(
                f"Fiber {basis_label} (g)",
                format_nutrient_value("fiber", base_values["fiber"]),
            )
            if log_unit == "serving" and dish_metrics["has_weight_basis"]:
                st.caption(
                    f"1 serving = {dish_metrics['final_qty'] / dish_metrics['servings']:.1f} "
                    f"{dish_metrics['final_unit']}"
                )
            entry_cols = st.columns(3)
            entry_cols[0].metric("Calories (this entry)", f"{est_c:.0f}")
            entry_cols[1].metric("Protein (this entry, g)", f"{est_p:.1f}")
            entry_cols[2].metric("Fiber (this entry, g)", format_nutrient_value("fiber", est_f))
            if dish_metrics["missing_nutrients"]:
                st.warning(
                    f"This dish cannot be logged until its {describe_missing_nutrients(dish_metrics['missing_nutrients'])} value is available."
                )
            if st.button(
                "Add to log",
                type="primary",
                use_container_width=True,
                key="add_dish_log",
                disabled=bool(dish_metrics["missing_nutrients"]),
            ):
                logs = add_log_entry(
                    logs, log_date, meal, "dish", d_name, log_unit, qty, est_c, est_p, est_f
                )
                save_df(logs, LOGS_CSV)
                clear_log_form()
                st.session_state.log_message = "Entry added."
                st.rerun()
    else:  # Batch
        if batches.empty:
            st.info("Create a batch in Master Data first.")
        else:
            batch_options = sorted(
                [(batch_key(row), row["batch_id"]) for _, row in batches.iterrows()],
                key=lambda item: item[0],
            )
            selected_batch_label = st.selectbox(
                "Batch",
                [label for label, _ in batch_options],
                key="log_batch_sel",
            )
            batch_id = dict(batch_options)[selected_batch_label]
            batch_row = get_batch_row(batches, batch_id)
            batch_metrics = get_batch_metrics(batch_row)
            batch_consumption = get_batch_consumption_summary(logs, batch_row)
            log_options = get_batch_log_options(batch_row)
            option_labels = [label for _, label in log_options]
            option_map = {label: unit for unit, label in log_options}
            selected_label = st.selectbox("Log by", option_labels, key="log_batch_basis")
            log_unit = option_map[selected_label]
            base_values = compute_batch_base(batch_row, log_unit)
            basis_label = get_dish_basis_label(log_unit)
            est_c = qty * as_float(base_values["calories"], 0.0)
            est_p = qty * as_float(base_values["protein"], 0.0)
            est_f = (
                qty * as_float(base_values["fiber"], 0.0)
                if pd.notna(base_values["fiber"])
                else None
            )

            info_cols = st.columns(3)
            with info_cols[0]:
                st.metric("Calories per serving", f"{batch_metrics['per_serving_calories']:.1f}")
                st.metric("Protein per serving (g)", f"{batch_metrics['per_serving_protein']:.2f}")
            with info_cols[1]:
                st.metric(
                    "Fiber per serving (g)",
                    format_nutrient_value("fiber", batch_metrics["per_serving_fiber"]),
                )
            with info_cols[2]:
                if batch_metrics["has_weight_basis"]:
                    source_label = (
                        "Manual final weight"
                        if as_text(batch_row.get("yield_source")) != "auto"
                        else "Auto final weight"
                    )
                    st.metric(
                        f"Calories per {batch_metrics['final_unit']}",
                        f"{batch_metrics['per_weight_calories']:.2f}",
                    )
                    st.metric(
                        f"Protein per {batch_metrics['final_unit']} (g)",
                        f"{batch_metrics['per_weight_protein']:.3f}",
                    )
                    st.metric(
                        f"Fiber per {batch_metrics['final_unit']} (g)",
                        format_nutrient_value("fiber", batch_metrics["per_weight_fiber"]),
                    )
                    st.caption(
                        f"{source_label}: {batch_metrics['final_qty']:.0f} {batch_metrics['final_unit']} total, "
                        f"{batch_metrics['servings']:.0f} servings, "
                        f"{batch_metrics['final_qty'] / batch_metrics['servings']:.1f} {batch_metrics['final_unit']} per serving."
                    )
                else:
                    st.caption(
                        "This batch only supports serving-based logging because no final weight was saved."
                    )

            remaining_cols = st.columns(2)
            if batch_metrics["has_weight_basis"]:
                remaining_cols[0].metric(
                    f"Remaining {batch_metrics['final_unit']}",
                    f"{batch_consumption['remaining_weight']:.1f}",
                )
                remaining_cols[1].metric(
                    "Remaining servings",
                    f"{batch_consumption['remaining_servings']:.2f}",
                )
                if batch_consumption["over_weight"] > 0:
                    st.caption(
                        f"Logged amount is over the saved batch total by "
                        f"{batch_consumption['over_weight']:.1f} {batch_metrics['final_unit']}."
                    )
                else:
                    st.caption(
                        f"Logged so far: {batch_consumption['consumed_weight']:.1f} {batch_metrics['final_unit']} "
                        f"across {batch_consumption['consumed_servings']:.2f} servings."
                    )
            else:
                remaining_cols[0].metric(
                    "Remaining servings",
                    f"{batch_consumption['remaining_servings']:.2f}",
                )
                remaining_cols[1].metric(
                    "Logged servings",
                    f"{batch_consumption['consumed_servings']:.2f}",
                )
                if batch_consumption["over_servings"] > 0:
                    st.caption(
                        f"Logged amount is over the saved batch total by "
                        f"{batch_consumption['over_servings']:.2f} servings."
                    )

            base_cols = st.columns(3)
            base_cols[0].metric(f"Calories {basis_label}", f"{as_float(base_values['calories'], 0.0):.2f}")
            base_cols[1].metric(f"Protein {basis_label} (g)", f"{as_float(base_values['protein'], 0.0):.3f}")
            base_cols[2].metric(
                f"Fiber {basis_label} (g)",
                format_nutrient_value("fiber", base_values["fiber"]),
            )
            if log_unit == "serving" and batch_metrics["has_weight_basis"]:
                st.caption(
                    f"1 serving = {batch_metrics['final_qty'] / batch_metrics['servings']:.1f} "
                    f"{batch_metrics['final_unit']}"
                )
            entry_cols = st.columns(3)
            entry_cols[0].metric("Calories (this entry)", f"{est_c:.0f}")
            entry_cols[1].metric("Protein (this entry, g)", f"{est_p:.1f}")
            entry_cols[2].metric("Fiber (this entry, g)", format_nutrient_value("fiber", est_f))
            if batch_metrics["missing_nutrients"]:
                st.warning(
                    f"This batch cannot be logged until its {describe_missing_nutrients(batch_metrics['missing_nutrients'])} value is available."
                )
            if st.button(
                "Add to log",
                type="primary",
                use_container_width=True,
                key="add_batch_log",
                disabled=bool(batch_metrics["missing_nutrients"]),
            ):
                logs = add_log_entry(
                    logs,
                    log_date,
                    meal,
                    "batch",
                    batch_row["dish_name"],
                    log_unit,
                    qty,
                    est_c,
                    est_p,
                    est_f,
                    batch_id=batch_id,
                )
                save_df(logs, LOGS_CSV)
                clear_log_form()
                st.session_state.log_message = "Entry added."
                st.rerun()

# --------- Tab 2: Day View ---------
with tabs[1]:
    st.subheader("Browse a day")
    colA, colB = st.columns([1, 1])
    with colA:
        nav_col1, nav_col2, nav_col3 = st.columns([0.5, 1, 0.5])
        with nav_col1:
            st.button("←", key="view_prev_day", on_click=shift_view_date, args=(-1,))
        with nav_col2:
            st.button("Today", key="view_today", on_click=set_view_date_today)
        with nav_col3:
            st.button("→", key="view_next_day", on_click=shift_view_date, args=(1,))
        view_date = st.date_input(
            "Pick a date",
            value=date.today(),
            format=DATE_INPUT_FORMAT,
            key="view_date",
        )
        st.markdown(
            f"<div style='font-size:1.08rem;font-weight:700;color:#374151;margin-top:0.28rem;line-height:1.3;'>{view_date.strftime('%A')}</div>",
            unsafe_allow_html=True,
        )
    with colB:
        st.write("Daily goals")

        # single global toggle (controls all past edits)
        allow = st.checkbox(
            "Allow editing past goals",
            help="If off, past dates cannot be edited anywhere.",
            key="allow_edit_past",
        )

        gcal, gprot = get_goal_for_date(goals, view_date)

        if gcal is None or gprot is None:
            d_cal = st.number_input(
                "Calorie goal", min_value=0.0, step=50.0, value=1800.0, key="gcal_new"
            )
            d_prot = st.number_input(
                "Protein goal", min_value=0.0, step=5.0, value=120.0, key="gprot_new"
            )
            disabled = view_date < date.today() and not allow
            if st.button(
                "Save goal for this date", disabled=disabled, key="save_day_goal"
            ):
                if disabled:
                    st.error("Editing past goals is disabled. Enable it above.")
                else:
                    goals = upsert_goal(goals, view_date, d_cal, d_prot)
                    save_df(goals, GOALS_CSV)
                    st.success("Goal saved.")
                    st.rerun()
        else:
            st.metric("Goal calories", f"{gcal:.0f}")
            st.metric("Goal protein (g)", f"{gprot:.0f}")

            # inline editor
            d_cal = st.number_input(
                "Edit calorie goal",
                min_value=0.0,
                step=50.0,
                value=float(gcal),
                key="gcal_edit",
            )
            d_prot = st.number_input(
                "Edit protein goal",
                min_value=0.0,
                step=5.0,
                value=float(gprot),
                key="gprot_edit",
            )
            disabled = view_date < date.today() and not allow
            if st.button("Update goal", disabled=disabled, key="update_day_goal"):
                if disabled:
                    st.error("Editing past goals is disabled. Enable it above.")
                else:
                    goals = upsert_goal(goals, view_date, d_cal, d_prot)
                    save_df(goals, GOALS_CSV)
                    st.success("Goal updated.")
                    st.rerun()

    day_logs = logs[logs["date"] == view_date.isoformat()].copy()
    tot_c, tot_p, tot_f = daily_totals(logs, view_date)
    st.markdown("### Daily totals")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Calories", f"{tot_c:.0f}")
    m2.metric("Protein (g)", f"{tot_p:.1f}")
    m3.metric("Fiber (g)", f"{tot_f:.1f}")
    if gcal is not None and gprot is not None:
        status_color, status_text, status_detail = classify_overall_goal_status(
            tot_c, gcal, tot_p, gprot
        )
        m4.markdown(
            f"""
            <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.04em;color:#666;">
                Overall
            </div>
            <div style="font-size:0.95rem;font-weight:700;color:{status_color};line-height:1.35;">
                {status_text}
            </div>
            <div style="font-size:0.8rem;color:#6b7280;line-height:1.3;margin-top:0.12rem;">
                {status_detail}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("#### Goal progress")
        p1, p2 = st.columns(2)
        with p1:
            render_goal_progress("Calories", tot_c, float(gcal), good_when_under=True)
        with p2:
            render_goal_progress("Protein", tot_p, float(gprot), good_when_under=False)
    else:
        m4.caption("Set daily goals to see calorie and protein status.")

    if day_logs.empty:
        st.info("No entries for this date.")
    else:
        day_logs["checked"] = to_bool_series(day_logs["checked"])
        day_logs["display_name"] = day_logs["name"]
        batch_mask = (day_logs["type"] == "batch") & day_logs["batch_id"].notna()
        day_logs.loc[batch_mask, "display_name"] = day_logs.loc[batch_mask].apply(
            lambda row: f"{row['name']} [{short_batch_id(row['batch_id'])}]",
            axis=1,
        )
        # Show grouped by meal
        for meal_name in MEAL_OPTIONS:
            sub = day_logs[day_logs["meal"] == meal_name]
            if sub.empty:
                continue
            st.markdown(f"### {meal_name}")
            meal_calories = float(sub["calories"].sum())
            meal_protein = float(sub["protein"].sum())
            meal_fiber = float(pd.to_numeric(sub["fiber"], errors="coerce").fillna(0.0).sum())
            meal_m1, meal_m2, meal_m3 = st.columns(3)
            meal_m1.metric("Meal calories", f"{meal_calories:.0f}")
            meal_m2.metric("Meal protein (g)", f"{meal_protein:.1f}")
            meal_m3.metric("Meal fiber (g)", f"{meal_fiber:.1f}")
            with st.container(border=True):
                header_cols = st.columns([0.5, 1.0, 2.9, 1, 1, 1.1, 1.1, 1.1])
                header_labels = ["", "Type", "Item", "Unit", "Qty", "Calories", "Protein (g)", "Fiber (g)"]
                for col, label in zip(header_cols, header_labels):
                    col.markdown(
                        f"<div style='font-size:0.78rem;color:#666;font-weight:700;'>{label}</div>",
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    "<div style='border-top:1px solid rgba(49,51,63,0.2); margin:0.25rem 0 0.35rem 0;'></div>",
                    unsafe_allow_html=True,
                )

                for row_pos, (idx, row) in enumerate(sub.iterrows()):
                    row_cols = st.columns([0.5, 1.0, 2.9, 1, 1, 1.1, 1.1, 1.1])
                    log_id = as_text(row.get("log_id"))
                    checkbox_key = f"day_view_done_{log_id}"
                    if checkbox_key not in st.session_state:
                        st.session_state[checkbox_key] = bool(row["checked"])
                    checked_value = row_cols[0].checkbox(
                        "Done",
                        key=checkbox_key,
                        label_visibility="collapsed",
                    )
                    if bool(row["checked"]) != bool(checked_value):
                        log_mask = logs["log_id"] == log_id
                        logs.loc[log_mask, "checked"] = bool(checked_value)
                        day_logs.loc[idx, "checked"] = bool(checked_value)
                        save_df(logs, LOGS_CSV)
                    row_cols[1].write(as_text(row["type"]))
                    row_cols[2].write(as_text(row["display_name"]))
                    row_cols[3].write(as_text(row["unit"]))
                    row_cols[4].write(f"{as_float(row['qty'], 0.0):g}")
                    row_cols[5].write(f"{as_float(row['calories'], 0.0):.0f}")
                    row_cols[6].write(f"{as_float(row['protein'], 0.0):.1f}")
                    row_cols[7].write(format_nutrient_value("fiber", row.get("fiber")))
                    if row_pos < len(sub.index) - 1:
                        st.markdown(
                            "<div style='border-top:1px solid rgba(49,51,63,0.12); margin:0.15rem 0 0.35rem 0;'></div>",
                            unsafe_allow_html=True,
                        )

        st.markdown("### Edit an entry")
        edit_options = {
            log_entry_label(row): as_text(row["log_id"]) for _, row in day_logs.iterrows()
        }
        edit_label = st.selectbox(
            "Select entry to edit",
            list(edit_options.keys()),
            key="edit_day_log_sel",
        )
        edit_log_id = edit_options[edit_label]
        edit_match = day_logs[day_logs["log_id"] == edit_log_id]
        edit_idx = edit_match.index[0]
        edit_row = edit_match.iloc[0]
        if st.session_state.get("edit_day_log_loaded_id") != edit_log_id:
            st.session_state.edit_day_log_qty = float(as_float(edit_row["qty"], 0.0))
            current_meal = as_text(edit_row["meal"])
            st.session_state.edit_day_log_meal = (
                current_meal if current_meal in MEAL_OPTIONS else MEAL_OPTIONS[0]
            )
            st.session_state.edit_day_log_date = (
                date.fromisoformat(as_text(edit_row["date"]))
                if as_text(edit_row.get("date"))
                else view_date
            )
            st.session_state.edit_day_log_loaded_id = edit_log_id

        new_date = st.date_input(
            "Date",
            value=view_date,
            format=DATE_INPUT_FORMAT,
            key="edit_day_log_date",
        )
        new_meal = st.selectbox("Meal", MEAL_OPTIONS, key="edit_day_log_meal")
        new_qty = st.number_input(
            "New quantity",
            min_value=0.0,
            step=1.0,
            key="edit_day_log_qty",
        )

        preview_cal = 0.0
        preview_prot = 0.0
        preview_fiber = None
        if edit_row["type"] == "food":
            frow = get_food_row(foods, edit_row["name"], edit_row["unit"])
            if frow is not None:
                preview_cal = new_qty * as_float(frow["cal_per_unit"], 0.0)
                preview_prot = new_qty * as_float(frow["protein_per_unit"], 0.0)
                preview_fiber = (
                    new_qty * as_float(frow["fiber_per_unit"], 0.0)
                    if pd.notna(frow.get("fiber_per_unit"))
                    else None
                )
        elif edit_row["type"] == "dish":
            base_values = compute_dish_base(
                edit_row["name"], dishes, dings, foods, batches, edit_row["unit"]
            )
            preview_cal = new_qty * as_float(base_values["calories"], 0.0)
            preview_prot = new_qty * as_float(base_values["protein"], 0.0)
            preview_fiber = (
                new_qty * as_float(base_values["fiber"], 0.0)
                if pd.notna(base_values["fiber"])
                else None
            )
        elif edit_row["type"] == "batch":
            batch_row = get_batch_row(batches, as_text(edit_row.get("batch_id")))
            base_values = compute_batch_base(batch_row, edit_row["unit"])
            preview_cal = new_qty * as_float(base_values["calories"], 0.0)
            preview_prot = new_qty * as_float(base_values["protein"], 0.0)
            preview_fiber = (
                new_qty * as_float(base_values["fiber"], 0.0)
                if pd.notna(base_values["fiber"])
                else None
            )

        edit_m1, edit_m2, edit_m3 = st.columns(3)
        edit_m1.metric("Updated calories", f"{preview_cal:.0f}")
        edit_m2.metric("Updated protein (g)", f"{preview_prot:.1f}")
        edit_m3.metric("Updated fiber (g)", format_nutrient_value("fiber", preview_fiber))

        if st.button("Save entry changes", key="save_day_log_edit_button"):
            if new_qty <= 0:
                st.error("Quantity must be greater than 0.")
            else:
                edit_mask = logs["log_id"] == edit_log_id
                logs.loc[edit_mask, "date"] = new_date.isoformat()
                logs.loc[edit_mask, "meal"] = new_meal
                logs.loc[edit_mask, "qty"] = new_qty
                logs.loc[edit_mask, "calories"] = preview_cal
                logs.loc[edit_mask, "protein"] = preview_prot
                logs.loc[edit_mask, "fiber"] = preview_fiber
                save_df(logs, LOGS_CSV)
                clear_session_keys(
                    [
                        "edit_day_log_sel",
                        "edit_day_log_date",
                        "edit_day_log_meal",
                        "edit_day_log_qty",
                        "edit_day_log_loaded_id",
                    ]
                )
                st.success("Entry updated.")
                st.rerun()

        st.markdown("### Delete an entry")
        delete_options = {
            log_entry_label(row): as_text(row["log_id"]) for _, row in day_logs.iterrows()
        }
        delete_label = st.selectbox(
            "Select entry to delete",
            list(delete_options.keys()),
            key="delete_day_log_sel",
        )
        confirm_delete_entry = st.text_input(
            "Type DELETE ENTRY to confirm",
            key="confirm_delete_day_log",
        )
        if st.button("Delete selected entry", key="delete_day_log_button"):
            if confirm_delete_entry.strip() == "DELETE ENTRY":
                delete_log_id = delete_options[delete_label]
                logs = logs[logs["log_id"] != delete_log_id].copy()
                save_df(logs, LOGS_CSV)
                clear_session_keys(["delete_day_log_sel", "confirm_delete_day_log"])
                st.success("Entry deleted.")
                st.rerun()
            else:
                st.error("Confirmation did not match. No entry was deleted.")

# --------- Tab 3: Dashboard ---------
with tabs[2]:
    st.subheader("Monthly Dashboard")
    if "dashboard_month" not in st.session_state:
        st.session_state.dashboard_month = month_start(date.today())

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
        if st.button("Previous month", key="dashboard_prev_month"):
            st.session_state.dashboard_month = shift_month(
                st.session_state.dashboard_month, -1
            )
            st.rerun()
    with nav2:
        st.markdown(
            f"### {st.session_state.dashboard_month.strftime('%B %Y')}"
        )
    with nav3:
        if st.button("Next month", key="dashboard_next_month"):
            st.session_state.dashboard_month = shift_month(
                st.session_state.dashboard_month, 1
            )
            st.rerun()

    dashboard_month = st.session_state.dashboard_month
    month_prefix = dashboard_month.strftime("%Y-%m")
    month_last_day = month_end(dashboard_month)
    today_value = date.today()
    if (dashboard_month.year, dashboard_month.month) < (today_value.year, today_value.month):
        dashboard_anchor_day = month_last_day
    elif (dashboard_month.year, dashboard_month.month) == (today_value.year, today_value.month):
        dashboard_anchor_day = min(today_value, month_last_day)
    else:
        dashboard_anchor_day = dashboard_month
    month_days_elapsed = max((dashboard_anchor_day - dashboard_month).days + 1, 1)
    week_start_day = dashboard_anchor_day - timedelta(days=dashboard_anchor_day.weekday())
    week_days_elapsed = dashboard_anchor_day.weekday() + 1
    week_end_day = week_start_day + timedelta(days=6)

    agg = (
        logs.groupby("date")
        .agg(calories=("calories", "sum"), protein=("protein", "sum"), fiber=("fiber", "sum"))
        .reset_index()
        if not logs.empty
        else pd.DataFrame(columns=["date", "calories", "protein", "fiber"])
    )
    month_days = pd.date_range(dashboard_month, month_last_day, freq="D")
    month_rows = pd.DataFrame(
        {"date": [day.date().isoformat() for day in month_days]}
    )
    month_rows = month_rows.merge(agg, on="date", how="left")
    month_rows = apply_effective_goals(month_rows, goals, "date")

    if month_rows.empty:
        st.info("No logged entries or goals for this month yet.")
    else:
        month_rows["calories"] = pd.to_numeric(month_rows["calories"], errors="coerce").fillna(0.0)
        month_rows["protein"] = pd.to_numeric(month_rows["protein"], errors="coerce").fillna(0.0)
        month_rows["fiber"] = pd.to_numeric(month_rows["fiber"], errors="coerce").fillna(0.0)
        month_rows["calorie_goal"] = pd.to_numeric(
            month_rows["calorie_goal"], errors="coerce"
        )
        month_rows["protein_goal"] = pd.to_numeric(
            month_rows["protein_goal"], errors="coerce"
        )
        month_rows["has_log"] = (
            (month_rows["calories"] > 0)
            | (month_rows["protein"] > 0)
            | (month_rows["fiber"] > 0)
        )
        month_rows["protein_met"] = (
            month_rows["protein"] >= month_rows["protein_goal"]
        ) & month_rows["protein_goal"].notna() & month_rows["has_log"]
        month_rows["calorie_ok"] = (
            month_rows["calories"] <= month_rows["calorie_goal"] * 1.04
        ) & month_rows["calorie_goal"].notna() & month_rows["has_log"]

        days_in_month = calendar.monthrange(
            dashboard_month.year, dashboard_month.month
        )[1]
        protein_met_days = int(month_rows["protein_met"].sum())
        calorie_ok_days = int(month_rows["calorie_ok"].sum())
        logged_days = int(month_rows["has_log"].sum())
        month_total_calories = float(month_rows["calories"].sum())
        month_total_protein = float(month_rows["protein"].sum())
        month_total_fiber = float(month_rows["fiber"].sum())
        month_avg_calories = month_total_calories / month_days_elapsed
        month_avg_protein = month_total_protein / month_days_elapsed
        month_avg_fiber = month_total_fiber / month_days_elapsed

        week_rows = month_rows.copy()
        week_rows["parsed_date"] = week_rows["date"].apply(parse_date_value)
        week_rows = week_rows[
            week_rows["parsed_date"].notna()
            & (week_rows["parsed_date"] >= week_start_day)
            & (week_rows["parsed_date"] <= dashboard_anchor_day)
        ].copy()
        week_total_calories = float(week_rows["calories"].sum()) if not week_rows.empty else 0.0
        week_total_protein = float(week_rows["protein"].sum()) if not week_rows.empty else 0.0
        week_total_fiber = float(week_rows["fiber"].sum()) if not week_rows.empty else 0.0
        week_avg_calories = week_total_calories / week_days_elapsed
        week_avg_protein = week_total_protein / week_days_elapsed
        week_avg_fiber = week_total_fiber / week_days_elapsed
        week_number = dashboard_anchor_day.isocalendar().week

        c1, c2, c3 = st.columns(3)
        c1.metric("Days logged", f"{logged_days}/{days_in_month}")
        c2.metric("Protein met", f"{protein_met_days}/{days_in_month}")
        c3.metric("Calories on target", f"{calorie_ok_days}/{days_in_month}")

        avg_m1, avg_m2 = st.columns(2)
        with avg_m1:
            st.markdown("#### Month-to-date daily average")
            mavg1, mavg2, mavg3 = st.columns(3)
            mavg1.metric("Calories", f"{month_avg_calories:.0f}")
            mavg2.metric("Protein (g)", f"{month_avg_protein:.1f}")
            mavg3.metric("Fiber (g)", f"{month_avg_fiber:.1f}")
            st.caption(
                f"Totals used: {month_total_calories:.0f} kcal, {month_total_protein:.1f}g protein, and {month_total_fiber:.1f}g fiber. "
            )
            st.caption(
                f"Using {month_days_elapsed} elapsed day{'s' if month_days_elapsed != 1 else ''} "
                f"through {format_day(dashboard_anchor_day)}."
            )
        with avg_m2:
            st.markdown(f"#### Week {week_number} daily average")
            wavg1, wavg2, wavg3 = st.columns(3)
            wavg1.metric("Calories", f"{week_avg_calories:.0f}")
            wavg2.metric("Protein (g)", f"{week_avg_protein:.1f}")
            wavg3.metric("Fiber (g)", f"{week_avg_fiber:.1f}")
            st.caption(
                f"Totals used: {week_total_calories:.0f} kcal, {week_total_protein:.1f}g protein, and {week_total_fiber:.1f}g fiber. "
            )
            st.caption(
                f"Monday-start week, using {week_days_elapsed} elapsed day{'s' if week_days_elapsed != 1 else ''} "
                f"from {format_day(week_start_day)} to {format_day(dashboard_anchor_day)}."
            )

        calorie_map = {}
        protein_map = {}
        for _, row in month_rows.iterrows():
            parsed_day = parse_date_value(row["date"])
            if parsed_day is None or not row["has_log"]:
                continue
            calorie_map[parsed_day.day] = {
                "value": row["calories"],
                "goal": row["calorie_goal"],
            }
            protein_map[parsed_day.day] = {
                "value": row["protein"],
                "goal": row["protein_goal"],
            }

        heat1, heat2 = st.columns(2)
        with heat1:
            render_month_heatmap(
                "Calories Heatmap", dashboard_month, calorie_map, calorie_status_for_day
            )
        with heat2:
            render_month_heatmap(
                "Protein Heatmap", dashboard_month, protein_map, protein_status_for_day
            )

        st.markdown("#### Month Detail")
        month_rows["date"] = format_date_series(month_rows["date"])
        st.dataframe(
            month_rows[
                [
                    "date",
                    "has_log",
                    "calories",
                    "calorie_goal",
                    "calorie_ok",
                    "protein",
                    "fiber",
                    "protein_goal",
                    "protein_met",
                ]
            ].fillna("—"),
            use_container_width=True,
        )

# --------- Tab 4: Master Data ---------
with tabs[3]:
    master_data_message = st.session_state.pop("master_data_message", None)
    if master_data_message:
        st.success(master_data_message)

    section_heading(
        "Foods",
        "Foods are atomic ingredients or packaged items. Food + unit is unique, so Milk [ml] and Milk [cup] are separate entries. Enter nutrition using a base quantity, like 100g or 250ml; Shoku derives per-unit values automatically.",
        level=3,
    )
    with collapsible_panel("Add food", "add_food") as panel_open:
        if panel_open:
            st.caption(
                "Create a reusable food definition. Example: Rice, unit g, base quantity 100, calories 130, protein 2.7, fiber 0.4."
            )
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                f_name = st.text_input("Food name", key="add_food_name")
            with c2:
                unit = st.text_input("Unit (e.g., g, ml, pc, bowl, tbsp)", key="add_food_unit")
            with c3:
                base_qty = st.number_input("Base quantity", min_value=1.0, step=1.0, value=100.0, key="add_base_qty")
                cal_base = st.number_input("Calories for base qty", min_value=0.0, step=1.0, key="add_cal_base")
            with c4:
                prot_base = st.number_input("Protein for base qty (g)", min_value=0.0, step=0.1, key="add_prot_base")
            with c5:
                fiber_base_text = st.text_input("Fiber for base qty (g)", key="add_fiber_base")

            b1, b2 = st.columns(2)
            with b1:
                save_food = st.button("Save food", key="save_food")
            with b2:
                st.button("Clear form", key="clear_add_food", on_click=clear_add_food_form)

            if save_food:
                f_name = f_name.strip()
                unit = unit.strip()
                if f_name and unit:
                    if not fiber_base_text.strip():
                        st.error("Fiber for base quantity is required. Use 0 if needed.")
                        st.stop()
                    try:
                        fiber_base = float(fiber_base_text.strip())
                    except ValueError:
                        st.error("Fiber for base quantity must be a number.")
                        st.stop()
                    if fiber_base < 0:
                        st.error("Fiber for base quantity cannot be negative.")
                        st.stop()
                    exists = (foods["food_name"] == f_name) & (foods["unit"] == unit)
                    if exists.any():
                        st.warning("Food with this unit already exists.")
                    else:
                        cal_per = cal_base / base_qty if base_qty > 0 else 0
                        prot_per = prot_base / base_qty if base_qty > 0 else 0
                        fiber_per = fiber_base / base_qty if base_qty > 0 else 0

                        foods.loc[len(foods)] = [
                            f_name,
                            unit,
                            base_qty,
                            cal_base,
                            prot_base,
                            fiber_base,
                            cal_per,
                            prot_per,
                            fiber_per,
                        ]
                        save_df(foods, FOODS_CSV)
                        clear_add_food_form()
                        st.session_state.master_data_message = "Food saved."
                        st.rerun()
                else:
                    st.error("Name and unit required.")

    with st.expander("View foods table", expanded=False):
        st.caption(
            "Reference table for all food definitions. Derived per-unit columns are what logs and ingredient dishes use."
        )
        st.dataframe(
            foods.assign(key=foods.apply(food_key, axis=1)), use_container_width=True
        )

    with collapsible_panel("Bulk edit food nutrients", "bulk_food_nutrients") as panel_open:
        if panel_open:
            st.caption(
                "Fastest way to backfill fiber for many foods. Edit the table and save once. Existing calorie/protein values are preloaded."
            )
            bulk_cols = [
            "food_name",
            "unit",
            "base_qty",
            "calories_base",
            "protein_base",
            "fiber_base",
            ]
            bulk_foods = foods[bulk_cols].copy().reset_index(names="source_index")
            bulk_foods["base_qty"] = pd.to_numeric(bulk_foods["base_qty"], errors="coerce").fillna(1.0)
            bulk_foods["calories_base"] = pd.to_numeric(
                bulk_foods["calories_base"], errors="coerce"
            ).fillna(0.0)
            bulk_foods["protein_base"] = pd.to_numeric(
                bulk_foods["protein_base"], errors="coerce"
            ).fillna(0.0)
            bulk_foods["fiber_base"] = pd.to_numeric(
                bulk_foods["fiber_base"], errors="coerce"
            )
            edited_bulk = st.data_editor(
                bulk_foods,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                disabled=["source_index", "food_name", "unit"],
                column_config={
                    "source_index": None,
                    "food_name": st.column_config.TextColumn("Food"),
                    "unit": st.column_config.TextColumn("Unit"),
                    "base_qty": st.column_config.NumberColumn("Base qty", min_value=1.0, step=1.0, required=True),
                    "calories_base": st.column_config.NumberColumn("Calories", min_value=0.0, step=1.0, required=True),
                    "protein_base": st.column_config.NumberColumn("Protein (g)", min_value=0.0, step=0.1, required=True),
                    "fiber_base": st.column_config.NumberColumn("Fiber (g)", min_value=0.0, step=0.1, required=True),
                },
                key="bulk_food_nutrient_editor",
            )
            if st.button("Save bulk food updates", key="save_bulk_food_updates"):
                updated_foods = foods.copy()
                impacted_food_refs = []
                for _, row in edited_bulk.iterrows():
                    source_index = int(row["source_index"])
                    updated_foods.loc[source_index, "base_qty"] = as_float(row["base_qty"], 1.0)
                    updated_foods.loc[source_index, "calories_base"] = as_float(row["calories_base"], 0.0)
                    updated_foods.loc[source_index, "protein_base"] = as_float(row["protein_base"], 0.0)
                    updated_foods.loc[source_index, "fiber_base"] = (
                        as_float(row["fiber_base"], 0.0)
                        if pd.notna(row["fiber_base"])
                        else None
                    )
                    impacted_food_refs.append(
                        (
                            as_text(updated_foods.loc[source_index, "food_name"]),
                            as_text(updated_foods.loc[source_index, "unit"]),
                        )
                    )

                updated_foods = updated_foods.apply(normalize_food_row, axis=1)
                foods = updated_foods
                save_df(foods, FOODS_CSV)

                for food_name_value, unit_value in impacted_food_refs:
                    logs = recalc_logs_for_food(logs, foods, food_name_value, unit_value)

                impacted_dishes = sorted(
                    dings[
                        (dings["ingredient_type"].fillna("food") == "food")
                        & dings["ingredient_food_name"].isin([name for name, _ in impacted_food_refs])
                    ]["dish_name"].unique().tolist()
                )
                if impacted_dishes:
                    logs = recalc_logs_for_dishes(logs, dishes, dings, foods, batches, impacted_dishes)
                batches, logs = recalc_batches_for_food_refs(
                    batches, batch_ings, logs, dishes, dings, foods, impacted_food_refs
                )
                batches, logs = recalc_recipe_dependents(
                    logs,
                    dishes,
                    dings,
                    foods,
                    batches,
                    batch_ings,
                    seed_dish_names=impacted_dishes,
                )
                save_df(batches, BATCHES_CSV)
                save_df(logs, LOGS_CSV)
                st.session_state.master_data_message = "Bulk food nutrient updates saved."
                st.rerun()

    if not foods.empty:
        section_heading(
            "Edit a food",
            "Change a food's name, unit, or nutrition values. Existing food logs are recalculated. If this food is used in dishes, keep propagation on when you are renaming the food or unit.",
        )
        with collapsible_panel("Edit a food", "edit_food") as panel_open:
            if panel_open:
                fedit = st.selectbox(
                "Select food to edit",
                foods.apply(food_key, axis=1).tolist(),
                key="edit_food_sel",
                )
                frow = foods[foods.apply(food_key, axis=1) == fedit].iloc[0]
                old_name, old_unit = frow["food_name"], frow["unit"]
                if st.session_state.get("edit_food_loaded_for") != fedit:
                    load_food_into_edit_form(frow, fedit)

                new_name = st.text_input("Food name", key="edit_food_name")
                new_unit = st.text_input("Unit", key="edit_food_unit")
                new_base_qty = st.number_input(
                "Base quantity",
                min_value=1.0,
                step=1.0,
                key="edit_base_qty",
                )

                new_cal_base = st.number_input(
                "Calories for base qty",
                min_value=0.0,
                step=1.0,
                key="edit_cal_base",
                )

                new_prot_base = st.number_input(
                "Protein for base qty",
                min_value=0.0,
                step=0.1,
                key="edit_prot_base",
                )
                new_fiber_base_text = st.text_input(
                "Fiber for base qty (g)",
                key="edit_fiber_base",
                )
                propagate = st.checkbox(
                "Also update dish ingredients that reference this food",
                key="edit_food_propagate",
                )

                if st.button("Save changes to food", key="save_food_edit"):
                    new_name = new_name.strip()
                    new_unit = new_unit.strip()
                    duplicate = (
                    (foods.index != frow.name)
                    & (foods["food_name"] == new_name)
                    & (foods["unit"] == new_unit)
                    )
                    validation_error = None
                    new_fiber_base = None
                    if not new_name or not new_unit:
                        validation_error = "Name and unit required."
                    elif duplicate.any():
                        validation_error = "Another food already uses this name and unit."
                    elif not new_fiber_base_text.strip():
                        validation_error = "Fiber for base quantity is required. Use 0 if needed."
                    else:
                        try:
                            new_fiber_base = float(new_fiber_base_text.strip())
                        except ValueError:
                            validation_error = "Fiber for base quantity must be a number."
                    if validation_error is None and new_fiber_base is not None and new_fiber_base < 0:
                        validation_error = "Fiber for base quantity cannot be negative."
                    if validation_error:
                        st.error(validation_error)
                    else:

                        impacted_before = sorted(
                        dings[
                            (dings["ingredient_type"].fillna("food") == "food")
                            &
                            (dings["ingredient_food_name"] == old_name)
                            & (dings["ingredient_unit"] == old_unit)
                        ]["dish_name"]
                        .unique()
                        .tolist()
                    )

                        # update foods table
                        cal_per = new_cal_base / new_base_qty if new_base_qty > 0 else 0
                        prot_per = new_prot_base / new_base_qty if new_base_qty > 0 else 0
                        fiber_per = new_fiber_base / new_base_qty if new_base_qty > 0 else 0

                        foods.loc[frow.name] = [
                        new_name,
                        new_unit,
                        new_base_qty,
                        new_cal_base,
                        new_prot_base,
                        new_fiber_base,
                        cal_per,
                        prot_per,
                        fiber_per,
                        ]
                        save_df(foods, FOODS_CSV)

                    # If name/unit changed, update existing food logs to new identifiers
                        if new_name != old_name or new_unit != old_unit:
                            mask_logs = (
                            (logs["type"] == "food")
                            & (logs["name"] == old_name)
                            & (logs["unit"] == old_unit)
                            )
                            logs.loc[mask_logs, ["name", "unit"]] = [new_name, new_unit]

                    # Optionally propagate to dish ingredients
                        if propagate and (new_name != old_name or new_unit != old_unit):
                            mask = (dings["ingredient_food_name"] == old_name) & (
                            dings["ingredient_unit"] == old_unit
                            )
                            mask = mask & (dings["ingredient_type"].fillna("food") == "food")
                            dings.loc[mask, "ingredient_food_name"] = new_name
                            dings.loc[mask, "ingredient_unit"] = new_unit
                            save_df(dings, DISH_ING_CSV)
                            st.success("References updated.")

                    # Recalculate logs that reference this food and any dishes that include it
                        logs = recalc_logs_for_food(logs, foods, new_name, new_unit)
                        impacted_after = sorted(
                        dings[
                            (dings["ingredient_type"].fillna("food") == "food")
                            &
                            (dings["ingredient_food_name"] == new_name)
                            & (dings["ingredient_unit"] == new_unit)
                        ]["dish_name"]
                        .unique()
                        .tolist()
                        )
                        impacted = sorted(set(impacted_before) | set(impacted_after))
                        if impacted:
                            logs = recalc_logs_for_dishes(logs, dishes, dings, foods, batches, impacted)
                        batches, logs = recalc_batches_for_food_refs(
                            batches,
                            batch_ings,
                            logs,
                            dishes,
                            dings,
                            foods,
                            [(new_name, new_unit)],
                        )
                        batches, logs = recalc_recipe_dependents(
                            logs,
                            dishes,
                            dings,
                            foods,
                            batches,
                            batch_ings,
                            seed_dish_names=impacted,
                        )
                        save_df(batches, BATCHES_CSV)
                        save_df(logs, LOGS_CSV)

                        st.success(f"Food {fedit} updated and logs recalculated.")
                        st.rerun()

    if not foods.empty:
        section_heading(
            "Delete a food",
            "Remove a food definition. This also deletes direct food logs for that food and removes matching ingredient references from dishes. Type the exact food key before deleting.",
        )
        with st.expander("Delete a food", expanded=False):
            fdel = st.selectbox(
                "Select food to delete",
                foods.apply(food_key, axis=1).tolist(),
                key="delete_food_sel",
            )

            # Preview how many logs/ingredients will be affected
            frow = foods[foods.apply(food_key, axis=1) == fdel].iloc[0]
            fname, funit = frow["food_name"], frow["unit"]
            affected_logs = logs[
                (logs["type"] == "food")
                & (logs["name"] == fname)
                & (logs["unit"] == funit)
            ]
            affected_ings = dings[
                (dings["ingredient_type"].fillna("food") == "food")
                &
                (dings["ingredient_food_name"] == fname)
                & (dings["ingredient_unit"] == funit)
            ]
            st.warning(
                f"Deleting **{fdel}** will remove {len(affected_logs)} log entries and {len(affected_ings)} dish ingredient references."
            )

            confirm_name = st.text_input(
                "Type the exact food name+unit to confirm", key="confirm_food"
            )
            if st.button("Delete food", key="delete_food_button"):
                if confirm_name.strip() == fdel:
                    impacted_dishes = sorted(affected_ings["dish_name"].unique().tolist())
                    logs = logs.drop(affected_logs.index)
                    dings = dings.drop(affected_ings.index)
                    foods = foods.drop(frow.name)

                    if impacted_dishes:
                        logs = recalc_logs_for_dishes(
                            logs, dishes, dings, foods, batches, impacted_dishes
                        )

                    save_df(foods, FOODS_CSV)
                    save_df(dings, DISH_ING_CSV)
                    save_df(logs, LOGS_CSV)
                    st.success(f"Deleted food {fdel}")
                    st.rerun()
                else:
                    st.error("Confirmation did not match. No delete.")

    section_heading(
        "Dishes",
        "Dishes are reusable meals or recipes. Use override mode for manually known nutrition per serving. Leave override off for ingredient-based dishes that calculate nutrition from foods.",
        level=3,
    )
    with collapsible_panel("Add / update dish", "add_update_dish") as panel_open:
        if panel_open:
            st.caption(
            "Use this to create or update a dish shell. Example override: Tea = 70 kcal, 2g protein, and 0g fiber per serving. Example ingredient dish: Dal with final dish quantity 850 and unit g, then add ingredients below."
            )
            dname = st.text_input("Dish name", key="add_dish_name")
            use_override = st.checkbox(
            "Use manual override values", key="add_dish_override"
            )
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                cal_o = st.number_input(
                "Calories per serving",
                min_value=0.0,
                step=1.0,
                value=0.0,
                disabled=not use_override,
                key="add_dish_cal",
                )
            with col2:
                prot_o = st.number_input(
                "Protein per serving (g)",
                min_value=0.0,
                step=0.1,
                value=0.0,
                disabled=not use_override,
                key="add_dish_prot",
                )
            with col3:
                fiber_o_text = st.text_input(
                "Fiber per serving (g)",
                disabled=not use_override,
                key="add_dish_fiber",
                )
            with col4:
                servings = st.number_input(
                "Servings definition",
                min_value=1.0,
                step=1.0,
                value=1.0,
                help="Use 1 unless you need a different base serving size.",
                key="add_dish_servings",
                )
            with col5:
                yield_qty = st.number_input(
                "Final dish quantity",
                min_value=0.0,
                step=1.0,
                value=0.0,
                disabled=use_override,
                help="Optional cooked/output quantity for ingredient dishes, e.g. 850.",
                key="add_dish_yield_qty",
                )
                yield_unit = st.text_input(
                "Final dish unit",
                disabled=use_override,
                help="Optional output unit, e.g. g. No unit conversion is applied.",
                key="add_dish_yield_unit",
                )
            b1, b2 = st.columns(2)
            with b1:
                save_dish = st.button("Save dish", key="save_dish")
            with b2:
                st.button("Clear form", key="clear_add_dish", on_click=clear_add_dish_form)

            if save_dish:
                dname = dname.strip()
                yield_unit = yield_unit.strip()
                if not dname:
                    st.error("Dish name required.")
                elif not use_override and yield_qty > 0 and not yield_unit:
                    st.error("Final dish unit is required when final dish quantity is set.")
                else:
                    if use_override and not fiber_o_text.strip():
                        st.error("Fiber per serving is required for override dishes. Use 0 if needed.")
                        st.stop()
                    fiberv = None
                    if use_override:
                        try:
                            fiberv = float(fiber_o_text.strip())
                        except ValueError:
                            st.error("Fiber per serving must be a number.")
                            st.stop()
                    exists = dishes["dish_name"] == dname
                    calv = cal_o if use_override else None
                    protv = prot_o if use_override else None
                    fiberv = fiberv if use_override else None
                    yieldv = yield_qty if not use_override and yield_qty > 0 else None
                    yield_unitv = yield_unit if yieldv is not None else None
                    if exists.any():
                        idx = dishes.index[exists][0]
                        dishes.loc[
                            idx,
                            [
                                "cal_override",
                                "protein_override",
                                "fiber_override",
                                "servings",
                                "yield_qty",
                                "yield_unit",
                            ],
                        ] = [calv, protv, fiberv, servings, yieldv, yield_unitv]
                    else:
                        dishes.loc[len(dishes)] = [
                            dname,
                            calv,
                            protv,
                            fiberv,
                            servings,
                            yieldv,
                            yield_unitv,
                        ]
                    save_df(dishes, DISHES_CSV)
                    batches, logs = recalc_recipe_dependents(
                        logs,
                        dishes,
                        dings,
                        foods,
                        batches,
                        batch_ings,
                        seed_dish_names=[dname],
                    )
                    save_df(logs, LOGS_CSV)
                    save_df(batches, BATCHES_CSV)
                    clear_add_dish_form()
                    st.session_state.master_data_message = "Dish saved and logs recalculated."
                    st.rerun()

    section_heading(
        "Duplicate a dish",
        "Copy a dish template and its ingredient rows into a new dish name. Useful when two recipes are mostly the same and you just want to tweak the copy.",
    )
    if not dishes.empty:
        with st.expander("Duplicate a dish", expanded=False):
            duplicate_source = st.selectbox(
                "Dish to duplicate",
                sorted(dishes["dish_name"].tolist()),
                key="duplicate_dish_source",
            )
            duplicate_name = st.text_input(
                "New dish name",
                key="duplicate_dish_name",
                help="The copy will include the dish settings and all template ingredients.",
            )
            dup_col1, dup_col2 = st.columns(2)
            with dup_col1:
                duplicate_dish = st.button("Duplicate dish", key="duplicate_dish_button")
            with dup_col2:
                st.button(
                    "Clear form",
                    key="clear_duplicate_dish",
                    on_click=clear_duplicate_dish_form,
                )

            if duplicate_dish:
                duplicate_name = duplicate_name.strip()
                if not duplicate_name:
                    st.error("New dish name required.")
                elif duplicate_name == duplicate_source:
                    st.error("New dish name must be different from the original.")
                elif (dishes["dish_name"] == duplicate_name).any():
                    st.error("A dish with that name already exists.")
                else:
                    source_row = dishes[dishes["dish_name"] == duplicate_source].iloc[0]
                    new_dish_row = source_row.copy()
                    new_dish_row["dish_name"] = duplicate_name
                    dishes = pd.concat(
                        [dishes, pd.DataFrame([new_dish_row])[DISH_COLUMNS]],
                        ignore_index=True,
                    )

                    source_ings = dings[dings["dish_name"] == duplicate_source].copy()
                    if not source_ings.empty:
                        source_ings["dish_name"] = duplicate_name
                        dings = pd.concat(
                            [dings, source_ings[DISH_INGREDIENT_COLUMNS]],
                            ignore_index=True,
                        )

                    save_df(dishes, DISHES_CSV)
                    save_df(dings, DISH_ING_CSV)
                    clear_duplicate_dish_form()
                    ing_count = len(source_ings)
                    st.session_state.master_data_message = (
                        f"Duplicated {duplicate_source} to {duplicate_name} "
                        f"with {ing_count} ingredient row{'s' if ing_count != 1 else ''}."
                    )
                    st.rerun()

    section_heading(
        "Edit a dish",
        "Edit override nutrition or final cooked yield. For ingredient dishes, final dish quantity lets raw ingredient nutrition scale to cooked weight, e.g. ingredients produce 850g dal so logging 100g uses 100/850 of the recipe.",
    )
    if not dishes.empty:
        with st.expander("Edit a dish", expanded=False):
            dsel_edit = st.selectbox(
                "Select dish to edit",
                sorted(dishes["dish_name"].tolist()),
                key="edit_dish_sel_unique",
            )
            drow = dishes[dishes["dish_name"] == dsel_edit].iloc[0]
            edit_use_override = st.checkbox(
                "Use manual override values",
                value=is_override_dish(drow),
                key="edit_dish_override_unique",
            )

            new_cal = st.number_input(
                "Calories per serving",
                min_value=0.0,
                step=1.0,
                value=float(drow["cal_override"])
                if pd.notna(drow["cal_override"])
                else 0.0,
                disabled=not edit_use_override,
                key="edit_dish_cal_unique",
            )
            new_prot = st.number_input(
                "Protein per serving",
                min_value=0.0,
                step=0.1,
                value=float(drow["protein_override"])
                if pd.notna(drow["protein_override"])
                else 0.0,
                disabled=not edit_use_override,
                key="edit_dish_prot_unique",
            )
            new_fiber_text = st.text_input(
                "Fiber per serving (g)",
                value="" if pd.isna(drow["fiber_override"]) else format_nutrient_value("fiber", drow["fiber_override"]),
                disabled=not edit_use_override,
                key="edit_dish_fiber_unique",
            )
            new_serv = st.number_input(
                "Servings definition",
                min_value=1.0,
                step=1.0,
                value=float(drow["servings"]) if pd.notna(drow["servings"]) else 1.0,
                key="edit_dish_serv_unique",
            )
            edit_yield_qty = st.number_input(
                "Final dish quantity",
                min_value=0.0,
                step=1.0,
                value=as_float(drow.get("yield_qty"), 0.0),
                disabled=edit_use_override,
                help="Optional cooked/output quantity for ingredient dishes.",
                key="edit_dish_yield_qty_unique",
            )
            edit_yield_unit = st.text_input(
                "Final dish unit",
                value=as_text(drow.get("yield_unit")),
                disabled=edit_use_override,
                help="Optional output unit, e.g. g. No unit conversion is applied.",
                key="edit_dish_yield_unit_unique",
            )

            if st.button("Save changes to dish", key="save_dish_edit_unique"):
                edit_yield_unit = edit_yield_unit.strip()
                if not edit_use_override and edit_yield_qty > 0 and not edit_yield_unit:
                    st.error("Final dish unit is required when final dish quantity is set.")
                else:
                    new_fiber = None
                    if edit_use_override:
                        if not new_fiber_text.strip():
                            st.error("Fiber per serving is required for override dishes. Use 0 if needed.")
                            st.stop()
                        try:
                            new_fiber = float(new_fiber_text.strip())
                        except ValueError:
                            st.error("Fiber per serving must be a number.")
                            st.stop()
                    yieldv = edit_yield_qty if not edit_use_override and edit_yield_qty > 0 else None
                    yield_unitv = edit_yield_unit if yieldv is not None else None
                    idx = drow.name
                    dishes.loc[
                        idx,
                        [
                            "cal_override",
                            "protein_override",
                            "fiber_override",
                            "servings",
                            "yield_qty",
                            "yield_unit",
                        ],
                    ] = [
                        new_cal if edit_use_override else None,
                        new_prot if edit_use_override else None,
                        new_fiber if edit_use_override else None,
                        new_serv,
                        yieldv,
                        yield_unitv,
                    ]
                    save_df(dishes, DISHES_CSV)
                    batches, logs = recalc_recipe_dependents(
                        logs,
                        dishes,
                        dings,
                        foods,
                        batches,
                        batch_ings,
                        seed_dish_names=[dsel_edit],
                    )
                    save_df(logs, LOGS_CSV)
                    save_df(batches, BATCHES_CSV)
                    st.success(f"Dish {dsel_edit} updated and logs recalculated.")
                    st.rerun()

    with collapsible_panel("Add ingredient to dish (for computed dishes)", "add_ing_dish") as panel_open:
        if panel_open:
            st.caption(
            "Add foods or saved batches into an ingredient-based dish. Example: 200g raw dal + 20g ghee + 300g of yesterday's cooked rajma batch."
            )
            has_other_dish_template = len(dishes["dish_name"].tolist()) > 1
            if dishes.empty or (foods.empty and batches.empty and not has_other_dish_template):
                st.info("Add at least one dish plus one food, batch, or another dish template first.")
            else:
                dsel = st.selectbox(
                "Dish", sorted(dishes["dish_name"].tolist()), key="add_ing_dish"
                )
                ing_type = st.selectbox(
                "Ingredient source",
                ["Food", "Dish", "Batch"],
                key="add_ing_type",
                )
                ingredient_type = ing_type.lower()
                ingredient_food_name = ""
                ingredient_batch_id = ""
                ingredient_ref_dish_name = ""
                if ingredient_type == "food":
                    if foods.empty:
                        st.info("No foods available. Choose Dish or Batch instead.")
                        ingredient_type = "dish" if not dishes.empty else "batch"
                    else:
                        fsel = st.selectbox(
                        "Ingredient food",
                        sorted(foods["food_name"].unique().tolist()),
                        key="add_ing_food",
                        )
                        units = get_ingredient_unit_choices("food", foods, dishes, dings, batches, food_name=fsel)
                        u_sel = st.selectbox("Ingredient unit", units, key="add_ing_unit")
                        ingredient_food_name = fsel
                        ingredient_batch_id = ""
                if ingredient_type == "dish":
                    dish_choices = sorted([name for name in dishes["dish_name"].tolist() if name != dsel])
                    if not dish_choices:
                        st.info("No other dish templates available. Choose Food or Batch instead.")
                        ingredient_type = "batch" if not batches.empty else "food"
                    else:
                        ingredient_ref_dish_name = st.selectbox(
                            "Ingredient dish",
                            dish_choices,
                            key="add_ing_dish_ref",
                        )
                        units = get_ingredient_unit_choices(
                            "dish",
                            foods,
                            dishes,
                            dings,
                            batches,
                            dish_name=ingredient_ref_dish_name,
                        )
                        unit_label_map = dict(get_dish_basis_options(ingredient_ref_dish_name, dishes, dings, foods, batches))
                        selected_unit_label = st.selectbox(
                            "Ingredient basis",
                            [unit_label_map[unit] for unit in units],
                            key="add_ing_dish_unit_label",
                        )
                        reverse_unit_map = {label: unit for unit, label in unit_label_map.items()}
                        u_sel = reverse_unit_map[selected_unit_label]
                        ingredient_food_name = ingredient_ref_dish_name
                        ingredient_batch_id = ""
                if ingredient_type == "batch":
                    batch_options = get_batch_select_options(batches)
                    if not batch_options:
                        st.info("No saved batches available. Choose Food or Dish instead.")
                        ingredient_type = "dish" if not dishes.empty else "food"
                        ingredient_food_name = ""
                        u_sel = ""
                    else:
                        batch_map = dict(batch_options)
                        selected_batch_label = st.selectbox(
                        "Ingredient batch",
                        list(batch_map.keys()),
                        key="add_ing_batch",
                        )
                        ingredient_batch_id = batch_map[selected_batch_label]
                        selected_batch_row = get_batch_row(batches, ingredient_batch_id)
                        ingredient_food_name = (
                        as_text(selected_batch_row["dish_name"]) if selected_batch_row is not None else ""
                        )
                        units = get_ingredient_unit_choices(
                        "batch", foods, dishes, dings, batches, batch_id=ingredient_batch_id
                        )
                        unit_label_map = dict(get_batch_basis_options(selected_batch_row))
                        selected_unit_label = st.selectbox(
                        "Ingredient basis",
                        [unit_label_map[unit] for unit in units],
                        key="add_ing_batch_unit_label",
                        )
                        reverse_unit_map = {label: unit for unit, label in unit_label_map.items()}
                        u_sel = reverse_unit_map[selected_unit_label]
                qty = st.number_input(
                "Ingredient qty in recipe",
                min_value=0.0,
                step=1.0,
                value=0.0,
                key="add_ing_qty",
                )
                if st.button("Add ingredient", key="add_ing_button"):
                    if qty <= 0:
                        st.error("Quantity must be > 0.")
                    elif not ingredient_food_name or not u_sel:
                        st.error("Choose a valid ingredient source and basis/unit.")
                    else:
                        dings.loc[len(dings)] = [
                        dsel,
                        ingredient_type,
                        ingredient_food_name,
                        u_sel,
                        qty,
                        ingredient_batch_id,
                        ]
                        save_df(dings, DISH_ING_CSV)
                        batches, logs = recalc_recipe_dependents(
                            logs,
                            dishes,
                            dings,
                            foods,
                            batches,
                            batch_ings,
                            seed_dish_names=[dsel],
                        )
                        save_df(logs, LOGS_CSV)
                        save_df(batches, BATCHES_CSV)
                        clear_add_ingredient_form()
                        st.session_state.master_data_message = "Ingredient added and logs recalculated."
                        st.rerun()

    section_heading(
        "Edit ingredients",
        "Adjust or remove the recipe ingredients for a computed dish. Any update recalculates logs for matching dish entries.",
    )
    if not dishes.empty:
        with st.expander("Edit ingredients", expanded=False):
            dsel_ing = st.selectbox(
                "Select dish to manage ingredients",
                sorted(dishes["dish_name"].tolist()),
                key="edit_ing_dish_sel_unique",
            )
            cur_ings = dings[dings["dish_name"] == dsel_ing]

            if cur_ings.empty:
                st.info("No ingredients for this dish.")
            else:
                st.write("Current ingredients (edit inline):")
                for i, ing in cur_ings.iterrows():
                    st.markdown(
                        f"**{ingredient_ref_label(ing, batches)}**"
                    )
                    current_type = (
                        "Batch" if ingredient_type_for_row(ing) == "batch"
                        else "Dish" if ingredient_type_for_row(ing) == "dish"
                        else "Food"
                    )
                    batch_options = get_batch_select_options(batches)
                    batch_map = dict(batch_options)
                    batch_labels = list(batch_map.keys())
                    selected_batch_id = as_text(ing.get("ingredient_batch_id"))
                    selected_batch_label = (
                        next((label for label, batch_id in batch_options if batch_id == selected_batch_id), None)
                        if batch_options
                        else None
                    )
                    food_choices = sorted(foods["food_name"].unique().tolist())

                    fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns([2, 3, 2, 2, 2])
                    with fcol1:
                        source_choice = st.selectbox(
                            "Source",
                            ["Food", "Dish", "Batch"],
                            index=["Food", "Dish", "Batch"].index(current_type),
                            key=f"ing_type_{i}",
                        )
                    with fcol2:
                        if source_choice == "Food":
                            food_choice = st.selectbox(
                                "Food",
                                food_choices if food_choices else [""],
                                index=food_choices.index(ing["ingredient_food_name"])
                                if food_choices and ing["ingredient_food_name"] in food_choices
                                else 0,
                                key=f"ing_food_{i}",
                            )
                            batch_choice_id = ""
                            batch_choice_label = None
                        elif source_choice == "Batch":
                            batch_choice_label = st.selectbox(
                                "Batch",
                                batch_labels if batch_labels else ["No saved batches"],
                                index=batch_labels.index(selected_batch_label)
                                if batch_labels and selected_batch_label in batch_labels
                                else 0,
                                key=f"ing_batch_{i}",
                            )
                            batch_choice_id = batch_map.get(batch_choice_label, "")
                            batch_choice_row = get_batch_row(batches, batch_choice_id)
                            food_choice = (
                                as_text(batch_choice_row["dish_name"]) if batch_choice_row is not None else ""
                            )
                        else:
                            dish_choices = sorted([name for name in dishes["dish_name"].tolist() if name != dsel_ing])
                            selected_dish_name = (
                                ing["ingredient_food_name"]
                                if ing["ingredient_food_name"] in dish_choices
                                else (dish_choices[0] if dish_choices else "")
                            )
                            food_choice = st.selectbox(
                                "Dish",
                                dish_choices if dish_choices else [""],
                                index=dish_choices.index(selected_dish_name) if selected_dish_name in dish_choices else 0,
                                key=f"ing_dish_{i}",
                            )
                            batch_choice_id = ""
                            batch_choice_label = None
                    with fcol3:
                        unit_options = get_ingredient_unit_choices(
                            source_choice.lower(),
                            foods,
                            dishes,
                            dings,
                            batches,
                            food_name=food_choice,
                            dish_name=food_choice,
                            batch_id=batch_choice_id if source_choice == "Batch" else "",
                        )
                        if source_choice == "Batch":
                            batch_choice_row = get_batch_row(batches, batch_choice_id) if batch_choice_id else None
                            unit_label_map = dict(get_batch_basis_options(batch_choice_row))
                            reverse_unit_map = {label: unit for unit, label in unit_label_map.items()}
                            current_unit_label = unit_label_map.get(as_text(ing["ingredient_unit"]), unit_label_map.get(unit_options[0], unit_options[0]))
                            unit_choice_label = st.selectbox(
                                "Basis",
                                [unit_label_map[unit] for unit in unit_options],
                                index=[unit_label_map[unit] for unit in unit_options].index(current_unit_label)
                                if current_unit_label in [unit_label_map[unit] for unit in unit_options]
                                else 0,
                                key=f"ing_unit_{i}",
                            )
                            unit_choice = reverse_unit_map[unit_choice_label]
                        elif source_choice == "Dish":
                            unit_label_map = dict(get_dish_basis_options(food_choice, dishes, dings, foods, batches))
                            reverse_unit_map = {label: unit for unit, label in unit_label_map.items()}
                            current_unit_label = unit_label_map.get(
                                as_text(ing["ingredient_unit"]),
                                unit_label_map.get(unit_options[0], unit_options[0]),
                            )
                            unit_choice_label = st.selectbox(
                                "Basis",
                                [unit_label_map[unit] for unit in unit_options],
                                index=[unit_label_map[unit] for unit in unit_options].index(current_unit_label)
                                if current_unit_label in [unit_label_map[unit] for unit in unit_options]
                                else 0,
                                key=f"ing_unit_{i}",
                            )
                            unit_choice = reverse_unit_map[unit_choice_label]
                        else:
                            unit_choice = st.selectbox(
                                "Unit",
                                unit_options,
                                index=unit_options.index(ing["ingredient_unit"])
                                if ing["ingredient_unit"] in unit_options
                                else 0,
                                key=f"ing_unit_{i}",
                            )
                    with fcol4:
                        qty_choice = st.number_input(
                            "Ingredient qty in recipe",
                            min_value=0.0,
                            step=1.0,
                            value=float(ing["ingredient_qty_per_serving"]),
                            key=f"ing_qty_{i}",
                        )
                    with fcol5:
                        preview_row = {
                            "ingredient_type": source_choice.lower(),
                            "ingredient_food_name": food_choice,
                            "ingredient_unit": unit_choice,
                            "ingredient_qty": qty_choice,
                            "ingredient_batch_id": batch_choice_id if source_choice == "Batch" else "",
                        }
                        est_c, est_p, est_f, err_text = estimate_ingredient_row(preview_row, foods, dishes, dings, batches)
                        if err_text:
                            st.caption(err_text)
                        else:
                            st.caption(
                                f"{est_c:.0f} kcal | {est_p:.1f}g protein | {format_nutrient_value('fiber', est_f, with_unit=True)} fiber"
                            )
                    action_col1, action_col2 = st.columns(2)
                    with action_col1:
                        if st.button("Update", key=f"ing_update_{i}"):
                            dings.loc[
                                i,
                                [
                                    "ingredient_type",
                                    "ingredient_food_name",
                                    "ingredient_unit",
                                    "ingredient_qty_per_serving",
                                    "ingredient_batch_id",
                                ],
                            ] = [
                                source_choice.lower(),
                                food_choice,
                                unit_choice,
                                qty_choice,
                                batch_choice_id if source_choice == "Batch" else "",
                            ]
                            save_df(dings, DISH_ING_CSV)
                            batches, logs = recalc_recipe_dependents(
                                logs,
                                dishes,
                                dings,
                                foods,
                                batches,
                                batch_ings,
                                seed_dish_names=[dsel_ing],
                            )
                            save_df(logs, LOGS_CSV)
                            save_df(batches, BATCHES_CSV)
                            st.success("Ingredient updated and logs recalculated.")
                            st.rerun()
                    with action_col2:
                        if st.button("Remove", key=f"ing_remove_{i}"):
                            dings = dings.drop(i)
                            save_df(dings, DISH_ING_CSV)
                            batches, logs = recalc_recipe_dependents(
                                logs,
                                dishes,
                                dings,
                                foods,
                                batches,
                                batch_ings,
                                seed_dish_names=[dsel_ing],
                            )
                            save_df(logs, LOGS_CSV)
                            save_df(batches, BATCHES_CSV)
                            st.success("Ingredient removed and logs recalculated.")
                            st.rerun()

    with st.expander("View dishes table", expanded=False):
        st.caption(
            "Preview dish totals plus both logging bases. Final quantity is manual when entered, otherwise auto-summed from ingredients only when all ingredient quantities use the same unit."
        )
        if dishes.empty:
            st.info("No dishes yet.")
        else:
            preview = []
            for dname in sorted(dishes["dish_name"].tolist()):
                metrics = get_dish_metrics(dname, dishes, dings, foods, batches)
                preview.append(
                    {
                        "dish_name": dname,
                        "servings": round(metrics["servings"], 2),
                        "total_calories": round(metrics["total_calories"], 2),
                        "total_protein": round(metrics["total_protein"], 2),
                        "total_fiber": round(as_float(metrics["total_fiber"], 0.0), 2)
                        if pd.notna(metrics["total_fiber"])
                        else None,
                        "calories_per_serving": round(metrics["per_serving_calories"], 2),
                        "protein_per_serving": round(metrics["per_serving_protein"], 2),
                        "fiber_per_serving": round(as_float(metrics["per_serving_fiber"], 0.0), 2)
                        if pd.notna(metrics["per_serving_fiber"])
                        else None,
                        "final_qty": round(metrics["final_qty"], 2)
                        if metrics["has_weight_basis"]
                        else None,
                        "final_unit": metrics["final_unit"],
                        "final_qty_source": metrics["yield_source"],
                        "calories_per_final_unit": round(metrics["per_weight_calories"], 4)
                        if metrics["has_weight_basis"]
                        else None,
                        "protein_per_final_unit": round(metrics["per_weight_protein"], 4)
                        if metrics["has_weight_basis"]
                        else None,
                        "fiber_per_final_unit": round(as_float(metrics["per_weight_fiber"], 0.0), 4)
                        if metrics["has_weight_basis"] and pd.notna(metrics["per_weight_fiber"])
                        else None,
                    }
                )
            st.dataframe(pd.DataFrame(preview), use_container_width=True)

    section_heading(
        "Batches",
        "Batches are immutable snapshots of one real cook. Create a new batch each time the ingredient quantities, servings, or final weight differ so old logs never change.",
        level=3,
    )
    with collapsible_panel("Create batch from dish", "create_batch") as panel_open:
        if panel_open:
            st.caption(
                "Use a dish as a template, then change ingredient quantities, servings, and final weight for this one cooked batch. Logging against batches preserves history even if you later change the dish template."
            )
            if dishes.empty:
                st.info("Add at least one dish first.")
            else:
                batch_dish_name = st.selectbox(
                    "Dish template",
                    sorted(dishes["dish_name"].tolist()),
                    key="create_batch_dish_name",
                )
                template_row = dishes[dishes["dish_name"] == batch_dish_name].iloc[0]
                template_ings = dings[dings["dish_name"] == batch_dish_name].copy()
                batch_loaded_key = "create_batch_loaded_template"
                force_reload_template = st.session_state.get(batch_loaded_key) != batch_dish_name
                row_state_key, row_seq_key = initialize_batch_ingredient_rows(
                    batch_dish_name, template_ings, force_reload=force_reload_template
                )
                st.session_state[batch_loaded_key] = batch_dish_name

                c1, c2 = st.columns(2)
                with c1:
                    batch_day = st.date_input(
                        "Batch date",
                        value=date.today(),
                        format=DATE_INPUT_FORMAT,
                        key="create_batch_date",
                    )
                    batch_servings = st.number_input(
                        "Batch servings",
                        min_value=1.0,
                        step=1.0,
                        value=float(template_row["servings"])
                        if pd.notna(template_row["servings"])
                        else 1.0,
                        key=f"create_batch_servings_{batch_dish_name}",
                    )
                with c2:
                    batch_final_qty = st.number_input(
                        "Final batch quantity",
                        min_value=0.0,
                        step=1.0,
                        value=0.0,
                        key=f"create_batch_final_qty_{batch_dish_name}",
                    )
                    batch_final_unit = st.text_input(
                        "Final batch unit",
                        value="",
                        key=f"create_batch_final_unit_{batch_dish_name}",
                    )

                batch_notes = st.text_input(
                    "Notes",
                    key=f"create_batch_notes_{batch_dish_name}",
                    placeholder="Optional note like thinner than usual, extra water, etc.",
                )

                batch_ingredient_rows = []
                if is_override_dish(template_row):
                    st.info(
                        "This template uses manual override macros. The batch will snapshot total macros from the dish template and batch servings."
                    )
                else:
                    st.write("Ingredient snapshot for this batch")
                    st.caption(
                        "Change quantities, swap foods or units, remove template ingredients, and add batch-only ingredients before saving this snapshot."
                    )
                    remove_row_id = None
                    food_choices = sorted(foods["food_name"].unique().tolist())
                    batch_options = get_batch_select_options(batches)
                    batch_map = dict(batch_options)
                    batch_labels = list(batch_map.keys())
                    current_rows = list(st.session_state.get(row_state_key, []))
                    if not current_rows:
                        st.info("No ingredient rows yet. Add one below if this batch needs ingredients.")

                    for row in current_rows:
                        row_id = row["row_id"]
                        type_key_name = f"{row_state_key}_{row_id}_type"
                        food_key_name = f"{row_state_key}_{row_id}_food"
                        batch_key_name = f"{row_state_key}_{row_id}_batch"
                        unit_key_name = f"{row_state_key}_{row_id}_unit"
                        qty_key_name = f"{row_state_key}_{row_id}_qty"

                        if type_key_name not in st.session_state:
                            st.session_state[type_key_name] = (
                                "Batch" if row.get("ingredient_type") == "batch"
                                else "Dish" if row.get("ingredient_type") == "dish"
                                else "Food"
                            )
                        if food_key_name not in st.session_state:
                            st.session_state[food_key_name] = row["ingredient_food_name"]
                        if batch_key_name not in st.session_state:
                            st.session_state[batch_key_name] = next(
                                (
                                    label
                                    for label, batch_id in batch_options
                                    if batch_id == as_text(row.get("ingredient_batch_id"))
                                ),
                                batch_labels[0] if batch_labels else "",
                            )
                        if qty_key_name not in st.session_state:
                            st.session_state[qty_key_name] = float(row["ingredient_qty"])

                        source_choice = st.session_state.get(type_key_name, "Food")
                        selected_food = st.session_state.get(food_key_name, "")
                        selected_batch_label = st.session_state.get(
                            batch_key_name, batch_labels[0] if batch_labels else ""
                        )
                        selected_batch_id = batch_map.get(selected_batch_label, "")
                        if source_choice == "Food" and selected_food not in food_choices and food_choices:
                            selected_food = food_choices[0]
                            st.session_state[food_key_name] = selected_food
                        if source_choice == "Dish":
                            dish_choices = sorted([name for name in dishes["dish_name"].tolist() if name != batch_dish_name])
                            if selected_food not in dish_choices and dish_choices:
                                selected_food = dish_choices[0]
                                st.session_state[food_key_name] = selected_food
                        if source_choice == "Batch" and batch_labels and selected_batch_label not in batch_labels:
                            selected_batch_label = batch_labels[0]
                            st.session_state[batch_key_name] = selected_batch_label
                            selected_batch_id = batch_map.get(selected_batch_label, "")

                        unit_choices = get_ingredient_unit_choices(
                            source_choice.lower(),
                            foods,
                            dishes,
                            dings,
                            batches,
                            food_name=selected_food,
                            dish_name=selected_food,
                            batch_id=selected_batch_id,
                        )
                        if (
                            unit_key_name not in st.session_state
                            or st.session_state[unit_key_name] not in unit_choices
                        ):
                            preferred_unit = row["ingredient_unit"]
                            st.session_state[unit_key_name] = (
                                preferred_unit if preferred_unit in unit_choices else unit_choices[0]
                            )

                        c1, c2, c3, c4, c5, c6 = st.columns([1.4, 2.6, 2, 2, 2, 1])
                        with c1:
                            source_choice = st.selectbox(
                                "Source",
                                ["Food", "Dish", "Batch"],
                                index=["Food", "Dish", "Batch"].index(source_choice),
                                key=type_key_name,
                                label_visibility="collapsed",
                            )
                        with c2:
                            if source_choice == "Batch":
                                batch_choice_label = st.selectbox(
                                    "Ingredient batch",
                                    batch_labels if batch_labels else ["No saved batches"],
                                    index=batch_labels.index(selected_batch_label)
                                    if batch_labels and selected_batch_label in batch_labels
                                    else 0,
                                    key=batch_key_name,
                                    label_visibility="collapsed",
                                )
                                batch_choice_id = batch_map.get(batch_choice_label, "")
                                batch_choice_row = get_batch_row(batches, batch_choice_id)
                                food_choice = (
                                    as_text(batch_choice_row["dish_name"]) if batch_choice_row is not None else ""
                                )
                            elif source_choice == "Dish":
                                dish_choices = sorted([name for name in dishes["dish_name"].tolist() if name != batch_dish_name])
                                food_choice = st.selectbox(
                                    "Ingredient dish",
                                    dish_choices if dish_choices else [""],
                                    index=(
                                        dish_choices.index(selected_food)
                                        if selected_food in dish_choices
                                        else 0
                                    ),
                                    key=food_key_name,
                                    label_visibility="collapsed",
                                )
                                batch_choice_id = ""
                            else:
                                batch_choice_id = ""
                                food_choice = st.selectbox(
                                    "Ingredient food",
                                    food_choices if food_choices else [""],
                                    index=(
                                        (food_choices if food_choices else [""]).index(selected_food)
                                        if selected_food in (food_choices if food_choices else [""])
                                        else 0
                                    ),
                                    key=food_key_name,
                                    label_visibility="collapsed",
                                )
                        with c3:
                            unit_choices = get_ingredient_unit_choices(
                                source_choice.lower(),
                                foods,
                                dishes,
                                dings,
                                batches,
                                food_name=food_choice,
                                dish_name=food_choice,
                                batch_id=batch_choice_id,
                            )
                            if source_choice == "Batch":
                                batch_choice_row = get_batch_row(batches, batch_choice_id) if batch_choice_id else None
                                unit_label_map = dict(get_batch_basis_options(batch_choice_row))
                                reverse_unit_map = {label: unit for unit, label in unit_label_map.items()}
                                unit_labels = [unit_label_map[unit] for unit in unit_choices]
                                current_unit_label = unit_label_map.get(
                                    st.session_state.get(unit_key_name, unit_choices[0]),
                                    unit_labels[0],
                                )
                                unit_choice_label = st.selectbox(
                                    "Ingredient basis",
                                    unit_labels,
                                    index=unit_labels.index(current_unit_label)
                                    if current_unit_label in unit_labels
                                    else 0,
                                    key=f"{unit_key_name}_label",
                                    label_visibility="collapsed",
                                )
                                unit_choice = reverse_unit_map[unit_choice_label]
                                st.session_state[unit_key_name] = unit_choice
                            elif source_choice == "Dish":
                                unit_label_map = dict(get_dish_basis_options(food_choice, dishes, dings, foods, batches))
                                reverse_unit_map = {label: unit for unit, label in unit_label_map.items()}
                                unit_labels = [unit_label_map[unit] for unit in unit_choices]
                                current_unit_label = unit_label_map.get(
                                    st.session_state.get(unit_key_name, unit_choices[0]),
                                    unit_labels[0],
                                )
                                unit_choice_label = st.selectbox(
                                    "Ingredient basis",
                                    unit_labels,
                                    index=unit_labels.index(current_unit_label)
                                    if current_unit_label in unit_labels
                                    else 0,
                                    key=f"{unit_key_name}_label",
                                    label_visibility="collapsed",
                                )
                                unit_choice = reverse_unit_map[unit_choice_label]
                                st.session_state[unit_key_name] = unit_choice
                            else:
                                unit_choice = st.selectbox(
                                    "Ingredient unit",
                                    unit_choices,
                                    index=(
                                        unit_choices.index(st.session_state[unit_key_name])
                                        if st.session_state[unit_key_name] in unit_choices
                                        else 0
                                    ),
                                    key=unit_key_name,
                                    label_visibility="collapsed",
                                )
                        with c4:
                            qty_value = st.number_input(
                                "Qty",
                                min_value=0.0,
                                step=1.0,
                                key=qty_key_name,
                                label_visibility="collapsed",
                            )
                        with c5:
                            preview_row = {
                                "ingredient_type": source_choice.lower(),
                                "ingredient_food_name": food_choice,
                                "ingredient_unit": unit_choice,
                                "ingredient_qty": qty_value,
                                "ingredient_batch_id": batch_choice_id,
                            }
                            est_c, est_p, est_f, err_text = estimate_ingredient_row(
                                preview_row, foods, dishes, dings, batches
                            )
                            if err_text:
                                st.caption(err_text)
                            else:
                                st.caption(
                                    f"{est_c:.0f} kcal | {est_p:.1f}g protein | {format_nutrient_value('fiber', est_f, with_unit=True)} fiber"
                                )
                        with c6:
                            if st.button("Remove", key=f"{row_state_key}_{row_id}_remove"):
                                remove_row_id = row_id

                        row["ingredient_type"] = source_choice.lower()
                        row["ingredient_food_name"] = food_choice
                        row["ingredient_unit"] = unit_choice
                        row["ingredient_qty"] = qty_value
                        row["ingredient_batch_id"] = batch_choice_id
                        if qty_value > 0 and food_choice and unit_choice:
                            batch_ingredient_rows.append(
                                {
                                    "ingredient_type": source_choice.lower(),
                                    "ingredient_food_name": food_choice,
                                    "ingredient_unit": unit_choice,
                                    "ingredient_qty": qty_value,
                                    "ingredient_batch_id": batch_choice_id,
                                }
                            )

                    st.session_state[row_state_key] = current_rows
                    add_col, _ = st.columns([1, 4])
                    with add_col:
                        if st.button("Add ingredient row", key=f"{row_state_key}_add"):
                            add_batch_ingredient_row(batch_dish_name, foods)
                            st.rerun()
                    if remove_row_id is not None:
                        remove_batch_ingredient_row(batch_dish_name, remove_row_id)
                        st.rerun()

                preview_metrics = None
                if is_override_dish(template_row):
                    nutrient_totals = {}
                    missing_nutrients = []
                    for spec in TRACKED_NUTRIENTS:
                        override_value = template_row.get(spec["dish_override_col"])
                        if pd.isna(override_value):
                            nutrient_totals[spec["key"]] = None
                            missing_nutrients.append(spec["key"])
                        else:
                            nutrient_totals[spec["key"]] = as_float(override_value, 0.0) * batch_servings
                    preview_metrics = build_portion_metrics(
                        batch_servings,
                        nutrient_totals,
                        batch_final_qty if batch_final_qty > 0 else 0.0,
                        batch_final_unit.strip(),
                        missing_nutrients=missing_nutrients,
                    )
                elif batch_ingredient_rows:
                    batch_ingredients_df = pd.DataFrame(batch_ingredient_rows)
                    nutrient_totals, missing_nutrients = compute_ingredient_totals(
                        batch_ingredients_df,
                        foods,
                        dishes,
                        dings,
                        batches,
                        "ingredient_qty",
                    )
                    auto_qty, auto_unit = get_auto_yield_from_ingredients(
                        batch_ingredients_df, "ingredient_qty"
                    )
                    preview_metrics = build_portion_metrics(
                        batch_servings,
                        nutrient_totals,
                        batch_final_qty if batch_final_qty > 0 else 0.0,
                        batch_final_unit.strip(),
                        auto_qty,
                        auto_unit,
                        missing_nutrients,
                    )

                if preview_metrics is not None:
                    p1, p2, p3, p4 = st.columns(4)
                    p1.metric("Batch calories", f"{preview_metrics['total_calories']:.0f}")
                    p2.metric("Batch protein (g)", f"{preview_metrics['total_protein']:.1f}")
                    p3.metric("Batch fiber (g)", format_nutrient_value("fiber", preview_metrics["total_fiber"]))
                    source_label = preview_metrics["yield_source"] or "none"
                    p4.metric("Final qty source", source_label)
                    st.caption(
                        f"Per serving: {preview_metrics['per_serving_calories']:.1f} kcal, "
                        f"{preview_metrics['per_serving_protein']:.2f}g protein, "
                        f"{format_nutrient_value('fiber', preview_metrics['per_serving_fiber'], with_unit=True)} fiber."
                    )
                    if preview_metrics["has_weight_basis"]:
                        st.caption(
                            f"Per {preview_metrics['final_unit']}: "
                            f"{preview_metrics['per_weight_calories']:.3f} kcal, "
                            f"{preview_metrics['per_weight_protein']:.4f}g protein, "
                            f"{format_nutrient_value('fiber', preview_metrics['per_weight_fiber'], with_unit=True)} fiber."
                        )

                c1, c2 = st.columns(2)
                with c1:
                    save_batch = st.button("Save batch", key="save_batch")
                with c2:
                    st.button(
                        "Clear batch form",
                        key="clear_create_batch",
                        on_click=clear_create_batch_form,
                    )

                if save_batch:
                    batch_final_unit = batch_final_unit.strip()
                    if batch_final_qty > 0 and not batch_final_unit:
                        st.error("Final batch unit is required when final batch quantity is set.")
                    elif not is_override_dish(template_row) and not batch_ingredient_rows:
                        st.error("This batch needs at least one ingredient quantity greater than 0.")
                    else:
                        batch_id = make_batch_id(batch_day)
                        if preview_metrics is None:
                            preview_metrics = build_portion_metrics(
                                batch_servings,
                                {spec["key"]: 0.0 for spec in TRACKED_NUTRIENTS},
                                0.0,
                                "",
                            )

                        batches.loc[len(batches)] = [
                            batch_id,
                            batch_dish_name,
                            batch_day.isoformat(),
                            batch_servings,
                            preview_metrics["final_qty"] if preview_metrics["has_weight_basis"] else None,
                            preview_metrics["final_unit"] if preview_metrics["has_weight_basis"] else None,
                            preview_metrics["yield_source"],
                            preview_metrics["total_calories"],
                            preview_metrics["total_protein"],
                            preview_metrics["total_fiber"],
                            batch_notes.strip(),
                        ]

                        if batch_ingredient_rows:
                            batch_ingredients_to_save = pd.DataFrame(batch_ingredient_rows)
                            batch_ingredients_to_save.insert(0, "batch_id", batch_id)
                            batch_ings = pd.concat(
                                [batch_ings, batch_ingredients_to_save[BATCH_INGREDIENT_COLUMNS]],
                                ignore_index=True,
                            )
                            save_df(batch_ings, BATCH_ING_CSV)

                        save_df(batches, BATCHES_CSV)
                        clear_create_batch_form()
                        st.session_state.master_data_message = "Batch saved."
                        st.rerun()

    with st.expander("View batches table", expanded=False):
        st.caption(
            "Batches are historical snapshots. Their totals, servings, and final weight stay fixed even if you later edit the dish template."
        )
        if batches.empty:
            st.info("No batches yet.")
        else:
            preview = batches.copy()
            preview["batch_date"] = format_date_series(preview["batch_date"])
            preview["batch_label"] = preview.apply(batch_key, axis=1)
            preview["calories_per_serving"] = preview.apply(
                lambda row: as_float(row["total_calories"], 0.0)
                / max(as_float(row["servings"], 1.0), 1.0),
                axis=1,
            )
            preview["protein_per_serving"] = preview.apply(
                lambda row: as_float(row["total_protein"], 0.0)
                / max(as_float(row["servings"], 1.0), 1.0),
                axis=1,
            )
            preview["fiber_per_serving"] = preview.apply(
                lambda row: as_float(row["total_fiber"], 0.0)
                / max(as_float(row["servings"], 1.0), 1.0)
                if pd.notna(row["total_fiber"])
                else None,
                axis=1,
            )
            preview["calories_per_final_unit"] = preview.apply(
                lambda row: as_float(row["total_calories"], 0.0) / as_float(row["final_qty"], 0.0)
                if as_float(row["final_qty"], 0.0) > 0 and as_text(row["final_unit"])
                else None,
                axis=1,
            )
            preview["protein_per_final_unit"] = preview.apply(
                lambda row: as_float(row["total_protein"], 0.0) / as_float(row["final_qty"], 0.0)
                if as_float(row["final_qty"], 0.0) > 0 and as_text(row["final_unit"])
                else None,
                axis=1,
            )
            preview["fiber_per_final_unit"] = preview.apply(
                lambda row: as_float(row["total_fiber"], 0.0) / as_float(row["final_qty"], 0.0)
                if pd.notna(row["total_fiber"])
                and as_float(row["final_qty"], 0.0) > 0
                and as_text(row["final_unit"])
                else None,
                axis=1,
            )
            st.dataframe(
                preview[
                    [
                        "batch_label",
                        "dish_name",
                        "batch_date",
                        "servings",
                        "final_qty",
                        "final_unit",
                        "yield_source",
                        "total_calories",
                        "total_protein",
                        "total_fiber",
                        "calories_per_serving",
                        "protein_per_serving",
                        "fiber_per_serving",
                        "calories_per_final_unit",
                        "protein_per_final_unit",
                        "fiber_per_final_unit",
                        "notes",
                    ]
                ],
                use_container_width=True,
            )

            bsel = st.selectbox(
                "Preview ingredients for batch",
                batches.apply(batch_key, axis=1).tolist(),
                key="view_batch_ingredients_sel",
            )
            batch_row = batches[batches.apply(batch_key, axis=1) == bsel].iloc[0]
            batch_ing_view = batch_ings[batch_ings["batch_id"] == batch_row["batch_id"]].copy()
            if batch_ing_view.empty:
                st.info("No batch ingredient snapshot stored for this batch.")
            else:
                batch_ing_view["ingredient_source"] = batch_ing_view.apply(
                    lambda row: ingredient_ref_label(row, batches), axis=1
                )
                st.dataframe(
                    batch_ing_view[
                        [
                            "ingredient_source",
                            "ingredient_unit",
                            "ingredient_qty",
                        ]
                    ],
                    hide_index=True,
                    use_container_width=True,
                )

    section_heading(
        "Edit a batch",
        "Update a saved batch snapshot, including servings, final weight, notes, and the saved ingredient snapshot. Batch log entries will be recalculated from the edited batch.",
    )
    if not batches.empty:
        with st.expander("Edit a batch", expanded=False):
            bedit = st.selectbox(
                "Select batch to edit",
                batches.apply(batch_key, axis=1).tolist(),
                key="edit_batch_sel",
            )
            brow = batches[batches.apply(batch_key, axis=1) == bedit].iloc[0]
            batch_id = brow["batch_id"]
            batch_dish_name = brow["dish_name"]
            template_match = dishes[dishes["dish_name"] == batch_dish_name]
            template_row = template_match.iloc[0] if not template_match.empty else None
            existing_batch_ings = batch_ings[batch_ings["batch_id"] == batch_id].copy()
            existing_batch_ings = existing_batch_ings.rename(
                columns={"ingredient_qty": "ingredient_qty_per_serving"}
            )
            batch_edit_state_key = f"edit_batch_{batch_id}"
            batch_edit_loaded_key = "edit_batch_loaded_id"
            force_reload_batch = st.session_state.get(batch_edit_loaded_key) != batch_id
            row_state_key, row_seq_key = initialize_batch_ingredient_rows(
                batch_edit_state_key,
                existing_batch_ings,
                force_reload=force_reload_batch,
            )
            st.session_state[batch_edit_loaded_key] = batch_id

            c0, c1, c2 = st.columns(3)
            with c0:
                edit_batch_date = st.date_input(
                    "Batch date",
                    value=date.fromisoformat(as_text(brow["batch_date"]))
                    if as_text(brow["batch_date"])
                    else date.today(),
                    format=DATE_INPUT_FORMAT,
                    key=f"edit_batch_date_{batch_id}",
                )
            with c1:
                edit_servings = st.number_input(
                    "Batch servings",
                    min_value=1.0,
                    step=1.0,
                    value=float(brow["servings"]) if pd.notna(brow["servings"]) else 1.0,
                    key=f"edit_batch_servings_{batch_id}",
                )
            with c2:
                edit_final_qty = st.number_input(
                    "Final batch quantity",
                    min_value=0.0,
                    step=1.0,
                    value=as_float(brow["final_qty"], 0.0),
                    key=f"edit_batch_final_qty_{batch_id}",
                )
            c1, c2 = st.columns(2)
            with c1:
                edit_final_unit = st.text_input(
                    "Final batch unit",
                    value=as_text(brow["final_unit"]),
                    key=f"edit_batch_final_unit_{batch_id}",
                )
            edit_notes = st.text_input(
                "Notes",
                value=as_text(brow["notes"]),
                key=f"edit_batch_notes_{batch_id}",
                placeholder="Optional note like thinner than usual, extra water, etc.",
            )

            edit_batch_ingredient_rows = []
            if template_row is not None and is_override_dish(template_row) and existing_batch_ings.empty:
                st.info(
                    "This batch is tied to an override dish template, so editing servings/final weight updates totals from the override values."
                )
            else:
                st.write("Batch ingredient snapshot")
                st.caption(
                    "Change quantities, swap foods or units, remove ingredients, and add new rows for this saved batch snapshot."
                )
                remove_row_id = None
                food_choices = sorted(foods["food_name"].unique().tolist())
                batch_options = get_batch_select_options(batches)
                batch_map = dict(batch_options)
                batch_labels = list(batch_map.keys())
                current_rows = list(st.session_state.get(row_state_key, []))
                if not current_rows:
                    st.info("No ingredient rows yet. Add one below if this batch needs ingredients.")

                for row in current_rows:
                    row_id = row["row_id"]
                    type_key_name = f"{row_state_key}_{row_id}_type"
                    food_key_name = f"{row_state_key}_{row_id}_food"
                    batch_key_name = f"{row_state_key}_{row_id}_batch"
                    unit_key_name = f"{row_state_key}_{row_id}_unit"
                    qty_key_name = f"{row_state_key}_{row_id}_qty"

                    if type_key_name not in st.session_state:
                        st.session_state[type_key_name] = (
                            "Batch" if row.get("ingredient_type") == "batch"
                            else "Dish" if row.get("ingredient_type") == "dish"
                            else "Food"
                        )
                    if food_key_name not in st.session_state:
                        st.session_state[food_key_name] = row["ingredient_food_name"]
                    if batch_key_name not in st.session_state:
                        st.session_state[batch_key_name] = next(
                            (
                                label
                                for label, batch_id_option in batch_options
                                if batch_id_option == as_text(row.get("ingredient_batch_id"))
                            ),
                            batch_labels[0] if batch_labels else "",
                        )
                    if qty_key_name not in st.session_state:
                        st.session_state[qty_key_name] = float(row["ingredient_qty"])

                    source_choice = st.session_state.get(type_key_name, "Food")
                    selected_food = st.session_state.get(food_key_name, "")
                    selected_batch_label = st.session_state.get(
                        batch_key_name, batch_labels[0] if batch_labels else ""
                    )
                    selected_batch_id = batch_map.get(selected_batch_label, "")
                    if source_choice == "Food" and selected_food not in food_choices and food_choices:
                        selected_food = food_choices[0]
                        st.session_state[food_key_name] = selected_food
                    if source_choice == "Dish":
                        dish_choices = sorted(
                            [name for name in dishes["dish_name"].tolist() if name != batch_dish_name]
                        )
                        if selected_food not in dish_choices and dish_choices:
                            selected_food = dish_choices[0]
                            st.session_state[food_key_name] = selected_food
                    if source_choice == "Batch" and batch_labels and selected_batch_label not in batch_labels:
                        selected_batch_label = batch_labels[0]
                        st.session_state[batch_key_name] = selected_batch_label
                        selected_batch_id = batch_map.get(selected_batch_label, "")

                    unit_choices = get_ingredient_unit_choices(
                        source_choice.lower(),
                        foods,
                        dishes,
                        dings,
                        batches,
                        food_name=selected_food,
                        dish_name=selected_food,
                        batch_id=selected_batch_id,
                    )
                    if (
                        unit_key_name not in st.session_state
                        or st.session_state[unit_key_name] not in unit_choices
                    ):
                        preferred_unit = row["ingredient_unit"]
                        st.session_state[unit_key_name] = (
                            preferred_unit if preferred_unit in unit_choices else unit_choices[0]
                        )

                    c1, c2, c3, c4, c5, c6 = st.columns([1.4, 2.6, 2, 2, 2, 1])
                    with c1:
                        source_choice = st.selectbox(
                            "Source",
                            ["Food", "Dish", "Batch"],
                            index=["Food", "Dish", "Batch"].index(source_choice),
                            key=type_key_name,
                            label_visibility="collapsed",
                        )
                    with c2:
                        if source_choice == "Batch":
                            batch_choice_label = st.selectbox(
                                "Ingredient batch",
                                batch_labels if batch_labels else ["No saved batches"],
                                index=batch_labels.index(selected_batch_label)
                                if batch_labels and selected_batch_label in batch_labels
                                else 0,
                                key=batch_key_name,
                                label_visibility="collapsed",
                            )
                            batch_choice_id = batch_map.get(batch_choice_label, "")
                            batch_choice_row = get_batch_row(batches, batch_choice_id)
                            food_choice = (
                                as_text(batch_choice_row["dish_name"]) if batch_choice_row is not None else ""
                            )
                        elif source_choice == "Dish":
                            dish_choices = sorted(
                                [name for name in dishes["dish_name"].tolist() if name != batch_dish_name]
                            )
                            food_choice = st.selectbox(
                                "Ingredient dish",
                                dish_choices if dish_choices else [""],
                                index=dish_choices.index(selected_food)
                                if selected_food in dish_choices
                                else 0,
                                key=food_key_name,
                                label_visibility="collapsed",
                            )
                            batch_choice_id = ""
                        else:
                            batch_choice_id = ""
                            food_choice = st.selectbox(
                                "Ingredient food",
                                food_choices if food_choices else [""],
                                index=(
                                    (food_choices if food_choices else [""]).index(selected_food)
                                    if selected_food in (food_choices if food_choices else [""])
                                    else 0
                                ),
                                key=food_key_name,
                                label_visibility="collapsed",
                            )
                    with c3:
                        unit_choices = get_ingredient_unit_choices(
                            source_choice.lower(),
                            foods,
                            dishes,
                            dings,
                            batches,
                            food_name=food_choice,
                            dish_name=food_choice,
                            batch_id=batch_choice_id,
                        )
                        if source_choice == "Batch":
                            batch_choice_row = get_batch_row(batches, batch_choice_id) if batch_choice_id else None
                            unit_label_map = dict(get_batch_basis_options(batch_choice_row))
                            reverse_unit_map = {label: unit for unit, label in unit_label_map.items()}
                            unit_labels = [unit_label_map[unit] for unit in unit_choices]
                            current_unit_label = unit_label_map.get(
                                st.session_state.get(unit_key_name, unit_choices[0]),
                                unit_labels[0],
                            )
                            unit_choice_label = st.selectbox(
                                "Ingredient basis",
                                unit_labels,
                                index=unit_labels.index(current_unit_label)
                                if current_unit_label in unit_labels
                                else 0,
                                key=f"{unit_key_name}_label",
                                label_visibility="collapsed",
                            )
                            unit_choice = reverse_unit_map[unit_choice_label]
                            st.session_state[unit_key_name] = unit_choice
                        elif source_choice == "Dish":
                            unit_label_map = dict(
                                get_dish_basis_options(food_choice, dishes, dings, foods, batches)
                            )
                            reverse_unit_map = {label: unit for unit, label in unit_label_map.items()}
                            unit_labels = [unit_label_map[unit] for unit in unit_choices]
                            current_unit_label = unit_label_map.get(
                                st.session_state.get(unit_key_name, unit_choices[0]),
                                unit_labels[0],
                            )
                            unit_choice_label = st.selectbox(
                                "Ingredient basis",
                                unit_labels,
                                index=unit_labels.index(current_unit_label)
                                if current_unit_label in unit_labels
                                else 0,
                                key=f"{unit_key_name}_label",
                                label_visibility="collapsed",
                            )
                            unit_choice = reverse_unit_map[unit_choice_label]
                            st.session_state[unit_key_name] = unit_choice
                        else:
                            unit_choice = st.selectbox(
                                "Ingredient unit",
                                unit_choices,
                                index=(
                                    unit_choices.index(st.session_state[unit_key_name])
                                    if st.session_state[unit_key_name] in unit_choices
                                    else 0
                                ),
                                key=unit_key_name,
                                label_visibility="collapsed",
                            )
                    with c4:
                        qty_value = st.number_input(
                            "Qty",
                            min_value=0.0,
                            step=1.0,
                            key=qty_key_name,
                            label_visibility="collapsed",
                        )
                    with c5:
                        preview_row = {
                            "ingredient_type": source_choice.lower(),
                            "ingredient_food_name": food_choice,
                            "ingredient_unit": unit_choice,
                            "ingredient_qty": qty_value,
                            "ingredient_batch_id": batch_choice_id,
                        }
                        est_c, est_p, est_f, err_text = estimate_ingredient_row(
                            preview_row, foods, dishes, dings, batches
                        )
                        if err_text:
                            st.caption(err_text)
                        else:
                            st.caption(
                                f"{est_c:.0f} kcal | {est_p:.1f}g protein | {format_nutrient_value('fiber', est_f, with_unit=True)} fiber"
                            )
                    with c6:
                        if st.button("Remove", key=f"{row_state_key}_{row_id}_remove"):
                            remove_row_id = row_id

                    row["ingredient_type"] = source_choice.lower()
                    row["ingredient_food_name"] = food_choice
                    row["ingredient_unit"] = unit_choice
                    row["ingredient_qty"] = qty_value
                    row["ingredient_batch_id"] = batch_choice_id
                    if qty_value > 0 and food_choice and unit_choice:
                        edit_batch_ingredient_rows.append(
                            {
                                "ingredient_type": source_choice.lower(),
                                "ingredient_food_name": food_choice,
                                "ingredient_unit": unit_choice,
                                "ingredient_qty": qty_value,
                                "ingredient_batch_id": batch_choice_id,
                            }
                        )

                st.session_state[row_state_key] = current_rows
                add_col, _ = st.columns([1, 4])
                with add_col:
                    if st.button("Add ingredient row", key=f"{row_state_key}_add"):
                        add_batch_ingredient_row(batch_edit_state_key, foods)
                        st.rerun()
                if remove_row_id is not None:
                    remove_batch_ingredient_row(batch_edit_state_key, remove_row_id)
                    st.rerun()

            edit_preview_metrics = None
            if template_row is not None and is_override_dish(template_row) and not edit_batch_ingredient_rows:
                nutrient_totals = {}
                missing_nutrients = []
                for spec in TRACKED_NUTRIENTS:
                    override_value = template_row.get(spec["dish_override_col"])
                    if pd.isna(override_value):
                        nutrient_totals[spec["key"]] = None
                        missing_nutrients.append(spec["key"])
                    else:
                        nutrient_totals[spec["key"]] = as_float(override_value, 0.0) * edit_servings
                edit_preview_metrics = build_portion_metrics(
                    edit_servings,
                    nutrient_totals,
                    edit_final_qty if edit_final_qty > 0 else 0.0,
                    edit_final_unit.strip(),
                    missing_nutrients=missing_nutrients,
                )
            elif edit_batch_ingredient_rows:
                edit_batch_ingredients_df = pd.DataFrame(edit_batch_ingredient_rows)
                nutrient_totals, missing_nutrients = compute_ingredient_totals(
                    edit_batch_ingredients_df,
                    foods,
                    dishes,
                    dings,
                    batches,
                    "ingredient_qty",
                )
                auto_qty, auto_unit = get_auto_yield_from_ingredients(
                    edit_batch_ingredients_df, "ingredient_qty"
                )
                edit_preview_metrics = build_portion_metrics(
                    edit_servings,
                    nutrient_totals,
                    edit_final_qty if edit_final_qty > 0 else 0.0,
                    edit_final_unit.strip(),
                    auto_qty,
                    auto_unit,
                    missing_nutrients,
                )

            if edit_preview_metrics is not None:
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Batch calories", f"{edit_preview_metrics['total_calories']:.0f}")
                p2.metric("Batch protein (g)", f"{edit_preview_metrics['total_protein']:.1f}")
                p3.metric("Batch fiber (g)", format_nutrient_value("fiber", edit_preview_metrics["total_fiber"]))
                p4.metric("Final qty source", edit_preview_metrics["yield_source"] or "none")
                st.caption(
                    f"Per serving: {edit_preview_metrics['per_serving_calories']:.1f} kcal, "
                    f"{edit_preview_metrics['per_serving_protein']:.2f}g protein, "
                    f"{format_nutrient_value('fiber', edit_preview_metrics['per_serving_fiber'], with_unit=True)} fiber."
                )
                if edit_preview_metrics["has_weight_basis"]:
                    st.caption(
                        f"Per {edit_preview_metrics['final_unit']}: "
                        f"{edit_preview_metrics['per_weight_calories']:.3f} kcal, "
                        f"{edit_preview_metrics['per_weight_protein']:.4f}g protein, "
                        f"{format_nutrient_value('fiber', edit_preview_metrics['per_weight_fiber'], with_unit=True)} fiber."
                    )

            if st.button("Save batch changes", key="save_batch_edit"):
                edit_final_unit = edit_final_unit.strip()
                if edit_final_qty > 0 and not edit_final_unit:
                    st.error("Final batch unit is required when final batch quantity is set.")
                elif template_row is None and not edit_batch_ingredient_rows:
                    st.error("This batch needs at least one saved ingredient row because its template is missing.")
                elif template_row is not None and not is_override_dish(template_row) and not edit_batch_ingredient_rows:
                    st.error("This batch needs at least one ingredient quantity greater than 0.")
                else:
                    if edit_preview_metrics is None:
                        edit_preview_metrics = build_portion_metrics(
                            edit_servings,
                            {spec["key"]: 0.0 for spec in TRACKED_NUTRIENTS},
                            0.0,
                            "",
                        )

                    new_batch_id = (
                        batch_id
                        if as_text(brow["batch_date"]) == edit_batch_date.isoformat()
                        else make_batch_id(edit_batch_date)
                    )
                    batch_index = brow.name
                    batches.loc[batch_index, "batch_id"] = new_batch_id
                    batches.loc[batch_index, "batch_date"] = edit_batch_date.isoformat()
                    batches.loc[batch_index, "servings"] = edit_servings
                    batches.loc[batch_index, "final_qty"] = (
                        edit_preview_metrics["final_qty"] if edit_preview_metrics["has_weight_basis"] else None
                    )
                    batches.loc[batch_index, "final_unit"] = (
                        edit_preview_metrics["final_unit"] if edit_preview_metrics["has_weight_basis"] else None
                    )
                    batches.loc[batch_index, "yield_source"] = edit_preview_metrics["yield_source"]
                    batches.loc[batch_index, "total_calories"] = edit_preview_metrics["total_calories"]
                    batches.loc[batch_index, "total_protein"] = edit_preview_metrics["total_protein"]
                    batches.loc[batch_index, "total_fiber"] = edit_preview_metrics["total_fiber"]
                    batches.loc[batch_index, "notes"] = edit_notes.strip()

                    logs.loc[
                        (logs["type"] == "batch") & (logs["batch_id"] == batch_id),
                        "batch_id",
                    ] = new_batch_id
                    if new_batch_id != batch_id:
                        dings.loc[
                            dings["ingredient_batch_id"] == batch_id,
                            "ingredient_batch_id",
                        ] = new_batch_id
                        batch_ings.loc[
                            batch_ings["ingredient_batch_id"] == batch_id,
                            "ingredient_batch_id",
                        ] = new_batch_id
                    batch_ings = batch_ings[batch_ings["batch_id"] != batch_id]
                    if edit_batch_ingredient_rows:
                        edit_batch_ingredients_to_save = pd.DataFrame(edit_batch_ingredient_rows)
                        edit_batch_ingredients_to_save.insert(0, "batch_id", new_batch_id)
                        batch_ings = pd.concat(
                            [batch_ings, edit_batch_ingredients_to_save[BATCH_INGREDIENT_COLUMNS]],
                            ignore_index=True,
                        )

                    updated_batch_row = get_batch_row(batches, new_batch_id)
                    logs = recalc_logs_for_batch(logs, updated_batch_row)
                    batches, logs = recalc_recipe_dependents(
                        logs,
                        dishes,
                        dings,
                        foods,
                        batches,
                        batch_ings,
                        seed_batch_ids=[new_batch_id],
                    )

                    save_df(batches, BATCHES_CSV)
                    save_df(batch_ings, BATCH_ING_CSV)
                    save_df(dings, DISH_ING_CSV)
                    save_df(logs, LOGS_CSV)
                    st.success("Batch updated.")
                    st.rerun()

    section_heading(
        "Delete a batch",
        "Remove a batch snapshot and any logs created from that batch. This does not delete the underlying dish template.",
    )
    if not batches.empty:
        with st.expander("Delete a batch", expanded=False):
            bdel = st.selectbox(
                "Select batch to delete",
                batches.apply(batch_key, axis=1).tolist(),
                key="delete_batch_sel",
            )
            brow = batches[batches.apply(batch_key, axis=1) == bdel].iloc[0]
            affected_batch_logs = logs[
                (logs["type"] == "batch") & (logs["batch_id"] == brow["batch_id"])
            ]
            affected_batch_ings = batch_ings[batch_ings["batch_id"] == brow["batch_id"]]
            dependent_dish_ings = dings[
                dings["ingredient_batch_id"] == brow["batch_id"]
            ]
            dependent_batch_ings = batch_ings[
                (batch_ings["ingredient_batch_id"] == brow["batch_id"])
                & (batch_ings["batch_id"] != brow["batch_id"])
            ]
            st.warning(
                f"Deleting this batch will remove {len(affected_batch_logs)} batch log entries and {len(affected_batch_ings)} batch ingredient snapshot rows."
            )
            if not dependent_dish_ings.empty or not dependent_batch_ings.empty:
                st.error(
                    f"This batch is still used as an ingredient in {len(dependent_dish_ings)} dish template row(s) "
                    f"and {len(dependent_batch_ings)} saved batch snapshot row(s). Remove those references first."
                )
            confirm_batch = st.text_input(
                "Type the exact batch label to confirm",
                key="confirm_batch_delete",
            )
            if st.button("Delete batch", key="delete_batch_button"):
                if not dependent_dish_ings.empty or not dependent_batch_ings.empty:
                    st.error("This batch is still referenced by dish or batch ingredients.")
                elif confirm_batch.strip() == bdel:
                    logs = logs.drop(affected_batch_logs.index)
                    batches = batches[batches["batch_id"] != brow["batch_id"]]
                    batch_ings = batch_ings[batch_ings["batch_id"] != brow["batch_id"]]
                    save_df(logs, LOGS_CSV)
                    save_df(batches, BATCHES_CSV)
                    save_df(batch_ings, BATCH_ING_CSV)
                    st.success("Batch deleted.")
                    st.rerun()
                else:
                    st.error("Confirmation did not match. No delete.")

    section_heading(
        "Delete a dish",
        "Remove a dish template, its ingredients, and any direct dish-template logs. Existing historical batches stay intact. Type the exact dish name before deleting.",
    )
    if not dishes.empty:
        with st.expander("Delete a dish", expanded=False):
            ddel = st.selectbox(
                "Select dish to delete",
                sorted(dishes["dish_name"].tolist()),
                key="delete_dish_sel",
            )

            affected_logs = logs[(logs["type"] == "dish") & (logs["name"] == ddel)]
            affected_ings = dings[dings["dish_name"] == ddel]
            affected_batches = batches[batches["dish_name"] == ddel]
            st.warning(
                f"Deleting **{ddel}** will remove {len(affected_logs)} direct dish log entries and {len(affected_ings)} template ingredients. {len(affected_batches)} historical batches will be kept."
            )

            confirm_dish = st.text_input(
                "Type the exact dish name to confirm", key="confirm_dish"
            )
            if st.button("Delete dish", key="delete_dish_button"):
                if confirm_dish.strip() == ddel:
                    logs = logs.drop(affected_logs.index)
                    dishes = dishes[dishes["dish_name"] != ddel]
                    dings = dings.drop(affected_ings.index)

                    save_df(dishes, DISHES_CSV)
                    save_df(dings, DISH_ING_CSV)
                    save_df(logs, LOGS_CSV)
                    clear_session_keys(
                        [
                            "delete_dish_sel",
                            "confirm_dish",
                            "edit_dish_sel_unique",
                            "edit_ing_dish_sel_unique",
                            "add_ing_dish",
                            "log_dish_name",
                        ]
                    )
                    st.session_state.master_data_message = f"Deleted dish {ddel}"
                    st.rerun()
            else:
                st.error("Confirmation did not match. No delete.")

    section_heading(
        "Goals",
        "Goals carry forward from their saved date until you change them again. Use a single-date save to start a new target from that day, or bulk goals to prefill a date range. Past-date edits require the Day View toggle.",
        level=3,
    )

    with st.expander("Set or update goal for a single date"):
        st.caption(
            "Set new targets starting on one day. Example: save 1800 kcal and 120g protein on May 3, and those targets stay active until a later goal row changes them."
        )
        day = st.date_input(
            "Date for goal",
            value=date.today(),
            format=DATE_INPUT_FORMAT,
            key="goal_date",
        )
        cal_goal = st.number_input(
            "Calorie goal", min_value=0.0, step=50.0, value=1800.0, key="cal_goal2"
        )
        prot_goal = st.number_input(
            "Protein goal", min_value=0.0, step=5.0, value=120.0, key="prot_goal2"
        )
        if st.button("Save goal (single date)", key="save_single_goal"):
            if day < date.today() and not st.session_state.allow_edit_past:
                st.error("Editing past goals is disabled. Enable it in Day View.")
            else:
                goals = upsert_goal(goals, day, cal_goal, prot_goal)
                save_df(goals, GOALS_CSV)
                clear_single_goal_form()
                st.session_state.master_data_message = "Goal saved."
                st.rerun()

    with st.expander("Bulk set goals for a date range"):
        st.caption(
            "Apply the same goal across many dates. Example: set every weekday in a cut phase to 1700 kcal and 130g protein."
        )
        r1, r2 = st.columns(2)
        with r1:
            start_day = st.date_input(
                "Start date",
                value=date.today(),
                format=DATE_INPUT_FORMAT,
                key="bulk_start",
            )
        with r2:
            end_day = st.date_input(
                "End date (inclusive)",
                value=date.today(),
                format=DATE_INPUT_FORMAT,
                key="bulk_end",
            )
        bcal = st.number_input(
            "Calorie goal (range)",
            min_value=0.0,
            step=50.0,
            value=1800.0,
            key="bulk_cal",
        )
        bprot = st.number_input(
            "Protein goal (range)",
            min_value=0.0,
            step=5.0,
            value=120.0,
            key="bulk_prot",
        )

        if st.button("Apply to range", key="apply_goal_range"):
            if end_day < start_day:
                st.error("End date must be on or after start date.")
            elif (
                end_day < date.today() or start_day < date.today()
            ) and not st.session_state.allow_edit_past:
                st.error("Editing past goals is disabled. Enable it in Day View.")
            else:
                cur = start_day
                while cur <= end_day:
                    goals = upsert_goal(goals, cur, bcal, bprot)
                    cur += timedelta(days=1)
                save_df(goals, GOALS_CSV)
                clear_bulk_goal_form()
                st.session_state.master_data_message = "Goals applied to range."
                st.rerun()

    with st.expander("View all goals", expanded=False):
        st.caption(
            "Read-only view of saved goal rows. Use Clear goals below if old test goals are cluttering this table."
        )
        goals_view = goals.sort_values("date").copy()
        goals_view["date"] = format_date_series(goals_view["date"])
        st.dataframe(goals_view, use_container_width=True)

    with st.expander("Clear goals", expanded=False):
        st.caption(
            "Deletes only goal rows. Foods, dishes, ingredients, and logs stay intact."
        )
        st.warning(
            f"This will delete all {len(goals)} saved goal rows. Food, dish, and log data will stay untouched."
        )
        confirm_clear_goals = st.text_input(
            "Type CLEAR GOALS to confirm",
            key="confirm_clear_goals",
        )
        if st.button("Clear all goals", key="clear_goals_button"):
            if confirm_clear_goals.strip() == "CLEAR GOALS":
                goals = empty_df(GOAL_COLUMNS)
                save_df(goals, GOALS_CSV)
                clear_session_keys(
                    [
                        "confirm_clear_goals",
                        "gcal_new",
                        "gprot_new",
                        "gcal_edit",
                        "gprot_edit",
                        "cal_goal2",
                        "prot_goal2",
                        "bulk_cal",
                        "bulk_prot",
                    ]
                )
                st.session_state.master_data_message = "All goals cleared."
                st.rerun()
            else:
                st.error("Confirmation did not match. Goals were not cleared.")

    section_heading(
        "Danger zone",
        "Use only when you want a fresh local database. Reset all data clears foods, dishes, ingredients, goals, and logs from the CSVs while keeping the files.",
        level=3,
    )
    with st.expander("Reset all data", expanded=False):
        st.warning(
            "This removes every food, dish, ingredient, goal, and log row from the local CSV files. The files and headers stay in place."
        )
        st.write(
            f"Current rows: {len(foods)} foods, {len(dishes)} dishes, {len(dings)} dish ingredients, "
            f"{len(batches)} batches, {len(batch_ings)} batch ingredients, {len(goals)} goals, {len(logs)} logs."
        )
        confirm_reset_all = st.text_input(
            "Type RESET ALL DATA to confirm",
            key="confirm_reset_all_data",
        )
        if st.button("Reset all data", key="reset_all_data_button"):
            if confirm_reset_all.strip() == "RESET ALL DATA":
                reset_all_data()
                clear_session_keys(
                    [
                        "confirm_reset_all_data",
                        "confirm_clear_goals",
                        "confirm_food",
                        "confirm_dish",
                        "delete_day_log_sel",
                        "confirm_delete_day_log",
                    ]
                )
                st.session_state.master_data_message = "All local data reset."
                st.rerun()
            else:
                st.error("Confirmation did not match. Data was not reset.")
