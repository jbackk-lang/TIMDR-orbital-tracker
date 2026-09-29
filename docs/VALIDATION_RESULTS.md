# Wyniki v0.1 — 29.09.2026

**23/23 testy automatyczne przeszły.** Zakres: wektory referencyjne SGP4, współrzędne, prędkość radialna, przeloty, świeżość danych, kojarzenie śladów, przyczynowość filtra, zapis SQLite, import CSV, odbiór HTTP oraz parser i dozwolone zapytania LX200.

SGP4 zgadza się z opublikowanymi wektorami Vallado dla NORAD 5 w granicy 1e-5 km w epoce oraz po 360 i 720 minutach. To zgodność obliczeń, nie dokładność rzeczywistej orbity.

## Filtr kierunku — syntetyka

30 niezależnych ziaren 1000–1029, opartych na publicznym torze ISS, z dodanym szumem, przesunięciem, dryfem, odstającymi próbkami i brakami:

- Mediana ilorazu RMSE względem surowego modelu: **0,133633**, czyli około **86,6% redukcji**.
- Końcowe 20 próbek bez pomiarów: iloraz **0,151484**, około **84,9% redukcji**.
- Odrzucone duże odstające próbki: **90/90**.
- Średni RMSE: surowy kierunek **0,18049°**, przyczynowa predykcja filtra **0,02439°**.
- Przykładowa seria została skojarzona z ISS, NORAD 25544.

Wszystkie wyniki: `artifacts/validation/tracking_validation.json`. Nie są to rzeczywiste niezależne pomiary satelity. Nie deklarujemy dokładności w metrach ani nowej dynamiki TIMDR lepszej od SGP4.

CLI zapisał `artifacts/association.json`, `artifacts/tracked_observations.json` oraz `artifacts/spin.json` i `artifacts/spin.csv`. Fotometria jest osobną symulacją; jej wyniki rozwojowe po poprawce harmonicznych są w `artifacts/validation/photometry_development.json`.

## Dane i przyrządy

Odbiór HTTP został przetestowany przez lokalny serwer: zapis CSV, analiza, odrzucanie niepoprawnych pomiarów i żądań bez klucza. Test SQLite ujawnił pozostawianie otwartych połączeń na Windows; dodano jawne zamykanie połączenia, a ponowna seria 23 testów przeszła. Konflikt próbki wycofuje całą partię; identyczna retransmisja nie duplikuje danych.

Bluetooth SPP/LX200: parser i komendy `:GZ#`, `:GA#` sprawdzono na atrapach transportu. **Brak testu fizycznego teleskopu.** Kierunek montażu nie jest potwierdzoną detekcją obiektu; czas i opóźnienie odczytu wymagają kontroli na urządzeniu.

## Interfejs

Podgląd orbit działa: wybór ENVISAT i zmiana suwaka aktualizują czas i parametry. Centrum obserwacji otwiera się z formularzem i katalogiem. **Pełny test zapisu przez formularz nie został potwierdzony**: próby interakcji nie dały rozstrzygającego wyniku, a dalszy test przeglądarki został zablokowany limitem narzędzia. Test API nie zastępuje testu przycisków.

Przed deklaracją skuteczności na realnych pomiarach potrzebne są niezależne łuki astrometryczne, zamrożone progi, inne obiekty i geometrie oraz próba na rzeczywistym teleskopie. Pełny test formularza pozostaje do wykonania.
