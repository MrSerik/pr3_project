# ПР №3 – пример выполнения: вариант 1 (HC-SR04) и вариант 3 (потенциометр)

## Состав проекта

| Файл | Что делает | Часть методички |
|---|---|---|
| `arduino/PR3_var01_HCSR04/PR3_var01_HCSR04.ino` | скетч для варианта 1 (HC-SR04, N = 5, α = 0,20) | ч. 1–2 |
| `arduino/PR3_var03_POT/PR3_var03_POT.ino` | скетч для варианта 3 (потенциометр, N = 5, α = 0,25) | ч. 1–2 |
| `config.py` | **номер варианта, COM-порт**, эталонные и контрольные точки | – |
| `logger.py` | запись сигналов с Arduino в CSV: режимы `calib`, `check`, `dyn` | ч. 3–5 |
| `analysis_calib.py` | таблица 3, пример расчёта, гистерезис, МНК, R², рисунок калибровки | ч. 3 |
| `analysis_check.py` | таблица 4: погрешность до/после калибровки | ч. 4 |
| `analysis_filters.py` | таблица 5, сравнение с теорией, графики фильтров и «шум – запаздывание» | ч. 5 |
| `simulate.py` | демонстрационные данные для проверки скриптов без стенда | – |
| `common.py` | общие функции (не менять) | – |

## 1. Открыть в PyCharm

1. File → Open → папка `pr3_project`.
2. Settings → Project → Python Interpreter → создать виртуальное окружение (venv).
3. В терминале PyCharm: `pip install -r requirements.txt`.
4. В `config.py` указать `VARIANT` и `PORT` (порт видно в Arduino IDE → Инструменты → Порт).

## 2. Порядок выполнения работы

| Шаг | Что сделать | Результат |
|---|---|---|
| 1 | Собрать схему (табл. 2), загрузить скетч своего варианта с `A_CAL = 1.0`, `B_CAL = 0.0` | – |
| 2 | Проверить в Serial Plotter, что показания меняются. **Закрыть Serial Monitor/Plotter** | – |
| 3 | `python logger.py calib` → проход 1 (прямой): по очереди все 10 точек | `data/varNN/calib.csv` |
| 4 | `python logger.py calib` → проход 2 (обратный) | дописывается в тот же файл |
| 5 | `python analysis_calib.py` | таблица 3, A_CAL, B_CAL, `fig_calibration.png` |
| 6 | Вписать A_CAL и B_CAL в скетч, загрузить повторно | – |
| 7 | `python logger.py check` → 3 контрольные точки | `check.csv` |
| 8 | `python analysis_check.py` | таблица 4 |
| 9 | `python logger.py dyn` → ступенька на ~5 с, выбросы на 8–14 с | `dynamic.csv` |
| 10 | `python analysis_filters.py` | таблица 5, `fig_filters.png`, `fig_tradeoff.png` |

В PyCharm каждый скрипт можно запускать правой кнопкой → Run; `logger.py` сам спросит режим.
Другой вариант без правки config.py: Run → Edit Configurations → Parameters: `calib --var 3`.

Все таблицы сохраняются в `results/varNN/*.csv` (открываются в Excel с запятой),
рисунки – в `results/varNN/*.png`.

## 3. Проверка без стенда

```
python simulate.py --var 1
python analysis_calib.py --var 1
python analysis_check.py --var 1
python analysis_filters.py --var 1
```

**Данные из `simulate.py` смоделированы. В отчёт их включать нельзя – это фальсификация (О = 0).**
