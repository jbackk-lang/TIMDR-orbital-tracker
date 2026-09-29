# TIMDR-orbital-tracker

Lokalny model śledzenia katalogowych obiektów na orbitach okołoziemskich. Przewiduje położenie i prędkość z publicznych elementów orbitalnych, oblicza kierunek obserwacji i przeloty, kojarzy serię pomiarów z obiektem katalogowym oraz koryguje krótkoterminowe wskazanie kierunku. Zawiera osobny eksperymentalny zegar fotometryczny.

**Status v0.1: działający prototyp.** Rdzeń orbitalny to klasyczny **SGP4 przez Skyfield**, nie nowa teoria dynamiki ani wytrenowana sieć. Dane demonstracyjne: ISS (25544), ENVISAT (27386), Vanguard 1 (5), pobrane z CelesTrak. Nie obejmuje orbit heliocentrycznych planetoid.

## Najprostsze uruchomienie

**Pełna aplikacja z dodawaniem danych:** uruchom `URUCHOM_APLIKACJE.cmd`, a następnie użyj formularza ręcznego, pliku CSV lub zakładki Bluetooth/teleskop. Obsługiwany pierwszy adapter to Bluetooth SPP → COM → LX200 (odczyt kierunku). Szczegóły i ograniczenia: [docs/INSTRUMENTS.md](docs/INSTRUMENTS.md).

Otwórz `artifacts/demo/dashboard.html` w przeglądarce — gotowy, samodzielny podgląd działa bez internetu i instalacji. Wybierz obiekt, przesuń czas lub odtwórz tor. To zapis prognozy dla wskazanych dat, a nie transmisja pomiarów na żywo.

Na Windows dwuklik `URUCHOM_DEMO.cmd` utworzy lokalne środowisko, w razie potrzeby pobierze zależności, odtworzy prognozę i otworzy podgląd. Wymagany Python 3.11 lub nowszy. Pierwsza instalacja wymaga internetu.

Demonstracyjny obserwator to **centrum Warszawy**, 52.2297° N, 21.0122° E, 110 m. Nie jest to ustalona lokalizacja użytkownika. Do własnych obserwacji podaj rzeczywiste współrzędne stanowiska.

## Instalacja ręczna

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python scripts/validate_tracking.py
```

Linux/macOS: zamień `.venv\Scripts\python` na `.venv/bin/python`. Nie trzeba aktywować środowiska.

## Aktualne dane i prognoza

```powershell
.venv\Scripts\python -m timdr_orbit.cli fetch --ids 25544 27386 5 --out data/catalog_now.json
.venv\Scripts\python -m timdr_orbit.cli predict --catalog data/catalog_now.json --lat 52.2297 --lon 21.0122 --height 110 --hours 3 --step 30 --pass-hours 24 --out artifacts/live
```

Bez `--start` używany jest aktualny czas UTC komputera. `fetch` zachowuje źródła, czas pobrania i SHA-256; nie nadpisuje istniejących snapshotów. Przy następnym pobraniu wybierz nową nazwę pliku. Pobieraj dopiero, kiedy potrzebujesz świeżych elementów; nie odpytuj CelesTrak przy każdej próbce pozycji.

Predykcja tworzy `prediction.json`, `tracks.csv` i `dashboard.html`. Własne obiekty dodaj przez ich identyfikatory NORAD. Obsługiwany jest JSON GP zgodny z OMM CelesTrak, z SGP4/TEME/UTC/EARTH. To obsługuje także skatalogowane szczątki orbitalne, jeśli mają poprawne, świeże elementy; demonstracja nie jest walidacją na szczątkach.

Odtworzenie zapisanej demonstracji:

```powershell
.venv\Scripts\python -m timdr_orbit.cli predict --catalog data/catalog_2026-09-28.json --lat 52.2297 --lon 21.0122 --height 110 --start 2026-09-28T20:00:00Z --hours 3 --step 30 --pass-hours 24 --out artifacts/demo
```

Elementy odległe o ponad 7 dni od żądanej chwili są domyślnie odrzucane. To roboczy próg świeżości, a nie gwarancja dokładności. `--allow-stale` jawnie dopuszcza stare elementy i oznacza je w wyniku. Dla szybko zmieniających się orbit potrzebna może być znacznie częstsza aktualizacja.

## Własne obserwacje kierunku

CSV: `time_utc,azimuth_deg,elevation_deg`. Czas musi zawierać `Z` lub strefę. Azymut liczony od północy ku wschodowi, elewacja od geometrycznego horyzontu. Pomiar z jednego stanowiska, minimum 5 próbek, rosnący czas. Refrakcja nie jest modelowana; pomiary powinny mieć zgodną konwencję.

```powershell
.venv\Scripts\python -m timdr_orbit.cli associate --catalog data/catalog_2026-09-28.json --observations artifacts/validation/synthetic_observations.csv --lat 52.2297 --lon 21.0122 --height 110 --out artifacts/association.json
.venv\Scripts\python -m timdr_orbit.cli track --catalog data/catalog_2026-09-28.json --id 25544 --observations artifacts/validation/synthetic_observations.csv --lat 52.2297 --lon 21.0122 --height 110 --sigma-deg 0.03 --out artifacts/tracked_observations.json
```

`associate` zwraca `matched`, `ambiguous` lub `unmatched` oraz ranking. Wybór dotyczy wyłącznie przekazanego katalogu. Obiekt nieobecny w katalogu może przypominać obecny — nie jest to identyfikacja globalnie unikalna.

`track` daje predykcję kierunku **przed przyswojeniem bieżącego pomiaru**. Filtr Kalmana śledzi sześć składowych: resztę jednostkowego kierunku ENU i jej tempo zmiany. Odrzuca duże innowacje i resetuje korektę po długiej przerwie. To korekta wskazania na krótkim łuku, nie nowe rozwiązanie orbitalne ani estymacja sześciu fizycznych współrzędnych położenia/prędkości. Formalna kowariancja nie jest skalibrowaną niepewnością całej orbity.

## Krzywa blasku / rotacja

```powershell
.venv\Scripts\python -m timdr_orbit.cli spin --csv data/example_light_curve.csv --f-bounds 0.35 0.8 --drift-bounds -0.01 0.03 --out artifacts/spin
```

CSV `time,flux`; sekundy → Hz. Zegar zakłada liniową zmianę częstotliwości, stałe amplitudy harmonicznych i jawne granice wyszukiwania. Nie identyfikuje jednoznacznie fizycznej rotacji. Nie jest używany do poprawiania pozycji orbitalnej bez danych uzasadniających takie sprzężenie. Szczegóły: `docs/PHOTOMETRY.md`.

## Co rzeczywiście sprawdzono

- 23 testy automatyczne (w tym zapis SQLite, CSV/HTTP i adapter LX200): opublikowane wektory referencyjne SGP4, współrzędne, prędkość radialna przez różniczkowanie odległości, zdarzenia przelotów, świeżość danych, kojarzenie i odmowa niejednoznacznego dopasowania, przyczynowość filtra, odrzucanie odstających obserwacji.
- 30 prób syntetycznych z niezależnymi ziarnami: szum, przesunięcie kierunku, dryf, błędne próbki, braki i końcowy odcinek bez pomiarów. Wszystkie przebiegi zachowane w `artifacts/validation/tracking_validation.json`.
- Rzeczywiste publiczne **elementy orbitalne**, ale **brak niezależnych rzeczywistych pomiarów pozycji**. Nie deklarujemy dokładności w metrach ani przewagi TIMDR nad komercyjnym śledzeniem.

Plan i wyniki: `docs/VALIDATION_PLAN.md`, `docs/VALIDATION_RESULTS.md`. Parametry/model: `model.json`. Nie ma pliku wag sieci, ponieważ model jest fizyczny i statystyczny.

## Ograniczenia i następny krok badawczy

Brak automatycznego odkrywania nieznanych obiektów, wyznaczania orbity wyłącznie z obrazu/jasności, estymacji manewrów, oporu z pogody kosmicznej, analizy kolizji i potwierdzenia widoczności optycznej. Ślad nad horyzontem nie oznacza, że obiekt jest oświetlony i widoczny.

Przed deklaracją skuteczności na realnych pomiarach należy pozyskać niezależne astrometryczne azymuty/elewacje lub RA/Dec ze znanego stanowiska i czasu, zamrozić progi, a następnie ocenić kolejne łuki bez dostrajania. Celem jest błąd kątowy prognozy i poprawność skojarzenia, nie AUC z eksperymentu turbiny. Rozszerzenie o nowy model dynamiczny wymaga oddzielnego porównania ze standardowym SGP4.

## Źródła i pochodzenie

- [CelesTrak GP/OMM](https://celestrak.org/NORAD/documentation/gp-data-formats.php): format i źródło snapshotów, metadane w `data/*.meta.json`.
- [Skyfield — Earth Satellites](https://rhodesmill.org/skyfield/earth-satellites.html): propagacja i obserwator.
- [Vallado i in. — Revisiting Spacetrack Report #3](https://celestrak.org/publications/AIAA/2006-6753/AIAA-2006-6753.pdf): SGP4 i referencje weryfikacyjne, dystrybuowane także z python-sgp4.
- TIMDR: organizacja warstw i dyscyplina testowania. Nazwa projektu nie przypisuje SGP4 autorstwa TIMDR. Nie stwierdzono nowego prawa orbitalnego ani przewagi nowego sita.

Repo: https://github.com/jbackk-lang/TIMDR-orbital-tracker. Licencję własnego kodu ustala właściciel repo; zależności zachowują swoje licencje. Lokalne pomiary, klucz odbiornika i środowisko Pythona są wyłączone z Gita.
