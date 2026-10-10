AutoDiag Pro – WERSJA REALNA 1.1.0 (BMW E39 540i, DME Bosch ME7.2, kabel K+DCAN)
=========================================================================

JAK URUCHOMIĆ
1. Włóż kabel K+DCAN do USB laptopa i do gniazda OBD w aucie. Przełącznik na kablu (jeśli jest) w tryb K-line / piny 7+8.
2. Zapłon w pozycji 2 (kontrolki świecą). Do odczytu na żywo i zapłonów: silnik pracuje, rozgrzany, wolne obroty.
3. Uruchom AutoDiagPro_real.exe (albo START.bat – sam zainstaluje co trzeba, potrzebny Python 3.10+).
4. Wybierz port oznaczony [FTDI – K+DCAN] i kliknij "Połącz z DME".
5. Zakładki: Identyfikacja, Pamięć błędów, Na żywo, Wypadanie zapłonów, Adaptacje / lambda, Wyłączone funkcje, Log.

CO JEST PRAWDZIWE
Każda liczba na ekranie pochodzi z bajtów odebranych z DME przez port COM. Nie ma trybu demo, nie ma symulatora,
nie ma przykładowych danych. Gdy kabel nie jest podłączony albo DME nie odpowiada, program pisze
"brak odpowiedzi z DME" i podaje powód (brak echa kabla / kabel działa, ale DME milczy / zły baud).
Wszystkie wysłane i odebrane bajty są w zakładce Log i w pliku %LOCALAPPDATA%\AutoDiagPro_real\trace_*.txt.

- Połączenie: 9600 baud 8E1, ramka B8 12 F1, echo kabla obsłużone.
- Identyfikacja (A2): numer części, hardware, indeksy, data produkcji, dostawca.
- Pamięć błędów (18 02 FF FF): kody BMW + status. Kasowanie (14 FF 00) tylko po potwierdzeniu w okienku.
- Na żywo (22 40 00): obroty, temp. płynu, temp. powietrza, prędkość, czas wtrysku, zapłon, przepustnica, MAF, moment, napięcie.
- Wypadanie zapłonów (22 40 03): nierówność biegu (Laufunruhe) każdego z 8 cylindrów – z tego DME wykrywa wypadanie.
  Program zbiera próbki i pokazuje, który cylinder statystycznie odstaje.
- Adaptacje mieszanki (22 40 04) i status sond lambda (22 40 07).

UCZCIWE OGRANICZENIA
- Program NIE był jeszcze testowany na Twoim aucie (kabel nie był podłączony). Protokół jest ten sam co w HannaAda
  i pochodzi z prawdziwych nagrań testera na M62TU, ale pierwsze uruchomienie na aucie = test.
- Odczyt/kasowanie błędów to standardowe komendy KWP2000 – format odpowiedzi ME7.2 niepotwierdzony. Kody porównaj z INPA.
- ME7.2 nie podaje "liczników wypadania" przez znany protokół; pokazujemy nierówność biegu per cylinder (ten sam sygnał).
  Kolejność pozycji DME vs numer cylindra M62 niepotwierdzona – potwierdź zamianą cewki.
- Skala adaptacji multiplikatywnej niepewna (oznaczona w programie).

CO JEST WYŁĄCZONE I DLACZEGO
- Flash / programowanie DME – bezpieczeństwo: zły zapis = auto nie odpali. Brak sprawdzonego bootloadera/sum kontrolnych.
- Mapy / tuning – brak zweryfikowanej definicji dla Twojego oprogramowania.
- Kodowanie NCS / Retrofit – brak zweryfikowanych danych; użyj NCS Expert.
- EWS / immobilizer – nie będzie (obchodzenie zabezpieczenia przed kradzieżą).
- Wyłączanie sond / katalizatora / emisji – nie będzie (nielegalne).
- Inne sterowniki (ABS, airbag, skrzynia) i testy elementów – nieobsługiwane w tej wersji.
- AI Mechanic, chmura, Companion, Autopilot, Smart Scan, LPG, Tryby mocy itd. – usunięte (patrz audyt).

AUDYT: STARA WERSJA (AutoDiagPro.exe) -> NOWA
Funkcja / przycisk           | Przed                                                     | Po
-----------------------------|-----------------------------------------------------------|---------------------------
Połączenie ME7.2             | realny kod, ale echo/7F78 słabo obsłużone, 5 protokołów   | REALNE, tylko ME7.2, pełna diagnoza braku odpowiedzi
Identyfikacja                | realna (A2)                                               | REALNA
Błędy – odczyt/kasowanie     | realne komendy, kasowanie bez dobrego potwierdzenia       | REALNE + okno potwierdzenia, status bitowo
Na żywo                      | realne dekodowanie, ale też OBD-PID i "DS2 surowe"        | REALNE (22 40 00)
Wypadanie zapłonów           | mieszane: asystent + symulator miał wpisany cyl. 2        | REALNE (22 40 03) + statystyka
Adaptacje / lambda           | adaptacje realne, lambda brak                             | REALNE oba
Tryb demo / SIMULATOR.json   | ATRAPA (losowe obroty, fałszywe P0302/P0171, VIN SIM)     | USUNIĘTE
Mapy ECU / Flash / Backup ECU| ATRAPA na danych symulatora / backend "simulator"         | WYŁĄCZONE (bezpieczeństwo)
Kodowanie / Retrofit         | PUSTE strony "w przygotowaniu"                            | WYŁĄCZONE z wyjaśnieniem
Tryby mocy / LPG / Wydech    | ATRAPA (bez komunikacji z autem)                          | USUNIĘTE
AI Mechanic / Autopilot      | baza wiedzy + wyniki z symulatora ("TRYB DEMO")           | USUNIĘTE
Smart Scan / Bateria / VIN   | częściowo, E39 ME7.2 nie podaje VIN tą drogą              | USUNIĘTE
Topologia / Active tests / Guided / Serwis | opisy z plików JSON, bez komend do auta     | USUNIĘTE
ODX / UDS / DoIP / J2534 / CAN| nie dotyczy E39 (inne auta)                              | USUNIĘTE
Chmura / Companion / QR      | wysyłanie danych na serwery / serwer HTTP                 | USUNIĘTE
Pulpit (CPU/RAM laptopa)     | dane laptopa udające "panel auta"                         | USUNIĘTE

Oryginalny folder C:\Users\jkrau\Projects\AutoDiagPro i stary AutoDiagPro.exe nie zostały zmienione.


WERSJA I AKTUALIZACJE (od 1.1.0)
- Numer wersji: w tytule okna i w menu Pomoc -> O programie.
- Przy starcie program sprawdza (w tle), czy na GitHub jest nowsza wersja. Przycisk "Aktualizuj" sprawdza ręcznie.
- Bez internetu: pojawi się zwykła informacja "Brak internetu – nie można sprawdzić aktualizacji", program działa dalej.
- Aktualizacja: pobiera ZIP, sprawdza sumę SHA256 (z pliku SHA256SUMS.txt w wydaniu). Jeśli suma się nie zgadza – przerywa.
  Potem program się zamyka, stara wersja trafia do %LOCALAPPDATA%\AutoDiagPro_real\backups, nowa jest wstawiana i uruchamiana.
- Pomoc -> Przywróć poprzednią wersję: wraca do ostatniej kopii z backups.
- Aktualizator zmienia TYLKO pliki programu. Nigdy niczego nie wgrywa do auta.
- Ikona: własny projekt (układ scalony + przebieg sygnału), nie logo BMW.
