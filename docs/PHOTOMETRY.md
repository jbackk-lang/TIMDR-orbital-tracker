# Zegar z krzywej blasku — prototyp

Moduł `timdr_orbit/rotation_clock.py` odtwarza częstotliwość i względną fazę fotometryczną. Wymaga Pythona, NumPy i SciPy. Nie wymaga tachometru, ale wymaga jawnych granic poszukiwanej częstotliwości początkowej i jej zmiany.

## Uruchomienie

Plik wejściowy CSV ma nagłówek `time,flux`. Czas w sekundach oznacza częstotliwość w Hz i jej zmianę w Hz/s. Możliwe są nieregularne czasy próbek i braki wartości; brakujące pomiary są pomijane.

```powershell
python -m timdr_orbit.cli spin --csv obserwacja.csv --f-bounds 0.35 0.8 --drift-bounds -0.01 0.03 --out wynik
```

Granice powyżej dotyczą wyłącznie demonstracji. Trzeba dobrać je do obserwacji i zapisać przed oceną wyniku. Zbyt ciasne lub błędne granice mogą wymusić błędne rozwiązanie. Wyniki to `wynik.json` (diagnostyka) i `wynik.csv` (czas, częstotliwość, względny kąt fotometryczny). CSV zawiera dopasowanie również przy statusie `unreliable`: wtedy nie należy używać go jako wiarygodnego zegara.

```powershell
python -m timdr_orbit.rotation_clock --benchmark --out benchmark
```

## Co dopasowuje

Model fazy: θ(t)=2π[f₀t+½at²]. Jasność to trend liniowy i suma sinusów oraz cosinusów pierwszych dwóch harmonicznych tej fazy. Amplitudy są stałe w oknie. Dwa niezależne uruchomienia optymalizacji globalnej są uzupełniane dopasowaniem na wszystkich próbkach. Nie jest to metoda czasu rzeczywistego.

Kąt ma umowny początek zero: nie oznacza orientacji obiektu w przestrzeni. Przerwy są przekraczane przez założenie modelu, nie przez niezależnie zmierzony obrót. Nie ma gwarancji poprawnego naliczenia obrotów przez długą przerwę.

Przy dwóch harmonicznych program dodatkowo sprawdza rozwiązanie o dwukrotnie większej częstotliwości, jeśli amplituda podstawowej stanowi mniej niż 20% drugiej harmonicznej. Przy podobnym błędzie (różnica ≤0,01 wariancji znormalizowanego sygnału) wybiera krótszy okres fotometryczny, o ile mieści się on w zadanych granicach. Ta jawna heurystyka została dodana po ujawnieniu pomyłki o czynnik dwa w testach rozwojowych. Może pomijać słabą rzeczywistą składową podstawową; nie rozstrzyga fizycznego okresu obrotu.

`data/example_light_curve.csv` zawiera demonstracyjne dane syntetyczne; `artifacts/spin.csv` i `artifacts/spin.json` są wynikiem kompletnego uruchomienia interfejsu CSV na osobnym ziarnie 712.

## Zakres i ograniczenia

- Testy syntetyczne obejmują przyspieszanie, zwalnianie, silniejszą drugą harmoniczną, nieregularne próbkowanie z przerwą, zanik sygnału i sam szum; po pięć ziaren losowych. Zakresy poszukiwania obejmują prawdę generatora — to podana informacja wstępna.
- Progi jakości są robocze: wyjaśniona zmienność ≥0,45 i lokalnie ≥0,15 w sześciu częściach nagrania, kontrola brzegu przedziału i zgodności optymalizacji. Nie są prawdopodobieństwem poprawności ani skalibrowaną częstością fałszywych alarmów.
- Częstotliwość zmian jasności nie określa jednoznacznie obrotu fizycznego: konieczne jest rozstrzygnięcie harmonicznych i geometrii obserwacji. Sam pojedynczy sinus tego nie rozwiązuje. Nie ma walidacji na satelitach lub planetoidach.
- Zmienna geometria, precesja, aliasing, duże zmiany amplitudy oraz przyspieszenie zależne od czasu mogą unieważnić model. Status przyjętego dopasowania nie dowodzi prawidłowości fizycznej.
- To estymator zegara, nie gotowe sito ani klasyfikator obiektów. Nie mierzy AUC i nie przenosi wyniku turbiny na astronomię. Do takiego testu trzeba określić cel klasyfikacji i niezależne etykiety.
- Porównanie STFT wykorzystuje dokładnie okno 128 i nakładanie 112 z pierwotnych skryptów, z pominięciem brzegowych 4 sekund. Nie jest porównaniem z najlepszym dostrojonym konkurencyjnym estymatorem.

Wyniki poszczególnych przebiegów znajdują się w `artifacts/validation/photometry_development.json`. To test rozwojowy, a nie prerejestrowana walidacja skuteczności.
