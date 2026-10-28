"""
common.py - общие функции для всех скриптов ПР №3 (этот файл менять не нужно).
"""
import argparse
import math
import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config

# Цвета графиков (одинаковые во всех рисунках отчёта)
C_RAW = "#9a9a94"      # исходный сигнал - серый
C_MA = "#2a78d6"       # скользящее среднее - синий
C_MED = "#eb6834"      # медианный - оранжевый
C_EMA = "#1baf7a"      # экспоненциальный - бирюзовый
C_REF = "#3a3a36"      # эталон / идеальная прямая
C_CAL = "#2a78d6"      # после калибровки

# Коэффициенты Стьюдента для P = 0,95 (число степеней свободы k = n - 1)
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
        14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
        20: 2.086, 24: 2.064, 29: 2.045, 39: 2.023, 59: 2.001, 119: 1.980}


def t_student(n):
    """Коэффициент Стьюдента t(P=0,95; n-1). Для n = 20 -> 2,093."""
    k = int(n) - 1
    if k in _T95:
        return _T95[k]
    keys = sorted(_T95)
    for lo, hi in zip(keys, keys[1:]):          # линейная интерполяция
        if lo < k < hi:
            return _T95[lo] + (_T95[hi] - _T95[lo]) * (k - lo) / (hi - lo)
    return 1.960


def setup():
    """Читает номер варианта (из config.py или ключа --var) и готовит папки."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--var", type=int, default=None)
    args, _ = p.parse_known_args()
    if args.var is not None:
        config.VARIANT = args.var
        config.DATA_DIR = f"data/var{args.var:02d}"
        config.RESULTS_DIR = f"results/var{args.var:02d}"
    os.chdir(os.path.dirname(os.path.abspath(__file__)))   # работаем из папки проекта
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    plot_style()
    return config.get_variant()


def data_path(name):
    return os.path.join(config.DATA_DIR, name)


def result_path(name):
    return os.path.join(config.RESULTS_DIR, name)


def save_table(df, name):
    """Сохраняет таблицу в CSV, который правильно открывается в русском Excel."""
    path = result_path(name)
    df.to_csv(path, sep=";", decimal=",", encoding="utf-8-sig", index=False)
    return path


def plot_style():
    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans",      # шрифт с кириллицей
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#8a8a84",
        "axes.labelcolor": "#3a3a36",
        "xtick.color": "#5a5a55",
        "ytick.color": "#5a5a55",
        "axes.grid": True,
        "grid.color": "#e4e3dc",
        "grid.linewidth": 0.8,
        "legend.frameon": False,
        "lines.linewidth": 2.0,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })


def fmt(x, nd=3):
    """Число с десятичной запятой, как принято в отчётах."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x:.{nd}f}".replace(".", ",")


# ---------- Фильтры: точная копия функций из скетча Arduino ----------
# Нужны, чтобы проверить фильтры с ДРУГИМИ N и α по уже записанному raw
# (п. 6 части 5) без повторной прошивки платы.

def moving_average(x, n):
    x = np.asarray(x, float)
    y = np.empty_like(x)
    for k in range(len(x)):
        y[k] = x[max(0, k - n + 1):k + 1].mean()
    return y


def median5(x):
    x = np.asarray(x, float)
    y = np.empty_like(x)
    for k in range(len(x)):
        y[k] = np.sort(x[max(0, k - 4):k + 1])[len(x[max(0, k - 4):k + 1]) // 2]
    return y


def exp_filter(x, alpha):
    x = np.asarray(x, float)
    y = np.empty_like(x)
    y[0] = x[0]
    for k in range(1, len(x)):
        y[k] = alpha * x[k] + (1 - alpha) * y[k - 1]
    return y


def finish(fig, name):
    path = result_path(name)
    fig.savefig(path)
    print(f"Рисунок сохранён: {path}")
    if not os.environ.get("PR3_NO_SHOW"):
        plt.show()
    plt.close(fig)
