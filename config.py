"""
config.py - настройки ПР №3. Это ЕДИНСТВЕННЫЙ файл, который нужно править.

1) Укажите номер своего варианта в VARIANT.
2) Укажите COM-порт Arduino в PORT (Arduino IDE -> Инструменты -> Порт).
3) Если вашего варианта нет в VARIANTS - добавьте его по образцу из таблицы 6.
"""

VARIANT = 1            # 1 - HC-SR04 (пример), 3 - потенциометр (пример)
PORT = "COM9"          # Windows: "COM5"; Linux: "/dev/ttyUSB0"; macOS: "/dev/cu.usbmodem..."
BAUD = 115200
N_PER_POINT = 20       # измерений в каждой эталонной точке
DYN_SECONDS = 15       # длительность динамической записи, с

# Таблица 6 (для примера - варианты 1 и 3)
VARIANTS = {
    1: dict(
        sensor="HC-SR04",
        unit="см",
        ref_points=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        control_points=[15, 55, 95],          # часть 4: середины интервалов
        n_ma=5,
        alpha=0.20,
        step=(20, 60),                        # часть 5: ступенька 20 -> 60 см
        x_n=100,                              # верхний предел диапазона (для γ)
        use_gamma=False,                      # в таблице 3 считаем δ, %
    ),
    3: dict(
        sensor="Потенциометр",
        unit="°",
        ref_points=[0, 30, 60, 90, 120, 150, 180, 210, 240, 270],
        control_points=[15, 135, 255],
        n_ma=5,
        alpha=0.25,
        step=(45, 180),
        x_n=270,
        use_gamma=True,                       # в точке 0° δ не определена -> γ, %
    ),
}

# Папки для данных и результатов (создаются автоматически)
DATA_DIR = f"data/var{VARIANT:02d}"
RESULTS_DIR = f"results/var{VARIANT:02d}"


def get_variant():
    if VARIANT not in VARIANTS:
        raise SystemExit(f"Вариант {VARIANT} не описан в config.VARIANTS - добавьте его.")
    v = dict(VARIANTS[VARIANT])
    v["number"] = VARIANT
    return v
