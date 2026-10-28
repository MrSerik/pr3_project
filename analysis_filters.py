"""
analysis_filters.py - часть 5: сравнение фильтров по dynamic.csv (таблица 5).

Для каждого сигнала считает:
  - СКО на установившемся участке до ступеньки (не менее 2 с);
  - время нарастания: от начала скачка до достижения 90 % нового значения;
  - удаление выбросов: во сколько раз фильтр уменьшил каждый выброс.
Сравнивает с теорией (п. 4.5) и строит графики.

Сигнал «без фильтра» - это cal: именно он поступает на вход фильтров в скетче
(cal = A_CAL·raw + B_CAL, то есть raw после калибровки).

Дополнительный опыт (п. 6): фильтры с другими N и α пересчитываются здесь же
по тому же записанному сигналу - функции точно повторяют код Arduino.
Значения задайте ниже в ALT_N_MA и ALT_ALPHA.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import (C_EMA, C_MA, C_MED, C_RAW, C_REF, data_path, exp_filter, finish,
                    fmt, median5, moving_average, save_table, setup)

V = setup()
U = V["unit"]
ALT_N_MA = V["n_ma"] + 4          # дополнительный опыт: большее окно
ALT_ALPHA = V["alpha"] / 2        # дополнительный опыт: меньшее α

df = pd.read_csv(data_path("dynamic.csv"))
t = (df["t_ms"] - df["t_ms"].iloc[0]).to_numpy() / 1000.0
dt = np.median(np.diff(t))                         # период опроса, с
x = df["cal"].to_numpy()

signals = {
    "Без фильтра (cal)": ("–", x, C_RAW),
    "Скользящее среднее": (f"N = {V['n_ma']}", df["ma"].to_numpy(), C_MA),
    "Медианный": ("окно 5", df["med"].to_numpy(), C_MED),
    "Экспоненциальный": (f"α = {fmt(V['alpha'], 2)}", df["ema"].to_numpy(), C_EMA),
}
extra = {
    "Доп. опыт: скольз. среднее": (f"N = {ALT_N_MA}", moving_average(x, ALT_N_MA), C_MA),
    "Доп. опыт: экспоненциальный": (f"α = {ALT_ALPHA:g}".replace(".", ","), exp_filter(x, ALT_ALPHA), C_EMA),
}

# ---------- поиск ступеньки ----------
# широкая медиана (11 точек = 0,55 с) убирает выбросы, но сохраняет ступеньку
base = pd.Series(x).rolling(11, center=True, min_periods=1).median().to_numpy()
j = int(np.argmax(np.abs(np.diff(base))))          # место самого резкого изменения
tj = t[j]
with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
    __import__("warnings").simplefilter("ignore")     # пустой участок -> nan, проверим ниже
    L0 = np.median(x[(t > 0.5) & (t < tj - 0.5)])      # уровень до ступеньки
    L1 = np.median(x[(t > tj + 1.0) & (t < tj + 3.0)]) # уровень после ступеньки
noise = 1.4826 * np.median(np.abs(x - base))
if not np.isfinite(L0 + L1) or abs(L1 - L0) < max(10 * noise, 1.0):
    raise SystemExit("Ступенька в записи не найдена. Повторите logger.py dyn: по подсказке "
                     "на 5-й секунде резко переставьте экран (поверните ручку).")
z = (x - L0) / (L1 - L0)                           # нормированный сигнал: 0 -> 1
k0 = np.where((t > tj - 1.0) & (z > 0.10))[0][0]   # начало скачка (10 % по cal)
t0 = t[k0]

# ---------- выбросы: ищем по ВСЕЙ записи (и до, и после ступеньки) ----------
# Выброс = точка, далеко ушедшая от местного уровня base. На самом фронте
# ступеньки base отстаёт от сигнала, поэтому там выбросы не ищем.
dev = x - base
step_zone = (t > t0 - 0.5) & (t < t0 + 1.0)
sigma = 1.4826 * np.median(np.abs(dev[~step_zone]))    # устойчивая оценка шума
thr = max(6 * sigma, 0.10 * abs(L1 - L0))
far = ~step_zone & (np.abs(dev) > thr)
events = []
k = 0
while k < len(x):
    if far[k]:
        k1 = k
        while k1 + 1 < len(x) and far[k1 + 1]:
            k1 += 1
        events.append((k, k1))
        k = k1 + 1
    else:
        k += 1

# ---------- установившийся участок: до ступеньки и БЕЗ выбросов ----------
TAIL = 12                                  # «хвост» фильтра после выброса, отсчётов
# экспоненциальный фильтр «помнит» выброс долго: до 2 % остатка нужно ln(0,02)/ln(1 − α) отсчётов
TAIL_SKO = max(TAIL, ALT_N_MA, int(np.ceil(np.log(0.02) / np.log(1 - min(V["alpha"], ALT_ALPHA)))))
bad = np.zeros(len(x), bool)
for a, b in events:
    bad[a:min(len(x), b + TAIL_SKO + 1)] = True
cand = (t >= 1.0) & (t <= t0 - 0.3) & ~bad
best, cur = (0, -1), None                  # самый длинный непрерывный кусок
for k in range(len(x)):
    if cand[k]:
        cur = k if cur is None else cur
        if k - cur > best[1] - best[0]:
            best = (cur, k)
    else:
        cur = None
k_end = best[1]
k_start = max(best[0], int(np.searchsorted(t, t[k_end] - 3.0)))   # не больше 3 с
steady = np.zeros(len(x), bool)
steady[k_start:k_end + 1] = True
steady_len = t[k_end] - t[k_start]


def evaluate(y, f):
    sko = y[steady].std(ddof=1)
    zy = (y - L0) / (L1 - L0)
    k90 = np.where((t >= t0) & (zy >= 0.9))[0]
    rise = t[k90[0]] - t0 if len(k90) else np.nan
    ratios = []
    for a, b in events:
        # Сравниваем фильтр на реальном сигнале и на том же сигнале, где этот выброс
        # заменён местным уровнем. Разница - ровно то, что фильтр пропустил от выброса.
        x_clean = x.copy()
        x_clean[a:b + 1] = base[a:b + 1]
        effect = np.abs(f(x) - f(x_clean))[a:]
        peak_raw = np.abs(dev[a:b + 1]).max()
        ratios.append(effect.max() / peak_raw)
    return sko, rise, ratios


funcs = {   # те же фильтры, что в скетче (common.py) - для оценки выбросов
    "Без фильтра (cal)": lambda v: v,
    "Скользящее среднее": lambda v: moving_average(v, V["n_ma"]),
    "Медианный": median5,
    "Экспоненциальный": lambda v: exp_filter(v, V["alpha"]),
    "Доп. опыт: скольз. среднее": lambda v: moving_average(v, ALT_N_MA),
    "Доп. опыт: экспоненциальный": lambda v: exp_filter(v, ALT_ALPHA),
}
rows, res = [], {}
for name, (param, y, _) in {**signals, **extra}.items():
    sko, rise, ratios = evaluate(y, funcs[name])
    res[name] = (sko, rise, ratios)
    removed = sum(r < 0.05 for r in ratios)   # удалён = на выход прошло < 5 %
    if not events:
        verdict = "выбросов не найдено"
    elif removed == len(events):
        verdict = "да"
    elif removed:
        verdict = f"частично ({removed} из {len(events)})"
    else:
        verdict = "нет (сглажены)" if max(ratios) < 0.6 else "нет"
    rows.append({
        "Сигнал / фильтр": name, "Параметр": param,
        f"СКО, {U}": round(sko, 3),
        "Время нарастания до 90 %, с": round(rise, 2),
        "Остаток выбросов, %": " / ".join(f"{100 * r:.0f}" for r in ratios) or "–",
        "Выбросы удалены?": verdict,
    })
t5 = pd.DataFrame(rows)
print(f"\nТаблица 5 - Сравнение цифровых фильтров (вариант {V['number']}, {V['sensor']})")
print(f"Ступенька {fmt(L0, 2)} -> {fmt(L1, 2)} {U}, начало скачка t0 = {fmt(t0, 2)} с; "
      f"период опроса {fmt(dt * 1000, 0)} мс")
print(f"Установившийся участок {fmt(t[k_start], 2)}-{fmt(t[k_end], 2)} с "
      f"(длительность {fmt(steady_len, 1)} с, выбросы исключены)")
if steady_len < 2.0:
    print(f"  ВНИМАНИЕ: участок без выбросов до ступеньки короче 2 с. Повторите запись: "
          f"держите {V['step'][0]} {U} 4-5 с, выбросы делайте ПОСЛЕ ступеньки.")
if events:
    where = ", ".join(f"{fmt(t[a], 1)} с – {b - a + 1} отсч." for a, b in events)
    print(f"Найдено выбросов: {len(events)} (порог ±{fmt(thr, 2)} {U}): {where}")
else:
    print(f"Выбросов не найдено (порог ±{fmt(thr, 2)} {U} от местного уровня).")
    print("  Сделайте 2-3 коротких выброса: быстро проведите рукой перед датчиком "
          "(для потенциометра - рывок ручки на 30-40° и обратно).")
print("«Остаток выбросов» - какую долю каждого выброса фильтр пропустил на выход.\n")
print(t5.to_string(index=False))
save_table(t5, "table5_filters.csv")

# ---------- диагностика шума: быстрый шум или медленный дрейф? ----------
xs = x[steady]
s_total = xs.std(ddof=1)
s_fast = np.diff(xs).std(ddof=1) / np.sqrt(2)      # шум «от отсчёта к отсчёту»
print(f"\nШум на установившемся участке: СКО = {fmt(s_total)} {U}, "
      f"из них быстрый шум ≈ {fmt(s_fast)} {U}")
if s_total > 1.3 * s_fast:
    print("  ВНИМАНИЕ: СКО заметно больше быстрого шума - значит, сигнал медленно «плывёт»")
    print("  (экран держат в руке, датчик или ручка сдвигаются). Фильтры подавляют только")
    print("  быстрый шум, медленный дрейф они не уберут - отсюда K намного меньше теории.")
    print("  Закрепите экран/датчик и повторите запись.")

# ---------- сравнение с теорией п. 4.5 ----------
s0 = res["Без фильтра (cal)"][0]
rise0 = res["Без фильтра (cal)"][1]
print("\nСравнение с теорией (шум уменьшается в K раз, запаздывание в периодах опроса):")
for name, n_ma, alpha in [("Скользящее среднее", V["n_ma"], None),
                          ("Доп. опыт: скольз. среднее", ALT_N_MA, None),
                          ("Экспоненциальный", None, V["alpha"]),
                          ("Доп. опыт: экспоненциальный", None, ALT_ALPHA)]:
    k_meas = s0 / res[name][0]
    if n_ma:
        k_th, lag_th = np.sqrt(n_ma), (n_ma - 1) / 2
        what = f"N = {n_ma}"
    else:
        k_th, lag_th = np.sqrt((2 - alpha) / alpha), (1 - alpha) / alpha
        what = f"α = {fmt(alpha, 2)}"
    print(f"  {name:30s} {what:9s} K: теория {fmt(k_th, 2):>5s}, опыт {fmt(k_meas, 2):>5s};"
          f"  запаздывание теория ≈ {fmt(lag_th, 1)} период. = {fmt(lag_th * dt, 2)} с")
print("  (для экспоненциального фильтра K = √((2 − α)/α) - формула для белого шума)")
k_ma = s0 / res["Скользящее среднее"][0]
if k_ma < 0.6 * np.sqrt(V["n_ma"]):
    print("  ВНИМАНИЕ: фильтры подавили шум намного хуже теории. Возможные причины:")
    print("   - сигнал медленно плывёт (экран в руке, датчик сдвигается) - см. диагностику выше;")
    print("   - шум меньше шага квантования (для HC-SR04 ~0,02 см, для АЦП ~0,26°);")
    print("   - участок слишком короткий, СКО по нему оценивается грубо.")
print(f"  Время нарастания самого сигнала {fmt(rise0, 2)} с - это время перестановки экрана "
      "рукой; фильтр добавляет к нему своё запаздывание.")

# ---------- рисунки ----------
fig = plt.figure(figsize=(11, 7.5))
gs = fig.add_gridspec(2, 2, height_ratios=[1.1, 1])
ax = fig.add_subplot(gs[0, :])
for name, (param, y, c) in signals.items():
    lw, z_ = (1.2, 1) if c == C_RAW else (1.8, 2)
    ax.plot(t, y, color=c, lw=lw, zorder=z_, label=f"{name} {param if param != '–' else ''}")
ax.axvspan(t[steady][0], t[steady][-1], color="#e4e3dc", alpha=0.6, lw=0,
           label="установившийся участок (СКО)")
for a, b in events:
    ax.annotate(f"{b - a + 1} отсч.", (t[a], x[a]), textcoords="offset points",
                xytext=(6, 6 if x[a] > base[a] else -14), fontsize=8, color="#5a5a55")
ax.set(xlabel="время t, с", ylabel=f"значение, {U}",
       title=f"Вариант {V['number']}: ступенька {fmt(L0, 1)} → {fmt(L1, 1)} {U} и выбросы")
ax.margins(y=0.10)                          # место для подписей выбросов
ax.legend(loc="upper left", fontsize=8.5)   # до ступеньки верх графика свободен

# крупно: ступенька
ax2 = fig.add_subplot(gs[1, 0])
m = (t > t0 - 0.6) & (t < t0 + 2.2)
for name, (param, y, c) in signals.items():
    ax2.plot(t[m], y[m], "-o" if c == C_RAW else "-", ms=3, color=c,
             lw=1.2 if c == C_RAW else 1.8)
L90 = L0 + 0.9 * (L1 - L0)
ax2.axhline(L90, color=C_REF, lw=0.8, ls="--")
ax2.text(t[m][0], L90, " 90 % нового значения", va="bottom", fontsize=8, color="#5a5a55")
ax2.axvline(t0, color=C_REF, lw=0.8, ls=":")
ax2.set(xlabel="время t, с", ylabel=f"значение, {U}", title="Крупно: фронт ступеньки")

# крупно: выбросы
ax3 = fig.add_subplot(gs[1, 1])
if events:
    m = (t > t[events[0][0]] - 0.8) & (t < t[events[-1][1]] + 1.0)
    for name, (param, y, c) in signals.items():
        ax3.plot(t[m], y[m], "-o" if c == C_RAW else "-", ms=3, color=c,
                 lw=1.2 if c == C_RAW else 1.8)
else:
    ax3.text(0.5, 0.5, "выбросы не найдены", ha="center", va="center",
             transform=ax3.transAxes, color="#5a5a55")
ax3.set(xlabel="время t, с", ylabel=f"значение, {U}", title="Крупно: выбросы")
fig.tight_layout()
finish(fig, "fig_filters.png")

# ---------- сырые и обработанные данные: каждый тип обработки отдельно ----------
# Слева - вся запись, справа - крупно установившийся участок (там виден сам шум).
raw = df["raw"].to_numpy()
panels = [
    ("Сырые данные (raw) и после калибровки (cal)", None, None),
    ("Скользящее среднее", signals["Скользящее среднее"], "Скользящее среднее"),
    ("Медианный фильтр", signals["Медианный"], "Медианный"),
    ("Экспоненциальный фильтр", signals["Экспоненциальный"], "Экспоненциальный"),
]
zoom = steady
def zlim(*arrays):                                # пределы оси для крупного плана
    lo = min(a[zoom].min() for a in arrays)
    hi = max(a[zoom].max() for a in arrays)
    pad = 0.12 * (hi - lo) + 1e-6
    return lo - pad, hi + 3 * pad                  # сверху место для подписи
leg_loc = "upper left" if L1 > L0 else "lower left"   # до ступеньки этот угол свободен

fig, axs = plt.subplots(4, 2, figsize=(12, 12), sharex="col",
                        gridspec_kw={"width_ratios": [2.2, 1]})
for r, (title, sig, key) in enumerate(panels):
    for c in range(2):
        a_ = axs[r, c]
        if sig is None:                                    # строка 1: raw и cal
            a_.plot(t, raw, "-", color=C_RAW, lw=1.2, label="raw – как измерил датчик")
            a_.plot(t, x, "-", color=C_REF, lw=1.4, label="cal = A_CAL·raw + B_CAL")
        else:                                              # строки 2-4: cal и фильтр
            a_.plot(t, x, "-o", color=C_RAW, lw=0.9, ms=2.5 if c else 0,
                    label="cal – вход фильтра")
            a_.plot(t, sig[1], "-", color=sig[2], lw=2.0, label=f"{title}, {sig[0]}")
        if c == 0:
            a_.axvspan(t[zoom][0], t[zoom][-1], color="#e4e3dc", alpha=0.6, lw=0)
            for ea, eb in events:
                a_.axvspan(t[ea] - 0.05, t[eb] + 0.05, color="#fbe3d6", lw=0)
            a_.set_title(title, loc="left", fontsize=10.5)
            a_.legend(loc=leg_loc, fontsize=8.5)
            a_.margins(y=0.08)
        else:
            a_.set_xlim(t[zoom][0], t[zoom][-1])
            a_.set_ylim(*(zlim(raw, x) if sig is None else zlim(x)))
            a_.set_title("крупно: установившийся участок", loc="left", fontsize=9.5,
                         color="#5a5a55")
            if key is not None:
                sko, rise, ratios = res[key]
                info = (f"СКО {fmt(sko)} {U} (без фильтра {fmt(s0)})\n"
                        f"нарастание до 90 %: {fmt(rise, 2)} с\n"
                        f"выбросы: {t5.loc[t5['Сигнал / фильтр'] == key, 'Выбросы удалены?'].iloc[0]}")
            else:
                same = np.allclose(raw, x, atol=0.011)
                info = (f"СКО raw {fmt(raw[zoom].std(ddof=1))} {U}\n"
                        f"среднее raw {fmt(raw[zoom].mean(), 2)}, cal {fmt(x[zoom].mean(), 2)} {U}\n"
                        + ("калибровка не введена: A_CAL = 1, B_CAL = 0,\nпоэтому cal = raw"
                           if same else "калибровка сдвигает, шум не меняет"))
            a_.text(0.02, 0.97, info, transform=a_.transAxes, va="top", fontsize=8.5,
                    color="#3a3a36", bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff",
                                               ec="#d6d5cf", alpha=0.92))
        a_.set_ylabel(U)
axs[-1, 0].set_xlabel("время t, с")
axs[-1, 1].set_xlabel("время t, с")
fig.suptitle(f"Вариант {V['number']} ({V['sensor']}): сырые данные и каждый тип обработки. "
             "Серая полоса – установившийся участок, розовые – найденные выбросы",
             fontsize=10.5, color="#3a3a36")
fig.tight_layout()
finish(fig, "fig_raw_vs_filters.png")

# дополнительный опыт: компромисс «шум - запаздывание»
fig, ax = plt.subplots(figsize=(6.5, 4.4))
for name in res:
    if name == "Без фильтра (cal)":
        continue
    sko, rise, _ = res[name]
    c = {**signals, **extra}[name][2]
    mk = "s" if name.startswith("Доп") else "o"
    ax.plot(rise, sko, mk, ms=9, color=c, mfc="white" if mk == "s" else c, mew=2)
    label = f"{name.replace('Доп. опыт: ', '')}\n{({**signals, **extra})[name][0]}"
    if mk == "s":       # подписи доп. опыта - под точкой, чтобы не налезали
        ax.annotate(label, (rise, sko), textcoords="offset points", xytext=(0, -12),
                    ha="center", va="top", fontsize=8)
    else:
        ax.annotate(label, (rise, sko), textcoords="offset points", xytext=(8, -4), fontsize=8)
ax.plot(rise0, s0, "o", ms=9, color=C_RAW)
ax.annotate("без фильтра", (rise0, s0), textcoords="offset points", xytext=(8, -4), fontsize=8)
ax.set(xlabel="время нарастания до 90 %, с (запаздывание)",
       ylabel=f"СКО на установившемся участке, {U} (шум)",
       title="Компромисс «шум – запаздывание»\n● основной опыт   □ дополнительный")
ax.set_xlim(left=0)
ax.set_ylim(bottom=0)
fig.tight_layout()
finish(fig, "fig_tradeoff.png")
