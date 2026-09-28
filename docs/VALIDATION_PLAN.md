# Plan sprawdzenia v0.1

Zapisany przed pierwszym uruchomieniem testów orbitalnych. To plan rozwojowy, nie niezależna prerejestracja zewnętrzna.

1. SGP4: zgodność pozycji TEME z opublikowanymi wektorami weryfikacyjnymi Vallado dla NORAD 5, w epoce oraz po 360 i 720 minutach. Tolerancja 1e-5 km; to poprawność obliczeniowa, nie dokładność względem rzeczywistego satelity.
2. Warstwa użytkowa: poprawne UTC, świeżość elementów, odrzucanie błędnych parametrów, poprawny zakres kątów i odległości, odtworzenie pliku JSON/HTML, zdarzenia przelotów i brak utożsamiania ich z widocznością optyczną.
3. Kojarzenie śladów: zaszumione kierunki wygenerowane z katalogowego ISS mają wskazywać ISS; przypadek spoza bramki ma zwrócić brak dopasowania, a prawie identyczni kandydaci — niejednoznaczność. To syntetyka oparta na prawdziwych elementach, nie rzeczywiste obserwacje.
4. Filtr reszt kierunku: 30 niezależnych ziaren 1000..1029; szum 0,03 stopnia, systematyczne przesunięcie 0,2/-0,1 stopnia i wolny dryf, duże odstające próbki, brakujące próbki, końcowe 20 próbek ukryte. Wszystkie predykcje liczone PRZED aktualizacją filtrem. Porównać błąd względem znanego generatora z surowym SGP4. Oczekiwanie: mediana ilorazu RMSE <0,5, również w końcowym odcinku bez pomiarów. Raportować wszystkie ziarna, liczbę odrzuconych odstających próbek i ewentualną porażkę.
5. Fotometria: odziedziczony eksperymentalny zegar pozostaje osobny; jego wcześniejszy wynik 20/20 to test rozwojowy po poprawce harmonicznych, nie walidacja satelitarna. Jasność nie jest używana do wyznaczania położenia.

Nie ma niezależnych pomiarów pozycji, więc v0.1 nie może otrzymać deklaracji dokładności orbitalnej w metrach. Nie ma też uczonej sieci, modelu planetoid ani samodzielnego wyznaczania orbity nieznanego obiektu z samej jasności. SGP4 i dane GP dotyczą orbit okołoziemskich.
