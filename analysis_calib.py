"""
analysis_calib.py - часть 3: обработка calib.csv (листинг 3, доработанный).

Что делает:
  1) по каждой эталонной точке считает x̄, s, Δ, δ (или γ), ε - формулы (3.6)-(3.8);
  2) печатает таблицу 3 и пример расчёта для одной точки (для отчёта);
  3) оценивает гистерезис (прямой и обратный проходы);
  4) МНК: x_кал = a·x_изм + b, R² - формулы (3.4), (3.5);
  5) строит рисунки: статическая характеристика и погрешность Δ до/после калибровки.

Результаты: папка results/varNN (таблицы .csv открываются в Excel, рисунки .png).
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import (C_CAL, C_MA, C_MED, C_REF, data_path, finish, fmt, save_table,
                    setup, t_student)

V = setup()
U = V["unit"]
df = pd.read_csv(data_path("calib.csv"))


def point_stats(d):
    """Статистика по одной серии измерений в точке: формулы (3.6)-(3.8)."""
    ref = float(d["ref"].iloc[0])
    x = d["raw"].to_numpy()
    n = len(x)
    mean = x.mean()
    s = x.std(ddof=1)                         # СКО, деление на (n - 1)
    delta = mean - ref                        # абсолютная погрешность
    delta_rel = 100 * delta / ref if ref != 0 else np.nan
    gamma = 100 * delta / V["x_n"]            # приведённая
    eps = t_student(n) * s / np.sqrt(n)       # доверительная граница, P = 0,95
    return pd.Series(dict(ref=ref, n=n, mean=mean, s=s, delta=delta,
                          delta_rel=delta_rel, gamma=gamma, eps=eps))


tabs = {}
for p in ["прямой", "обратный"]:
    part = df[df["pass"] == p]
    if len(part):
        tabs[p] = pd.DataFrame([point_stats(d) for _, d in part.groupby("ref")])
fwd = tabs["прямой"]
rev = tabs.get("обратный")

# ---------- Таблица 3 (по прямому проходу, n = 20 в каждой точке) ----------
rel_col, rel_name = ("gamma", "γ, %") if V["use_gamma"] else ("delta_rel", "δ, %")
t3 = pd.DataFrame({
    "№": range(1, len(fwd) + 1),
    f"x_эт, {U}": fwd["ref"],
    f"x̄, {U}": fwd["mean"].round(3),
    f"s, {U}": fwd["s"].round(3),
    f"Δ, {U}": fwd["delta"].round(3),
    rel_name: fwd[rel_col].round(2),
    f"ε, {U}": fwd["eps"].round(3),
})
print(f"\nТаблица 3 - Результаты статической калибровки (вариант {V['number']}, "
      f"{V['sensor']}, прямой проход)")
print(t3.to_string(index=False))
save_table(t3, "table3_calibration.csv")

# ---------- Пример расчёта для одной точки (вставить в отчёт) ----------
k = len(fwd) // 2
r = fwd.iloc[k]
x = df[(df["pass"] == "прямой") & (df["ref"] == r["ref"])]["raw"].to_numpy()
n = int(r["n"])
t = t_student(n)
print(f"\nПример расчёта для точки x_эт = {fmt(r['ref'], 0)} {U}:")
print(f"  x̄ = (1/{n})·Σxi = {fmt(x.sum(), 2)} / {n} = {fmt(r['mean'])} {U}")
print(f"  s = √(Σ(xi − x̄)² / (n − 1)) = √({fmt(((x - r['mean'])**2).sum(), 4)} / {n - 1})"
      f" = {fmt(r['s'])} {U}")
print(f"  Δ = x̄ − x_эт = {fmt(r['mean'])} − {fmt(r['ref'], 0)} = {fmt(r['delta'])} {U}")
if V["use_gamma"]:
    print(f"  γ = Δ / X_N · 100 % = {fmt(r['delta'])} / {V['x_n']} · 100 % = {fmt(r['gamma'], 2)} %")
else:
    print(f"  δ = Δ / x_эт · 100 % = {fmt(r['delta'])} / {fmt(r['ref'], 0)} · 100 % = "
          f"{fmt(r['delta_rel'], 2)} %")
print(f"  ε = t·s/√n = {fmt(t)} · {fmt(r['s'])} / √{n} = {fmt(r['eps'])} {U}")
print(f"  Результат: x = {fmt(r['mean'], 2)} ± {fmt(r['eps'], 2)} {U}, P = 0,95")

# ---------- Гистерезис и воспроизводимость ----------
if rev is not None:
    hyst = pd.DataFrame({
        f"x_эт, {U}": fwd["ref"],
        f"x̄ прямой, {U}": fwd["mean"].round(3),
        f"x̄ обратный, {U}": rev["mean"].round(3),
        f"H = x̄обр − x̄пр, {U}": (rev["mean"] - fwd["mean"]).round(3),
    })
    print("\nГистерезис (разность показаний обратного и прямого проходов):")
    print(hyst.to_string(index=False))
    h = (rev["mean"] - fwd["mean"]).to_numpy()
    print(f"  средний H = {fmt(h.mean())} {U}, максимальный |H| = {fmt(np.abs(h).max())} {U}")
    save_table(hyst, "hysteresis.csv")

# ---------- МНК: x_эт = a·x̄ + b ----------
# Для калибровки берём среднее двух проходов (середину петли гистерезиса).
xm = fwd["mean"].to_numpy() if rev is None else (fwd["mean"].to_numpy() + rev["mean"].to_numpy()) / 2
y = fwd["ref"].to_numpy()
nn = len(xm)
Sx, Sy, Sxy, Sxx = xm.sum(), y.sum(), (xm * y).sum(), (xm**2).sum()
a = (nn * Sxy - Sx * Sy) / (nn * Sxx - Sx**2)          # формула (3.5)
b = y.mean() - a * xm.mean()
fit = a * xm + b
r2 = 1 - ((y - fit) ** 2).sum() / ((y - y.mean()) ** 2).sum()
print("\nМетод наименьших квадратов (формула 3.5), n =", nn, "точек:")
print(f"  Σx = {fmt(Sx, 3)};  Σy = {fmt(Sy, 1)};  Σxy = {fmt(Sxy, 2)};  Σx² = {fmt(Sxx, 2)}")
print(f"  a = ({nn}·{fmt(Sxy, 2)} − {fmt(Sx, 3)}·{fmt(Sy, 1)}) / ({nn}·{fmt(Sxx, 2)} − "
      f"{fmt(Sx, 3)}²) = {fmt(a, 4)}")
print(f"  b = ȳ − a·x̄ = {fmt(y.mean(), 2)} − {fmt(a, 4)}·{fmt(xm.mean(), 3)} = {fmt(b, 4)}")
print(f"  R² = {r2:.5f}".replace(".", ","))
print("\n>>> Впишите в скетч Arduino (часть 4):")
print(f"const float A_CAL = {a:.4f};")
print(f"const float B_CAL = {b:.4f};")
pd.DataFrame({"A_CAL": [round(a, 4)], "B_CAL": [round(b, 4)], "R2": [round(r2, 5)]}) \
    .to_csv(data_path("calib_coeffs.csv"), index=False)

# ---------- Рисунок: статическая характеристика ----------
fig, ax = plt.subplots(1, 2, figsize=(11, 4.8))
lo, hi = min(y.min(), 0), y.max() * 1.05
ax[0].plot([lo, hi], [lo, hi], "--", color=C_REF, lw=1.2, label="идеальная y = x")
ax[0].errorbar(fwd["ref"], fwd["mean"], yerr=fwd["eps"], fmt="o", ms=6, capsize=3,
               color=C_MA, label="прямой проход (x̄ ± ε)")
if rev is not None:
    ax[0].errorbar(rev["ref"], rev["mean"], yerr=rev["eps"], fmt="s", ms=5, capsize=3,
                   color=C_MED, mfc="white", label="обратный проход (x̄ ± ε)")
ax[0].set(xlabel=f"эталонное значение x_эт, {U}", ylabel=f"показание датчика x̄, {U}",
          title="Статическая характеристика")
ax[0].legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=8.5)

# ---------- Рисунок: погрешность до и после калибровки ----------
ax[1].axhline(0, color=C_REF, lw=0.8)
ax[1].errorbar(fwd["ref"], fwd["delta"], yerr=fwd["eps"], fmt="o-", ms=6, capsize=3,
               color=C_MA, label="до калибровки, прямой")
if rev is not None:
    ax[1].errorbar(rev["ref"], rev["delta"], yerr=rev["eps"], fmt="s-", ms=5, capsize=3,
                   color=C_MED, mfc="white", label="до калибровки, обратный")
ax[1].plot(y, fit - y, "D-", ms=6, color="#1baf7a", label="после калибровки (a·x̄ + b − x_эт)")
ax[1].set(xlabel=f"эталонное значение x_эт, {U}", ylabel=f"Δ, {U}",
          title="Абсолютная погрешность")
ax[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=8.5)
fig.suptitle(f"Вариант {V['number']}: {V['sensor']}.  a = {fmt(a, 4)}, b = {fmt(b, 4)}, "
             f"R² = {fmt(r2, 5)}", fontsize=10, color="#5a5a55")
fig.tight_layout()
finish(fig, "fig_calibration.png")
