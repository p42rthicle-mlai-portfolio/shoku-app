Shoku (Food Tracker) (Streamlit v0)

Quick start
-----------
1) Install Python 3.10+.
2) In a terminal:
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m streamlit run app.py

Data model
----------
- data/foods.csv: food_name, unit, base_qty, calories_base, protein_base, cal_per_unit, protein_per_unit
- data/dishes.csv: dish_name, cal_override, protein_override, servings, yield_qty, yield_unit
- data/dish_ingredients.csv: dish_name, ingredient_food_name, ingredient_unit, ingredient_qty_per_serving
- data/goals.csv: date (YYYY-MM-DD), calorie_goal, protein_goal
- data/logs.csv: date, meal, type (food|dish), name, unit, qty, calories, protein

Notes
-----
- Food+unit is unique (e.g., Butter [g] and Butter [tbsp] are different).
- Foods are entered with a base quantity, such as nutrition per 100g or 250ml. Per-unit values are derived automatically.
- Dishes can be fixed (override) like Tea (fixed), or computed from ingredients like Veg Kebab.
- Ingredient dishes can store a final cooked/output quantity, such as 850g dal, so logs can use custom weights instead of servings.
- Goals are stored per date to lock history. You can prevent editing past goals from the Day View tab.
- Use the 'Master Data' tab to add foods, dishes, and ingredients. Use 'Log' to add daily entries.
