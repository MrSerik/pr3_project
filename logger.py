"""
logger.py - запись измерений с Arduino в CSV (листинг 2, доработанный).

Запуск в PyCharm: правой кнопкой по файлу -> Run 'logger'.
Программа спросит режим. Можно и из терминала:
    python logger.py calib      - часть 3, калибровка (20 измерений в каждой точке)
    python logger.py check      - часть 4, контрольные точки после калибровки
    python logger.py dyn        - часть 5, динамическая запись (DYN_SECONDS секунд)
    python logger.py dyn --var 3  - то же для другого варианта

ВАЖНО: перед запуском закройте Serial Monitor / Serial Plotter в Arduino IDE -
порт может занимать только одна программа.
"""
import csv
import os
import sys
import time

import serial                       # pip install pyserial

import config
from common import data_path, setup

V = setup()


def open_port():
    try:
        ser = serial.Serial(config.PORT, config.BAUD, timeout=2)
    except serial.SerialException as e:
        sys.exit(f"Не удалось открыть порт {config.PORT}: {e}\n"
                 "Проверьте PORT в config.py и закройте Serial Monitor.")
    time.sleep(2)                   # Arduino перезагружается при открытии порта
    ser.reset_input_buffer()
    return ser


def read_row(ser):
    """Возвращает одну строку CSV от Arduino: t_ms, raw, cal, ma, med, ema."""
    while True:
        p = ser.readline().decode(errors="ignore").strip().split(",")
        if len(p) == 6 and p[0].isdigit():
            return p


def ask_number(prompt):
    while True:
        s = input(prompt).strip().replace(",", ".")   # 10,5 -> 10.5
        if s == "":
            return None
        try:
            return float(s)
        except ValueError:
            print("  нужно число, например 30 или 12.5")


def record_points(ser, filename, points, with_pass):
    """Общая часть режимов calib и check: точка -> N измерений."""
    path = data_path(filename)
    new = not os.path.exists(path)
    pass_name = "контроль"
    if with_pass:
        d = input("Проход: 1 - прямой (от меньших к большим), 2 - обратный: ").strip()
        pass_name = "обратный" if d == "2" else "прямой"
        if pass_name == "обратный":
            points = list(reversed(points))
    print(f"\nЭталонные точки варианта {V['number']}: {points} {V['unit']}")
    print("Установите экран/ручку в точку, введите её значение и нажмите Enter.")
    print("Пустой Enter - выход.\n")
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["pass", "ref", "t_ms", "raw", "cal", "ma", "med", "ema"])
        while True:
            ref = ask_number(f"Эталонное значение, {V['unit']}: ")
            if ref is None:
                break
            ser.reset_input_buffer()
            for i in range(config.N_PER_POINT):
                w.writerow([pass_name, ref] + read_row(ser))
                print(f"\r  {i + 1}/{config.N_PER_POINT}", end="")
            f.flush()
            print(f"  - записано для {ref:g} {V['unit']}")
    print(f"Данные дописаны в {path}")


def record_dynamic(ser):
    path = data_path("dynamic.csv")
    a, b = V["step"]
    # Подсказки появляются в момент, когда нужно действовать: (время, текст)
    cues = [
        (0.0, f"ДЕРЖИТЕ {a} {V['unit']} неподвижно"),
        (5.0, f">>> СЕЙЧАС: резко переставьте на {b} {V['unit']} и держите <<<"),
        (8.0, ">>> ВЫБРОС 1: быстро проведите рукой перед датчиком <<<"),
        (10.0, ">>> ВЫБРОС 2 <<<"),
        (12.0, ">>> ВЫБРОС 3 <<<"),
        (13.0, "держите до конца записи"),
    ]
    if V["sensor"] != "HC-SR04":
        cues[2] = (8.0, ">>> ВЫБРОС 1: резко дёрните ручку на 30-40° и сразу верните <<<")
    print(f"Запись {config.DYN_SECONDS} с. План опыта для варианта {V['number']}:")
    print(f"  0-5 с   - держать {a} {V['unit']} (экран на подставке, не в руке)")
    print(f"  5 с     - резко перейти на {b} {V['unit']} и держать")
    print("  8, 10, 12 с - короткие выбросы (не дольше 0,1 с)")
    print(f"Совет: заранее отметьте на столе положения {a} и {b} {V['unit']} скотчем.")
    print("Подсказки появятся в нужный момент во время записи.")
    input("Поставьте экран в начальное положение и нажмите Enter для старта...")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_ms", "raw", "cal", "ma", "med", "ema"])
        ser.reset_input_buffer()
        t0 = time.time()
        i_cue = 0
        while time.time() - t0 < config.DYN_SECONDS:
            row = read_row(ser)
            w.writerow(row)
            el = time.time() - t0
            if i_cue < len(cues) and el >= cues[i_cue][0]:
                print(f"\n[{el:4.1f} с] {cues[i_cue][1]}\a")   # \a - звуковой сигнал
                i_cue += 1
            print(f"\r  {el:4.1f} с   показание: {row[1]:>7s} {V['unit']}   ", end="")
    print(f"\n{path} сохранён")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--") and not a.isdigit()]
    mode = args[0] if args else input("Режим (calib / check / dyn): ").strip()
    ser = open_port()
    try:
        if mode == "calib":
            record_points(ser, "calib.csv", V["ref_points"], with_pass=True)
        elif mode == "check":
            record_points(ser, "check.csv", V["control_points"], with_pass=False)
        elif mode == "dyn":
            record_dynamic(ser)
        else:
            print("Неизвестный режим. Варианты: calib, check, dyn")
    finally:
        ser.close()
