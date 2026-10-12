AutoDiag Pro 1.3.0 – opcje ze starego AutoDiag Pro (tylko prawdziwe odczyty, bez trybu demo)

DZIAŁA (wymaga kabla K+DCAN i zapłonu):
- AUTO-DIAGNOZA (Smart Scan): identyfikacja, błędy, dane na żywo, adaptacje, lambda, skan modułów DS2 + raport
- Pokaż wszystkie DTC: DME + EGS, ABS/DSC, Airbag, IKE, LCM, EHC, IHKA, GM
- Szczegóły błędu (freeze frame, KWP 17 HH LL) – surowe bajty, format niepotwierdzony
- Opisy 132 kodów DME 7.2 (źródło: endtuning.com/bmwcodes.html, sprawdzone 132/132)
- Data Log: wykres + zapis CSV; eksport CSV z tabel (błędy, live, adaptacje, moduły, bateria)
- Lista sterowników z identyfikacją w tekście, Topologia, Bateria (napięcie z DME), Raport HTML
- VIN: dekodowanie wpisanego numeru; Ustawienia: autołączenie po wykryciu kabla FTDI
- Blokada portu: jedno żądanie naraz (DME i DS2)

WYŁĄCZONE (widoczne, z powodem): Serwis/Procedury (reset serwisu, interwał IKE, kasowanie adaptacji), Active tests,
Backup ECU, Guided, Touring Studio/Stage (tylko opis), Kodowanie NCS, Retrofit, Mapy, Flash, Katalog SF, Pojazdy,
AI Mechanic/Chmura, Companion, ODX/Sekwencje/UDS, VCI/DoIP/J2534, LPG, Klapa wydechu, Wirtualna hamownia, EWS/emisja (na stałe).

PODZIĘKOWANIA: tabela 132 kodów ME7.2 i pomysł blokady portu pochodzą z poprawek w AutoDiagPro_poprawiony (AUDYT_AutoDiagPro.md, inny bot).
Nie przeniesiono: inicjalizacji 5-baud OBD-II (ogólne OBD 10400 baud, inna ścieżka niż B8 KWP ME7.2 i zależna od starego kodu .pyc),
tokenu podglądu na telefon (Companion usunięty) ani bezpiecznych aktualizacji definicji (ta wersja nie ładuje definicji; aktualizacje programu sprawdzają SHA256).

BEZPIECZEŃSTWO: aktualizator sprawdza SHA256 przed rozpakowaniem i rozpakowuje bezpiecznie (odrzuca ścieżki bezwzględne, C:, '..' i wyjście poza folder – ochrona przed zip-slip).
Wersja 1.3.0 nie ma serwera podglądu na telefon/LAN ani aktualizacji definicji – nie ma czego zabezpieczać tokenem.

## Gałąź lingxi/readonly-dtc-live-modules (tylko odczyt)
- `autodiag_real/bmw_dtc.py` – integracja pracy Engineer Bota: opisy DE z lokalnego `bmw_me72_prg.json` (131 kodów), zapas: publiczna lista EN. Plik JSON NIE trafia do publicznego repo (dane pochodne BMW) – szukany lokalnie. Mapowanie ORT→nr oznaczone jako NIEPEWNE.
- `autodiag_real/live.py` – migawka parametrów ME7.2 (silnik, nierówność biegu, lambda); bez połączenia „—” + „brak połączenia”.
- `autodiag_real/modules_ro.py` – odczyt identyfikacji i pamięci błędów pozostałych modułów E39 przez DS2, z twardą blokadą komend zapisu/kodowania/flash i EWS.
- Niezweryfikowane na aucie: wszystkie adresy DS2, pozycje bajtów live, mapowanie ORT. Kodowanie, flash i EWS pozostają wyłączone.
- UI (`app.py`) nie zmieniony – podpięcie do zrobienia przez właściciela app.py.
