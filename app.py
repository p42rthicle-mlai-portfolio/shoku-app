# Shoku (Food Tracker) (Streamlit v0)
# MVP: meals, units, foods+dishes, per-day goal locking, calendar view, mandatory list, dashboard

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import io
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

FOOD_COLUMNS = [
    "food_name",
    "unit",
    "base_qty",
    "calories_base",
    "protein_base",
    "cal_per_unit",
    "protein_per_unit",
]
DISH_COLUMNS = [
    "dish_name",
    "cal_override",
    "protein_override",
    "servings",
    "yield_qty",
    "yield_unit",
]
DISH_INGREDIENT_COLUMNS = [
    "dish_name",
    "ingredient_food_name",
    "ingredient_unit",
    "ingredient_qty_per_serving",
]
GOAL_COLUMNS = ["date", "calorie_goal", "protein_goal"]
LOG_COLUMNS = ["date", "meal", "type", "name", "batch_id", "unit", "qty", "calories", "protein"]
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
    "notes",
]
BATCH_INGREDIENT_COLUMNS = [
    "batch_id",
    "ingredient_food_name",
    "ingredient_unit",
    "ingredient_qty",
]
DATE_INPUT_FORMAT = "DD/MM/YYYY"
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
    for col in ["base_qty", "calories_base", "protein_base", "cal_per_unit", "protein_per_unit"]:
        if col in foods.columns:
            foods[col] = pd.to_numeric(foods[col], errors="coerce")
    for col in ["cal_override", "protein_override", "servings", "yield_qty"]:
        if col in dishes.columns:
            dishes[col] = pd.to_numeric(dishes[col], errors="coerce")
    for col in ["ingredient_qty_per_serving"]:
        if col in dings.columns:
            dings[col] = pd.to_numeric(dings[col], errors="coerce")
    for col in ["calorie_goal", "protein_goal"]:
        if col in goals.columns:
            goals[col] = pd.to_numeric(goals[col], errors="coerce")
    for col in ["qty", "calories", "protein"]:
        if col in logs.columns:
            logs[col] = pd.to_numeric(logs[col], errors="coerce")
    for col in ["servings", "final_qty", "total_calories", "total_protein"]:
        if col in batches.columns:
            batches[col] = pd.to_numeric(batches[col], errors="coerce")
    for col in ["ingredient_qty"]:
        if col in batch_ings.columns:
            batch_ings[col] = pd.to_numeric(batch_ings[col], errors="coerce")
    return foods, dishes, dings, goals, logs, batches, batch_ings


def save_df(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False)


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


def get_food_row(foods: pd.DataFrame, food_name: str, unit: str):
    m = (foods["food_name"] == food_name) & (foods["unit"] == unit)
    if not m.any():
        return None
    return foods[m].iloc[0]


def compute_ingredient_totals(
    ingredients: pd.DataFrame, foods: pd.DataFrame, qty_column: str
) -> Tuple[float, float]:
    total_c = 0.0
    total_p = 0.0
    for _, ing in ingredients.iterrows():
        frow = get_food_row(foods, ing["ingredient_food_name"], ing["ingredient_unit"])
        if frow is None:
            continue
        qty = as_float(ing[qty_column], 0.0)
        total_c += qty * as_float(frow["cal_per_unit"], 0.0)
        total_p += qty * as_float(frow["protein_per_unit"], 0.0)
    return total_c, total_p


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
    total_calories: float,
    total_protein: float,
    manual_qty: float,
    manual_unit: str,
    auto_qty: float = 0.0,
    auto_unit: str = "",
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
    return {
        "servings": safe_servings,
        "total_calories": total_calories,
        "total_protein": total_protein,
        "per_serving_calories": total_calories / safe_servings,
        "per_serving_protein": total_protein / safe_servings,
        "final_qty": final_qty,
        "final_unit": final_unit,
        "yield_source": yield_source,
        "has_weight_basis": has_weight_basis,
        "per_weight_calories": total_calories / final_qty if has_weight_basis else 0.0,
        "per_weight_protein": total_protein / final_qty if has_weight_basis else 0.0,
    }


def normalize_food_row(row):
    base_qty = as_float(row.get("base_qty"), 0.0)
    cal_per_unit = as_float(row.get("cal_per_unit"), 0.0)
    protein_per_unit = as_float(row.get("protein_per_unit"), 0.0)

    if base_qty <= 0:
        base_qty = 1.0

    calories_base = row.get("calories_base")
    protein_base = row.get("protein_base")
    if pd.isna(calories_base):
        calories_base = cal_per_unit * base_qty
    if pd.isna(protein_base):
        protein_base = protein_per_unit * base_qty

    row["base_qty"] = base_qty
    row["calories_base"] = as_float(calories_base, 0.0)
    row["protein_base"] = as_float(protein_base, 0.0)
    row["cal_per_unit"] = row["calories_base"] / base_qty
    row["protein_per_unit"] = row["protein_base"] / base_qty
    return row


def clear_add_food_form():
    clear_session_keys(
        [
            "add_food_name",
            "add_food_unit",
            "add_base_qty",
            "add_cal_base",
            "add_prot_base",
        ]
    )


def clear_add_dish_form():
    clear_session_keys(
        [
            "add_dish_name",
            "add_dish_override",
            "add_dish_cal",
            "add_dish_prot",
            "add_dish_servings",
            "add_dish_yield_qty",
            "add_dish_yield_unit",
        ]
    )


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
    clear_session_keys(["add_ing_food", "add_ing_unit", "add_ing_qty"])


def clear_single_goal_form():
    clear_session_keys(["goal_date", "cal_goal2", "prot_goal2"])


def clear_bulk_goal_form():
    clear_session_keys(["bulk_start", "bulk_end", "bulk_cal", "bulk_prot"])


def set_view_date_today():
    st.session_state.view_date = date.today()


def log_entry_label(idx, row) -> str:
    item_name = row["name"]
    if row.get("type") == "batch" and as_text(row.get("batch_id")):
        item_name = f"{item_name} [{short_batch_id(row.get('batch_id'))}]"
    return (
        f"{idx}: {row['meal']} - {row['type']} - {item_name} "
        f"({as_float(row['qty'], 0.0):g} {row['unit']}, "
        f"{as_float(row['calories'], 0.0):.0f} kcal, "
        f"{as_float(row['protein'], 0.0):.1f}g protein)"
    )


def clear_session_keys(keys):
    for key in keys:
        st.session_state.pop(key, None)


def render_status_pie(calories_ok: bool, protein_ok: bool):
    green = "#2e7d32"
    red = "#c62828"
    ok_count = int(calories_ok) + int(protein_ok)
    if ok_count == 2:
        gradient = f"{green} 0 100%"
    elif ok_count == 1:
        gradient = f"{green} 0 50%, {red} 50% 100%"
    else:
        gradient = f"{red} 0 100%"

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:12px;margin-top:4px;">
            <div aria-label="Daily status pie chart" style="
                width:64px;
                height:64px;
                border-radius:50%;
                background:conic-gradient({gradient});
                border:1px solid rgba(0,0,0,0.12);
            "></div>
            <div style="font-size:0.85rem;line-height:1.35;">
                <div><span style="color:{green};font-weight:700;">Green</span>: goal met</div>
                <div><span style="color:{red};font-weight:700;">Red</span>: needs attention</div>
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
    dish_name: str, dishes: pd.DataFrame, dings: pd.DataFrame, foods: pd.DataFrame
) -> Tuple[float, float]:
    md = dishes[dishes["dish_name"] == dish_name]
    if md.empty:
        return 0.0, 0.0
    row = md.iloc[0]
    if is_override_dish(row):
        servings = get_dish_servings(row)
        return float(row["cal_override"]) * servings, float(row["protein_override"]) * servings

    use = dings[dings["dish_name"] == dish_name]
    return compute_ingredient_totals(use, foods, "ingredient_qty_per_serving")


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
    dish_name: str, dishes: pd.DataFrame, dings: pd.DataFrame, foods: pd.DataFrame
):
    md = dishes[dishes["dish_name"] == dish_name]
    if md.empty:
        return {
            "servings": 1.0,
            "total_calories": 0.0,
            "total_protein": 0.0,
            "per_serving_calories": 0.0,
            "per_serving_protein": 0.0,
            "final_qty": 0.0,
            "final_unit": "",
            "yield_source": "none",
            "has_weight_basis": False,
            "per_weight_calories": 0.0,
            "per_weight_protein": 0.0,
        }

    row = md.iloc[0]
    servings = get_dish_servings(row)
    total_c, total_p = compute_dish_totals(dish_name, dishes, dings, foods)
    manual_qty, manual_unit = get_dish_yield(row)
    auto_qty, auto_unit = get_auto_dish_yield(dish_name, dings)
    return build_portion_metrics(
        servings,
        total_c,
        total_p,
        manual_qty,
        manual_unit,
        auto_qty,
        auto_unit,
    )


def get_dish_log_options(
    dish_name: str, dishes: pd.DataFrame, dings: pd.DataFrame, foods: pd.DataFrame
):
    metrics = get_dish_metrics(dish_name, dishes, dings, foods)
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
    log_unit: str = "serving",
) -> Tuple[float, float]:
    metrics = get_dish_metrics(dish_name, dishes, dings, foods)
    if log_unit == "serving":
        return metrics["per_serving_calories"], metrics["per_serving_protein"]
    if metrics["has_weight_basis"] and log_unit == metrics["final_unit"]:
        return metrics["per_weight_calories"], metrics["per_weight_protein"]
    return 0.0, 0.0


def make_batch_id(batch_day: date) -> str:
    return f"batch_{batch_day.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S%f')}"


def get_batch_row(batches: pd.DataFrame, batch_id: str):
    match = batches[batches["batch_id"] == batch_id]
    if match.empty:
        return None
    return match.iloc[0]


def get_batch_metrics(batch_row):
    if batch_row is None:
        return build_portion_metrics(1.0, 0.0, 0.0, 0.0, "")
    return build_portion_metrics(
        as_float(batch_row.get("servings"), 1.0),
        as_float(batch_row.get("total_calories"), 0.0),
        as_float(batch_row.get("total_protein"), 0.0),
        as_float(batch_row.get("final_qty"), 0.0),
        as_text(batch_row.get("final_unit")),
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


def compute_batch_base(batch_row, log_unit: str = "serving") -> Tuple[float, float]:
    metrics = get_batch_metrics(batch_row)
    if log_unit == "serving":
        return metrics["per_serving_calories"], metrics["per_serving_protein"]
    if metrics["has_weight_basis"] and log_unit == metrics["final_unit"]:
        return metrics["per_weight_calories"], metrics["per_weight_protein"]
    return 0.0, 0.0


def get_goal_for_date(goals: pd.DataFrame, day: date):
    s = goals[goals["date"] == day.isoformat()]
    if s.empty:
        return None, None
    r = s.iloc[0]
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
    batch_id: str = "",
) -> pd.DataFrame:
    logs.loc[len(logs)] = [
        day.isoformat(),
        meal,
        typ,
        name,
        batch_id,
        unit,
        qty,
        cal,
        prot,
    ]
    return logs


def daily_totals(logs: pd.DataFrame, day: date):
    d = logs[logs["date"] == day.isoformat()]
    return float(d["calories"].sum()), float(d["protein"].sum())


# --- Recalc helpers ---
def recalc_logs_for_food(
    logs: pd.DataFrame, foods: pd.DataFrame, food_name: str, unit: str
) -> pd.DataFrame:
    frow = get_food_row(foods, food_name, unit)
    if frow is None:
        return logs
    cal_per = as_float(frow["cal_per_unit"], 0.0)
    prot_per = as_float(frow["protein_per_unit"], 0.0)
    mask = (
        (logs["type"] == "food") & (logs["name"] == food_name) & (logs["unit"] == unit)
    )
    qty = logs.loc[mask, "qty"].fillna(0).astype(float)
    logs.loc[mask, "calories"] = qty * cal_per
    logs.loc[mask, "protein"] = qty * prot_per
    return logs


def recalc_logs_for_dishes(
    logs: pd.DataFrame,
    dishes: pd.DataFrame,
    dings: pd.DataFrame,
    foods: pd.DataFrame,
    dish_names: list,
) -> pd.DataFrame:
    for dn in dish_names:
        metrics = get_dish_metrics(dn, dishes, dings, foods)

        serving_mask = (
            (logs["type"] == "dish")
            & (logs["name"] == dn)
            & (logs["unit"] == "serving")
        )
        serving_qty = logs.loc[serving_mask, "qty"].fillna(0).astype(float)
        logs.loc[serving_mask, "calories"] = (
            serving_qty * metrics["per_serving_calories"]
        )
        logs.loc[serving_mask, "protein"] = (
            serving_qty * metrics["per_serving_protein"]
        )

        if metrics["has_weight_basis"]:
            weight_mask = (
                (logs["type"] == "dish")
                & (logs["name"] == dn)
                & (logs["unit"] == metrics["final_unit"])
            )
            weight_qty = logs.loc[weight_mask, "qty"].fillna(0).astype(float)
            logs.loc[weight_mask, "calories"] = (
                weight_qty * metrics["per_weight_calories"]
            )
            logs.loc[weight_mask, "protein"] = (
                weight_qty * metrics["per_weight_protein"]
            )
    return logs


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
        meal = st.selectbox(
            "Meal", ["Breakfast", "Lunch", "Dinner", "Snacks"], index=0, key="log_meal"
        )
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
                cal_per = as_float(frow["cal_per_unit"], 0.0)
                prot_per = as_float(frow["protein_per_unit"], 0.0)
                est_c = qty * cal_per
                est_p = qty * prot_per
                st.metric("Calories (est.)", f"{est_c:.0f}")
                st.metric("Protein (g, est.)", f"{est_p:.1f}")
                if st.button(
                    "Add to log",
                    type="primary",
                    use_container_width=True,
                    key="add_food_log",
                ):
                    logs = add_log_entry(
                        logs, log_date, meal, "food", f_name, unit, qty, est_c, est_p
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
            dish_metrics = get_dish_metrics(d_name, dishes, dings, foods)
            log_options = get_dish_log_options(d_name, dishes, dings, foods)
            option_labels = [label for _, label in log_options]
            option_map = {label: unit for unit, label in log_options}
            selected_label = st.selectbox("Log by", option_labels, key="log_dish_basis")
            log_unit = option_map[selected_label]
            base_c, base_p = compute_dish_base(d_name, dishes, dings, foods, log_unit)
            basis_label = get_dish_basis_label(log_unit)
            est_c = qty * base_c
            est_p = qty * base_p

            info_cols = st.columns(2)
            with info_cols[0]:
                st.metric("Calories per serving", f"{dish_metrics['per_serving_calories']:.1f}")
                st.metric("Protein per serving (g)", f"{dish_metrics['per_serving_protein']:.2f}")
            with info_cols[1]:
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
                    st.caption(
                        f"{source_label}: {dish_metrics['final_qty']:.0f} {dish_metrics['final_unit']} total, "
                        f"{dish_metrics['servings']:.0f} servings, "
                        f"{dish_metrics['final_qty'] / dish_metrics['servings']:.1f} {dish_metrics['final_unit']} per serving."
                    )
                else:
                    st.caption(
                        "Weight logging becomes available when you add a manual final dish quantity or when all ingredient quantities share the same unit and can be auto-summed."
                    )

            st.metric(f"Calories {basis_label}", f"{base_c:.2f}")
            st.metric(f"Protein {basis_label} (g)", f"{base_p:.3f}")
            st.metric("Calories (this entry)", f"{est_c:.0f}")
            st.metric("Protein (this entry, g)", f"{est_p:.1f}")
            if st.button(
                "Add to log",
                type="primary",
                use_container_width=True,
                key="add_dish_log",
            ):
                logs = add_log_entry(
                    logs, log_date, meal, "dish", d_name, log_unit, qty, est_c, est_p
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
            log_options = get_batch_log_options(batch_row)
            option_labels = [label for _, label in log_options]
            option_map = {label: unit for unit, label in log_options}
            selected_label = st.selectbox("Log by", option_labels, key="log_batch_basis")
            log_unit = option_map[selected_label]
            base_c, base_p = compute_batch_base(batch_row, log_unit)
            basis_label = get_dish_basis_label(log_unit)
            est_c = qty * base_c
            est_p = qty * base_p

            info_cols = st.columns(2)
            with info_cols[0]:
                st.metric("Calories per serving", f"{batch_metrics['per_serving_calories']:.1f}")
                st.metric("Protein per serving (g)", f"{batch_metrics['per_serving_protein']:.2f}")
            with info_cols[1]:
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
                    st.caption(
                        f"{source_label}: {batch_metrics['final_qty']:.0f} {batch_metrics['final_unit']} total, "
                        f"{batch_metrics['servings']:.0f} servings, "
                        f"{batch_metrics['final_qty'] / batch_metrics['servings']:.1f} {batch_metrics['final_unit']} per serving."
                    )
                else:
                    st.caption(
                        "This batch only supports serving-based logging because no final weight was saved."
                    )

            st.metric(f"Calories {basis_label}", f"{base_c:.2f}")
            st.metric(f"Protein {basis_label} (g)", f"{base_p:.3f}")
            st.metric("Calories (this entry)", f"{est_c:.0f}")
            st.metric("Protein (this entry, g)", f"{est_p:.1f}")
            if st.button(
                "Add to log",
                type="primary",
                use_container_width=True,
                key="add_batch_log",
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
        st.button("Today", key="view_today", on_click=set_view_date_today)
        view_date = st.date_input(
            "Pick a date",
            value=date.today(),
            format=DATE_INPUT_FORMAT,
            key="view_date",
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
    if day_logs.empty:
        st.info("No entries for this date.")
    else:
        day_logs["display_name"] = day_logs["name"]
        batch_mask = (day_logs["type"] == "batch") & day_logs["batch_id"].notna()
        day_logs.loc[batch_mask, "display_name"] = day_logs.loc[batch_mask].apply(
            lambda row: f"{row['name']} [{short_batch_id(row['batch_id'])}]",
            axis=1,
        )
        # Show grouped by meal
        for meal_name in ["Breakfast", "Lunch", "Dinner", "Snacks"]:
            sub = day_logs[day_logs["meal"] == meal_name]
            if sub.empty:
                continue
            st.markdown(f"### {meal_name}")
            # mandatory list with per-item breakdown
            show = sub[["type", "display_name", "unit", "qty", "calories", "protein"]].copy()
            show = show.rename(
                columns={
                    "type": "Type",
                    "display_name": "Item",
                    "unit": "Unit",
                    "qty": "Qty",
                    "calories": "Calories",
                    "protein": "Protein (g)",
                }
            )
            st.dataframe(show, hide_index=True, use_container_width=True)

        st.markdown("### Delete an entry")
        delete_options = {
            log_entry_label(idx, row): idx for idx, row in day_logs.iterrows()
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
                delete_idx = delete_options[delete_label]
                logs = logs.drop(delete_idx)
                save_df(logs, LOGS_CSV)
                clear_session_keys(["delete_day_log_sel", "confirm_delete_day_log"])
                st.success("Entry deleted.")
                st.rerun()
            else:
                st.error("Confirmation did not match. No entry was deleted.")

        tot_c, tot_p = daily_totals(logs, view_date)
        st.markdown("### Daily totals")
        m1, m2, m3 = st.columns(3)
        m1.metric("Calories", f"{tot_c:.0f}")
        m2.metric("Protein (g)", f"{tot_p:.1f}")
        if gcal is not None and gprot is not None:
            ok_c = tot_c <= gcal
            ok_p = tot_p >= gprot
            status_color = "#2e7d32" if ok_c and ok_p else "#c62828"
            status_text = (
                f"{'Under calories' if ok_c else 'Over calories'} | "
                f"{'Protein met' if ok_p else 'Protein not met'}"
            )
            m3.markdown(
                f"""
                <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.04em;color:#666;">
                    Status
                </div>
                <div style="font-size:0.95rem;font-weight:700;color:{status_color};line-height:1.35;">
                    {status_text}
                </div>
                """,
                unsafe_allow_html=True,
            )
            m3.caption("Daily goal status")
            with m3:
                render_status_pie(ok_c, ok_p)

# --------- Tab 3: Dashboard ---------
with tabs[2]:
    st.subheader("Summary")
    if logs.empty:
        st.info("No data yet.")
    else:
        # Join logs with goals by date
        agg = (
            logs.groupby("date")
            .agg(calories=("calories", "sum"), protein=("protein", "sum"))
            .reset_index()
        )
        goals_join = goals.rename(columns={"date": "date"})
        merged = pd.merge(agg, goals_join, on="date", how="left")
        # Flags only apply to days that have both goals defined.
        has_goals = merged["calorie_goal"].notna() & merged["protein_goal"].notna()
        merged["protein_met"] = pd.NA
        merged["under_cal"] = pd.NA
        merged.loc[has_goals, "protein_met"] = (
            merged.loc[has_goals, "protein"] >= merged.loc[has_goals, "protein_goal"]
        )
        merged.loc[has_goals, "under_cal"] = (
            merged.loc[has_goals, "calories"] <= merged.loc[has_goals, "calorie_goal"]
        )
        # Counts
        days_with_goals = merged.dropna(subset=["calorie_goal", "protein_goal"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Days logged", f"{len(agg)}")
        c2.metric(
            "Protein goal met (days)", f"{int(days_with_goals['protein_met'].sum())}"
        )
        c3.metric(
            "Under calorie budget (days)", f"{int(days_with_goals['under_cal'].sum())}"
        )
        st.markdown("#### Per-day view")
        merged["date"] = format_date_series(merged["date"])
        st.dataframe(merged.fillna("—"), use_container_width=True)

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
    with st.expander("Add food"):
        st.caption(
            "Create a reusable food definition. Example: Rice, unit g, base quantity 100, calories 130, protein 2.7."
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            f_name = st.text_input("Food name", key="add_food_name")
        with c2:
            unit = st.text_input("Unit (e.g., g, ml, pc, bowl, tbsp)", key="add_food_unit")
        with c3:
            base_qty = st.number_input("Base quantity", min_value=1.0, step=1.0, value=100.0, key="add_base_qty")
            cal_base = st.number_input("Calories for base qty", min_value=0.0, step=1.0, key="add_cal_base")
        with c4:
            prot_base = st.number_input("Protein for base qty (g)", min_value=0.0, step=0.1, key="add_prot_base")

        b1, b2 = st.columns(2)
        with b1:
            save_food = st.button("Save food", key="save_food")
        with b2:
            st.button("Clear form", key="clear_add_food", on_click=clear_add_food_form)

        if save_food:
            f_name = f_name.strip()
            unit = unit.strip()
            if f_name and unit:
                exists = (foods["food_name"] == f_name) & (foods["unit"] == unit)
                if exists.any():
                    st.warning("Food with this unit already exists.")
                else:
                    cal_per = cal_base / base_qty if base_qty > 0 else 0
                    prot_per = prot_base / base_qty if base_qty > 0 else 0

                    foods.loc[len(foods)] = [
                        f_name,
                        unit,
                        base_qty,
                        cal_base,
                        prot_base,
                        cal_per,
                        prot_per,
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

    section_heading(
        "Edit a food",
        "Change a food's name, unit, or nutrition values. Existing food logs are recalculated. If this food is used in dishes, keep propagation on when you are renaming the food or unit.",
    )
    if not foods.empty:
        fedit = st.selectbox(
            "Select food to edit",
            foods.apply(food_key, axis=1).tolist(),
            key="edit_food_sel",
        )
        frow = foods[foods.apply(food_key, axis=1) == fedit].iloc[0]
        old_name, old_unit = frow["food_name"], frow["unit"]

        new_name = st.text_input("Food name", value=old_name, key="edit_food_name")
        new_unit = st.text_input("Unit", value=old_unit, key="edit_food_unit")
        new_base_qty = st.number_input(
            "Base quantity",
            min_value=1.0,
            step=1.0,
            value=float(frow["base_qty"]),
            key="edit_base_qty",
        )

        new_cal_base = st.number_input(
            "Calories for base qty",
            min_value=0.0,
            step=1.0,
            value=float(frow["calories_base"]),
            key="edit_cal_base",
        )

        new_prot_base = st.number_input(
            "Protein for base qty",
            min_value=0.0,
            step=0.1,
            value=float(frow["protein_base"]),
            key="edit_prot_base",
        )
        propagate = st.checkbox(
            "Also update dish ingredients that reference this food",
            value=True,
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
            if not new_name or not new_unit:
                st.error("Name and unit required.")
                st.stop()
            if duplicate.any():
                st.error("Another food already uses this name and unit.")
                st.stop()

            impacted_before = sorted(
                dings[
                    (dings["ingredient_food_name"] == old_name)
                    & (dings["ingredient_unit"] == old_unit)
                ]["dish_name"]
                .unique()
                .tolist()
            )

            # update foods table
            cal_per = new_cal_base / new_base_qty if new_base_qty > 0 else 0
            prot_per = new_prot_base / new_base_qty if new_base_qty > 0 else 0

            foods.loc[frow.name] = [
                new_name,
                new_unit,
                new_base_qty,
                new_cal_base,
                new_prot_base,
                cal_per,
                prot_per,
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
                dings.loc[mask, "ingredient_food_name"] = new_name
                dings.loc[mask, "ingredient_unit"] = new_unit
                save_df(dings, DISH_ING_CSV)
                st.success("References updated.")

            # Recalculate logs that reference this food and any dishes that include it
            logs = recalc_logs_for_food(logs, foods, new_name, new_unit)
            impacted_after = sorted(
                dings[
                    (dings["ingredient_food_name"] == new_name)
                    & (dings["ingredient_unit"] == new_unit)
                ]["dish_name"]
                .unique()
                .tolist()
            )
            impacted = sorted(set(impacted_before) | set(impacted_after))
            if impacted:
                logs = recalc_logs_for_dishes(logs, dishes, dings, foods, impacted)
            save_df(logs, LOGS_CSV)

            st.success(f"Food {fedit} updated and logs recalculated.")
            st.rerun()



    section_heading(
        "Delete a food",
        "Remove a food definition. This also deletes direct food logs for that food and removes matching ingredient references from dishes. Type the exact food key before deleting.",
    )
    if not foods.empty:
        fdel = st.selectbox(
            "Select food to delete",
            foods.apply(food_key, axis=1).tolist(),
            key="delete_food_sel",
        )

        # Preview how many logs/ingredients will be affected
        frow = foods[foods.apply(food_key, axis=1) == fdel].iloc[0]
        fname, funit = frow["food_name"], frow["unit"]
        affected_logs = logs[
            (logs["type"] == "food") & (logs["name"] == fname) & (logs["unit"] == funit)
        ]
        affected_ings = dings[
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
                        logs, dishes, dings, foods, impacted_dishes
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
    with st.expander("Add / update dish"):
        st.caption(
            "Use this to create or update a dish shell. Example override: Tea = 70 kcal and 2g protein per serving. Example ingredient dish: Dal with final dish quantity 850 and unit g, then add ingredients below."
        )
        dname = st.text_input("Dish name", key="add_dish_name")
        use_override = st.checkbox(
            "Use manual override values", key="add_dish_override"
        )
        col1, col2, col3, col4 = st.columns(4)
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
            servings = st.number_input(
                "Servings definition",
                min_value=1.0,
                step=1.0,
                value=1.0,
                help="Use 1 unless you need a different base serving size.",
                key="add_dish_servings",
            )
        with col4:
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
                exists = dishes["dish_name"] == dname
                calv = cal_o if use_override else None
                protv = prot_o if use_override else None
                yieldv = yield_qty if not use_override and yield_qty > 0 else None
                yield_unitv = yield_unit if yieldv is not None else None
                if exists.any():
                    idx = dishes.index[exists][0]
                    dishes.loc[
                        idx,
                        [
                            "cal_override",
                            "protein_override",
                            "servings",
                            "yield_qty",
                            "yield_unit",
                        ],
                    ] = [calv, protv, servings, yieldv, yield_unitv]
                else:
                    dishes.loc[len(dishes)] = [
                        dname,
                        calv,
                        protv,
                        servings,
                        yieldv,
                        yield_unitv,
                    ]
                save_df(dishes, DISHES_CSV)
                logs = recalc_logs_for_dishes(logs, dishes, dings, foods, [dname])
                save_df(logs, LOGS_CSV)
                clear_add_dish_form()
                st.session_state.master_data_message = "Dish saved and logs recalculated."
                st.rerun()

    section_heading(
        "Edit a dish",
        "Edit override nutrition or final cooked yield. For ingredient dishes, final dish quantity lets raw ingredient nutrition scale to cooked weight, e.g. ingredients produce 850g dal so logging 100g uses 100/850 of the recipe.",
    )
    if not dishes.empty:
        dsel_edit = st.selectbox(
            "Select dish to edit",
            sorted(dishes["dish_name"].tolist()),
            key="edit_dish_sel_unique",
        )
        drow = dishes[dishes["dish_name"] == dsel_edit].iloc[0]
        edit_use_override = st.checkbox(
            "Use manual override values",
            value=pd.notna(drow["cal_override"]) and pd.notna(drow["protein_override"]),
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
                yieldv = edit_yield_qty if not edit_use_override and edit_yield_qty > 0 else None
                yield_unitv = edit_yield_unit if yieldv is not None else None
                idx = drow.name
                dishes.loc[
                    idx,
                    [
                        "cal_override",
                        "protein_override",
                        "servings",
                        "yield_qty",
                        "yield_unit",
                    ],
                ] = [
                    new_cal if edit_use_override else None,
                    new_prot if edit_use_override else None,
                    new_serv,
                    yieldv,
                    yield_unitv,
                ]
                save_df(dishes, DISHES_CSV)
                # Recalculate all logs for this dish
                logs = recalc_logs_for_dishes(logs, dishes, dings, foods, [dsel_edit])
                save_df(logs, LOGS_CSV)
                st.success(f"Dish {dsel_edit} updated and logs recalculated.")
                st.rerun()

    with st.expander("Add ingredient to dish (for computed dishes)"):
        st.caption(
            "Add foods into an ingredient-based dish. Quantities are recipe quantities in the selected food unit. Example: 200g raw dal + 20g ghee + 500ml water."
        )
        if dishes.empty or foods.empty:
            st.info("Add at least one dish and one food first.")
        else:
            dsel = st.selectbox(
                "Dish", sorted(dishes["dish_name"].tolist()), key="add_ing_dish"
            )
            fsel = st.selectbox(
                "Ingredient food",
                sorted(foods["food_name"].unique().tolist()),
                key="add_ing_food",
            )
            units = sorted(foods[foods["food_name"] == fsel]["unit"].unique().tolist())
            u_sel = st.selectbox("Ingredient unit", units, key="add_ing_unit")
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
                else:
                    dings.loc[len(dings)] = [dsel, fsel, u_sel, qty]
                    save_df(dings, DISH_ING_CSV)
                    # Recalculate logs for this dish
                    logs = recalc_logs_for_dishes(logs, dishes, dings, foods, [dsel])
                    save_df(logs, LOGS_CSV)
                    clear_add_ingredient_form()
                    st.session_state.master_data_message = "Ingredient added and logs recalculated."
                    st.rerun()

    section_heading(
        "Edit ingredients",
        "Adjust or remove the recipe ingredients for a computed dish. Any update recalculates logs for matching dish entries.",
    )
    if not dishes.empty:
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
                    f"**{ing['ingredient_food_name']} [{ing['ingredient_unit']}]**"
                )

                # choose a food and unit (allows replacing the ingredient)
                fcol1, fcol2, fcol3, fcol4 = st.columns([3, 2, 2, 2])
                with fcol1:
                    food_choice = st.selectbox(
                        "Food",
                        sorted(foods["food_name"].unique().tolist()),
                        index=sorted(foods["food_name"].unique().tolist()).index(
                            ing["ingredient_food_name"]
                        )
                        if ing["ingredient_food_name"] in foods["food_name"].unique()
                        else 0,
                        key=f"ing_food_{i}",
                    )
                with fcol2:
                    unit_options = sorted(
                        foods[foods["food_name"] == food_choice]["unit"]
                        .unique()
                        .tolist()
                    )
                    # default to existing unit if present
                    default_unit_idx = (
                        unit_options.index(ing["ingredient_unit"])
                        if ing["ingredient_unit"] in unit_options
                        else 0
                    )
                    unit_choice = st.selectbox(
                        "Unit",
                        unit_options,
                        index=default_unit_idx,
                        key=f"ing_unit_{i}",
                    )
                with fcol3:
                    qty_choice = st.number_input(
                        "Ingredient qty in recipe",
                        min_value=0.0,
                        step=1.0,
                        value=float(ing["ingredient_qty_per_serving"]),
                        key=f"ing_qty_{i}",
                    )
                with fcol4:
                    if st.button("Update", key=f"ing_update_{i}"):
                        dings.loc[
                            i,
                            [
                                "ingredient_food_name",
                                "ingredient_unit",
                                "ingredient_qty_per_serving",
                            ],
                        ] = [food_choice, unit_choice, qty_choice]
                        save_df(dings, DISH_ING_CSV)
                        logs = recalc_logs_for_dishes(
                            logs, dishes, dings, foods, [dsel_ing]
                        )
                        save_df(logs, LOGS_CSV)
                        st.success("Ingredient updated and logs recalculated.")
                        st.rerun()
                    if st.button("Remove", key=f"ing_remove_{i}"):
                        dings = dings.drop(i)
                        save_df(dings, DISH_ING_CSV)
                        logs = recalc_logs_for_dishes(
                            logs, dishes, dings, foods, [dsel_ing]
                        )
                        save_df(logs, LOGS_CSV)
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
                metrics = get_dish_metrics(dname, dishes, dings, foods)
                preview.append(
                    {
                        "dish_name": dname,
                        "servings": round(metrics["servings"], 2),
                        "total_calories": round(metrics["total_calories"], 2),
                        "total_protein": round(metrics["total_protein"], 2),
                        "calories_per_serving": round(metrics["per_serving_calories"], 2),
                        "protein_per_serving": round(metrics["per_serving_protein"], 2),
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
                    }
                )
            st.dataframe(pd.DataFrame(preview), use_container_width=True)

    section_heading(
        "Batches",
        "Batches are immutable snapshots of one real cook. Create a new batch each time the ingredient quantities, servings, or final weight differ so old logs never change.",
        level=3,
    )
    with st.expander("Create batch from dish"):
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
            elif template_ings.empty:
                st.warning("This dish has no ingredients yet.")
            else:
                st.write("Ingredient snapshot for this batch")
                for i, ing in template_ings.iterrows():
                    qty_key = f"create_batch_qty_{batch_dish_name}_{i}"
                    c1, c2, c3 = st.columns([4, 2, 2])
                    with c1:
                        st.write(f"{ing['ingredient_food_name']} [{ing['ingredient_unit']}]")
                    with c2:
                        qty_value = st.number_input(
                            "Qty",
                            min_value=0.0,
                            step=1.0,
                            value=float(ing["ingredient_qty_per_serving"]),
                            key=qty_key,
                            label_visibility="collapsed",
                        )
                    with c3:
                        frow = get_food_row(
                            foods,
                            ing["ingredient_food_name"],
                            ing["ingredient_unit"],
                        )
                        if frow is None:
                            st.caption("Food missing")
                        else:
                            est_c = qty_value * as_float(frow["cal_per_unit"], 0.0)
                            est_p = qty_value * as_float(frow["protein_per_unit"], 0.0)
                            st.caption(f"{est_c:.0f} kcal | {est_p:.1f}g")
                    if qty_value > 0:
                        batch_ingredient_rows.append(
                            {
                                "ingredient_food_name": ing["ingredient_food_name"],
                                "ingredient_unit": ing["ingredient_unit"],
                                "ingredient_qty": qty_value,
                            }
                        )

            preview_metrics = None
            if is_override_dish(template_row):
                total_c = as_float(template_row["cal_override"], 0.0) * batch_servings
                total_p = as_float(template_row["protein_override"], 0.0) * batch_servings
                preview_metrics = build_portion_metrics(
                    batch_servings,
                    total_c,
                    total_p,
                    batch_final_qty if batch_final_qty > 0 else 0.0,
                    batch_final_unit.strip(),
                )
            elif batch_ingredient_rows:
                batch_ingredients_df = pd.DataFrame(batch_ingredient_rows)
                total_c, total_p = compute_ingredient_totals(
                    batch_ingredients_df, foods, "ingredient_qty"
                )
                auto_qty, auto_unit = get_auto_yield_from_ingredients(
                    batch_ingredients_df, "ingredient_qty"
                )
                preview_metrics = build_portion_metrics(
                    batch_servings,
                    total_c,
                    total_p,
                    batch_final_qty if batch_final_qty > 0 else 0.0,
                    batch_final_unit.strip(),
                    auto_qty,
                    auto_unit,
                )

            if preview_metrics is not None:
                p1, p2, p3 = st.columns(3)
                p1.metric("Batch calories", f"{preview_metrics['total_calories']:.0f}")
                p2.metric("Batch protein (g)", f"{preview_metrics['total_protein']:.1f}")
                source_label = preview_metrics["yield_source"] or "none"
                p3.metric("Final qty source", source_label)
                st.caption(
                    f"Per serving: {preview_metrics['per_serving_calories']:.1f} kcal, "
                    f"{preview_metrics['per_serving_protein']:.2f}g protein."
                )
                if preview_metrics["has_weight_basis"]:
                    st.caption(
                        f"Per {preview_metrics['final_unit']}: "
                        f"{preview_metrics['per_weight_calories']:.3f} kcal, "
                        f"{preview_metrics['per_weight_protein']:.4f}g protein."
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
                        preview_metrics = build_portion_metrics(batch_servings, 0.0, 0.0, 0.0, "")

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
                        "calories_per_serving",
                        "protein_per_serving",
                        "calories_per_final_unit",
                        "protein_per_final_unit",
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
                st.dataframe(batch_ing_view, hide_index=True, use_container_width=True)

    section_heading(
        "Delete a batch",
        "Remove a batch snapshot and any logs created from that batch. This does not delete the underlying dish template.",
    )
    if not batches.empty:
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
        st.warning(
            f"Deleting this batch will remove {len(affected_batch_logs)} batch log entries and {len(affected_batch_ings)} batch ingredient snapshot rows."
        )
        confirm_batch = st.text_input(
            "Type the exact batch label to confirm",
            key="confirm_batch_delete",
        )
        if st.button("Delete batch", key="delete_batch_button"):
            if confirm_batch.strip() == bdel:
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
        "Goals are date-specific. Use single-date goals for one day, or bulk goals to prefill a date range. Past-date edits require the Day View toggle.",
        level=3,
    )

    with st.expander("Set or update goal for a single date"):
        st.caption(
            "Set one day's targets. Example: May 3 has 1800 kcal and 120g protein; changing May 3 does not change other days."
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
