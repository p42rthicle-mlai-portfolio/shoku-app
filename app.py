# Shoku (Food Tracker) (Streamlit v0)
# MVP: meals, units, foods+dishes, per-day goal locking, calendar view, mandatory list, dashboard

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date, datetime
from typing import Tuple

if "allow_edit_past" not in st.session_state:
    st.session_state.allow_edit_past = False

DATA_DIR = Path(__file__).parent / "data"
FOODS_CSV = DATA_DIR / "foods.csv"
DISHES_CSV = DATA_DIR / "dishes.csv"
DISH_ING_CSV = DATA_DIR / "dish_ingredients.csv"
GOALS_CSV = DATA_DIR / "goals.csv"
LOGS_CSV  = DATA_DIR / "logs.csv"

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
    foods = ensure_csv(FOODS_CSV, ["food_name","unit","cal_per_unit","protein_per_unit"])
    dishes = ensure_csv(DISHES_CSV, ["dish_name","cal_override","protein_override","servings"])
    dings = ensure_csv(DISH_ING_CSV, ["dish_name","ingredient_food_name","ingredient_unit","ingredient_qty_per_serving"])
    goals = ensure_csv(GOALS_CSV, ["date","calorie_goal","protein_goal"])
    logs  = ensure_csv(LOGS_CSV,  ["date","meal","type","name","unit","qty","calories","protein"])
    # Coerce types
    for col in ["cal_per_unit","protein_per_unit"]:
        if col in foods.columns:
            foods[col] = pd.to_numeric(foods[col], errors="coerce")
    for col in ["cal_override","protein_override","servings"]:
        if col in dishes.columns:
            dishes[col] = pd.to_numeric(dishes[col], errors="coerce")
    for col in ["ingredient_qty_per_serving"]:
        if col in dings.columns:
            dings[col] = pd.to_numeric(dings[col], errors="coerce")
    for col in ["calorie_goal","protein_goal"]:
        if col in goals.columns:
            goals[col] = pd.to_numeric(goals[col], errors="coerce")
    for col in ["qty","calories","protein"]:
        if col in logs.columns:
            logs[col] = pd.to_numeric(logs[col], errors="coerce")
    return foods, dishes, dings, goals, logs

def save_df(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False)

def food_key(row) -> str:
    return f"{row['food_name']} [{row['unit']}]"

def get_food_row(foods: pd.DataFrame, food_name: str, unit: str):
    m = (foods["food_name"]==food_name) & (foods["unit"]==unit)
    if not m.any():
        return None
    return foods[m].iloc[0]

def compute_dish_base(dish_name: str, dishes: pd.DataFrame, dings: pd.DataFrame, foods: pd.DataFrame) -> Tuple[float,float]:
    """Return (calories_per_serving, protein_per_serving) for a dish.
       Uses override if present. Else sums ingredients per serving."""
    md = dishes[dishes["dish_name"]==dish_name]
    if md.empty:
        return 0.0, 0.0
    row = md.iloc[0]
    if pd.notna(row.get("cal_override")) and pd.notna(row.get("protein_override")):
        return float(row["cal_override"]), float(row["protein_override"])
    # Sum ingredients
    use = dings[dings["dish_name"]==dish_name]
    total_c = 0.0
    total_p = 0.0
    for _, ing in use.iterrows():
        frow = get_food_row(foods, ing["ingredient_food_name"], ing["ingredient_unit"])
        if frow is None:
            continue  # missing ingredient definition, skip
        qty = float(ing["ingredient_qty_per_serving"] or 0)
        total_c += qty * float(frow["cal_per_unit"] or 0)
        total_p += qty * float(frow["protein_per_unit"] or 0)
    return total_c, total_p

def get_goal_for_date(goals: pd.DataFrame, day: date):
    s = goals[goals["date"]==day.isoformat()]
    if s.empty:
        return None, None
    r = s.iloc[0]
    return float(r["calorie_goal"]), float(r["protein_goal"])

def upsert_goal(goals: pd.DataFrame, day: date, cal_goal: float, prot_goal: float) -> pd.DataFrame:
    idx = goals.index[goals["date"]==day.isoformat()].tolist()
    if idx:
        goals.loc[idx[0],"calorie_goal"] = cal_goal
        goals.loc[idx[0],"protein_goal"] = prot_goal
    else:
        goals.loc[len(goals)] = [day.isoformat(), cal_goal, prot_goal]
    return goals

def add_log_entry(logs: pd.DataFrame, day: date, meal: str, typ: str, name: str, unit: str, qty: float, cal: float, prot: float) -> pd.DataFrame:
    logs.loc[len(logs)] = [day.isoformat(), meal, typ, name, unit, qty, cal, prot]
    return logs

def daily_totals(logs: pd.DataFrame, day: date):
    d = logs[logs["date"]==day.isoformat()]
    return float(d["calories"].sum()), float(d["protein"].sum())

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
    unsafe_allow_html=True
)

foods, dishes, dings, goals, logs = load_all()

st.title("Shoku 🍱")

tabs = st.tabs(["Log", "Day View", "Dashboard", "Master Data"])

# --------- Tab 1: Log ---------
with tabs[0]:
    st.subheader("Add entry")
    c1, c2 = st.columns([1,1])
    with c1:
        log_date = st.date_input("Date", value=date.today())
        meal = st.selectbox("Meal", ["Breakfast","Lunch","Dinner","Snacks"], index=0)
        entry_type = st.radio("Type", ["Food","Dish"], horizontal=True)
    with c2:
        qty = st.number_input("Quantity", min_value=0.0, step=1.0, value=1.0)

    if entry_type == "Food":
        food_names = sorted(foods["food_name"].unique().tolist())
        if not food_names:
            st.info("Add foods in Master Data first.")
        else:
            f_name = st.selectbox("Food", food_names)
            units = sorted(foods[foods["food_name"]==f_name]["unit"].unique().tolist())
            unit = st.selectbox("Unit", units)
            frow = get_food_row(foods, f_name, unit)
            if frow is not None:
                cal_per = float(frow["cal_per_unit"] or 0)
                prot_per = float(frow["protein_per_unit"] or 0)
                est_c = qty * cal_per
                est_p = qty * prot_per
                st.metric("Calories (est.)", f"{est_c:.0f}")
                st.metric("Protein (g, est.)", f"{est_p:.1f}")
                if st.button("Add to log", type="primary", use_container_width=True):
                    logs = add_log_entry(logs, log_date, meal, "food", f_name, unit, qty, est_c, est_p)
                    save_df(logs, LOGS_CSV)
                    st.success("Entry added.")
            else:
                st.warning("Food+unit not found.")

    else:  # Dish
        dish_names = sorted(dishes["dish_name"].unique().tolist())
        if not dish_names:
            st.info("Add dishes in Master Data first.")
        else:
            d_name = st.selectbox("Dish", dish_names)
            base_c, base_p = compute_dish_base(d_name, dishes, dings, foods)
            # servings
            servings_row = dishes[dishes["dish_name"]==d_name]
            per_serv = 1.0
            if not servings_row.empty and pd.notna(servings_row.iloc[0].get("servings")):
                per_serv = float(servings_row.iloc[0]["servings"] or 1.0)
            # interpret qty as "servings"
            est_c = qty * base_c
            est_p = qty * base_p
            st.metric("Calories per serving", f"{base_c:.0f}")
            st.metric("Protein per serving (g)", f"{base_p:.1f}")
            st.metric("Calories (this entry)", f"{est_c:.0f}")
            st.metric("Protein (this entry, g)", f"{est_p:.1f}")
            if st.button("Add to log", type="primary", use_container_width=True):
                logs = add_log_entry(logs, log_date, meal, "dish", d_name, "serving", qty, est_c, est_p)
                save_df(logs, LOGS_CSV)
                st.success("Entry added.")

# --------- Tab 2: Day View ---------
with tabs[1]:
    st.subheader("Browse a day")
    colA, colB = st.columns([1,1])
    with colA:
        view_date = st.date_input("Pick a date", value=date.today(), key="view_date")
    with colB:
        st.write("Daily goals")

        # single global toggle (controls all past edits)
        st.session_state.allow_edit_past = st.checkbox(
            "Allow editing past goals",
            value=st.session_state.allow_edit_past,
            help="If off, past dates cannot be edited anywhere."
        )
        allow = st.session_state.allow_edit_past

        gcal, gprot = get_goal_for_date(goals, view_date)

        if gcal is None or gprot is None:
            d_cal = st.number_input("Calorie goal", min_value=0.0, step=50.0, value=1800.0, key="gcal_new")
            d_prot = st.number_input("Protein goal", min_value=0.0, step=5.0, value=120.0, key="gprot_new")
            disabled = (view_date < date.today() and not allow)
            if st.button("Save goal for this date", disabled=disabled):
                if disabled:
                    st.error("Editing past goals is disabled. Enable it above.")
                else:
                    goals = upsert_goal(goals, view_date, d_cal, d_prot)
                    save_df(goals, GOALS_CSV)
                    st.success("Goal saved.")
        else:
            st.metric("Goal calories", f"{gcal:.0f}")
            st.metric("Goal protein (g)", f"{gprot:.0f}")

            # inline editor
            d_cal = st.number_input("Edit calorie goal", min_value=0.0, step=50.0, value=float(gcal), key="gcal_edit")
            d_prot = st.number_input("Edit protein goal", min_value=0.0, step=5.0, value=float(gprot), key="gprot_edit")
            disabled = (view_date < date.today() and not allow)
            if st.button("Update goal", disabled=disabled):
                if disabled:
                    st.error("Editing past goals is disabled. Enable it above.")
                else:
                    goals = upsert_goal(goals, view_date, d_cal, d_prot)
                    save_df(goals, GOALS_CSV)
                    st.success("Goal updated.")

        

    day_logs = logs[logs["date"]==view_date.isoformat()].copy()
    if day_logs.empty:
        st.info("No entries for this date.")
    else:
        # Show grouped by meal
        for meal_name in ["Breakfast","Lunch","Dinner","Snacks"]:
            sub = day_logs[day_logs["meal"]==meal_name]
            if sub.empty:
                continue
            st.markdown(f"### {meal_name}")
            # mandatory list with per-item breakdown
            show = sub[["type","name","unit","qty","calories","protein"]].copy()
            show = show.rename(columns={
                "type":"Type", "name":"Item", "unit":"Unit", "qty":"Qty",
                "calories":"Calories", "protein":"Protein (g)"
            })
            st.dataframe(show, hide_index=True, use_container_width=True)
        tot_c, tot_p = daily_totals(logs, view_date)
        st.markdown("### Daily totals")
        m1, m2, m3 = st.columns(3)
        m1.metric("Calories", f"{tot_c:.0f}")
        m2.metric("Protein (g)", f"{tot_p:.1f}")
        if gcal is not None and gprot is not None:
            ok_c = tot_c <= gcal
            ok_p = tot_p >= gprot
            m3.metric("Status", f"{'Under calories' if ok_c else 'Over calories'} | {'Protein met' if ok_p else 'Protein not met'}")

# --------- Tab 3: Dashboard ---------
with tabs[2]:
    st.subheader("Summary")
    if logs.empty:
        st.info("No data yet.")
    else:
        # Join logs with goals by date
        agg = logs.groupby("date").agg(calories=("calories","sum"), protein=("protein","sum")).reset_index()
        goals_join = goals.rename(columns={"date":"date"})
        merged = pd.merge(agg, goals_join, on="date", how="left")
        # Flags
        merged["protein_met"] = merged["protein"] >= merged["protein_goal"]
        merged["under_cal"] = merged["calories"] <= merged["calorie_goal"]
        # Counts
        days_with_goals = merged.dropna(subset=["calorie_goal","protein_goal"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Days logged", f"{len(agg)}")
        c2.metric("Protein goal met (days)", f"{int(days_with_goals['protein_met'].sum())}")
        c3.metric("Under calorie budget (days)", f"{int(days_with_goals['under_cal'].sum())}")
        st.markdown("#### Per-day view")
        st.dataframe(merged.fillna("—"), use_container_width=True)

# --------- Tab 4: Master Data ---------
with tabs[3]:
    st.subheader("Foods (food + unit is unique)")
    with st.expander("Add food"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: f_name = st.text_input("Food name")
        with c2: unit = st.text_input("Unit (e.g., g, ml, pc, bowl, tbsp)")
        with c3: cal_per = st.number_input("Calories per unit", min_value=0.0, step=1.0)
        with c4: prot_per = st.number_input("Protein per unit (g)", min_value=0.0, step=0.1)
        if st.button("Save food"):
            if f_name and unit:
                exists = (foods["food_name"]==f_name) & (foods["unit"]==unit)
                if exists.any():
                    st.warning("Food with this unit already exists.")
                else:
                    foods.loc[len(foods)] = [f_name, unit, cal_per, prot_per]
                    save_df(foods, FOODS_CSV)
                    st.success("Food saved.")
            else:
                st.error("Name and unit required.")

    st.dataframe(foods.assign(key=foods.apply(food_key, axis=1)), use_container_width=True)


    st.markdown("#### Delete a food")
    if not foods.empty:
        fdel = st.selectbox("Select food to delete", foods.apply(food_key, axis=1).tolist())

        # Preview how many logs/ingredients will be affected
        frow = foods[foods.apply(food_key, axis=1)==fdel].iloc[0]
        fname, funit = frow["food_name"], frow["unit"]
        affected_logs = logs[(logs["type"]=="food") & (logs["name"]==fname) & (logs["unit"]==funit)]
        affected_ings = dings[(dings["ingredient_food_name"]==fname) & (dings["ingredient_unit"]==funit)]
        st.warning(f"Deleting **{fdel}** will remove {len(affected_logs)} log entries and {len(affected_ings)} dish ingredient references.")

        confirm_name = st.text_input("Type the exact food name+unit to confirm", key="confirm_food")
        if st.button("Delete food", key="delete_food_button"):
            if confirm_name.strip() == fdel:
                logs = logs.drop(affected_logs.index)
                dings = dings.drop(affected_ings.index)
                foods = foods.drop(frow.name)

                save_df(foods, FOODS_CSV)
                save_df(dings, DISH_ING_CSV)
                save_df(logs, LOGS_CSV)
                st.success(f"Deleted food {fdel}")
            else:
                st.error("Confirmation did not match. No delete.")


    st.subheader("Dishes")
    with st.expander("Add / update dish"):
        dname = st.text_input("Dish name")
        col1, col2, col3 = st.columns(3)
        with col1:
            cal_o = st.number_input("Calorie override (optional)", min_value=0.0, step=1.0, value=0.0)
        with col2:
            prot_o = st.number_input("Protein override (g, optional)", min_value=0.0, step=0.1, value=0.0)
        with col3:
            servings = st.number_input("Servings definition", min_value=1.0, step=1.0, value=1.0, help="Use 1 unless you need a different base serving size.")
        if st.button("Save dish"):
            if dname:
                exists = dishes["dish_name"]==dname
                calv = cal_o if cal_o > 0 else None
                protv = prot_o if prot_o > 0 else None
                if exists.any():
                    idx = dishes.index[exists][0]
                    dishes.loc[idx, ["cal_override","protein_override","servings"]] = [calv, protv, servings]
                else:
                    dishes.loc[len(dishes)] = [dname, calv, protv, servings]
                save_df(dishes, DISHES_CSV)
                st.success("Dish saved.")
            else:
                st.error("Dish name required.")

    with st.expander("Add ingredient to dish (for computed dishes)"):
        if dishes.empty or foods.empty:
            st.info("Add at least one dish and one food first.")
        else:
            dsel = st.selectbox("Dish", sorted(dishes["dish_name"].tolist()))
            fsel = st.selectbox("Ingredient food", sorted(foods["food_name"].unique().tolist()))
            units = sorted(foods[foods["food_name"]==fsel]["unit"].unique().tolist())
            u_sel = st.selectbox("Ingredient unit", units)
            qty = st.number_input("Qty per serving", min_value=0.0, step=1.0, value=0.0)
            if st.button("Add ingredient"):
                if qty <= 0:
                    st.error("Quantity must be > 0.")
                else:
                    dings.loc[len(dings)] = [dsel, fsel, u_sel, qty]
                    save_df(dings, DISH_ING_CSV)
                    st.success("Ingredient added.")

    st.markdown("#### Current dishes")
    if dishes.empty:
        st.info("No dishes yet.")
    else:
        preview = []
        for dname in sorted(dishes["dish_name"].tolist()):
            base_c, base_p = compute_dish_base(dname, dishes, dings, foods)
            preview.append({"dish_name": dname, "calories_per_serving": round(base_c,1), "protein_per_serving": round(base_p,1)})
        st.dataframe(pd.DataFrame(preview), use_container_width=True)

    st.markdown("#### Delete a dish")
    if not dishes.empty:
        ddel = st.selectbox("Select dish to delete", sorted(dishes["dish_name"].tolist()))

        affected_logs = logs[(logs["type"]=="dish") & (logs["name"]==ddel)]
        affected_ings = dings[dings["dish_name"]==ddel]
        st.warning(f"Deleting **{ddel}** will remove {len(affected_logs)} log entries and {len(affected_ings)} ingredients.")

        confirm_dish = st.text_input("Type the exact dish name to confirm", key="confirm_dish")
        if st.button("Delete dish", key="delete_dish_button"):
            if confirm_dish.strip() == ddel:
                logs = logs.drop(affected_logs.index)
                dishes = dishes[dishes["dish_name"]!=ddel]
                dings = dings.drop(affected_ings.index)

                save_df(dishes, DISHES_CSV)
                save_df(dings, DISH_ING_CSV)
                save_df(logs, LOGS_CSV)
                st.success(f"Deleted dish {ddel}")
            else:
                st.error("Confirmation did not match. No delete.")



    st.subheader("Goals (advanced)")

    with st.expander("Set or update goal for a single date"):
        day = st.date_input("Date for goal", value=date.today(), key="goal_date")
        cal_goal = st.number_input("Calorie goal", min_value=0.0, step=50.0, value=1800.0, key="cal_goal2")
        prot_goal = st.number_input("Protein goal", min_value=0.0, step=5.0, value=120.0, key="prot_goal2")
        if st.button("Save goal (single date)"):
            if day < date.today() and not st.session_state.allow_edit_past:
                st.error("Editing past goals is disabled. Enable it in Day View.")
            else:
                goals = upsert_goal(goals, day, cal_goal, prot_goal)
                save_df(goals, GOALS_CSV)
                st.success("Goal saved.")

    with st.expander("Bulk set goals for a date range"):
        r1, r2 = st.columns(2)
        with r1:
            start_day = st.date_input("Start date", value=date.today(), key="bulk_start")
        with r2:
            end_day = st.date_input("End date (inclusive)", value=date.today(), key="bulk_end")
        bcal = st.number_input("Calorie goal (range)", min_value=0.0, step=50.0, value=1800.0, key="bulk_cal")
        bprot = st.number_input("Protein goal (range)", min_value=0.0, step=5.0, value=120.0, key="bulk_prot")

        if st.button("Apply to range"):
            if (end_day < start_day):
                st.error("End date must be on or after start date.")
            elif (end_day < date.today() or start_day < date.today()) and not st.session_state.allow_edit_past:
                st.error("Editing past goals is disabled. Enable it in Day View.")
            else:
                cur = start_day
                from datetime import timedelta
                while cur <= end_day:
                    goals = upsert_goal(goals, cur, bcal, bprot)
                    cur += timedelta(days=1)
                save_df(goals, GOALS_CSV)
                st.success("Goals applied to range.")

    st.markdown("#### All goals")
    st.dataframe(goals.sort_values("date"), use_container_width=True)