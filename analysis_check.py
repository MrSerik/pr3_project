"""
analysis_check.py - часть 4: проверка калибровки в контрольных точках (таблица 4).

check.csv записывается logger.py в режиме check ПОСЛЕ того, как в скетч вписаны
A_CAL и B_CAL. В каждой строке есть raw (до калибровки) и cal (после).
"""
import numpy as np
import pandas as pd

from common import data_path, fmt, save_table, setup

V = setup()
U = V["unit"]
df = pd.read_csv(data_path("check.csv"))

rows = []
for ref, d in df.groupby("ref"):
    rows.append({
        f"x_эт, {U}": ref,
        f"x̄ raw, {U}": round(d["raw"].mean(), 3),
        f"Δ до, {U}": round(d["raw"].mean() - ref, 3),
        f"x̄ cal, {U}": round(d["cal"].mean(), 3),
        f"Δ после, {U}": round(d["cal"].mean() - ref, 3),
        f"s raw, {U}": round(d["raw"].std(ddof=1), 3),
        f"s cal, {U}": round(d["cal"].std(ddof=1), 3),
    })
t4 = pd.DataFrame(rows)
print(f"\nТаблица 4 - Проверка калибровки в контрольных точках (вариант {V['number']})")
print(t4.to_string(index=False))
save_table(t4, "table4_check.csv")

d_before = np.abs(t4[f"Δ до, {U}"]).mean()
d_after = np.abs(t4[f"Δ после, {U}"]).mean()
print(f"\nСредний |Δ| до калибровки:    {fmt(d_before)} {U}")
print(f"Средний |Δ| после калибровки: {fmt(d_after)} {U}  (уменьшение в "
      f"{fmt(d_before / d_after, 1)} раза)")
print(f"СКО s до и после почти одинаково ({fmt(t4[f's raw, {U}'].mean())} и "
      f"{fmt(t4[f's cal, {U}'].mean())} {U}):")
print("  калибровка убирает СИСТЕМАТИЧЕСКУЮ погрешность (смещение), но не СЛУЧАЙНУЮ (шум).")
print("  Шум уменьшают усреднением серии (ε ~ 1/√n) или фильтрацией - часть 5.")
