# Dane ręczne, pliki i Bluetooth

Uruchom `URUCHOM_APLIKACJE.cmd`, albo:

```powershell
.venv\Scripts\python -m timdr_orbit.cli serve --catalog data/catalog_2026-09-28.json --example artifacts/validation/synthetic_observations.csv
```

Otwórz `http://127.0.0.1:8766/`. Aplikacja działa lokalnie. Uzupełnij położenie stanowiska; początkowa Warszawa jest tylko przykładem. Przed aktualnymi obserwacjami kliknij „Pobierz świeże elementy”. Nie odświeżaj katalogu w każdej próbce.

## Wpisywanie ręczne i CSV

Wpisz minimum pięć pomiarów czasu UTC, azymutu i elewacji, albo wczytaj CSV z nagłówkiem `time_utc,azimuth_deg,elevation_deg`. Zapis pojedynczej próbki jest możliwy, ale skojarzenie śladu wymaga co najmniej pięciu. Jedna sesja oznacza jeden śledzony obiekt i jedno nieruchome stanowisko. Nie mieszaj pomiarów różnych obiektów w jednej sesji.

Przycisk przykładu ładuje jawnie oznaczone dane syntetyczne, które powinny wskazać ISS w katalogu demonstracyjnym. Baza SQLite zapisuje dane w `runtime/measurements.sqlite`. Analizy trafiają do `runtime/sessions/<identyfikator>/analysis.json`. Katalog `runtime` jest wyłączony z Gita, aby własne pomiary i klucz odbiornika nie trafiły do publikowanego repo.

## Bluetooth teleskopu: obsługiwany wariant

1. Sparuj adapter/teleskop w ustawieniach Bluetooth Windows. Program sam nie wykonuje parowania.
2. Adapter musi obsługiwać **Bluetooth Classic SPP**, udostępniać port COM i przenosić komendy **Meade LX200**. Sam napis „Bluetooth” nie gwarantuje zgodności.
3. W zakładce Bluetooth odśwież listę portów. Wybierz właściwy port teleskopu i szybkość zgodną z urządzeniem (domyślnie 9600, 8N1).
4. Ustaw i wyrównaj montaż zgodnie z instrukcją urządzenia. Zadbaj o czas komputera. Kliknij „Połącz i odczytuj”.
5. Program wysyła wyłącznie `:GZ#` (azymut) i `:GA#` (elewacja). Odpowiedzi są sprawdzane, zapis następuje co około sekundę. „Zatrzymaj odczyt” zamyka połączenie. Zamknięcie samej karty nie kończy działającego serwera; użyj przycisku lub zakończ aplikację.
6. W zapisanych sesjach wybierz serię, aby porównać kierunek z katalogiem.

Odczyt oznacza **kierunek osi teleskopu, nie potwierdzoną detekcję obiektu**. Montaż może patrzeć w kierunku satelity, nie rejestrując go. Nie ma tu sterowania nadążnego, rozpoznawania obrazu ani GOTO. Teleskopy NexStar, SynScan, BLE GATT lub inne języki wymagają właściwego adaptera; nie wysyłaj do nich komend LX200 bez potwierdzenia zgodności.

Czas próbki to środek przedziału odczytu dwóch osi według UTC komputera. Odczyty osi są sekwencyjne; opóźnienie Bluetooth, rozdzielczość enkoderów, refrakcja, błąd wyrównania i niesynchronizowany zegar ograniczają dokładność. Próba trwająca ponad 2 s jest odrzucana. Brak testu na fizycznym teleskopie — parser i dozwolone komendy sprawdzono na atrapach transportu. Lista COM jest listą wszystkich portów szeregowych, nie automatycznym rozpoznaniem teleskopów.

Źródła: [dokument producenta Meade, komendy GA/GZ](https://aggregate.org/DIT/CAPTURE/LX200CommandSet.pdf), [dokumentacja pySerial](https://pyserial.readthedocs.io/en/latest/pyserial_api.html).

## Lokalny odbiornik dla adaptera urządzenia

`POST http://127.0.0.1:8766/api/measurements`, `Content-Type: application/json`, nagłówek `X-TIMDR-Key` z zawartością `runtime/instrument-token.txt`.

```json
{
  "station": {"latitude_deg":52.2297,"longitude_deg":21.0122,"elevation_m":110},
  "source":"instrument",
  "observations":[
    {"time_utc":"2026-09-29T00:00:00Z","azimuth_deg":120.5,"elevation_deg":35.2}
  ]
}
```

Odpowiedź zawiera `session_id`; dopisz go do kolejnych żądań dla tej samej sesji. Powtórzenie identycznej próbki jest bezpieczne, a konflikt danych w tym samym czasie odrzuca całą partię. Maksimum 5000 próbek / 2 MB na żądanie. Obecna aplikacja nasłuchuje tylko na tym komputerze, więc zdalny przyrząd wymaga lokalnego adaptera, np. programu czytającego port Bluetooth. Nie otwiera portów LAN.
