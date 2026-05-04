# Shoku (Food Tracker) (Streamlit v0)
# MVP: meals, units, foods+dishes, per-day goal locking, calendar view, mandatory list, dashboard

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
from typing import Tuple

import shutil
import os

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


# --- 2. BACKUP UTILITY ---
st.sidebar.header("System Admin")
if st.sidebar.button("Generate CSV Backup"):
    # Creates a ZIP file of your entire 'data' folder
    if os.path.exists("data"):
        shutil.make_archive("backup_data", 'zip', "data")
        with open("backup_data.zip", "rb") as f:
            st.sidebar.download_button(
                label="Download Backup ZIP",
                data=f,
                file_name="shoku_data_backup.zip",
                mime="application/zip"
            )
    else:
        st.sidebar.error("Data directory not found on server.")

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
LOG_COLUMNS = ["date", "meal", "type", "name", "unit", "qty", "calories", "protein"]

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
    return foods, dishes, dings, goals, logs


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


def get_food_row(foods: pd.DataFrame, food_name: str, unit: str):
    m = (foods["food_name"] == food_name) & (foods["unit"] == unit)
    if not m.any():
        return None
    return foods[m].iloc[0]


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
    st.session_state.add_food_name = ""
    st.session_state.add_food_unit = ""
    st.session_state.add_base_qty = 100.0
    st.session_state.add_cal_base = 0.0
    st.session_state.add_prot_base = 0.0


def clear_add_dish_form():
    st.session_state.add_dish_name = ""
    st.session_state.add_dish_override = False
    st.session_state.add_dish_cal = 0.0
    st.session_state.add_dish_prot = 0.0
    st.session_state.add_dish_servings = 1.0
    st.session_state.add_dish_yield_qty = 0.0
    st.session_state.add_dish_yield_unit = ""


def set_view_date_today():
    st.session_state.view_date = date.today()


def log_entry_label(idx, row) -> str:
    return (
        f"{idx}: {row['meal']} - {row['type']} - {row['name']} "
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
    total_c = 0.0
    total_p = 0.0
    for _, ing in use.iterrows():
        frow = get_food_row(foods, ing["ingredient_food_name"], ing["ingredient_unit"])
        if frow is None:
            continue
        qty = as_float(ing["ingredient_qty_per_serving"], 0.0)
        total_c += qty * as_float(frow["cal_per_unit"], 0.0)
        total_p += qty * as_float(frow["protein_per_unit"], 0.0)
    return total_c, total_p


def get_auto_dish_yield(
    dish_name: str, dings: pd.DataFrame
) -> Tuple[float, str]:
    use = dings[dings["dish_name"] == dish_name].copy()
    if use.empty:
        return 0.0, ""

    use["ingredient_unit"] = use["ingredient_unit"].fillna("").astype(str).str.strip()
    use["ingredient_qty_per_serving"] = pd.to_numeric(
        use["ingredient_qty_per_serving"], errors="coerce"
    )
    use = use[
        (use["ingredient_unit"] != "") & use["ingredient_qty_per_serving"].notna()
    ]
    if use.empty:
        return 0.0, ""

    units = use["ingredient_unit"].unique().tolist()
    if len(units) != 1:
        return 0.0, ""

    return float(use["ingredient_qty_per_serving"].sum()), units[0]


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
    final_qty, final_unit, yield_source = get_effective_dish_yield(dish_name, row, dings)
    has_weight_basis = final_qty > 0 and bool(final_unit)

    return {
        "servings": servings,
        "total_calories": total_c,
        "total_protein": total_p,
        "per_serving_calories": total_c / servings if servings > 0 else 0.0,
        "per_serving_protein": total_p / servings if servings > 0 else 0.0,
        "final_qty": final_qty,
        "final_unit": final_unit,
        "yield_source": yield_source,
        "has_weight_basis": has_weight_basis,
        "per_weight_calories": total_c / final_qty if has_weight_basis else 0.0,
        "per_weight_protein": total_p / final_qty if has_weight_basis else 0.0,
    }


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
) -> pd.DataFrame:
    logs.loc[len(logs)] = [day.isoformat(), meal, typ, name, unit, qty, cal, prot]
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

foods, dishes, dings, goals, logs = load_all()

if not foods.empty:
    foods = foods.apply(normalize_food_row, axis=1)

st.title("Shoku 🍱")

tabs = st.tabs(["Log", "Day View", "Dashboard", "Master Data"])

# --------- Tab 1: Log ---------
with tabs[0]:
    st.subheader("Add entry")
    c1, c2 = st.columns([1, 1])
    with c1:
        log_date = st.date_input("Date", value=date.today(), key="log_date")
        meal = st.selectbox(
            "Meal", ["Breakfast", "Lunch", "Dinner", "Snacks"], index=0, key="log_meal"
        )
        entry_type = st.radio("Type", ["Food", "Dish"], horizontal=True, key="log_type")
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
                    st.success("Entry added.")
            else:
                st.warning("Food+unit not found.")

    else:  # Dish
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
                st.success("Entry added.")

# --------- Tab 2: Day View ---------
with tabs[1]:
    st.subheader("Browse a day")
    colA, colB = st.columns([1, 1])
    with colA:
        st.button("Today", key="view_today", on_click=set_view_date_today)
        view_date = st.date_input("Pick a date", value=date.today(), key="view_date")
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
        # Show grouped by meal
        for meal_name in ["Breakfast", "Lunch", "Dinner", "Snacks"]:
            sub = day_logs[day_logs["meal"] == meal_name]
            if sub.empty:
                continue
            st.markdown(f"### {meal_name}")
            # mandatory list with per-item breakdown
            show = sub[["type", "name", "unit", "qty", "calories", "protein"]].copy()
            show = show.rename(
                columns={
                    "type": "Type",
                    "name": "Item",
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
                    st.success("Food saved.")
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
                st.success("Dish saved and logs recalculated.")
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
                    st.success("Ingredient added and logs recalculated.")
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
        "Delete a dish",
        "Remove a dish, its ingredients, and any logged entries for that dish. Type the exact dish name before deleting.",
    )
    if not dishes.empty:
        ddel = st.selectbox(
            "Select dish to delete",
            sorted(dishes["dish_name"].tolist()),
            key="delete_dish_sel",
        )

        affected_logs = logs[(logs["type"] == "dish") & (logs["name"] == ddel)]
        affected_ings = dings[dings["dish_name"] == ddel]
        st.warning(
            f"Deleting **{ddel}** will remove {len(affected_logs)} log entries and {len(affected_ings)} ingredients."
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
        day = st.date_input("Date for goal", value=date.today(), key="goal_date")
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
                st.success("Goal saved.")
                st.rerun()

    with st.expander("Bulk set goals for a date range"):
        st.caption(
            "Apply the same goal across many dates. Example: set every weekday in a cut phase to 1700 kcal and 130g protein."
        )
        r1, r2 = st.columns(2)
        with r1:
            start_day = st.date_input(
                "Start date", value=date.today(), key="bulk_start"
            )
        with r2:
            end_day = st.date_input(
                "End date (inclusive)", value=date.today(), key="bulk_end"
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
                st.success("Goals applied to range.")
                st.rerun()

    with st.expander("View all goals", expanded=False):
        st.caption(
            "Read-only view of saved goal rows. Use Clear goals below if old test goals are cluttering this table."
        )
        st.dataframe(goals.sort_values("date"), use_container_width=True)

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
            f"Current rows: {len(foods)} foods, {len(dishes)} dishes, {len(dings)} ingredients, {len(goals)} goals, {len(logs)} logs."
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
