"""
simulate.py - ДЕМОНСТРАЦИОННЫЕ (смоделированные) данные для примера.

Создаёт файлы calib.csv, check.csv и dynamic.csv в том же формате, что logger.py,
чтобы скрипты обработки можно было проверить без стенда. В модель заложены
типичные для реальных датчиков эффекты:
  HC-SR04      - скорость звука при 24 °C вместо 20 °C (масштаб), смещение нуля
                 рулетки относительно излучателя, шаг pulseIn() 1 мкс,
                 редкие переотражения, пропуски эха;
  потенциометр - электрический угол 285° вместо принятых 270°, смещение нуля
                 транспортира, нелинейность резистивного слоя, люфт ручки
                 (гистерезис), шум и шаг квантования 10-разрядного АЦП.

!!! В отчёте студента такие данные использовать НЕЛЬЗЯ - это фальсификация
!!! (коэффициент О = 0). Только для проверки программ и для разбора на занятии.

Запуск: python simulate.py --var 1   (или --var 3); без ключа - вариант из config.py
"""
import numpy as np
import pandas as pd

from common import data_path, exp_filter, median5, moving_average, setup

V = setup()
rng = np.random.default_rng(2026 + V["number"])
N = 20
DT = 0.05                                    # период опроса 50 мс

# ---------------- модели датчиков: истинное значение -> raw ----------------
if V["sensor"] == "HC-SR04":
    T_AIR = 24.0                             # реальная температура в аудитории, °C
    v_real = 331.3 + 0.606 * T_AIR           # м/с, формула (3.2)
    K = 343.0 / v_real                       # Arduino считает для 343 м/с
    OFFSET = 1.1                             # см: нуль рулетки не у излучателя

    def sensor(x_true, n=1):
        d = K * x_true + OFFSET + rng.normal(0, 0.10 + 0.0025 * x_true, n)
        t_us = np.round(d / 0.0343 * 2)      # pulseIn() возвращает целые мкс
        raw = t_us * 0.0343 / 2
        multi = rng.random(n) < 0.012        # редкие переотражения
        raw[multi] += rng.uniform(2, 6, multi.sum())
        return np.round(raw, 2)
else:
    TH_EL, TH0 = 285.0, 4.0                  # электрический угол, смещение нуля, °

    def sensor(x_true, n=1, backlash=0.0):
        th = x_true + backlash + 1.2 * np.sin(np.pi * x_true / 270)   # нелинейность
        code = (th + TH0) / TH_EL * 1023 + rng.normal(0, 0.6, n)       # шум АЦП
        code = np.clip(np.round(code), 0, 1023)
        return np.round(code * 270 / 1023, 2)


def arduino_rows(raw, a_cal=1.0, b_cal=0.0, t0_ms=2100, idx=None):
    """Пропускает raw через ту же обработку, что скетч: cal, ma, med, ema."""
    cal = a_cal * raw + b_cal
    idx = np.arange(len(raw)) if idx is None else idx
    t = t0_ms + idx * 50
    return pd.DataFrame({
        "t_ms": t, "raw": raw, "cal": np.round(cal, 2),
        "ma": np.round(moving_average(cal, V["n_ma"]), 2),
        "med": np.round(median5(cal), 2),
        "ema": np.round(exp_filter(cal, V["alpha"]), 2),
    })


SET_ERR = 0.15 if V["sensor"] == "HC-SR04" else 0.3   # см или °: точность установки

# ---------------- часть 3: калибровка, прямой и обратный проход ----------------
rows = []
t_ms = 4000
for pass_name, pts in [("прямой", V["ref_points"]), ("обратный", V["ref_points"][::-1])]:
    for ref in pts:
        set_err = rng.normal(0, SET_ERR)      # студент ставит экран/ручку не идеально
        if V["sensor"] == "HC-SR04":
            raw = sensor(ref + set_err, N)
        else:
            bl = -0.5 if pass_name == "прямой" else 0.5        # люфт ручки
            raw = sensor(ref + set_err, N, backlash=bl)
        df = arduino_rows(raw, t0_ms=t_ms)
        df.insert(0, "ref", ref)
        df.insert(0, "pass", pass_name)
        rows.append(df)
        t_ms += 25000
calib = pd.concat(rows, ignore_index=True)
calib.to_csv(data_path("calib.csv"), index=False)

# коэффициенты, которые студент получил бы в части 3 (МНК по средним)
m = calib.groupby("ref")["raw"].mean()
A_CAL, B_CAL = np.polyfit(m.values, m.index.values.astype(float), 1)
A_CAL, B_CAL = round(A_CAL, 4), round(B_CAL, 4)

# ---------------- часть 4: контрольные точки после прошивки A_CAL, B_CAL ----------------
rows = []
for ref in V["control_points"]:
    set_err = rng.normal(0, SET_ERR)
    raw = sensor(ref + set_err, N) if V["sensor"] == "HC-SR04" else sensor(ref + set_err, N, 0.0)
    df = arduino_rows(raw, A_CAL, B_CAL, t0_ms=t_ms)
    df.insert(0, "ref", ref)
    df.insert(0, "pass", "контроль")
    rows.append(df)
    t_ms += 25000
pd.concat(rows, ignore_index=True).to_csv(data_path("check.csv"), index=False)

# ---------------- часть 5: ступенька + выбросы ----------------
n = int(15 / DT)
t = np.arange(n) * DT
a, b = V["step"]
ramp = 0.25                                       # переставить экран/ручку ~0,25 с
x_true = np.where(t < 5.0, a, np.where(t < 5.0 + ramp, a + (b - a) * (t - 5.0) / ramp, b))
x_true = x_true + np.cumsum(rng.normal(0, 0.01, n))   # рука/стол чуть "плывут"
raw = np.array([sensor(x)[0] for x in x_true])

# выбросы длительностью 1, 2 и 4 отсчёта (0,05 / 0,10 / 0,20 с)
for t_out, length in [(8.5, 1), (10.5, 2), (12.5, 4)]:
    k = int(t_out / DT)
    if V["sensor"] == "HC-SR04":
        raw[k:k + length] = np.round(rng.normal(27, 0.5, length), 2)   # рука перед датчиком
    else:
        raw[k:k + length] = np.round(raw[k:k + length] + 35, 2)        # рывок ручки на 35°

keep = np.ones(n, bool)
if V["sensor"] == "HC-SR04":                      # пропуски эха: скетч делает return,
    keep[rng.choice(np.arange(20, 90), 2, replace=False)] = False   # строки просто нет
dyn = arduino_rows(raw[keep], A_CAL, B_CAL, t0_ms=2100, idx=np.arange(n)[keep])
dyn.to_csv(data_path("dynamic.csv"), index=False)

print(f"Вариант {V['number']} ({V['sensor']}): демо-данные записаны в {data_path('')}")
print(f"  calib.csv   - {len(calib)} строк;  check.csv и dynamic.csv - с A_CAL={A_CAL}, B_CAL={B_CAL}")
