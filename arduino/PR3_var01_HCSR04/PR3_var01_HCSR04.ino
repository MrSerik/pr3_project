// ПР №3. Сбор данных с датчика, калибровка и фильтрация измерений
// ПРИМЕР ВЫПОЛНЕНИЯ: вариант 1 (HC-SR04, 10–100 см)
// Arduino Uno. HC-SR04: Trig -> D9, Echo -> D10. Потенциометр: движок -> A0
//
// ИЗМЕНЁННЫЕ ПАРАМЕТРЫ по сравнению с листингом 1 отмечены  <<< ВАР. 1

#define USE_ULTRASONIC 1          // 1 - HC-SR04 (см), 0 - потенциометр (градусы)  <<< ВАР. 1

const uint8_t TRIG_PIN = 9;
const uint8_t ECHO_PIN = 10;
const uint8_t POT_PIN  = A0;
const float   POT_RANGE = 270.0;  // полный угол поворота потенциометра, град

const unsigned long PERIOD_MS = 50; // период опроса 50 мс (20 Гц)
const uint8_t N_MA  = 5;            // окно скольз. среднего  <<< ВАР. 1
const float   ALPHA = 0.20;         // коэфф. экспоненц. фильтра  <<< ВАР. 1

// Калибровка: x_кал = A_CAL * x_изм + B_CAL
// ШАГ 1 (части 2-3): оставить A_CAL = 1.0, B_CAL = 0.0 (калибровки нет, cal = raw).
// ШАГ 2 (часть 4): вписать коэффициенты, которые напечатал analysis_calib.py,
//                  и загрузить скетч повторно.
const float A_CAL = 1.0053;    // <<< после части 3 заменить, например на 1.0086 (демо-данные)
const float B_CAL = -0.5462;    // <<< после части 3 заменить, например на -1.2118 (демо-данные)

float bufMA[20];  uint8_t iMA = 0,  nMA = 0;
float bufMed[5];  uint8_t iMed = 0, nMed = 0;
float ema = NAN;
unsigned long tPrev = 0;

float readUltrasonicCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);          // импульс запуска 10 мкс
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long t = pulseIn(ECHO_PIN, HIGH, 30000UL); // таймаут 30 мс
  if (t == 0) return NAN;                // эхо не получено
  return t * 0.0343 / 2.0;               // d = v*t/2, v = 0,0343 см/мкс
}

float readPotDeg() {
  int n = analogRead(POT_PIN);           // код АЦП 0...1023
  return n * POT_RANGE / 1023.0;
}

float movingAverage(float x) {           // скользящее среднее по N_MA точкам
  bufMA[iMA] = x;
  iMA = (iMA + 1) % N_MA;
  if (nMA < N_MA) nMA++;
  float s = 0;
  for (uint8_t i = 0; i < nMA; i++) s += bufMA[i];
  return s / nMA;
}

float median5(float x) {                 // медианный фильтр, окно 5
  bufMed[iMed] = x;
  iMed = (iMed + 1) % 5;
  if (nMed < 5) nMed++;
  float a[5];
  for (uint8_t i = 0; i < nMed; i++) a[i] = bufMed[i];
  for (uint8_t i = 1; i < nMed; i++) {   // сортировка вставками
    float v = a[i]; int8_t j = i - 1;
    while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; }
    a[j + 1] = v;
  }
  return a[nMed / 2];
}

float expFilter(float x) {               // экспоненциальный фильтр
  if (isnan(ema)) ema = x;
  else ema = ALPHA * x + (1.0 - ALPHA) * ema;
  return ema;
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Serial.println("t_ms,raw,cal,ma,med,ema");
}

void loop() {
  if (millis() - tPrev < PERIOD_MS) return;
  tPrev = millis();
#if USE_ULTRASONIC
  float raw = readUltrasonicCm();
#else
  float raw = readPotDeg();
#endif
  if (isnan(raw)) return;                // пропускаем неудачное измерение
  float cal = A_CAL * raw + B_CAL;
  float ma  = movingAverage(cal);
  float med = median5(cal);
  float ef  = expFilter(cal);
  Serial.print(tPrev);   Serial.print(',');
  Serial.print(raw, 2);  Serial.print(',');
  Serial.print(cal, 2);  Serial.print(',');
  Serial.print(ma, 2);   Serial.print(',');
  Serial.print(med, 2);  Serial.print(',');
  Serial.println(ef, 2);
}
