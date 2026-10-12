"""AutoDiag Pro 1.2 – pełny interfejs (menu boczne, grafika, kafelki) + PRAWDZIWY rdzeń ME7.2.
Każda wartość na ekranie pochodzi z odpowiedzi DME. Gdy jej nie ma: „brak odpowiedzi z DME” albo „—”. Brak trybu demo."""
import datetime, os, queue, sys, threading, time
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QRect
from PySide6.QtGui import QIcon, QAction, QColor, QPainter
from PySide6.QtWidgets import (QLineEdit, QCheckBox, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QComboBox, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit, QMessageBox, QFileDialog, QStackedWidget, QFrame, QSizePolicy, QAbstractItemView, QScrollArea)

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from autodiag_real import me72, ds2, updater, extras, me72_dtc, bmw_dtc, coldstart, live as live_ro, modules_ro
from autodiag_real.version import VERSION
from autodiag_real.ui.theme import Theme
from autodiag_real.ui.widgets import glow, Panel, Ring, Spark, Bar, Icon, MStripe, Hero, WindowArt, RED, BLUE, CYAN, GREEN, AMBER, TXT, MUTED

NO_DME = "brak odpowiedzi z DME"
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AutoDiagPro_real")
os.makedirs(LOG_DIR, exist_ok=True)


def resource(*name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", *name)


DISABLED = {
    "Flash": ("ECU Programowanie (Flash / Write)", "Wyłączone na stałe dla bezpieczeństwa. Błąd zapisu może trwale uszkodzić sterownik silnika – auto nie odpali. "
              "Brak sprawdzonego bootloadera i sum kontrolnych dla Twojego DME."),
    "Backup": ("Backup ECU (kopia pamięci DME)", "Wyłączone. ME7.2 udostępnia odczyt pamięci (23 readMemoryByAddress) dopiero po odblokowaniu zabezpieczenia (seed/key), "
               "a bezpiecznej, sprawdzonej procedury dla tego DME nie mamy. Pełny odczyt robi się przez BDM/bootmode z otwartym sterownikiem."),
    "Mapy": ("Mapy ECU", "Wyłączone. Edycja map bez zweryfikowanej definicji dla Twojego numeru oprogramowania to zgadywanie, a zapis wymaga flash."),
    "Tryby mocy": ("Touring Studio / Tryby mocy · Chip-tuning Stage 1/2/3", "Tylko do wglądu: Stage 1 – sama zmiana map (typowo +5–8% na M62), Stage 2 – mapy + dolot/wydech, "
                   "Stage 3 – zmiany mechaniczne. Każdy wymaga zapisu map (flash), a flash jest wyłączony na stałe."),
    "Kodowanie": ("Kodowanie (NCS)", "Wyłączone na stałe. Brak zweryfikowanych danych kodowania dla E39 – do kodowania użyj NCS Expert."),
    "Retrofit": ("Retrofit & Tuning", "Wyłączone. Retrofit wymaga kodowania modułów (NCS), a kodowanie jest wyłączone."),
    "Serwis": ("Serwis / Procedury (reset serwisu, interwał IKE, adaptacje)", "Wyłączone. Nie mamy sprawdzonych komend DS2 do odczytu i kasowania interwału serwisowego w IKE E39 "
               "ani komendy kasowania adaptacji ME7.2 (KWP 31/3B) z potwierdzonym formatem. Reset serwisu zrób przyciskiem w zegarach (licznik dzienny + zapłon poz. 1). "
               "Adaptacje mieszanki można ODCZYTAĆ w zakładce Adaptacje."),
    "Testy": ("Active tests (testy elementów wykonawczych)", "Wyłączone. Brak sprawdzonych komend sterowania elementami (wtryskiwacze, wentylator, VANOS) dla ME7.2 – "
              "zła komenda przy pracującym silniku może być niebezpieczna."),
    "Guided": ("Guided (diagnoza prowadzona)", "Wyłączone. Wymagała bazy procedur producenta, której program nie ma. Użyj AUTO-DIAGNOZA (Smart Scan) – zbiera prawdziwe odczyty."),
    "Pojazdy": ("Pojazdy (baza aut)", "Niepotrzebne – program jest dopasowany do jednego auta: BMW E39 540i (M62TU, ME7.2)."),
    "Katalog": ("Katalog funkcji specjalnych (SF)", "Wyłączone. Funkcje specjalne to kodowanie i procedury serwisowe bez sprawdzonych komend dla E39."),
    "AI": ("AI Mechanic / Baza wiedzy / Chmura", "Usunięte w audycie. Stara wersja wysyłała dane do chmury i podawała ogólne porady, nie odczyty z auta."),
    "Companion": ("Companion (telefon) / QR", "Usunięte w audycie – otwierało serwer sieciowy na laptopie bez zabezpieczeń."),
    "ODX": ("ODX / Sekwencje / UDS", "Nie dotyczy E39. ODX i UDS (ISO 14229) to diagnostyka nowszych aut na CAN; E39 używa DS2 i KWP2000 po K-line."),
    "VCI": ("VCI / DoIP / J2534", "Nie dotyczy. Jedynym interfejsem jest kabel K+DCAN (port COM – wybór na stronie Przegląd). DoIP jest od serii F."),
    "LPG": ("LPG", "Nie dotyczy. Sterownik LPG ma własny program producenta instalacji i nie rozmawia przez K-line BMW."),
    "Wydech": ("Klapa wydechu", "Nie dotyczy. E39 540i nie ma sterowanej klapy wydechu w DME."),
    "Hamownia": ("Wirtualna hamownia", "Wyłączone. Stara wersja podawała szacunek, nie pomiar. Do rzeczywistej mocy potrzebna jest hamownia."),
    "EWS": ("EWS / immobilizer · emisja", "Niedostępne i nie będzie. Obchodzenie zabezpieczenia przed kradzieżą i wyłączanie sond/katalizatora/emisji "
            "nie są wspierane (nielegalne / niebezpieczne)."),
}

NAV = [("Home", "home", "home"), ("Auto-diagnoza", "ai", "Smart"), ("Diagnostyka", "gear", "Błędy"), ("Live Data", "chart", "Na żywo"), ("Data Log", "db", "DataLog"),
       ("Zapłony", "ai", "Zapłony"), ("BMW Expert", "roundel", "Moduły"), ("Touring Studio", "car", "Tryby mocy"), ("Serwis", "wrench", "Serwis"), ("Kodowanie", "code", "Kodowanie"),
       ("ECU Program.", "chip", "Flash"), ("Raport", "book", "Raport"), ("Dane / Logi", "db", "Log"), ("Ustawienia", "gear", "Ustawienia")]
SIDE = [("Przegląd", "home", "home"), ("AUTO-DIAGNOZA (Smart Scan)", "ai", "Smart"), ("Identyfikacja DME", "chip", "Identyfikacja"), ("Diagnostyka (błędy DME)", "gear", "Błędy"),
        ("Pokaż wszystkie DTC", "gear", "WszystkieDTC"), ("Live Data", "chart", "Na żywo"), ("Data Log (wykres + CSV)", "db", "DataLog"),
        ("Wypadanie zapłonów", "ai", "Zapłony"), ("Nie odpala na zimno", "wrench", "Zimny start"), ("Adaptacje / lambda", "wrench", "Adaptacje"), ("BMW Expert / Lista sterowników", "roundel", "Moduły"),
        ("Zawieszenie EHC", "car", "Moduły"), ("Topologia", "plug", "Topologia"), ("Bateria", "chip", "Bateria"), ("VIN Auto", "book", "VIN"),
        ("Raport", "book", "Raport"), ("Log (surowe bajty)", "db", "Log"), ("Ustawienia / VCI", "gear", "Ustawienia"),
        None, ("Serwis / Procedury", "wrench", "Serwis"), ("Active tests", "plug", "Testy"), ("Backup ECU", "db", "Backup"), ("Guided", "ai", "Guided"),
        ("Touring Studio / Stage", "car", "Tryby mocy"), ("Kodowanie (NCS)", "code", "Kodowanie"), ("Retrofit & Tuning", "plug", "Retrofit"), ("Mapy ECU", "db", "Mapy"),
        ("ECU Programowanie", "chip", "Flash"), ("Katalog SF", "book", "Katalog"), ("Pojazdy", "car", "Pojazdy"), ("AI Mechanic / Chmura", "ai", "AI"),
        ("Companion", "plug", "Companion"), ("ODX / Sekwencje / UDS", "code", "ODX"), ("VCI / DoIP", "plug", "VCI"), ("LPG", "gear", "LPG"),
        ("Klapa wydechu", "car", "Wydech"), ("Wirtualna hamownia", "chart", "Hamownia"), ("EWS / emisja", "book", "EWS")]

SHELL_QSS = """
#Root{background:transparent}
#Top{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(8,14,30,200),stop:1 rgba(4,8,18,175));border-bottom:1px solid rgba(63,169,255,200)}
#NavBtn{background:rgba(10,18,36,170);border:1px solid rgba(31,111,255,70);border-radius:6px}
#NavBtn:checked{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2f7fff,stop:1 #0b3d99);border:2px solid #8cc6ff}
#Side{background:rgba(4,8,18,170);border-right:1px solid rgba(255,35,64,170);border-top-right-radius:10px}
#SideBtn{background:transparent;border:none;border-left:3px solid transparent;border-radius:0;text-align:left;padding:8px 10px;font-size:10pt;font-weight:500;color:#d5ddef}
#SideBtn:hover{background:rgba(31,111,255,40)}
#SideBtn:checked{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(255,35,64,110),stop:1 rgba(255,35,64,0));border-left:3px solid #ff2340;color:#fff;font-weight:700}
#SideSep{color:#8d9ab3;font-size:7.5pt;letter-spacing:2px;padding:6px 12px 2px 12px}
#VCard{background:rgba(5,10,22,185);border:2px solid rgba(63,169,255,230);border-radius:8px}
#Tile{background:rgba(6,12,26,170);border:2px solid rgba(63,169,255,230);border-radius:8px}
#TileRed{background:rgba(26,6,10,175);border:2px solid #ff2340;border-radius:8px}
#Status{background:rgba(4,8,18,200);border-top:1px solid rgba(31,111,255,110)}
#Status QLabel{font-size:8.5pt;color:#d5ddef}
"""

LIVE_TILES = [("Obroty", "Obroty", "obr/min", CYAN), ("Temp. płynu chłodzącego", "Temp. płynu", "°C", RED), ("Temp. powietrza dolotowego", "Temp. ssania", "°C", AMBER),
              ("Napięcie akumulatora (DME)", "Napięcie", "V", "#c64bff"), ("Masa powietrza (MAF)", "MAF", "kg/h", CYAN), ("Kąt wyprzedzenia zapłonu", "Kąt zapłonu", "°", GREEN)]


class Bus(QObject):
    done = Signal(str, object, object)
    log = Signal(str)
    upd = Signal(str, object, object, bool)


class Worker:
    """Jeden wątek rozmawia z kablem – GUI się nie zawiesza."""
    def __init__(self, bus):
        self.bus = bus; self.q = queue.Queue(); threading.Thread(target=self._run, daemon=True).start()

    def submit(self, name, fn): self.q.put((name, fn))

    def busy(self): return not self.q.empty()

    def _run(self):
        while True:
            name, fn = self.q.get()
            try: self.bus.done.emit(name, fn(), None)
            except Exception as e: self.bus.done.emit(name, None, e)


def table(headers):
    t = QTableWidget(0, len(headers)); t.setHorizontalHeaderLabels(headers); t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); t.setEditTriggers(QTableWidget.NoEditTriggers); return t


BMW_TOOLS = {"NCS": ("NCS Expert", [r"C:\NCSEXPER\BIN\NCSEXPER.EXE"]),
             "Flash": ("WinKFP", [r"C:\EC-APPS\NFS\BIN\WINKFP.EXE", r"C:\EC-APPS\NFS\WINKFP.EXE"])}


def _bmw_tool_status(title):
    """Tylko informacja – AutoDiag Pro nie uruchamia NCS/WinKFP."""
    key = "NCS" if "NCS" in title else ("Flash" if "Flash" in title else None)
    if not key: return ""
    name, paths = BMW_TOOLS[key]
    found = next((p for p in paths if os.path.isfile(p)), None)
    return ("%s: zainstalowano (%s) – w AutoDiag Pro nadal wyłączone." % (name, found)) if found else ("%s: nie zainstalowano." % name)


def fill(t, rows):
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            t.setItem(r, c, QTableWidgetItem(("%.2f" % v) if isinstance(v, float) else str(v)))


class Chart(QWidget):
    """Wykres historii wybranego parametru – wyłącznie punkty odebrane z DME."""
    def __init__(self, owner): super().__init__(); self.o = owner; self.setMinimumHeight(260)

    def paintEvent(self, e):
        from PySide6.QtGui import QPen
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); r = self.rect().adjusted(50, 12, -12, -24)
        p.fillRect(self.rect(), QColor(7, 13, 28, 170)); p.setPen(QColor("#2a3a5c")); p.drawRect(r)
        ys = self.o.hist.get(self.o.dl_param.currentText(), [])
        if len(ys) < 2:
            p.setPen(QColor(MUTED)); p.drawText(self.rect(), Qt.AlignCenter, "brak danych – włącz odczyt na żywo (wymaga połączenia z DME)"); return
        lo, hi = min(ys), max(ys); hi = hi if hi > lo else lo + 1
        p.setPen(QColor(MUTED)); p.drawText(4, r.top() + 10, "%.1f" % hi); p.drawText(4, r.bottom(), "%.1f" % lo)
        p.drawText(r.left(), self.height() - 6, "ostatnie %d próbek (co ok. 0,7 s), teraz: %.2f" % (len(ys), ys[-1]))
        p.setPen(QPen(QColor(CYAN), 2)); n = len(ys); pts = [(r.left() + r.width() * i / (n - 1), r.bottom() - r.height() * (y - lo) / (hi - lo)) for i, y in enumerate(ys)]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]): p.drawLine(int(x1), int(y1), int(x2), int(y2))


class Topology(QWidget):
    """Mapa magistrali: moduły jako węzły z kolorem wg wyniku prawdziwego skanu DS2."""
    def __init__(self): super().__init__(); self.rows = []; self.conn = False; self.setMinimumHeight(260)
    def set_data(self, conn, rows): self.conn = conn; self.rows = rows; self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); W, H = self.width(), self.height(); p.fillRect(self.rect(), QColor(7, 13, 28, 170))
        nodes = [("DME ME7.2", "0x12", None)] + [(r[0], r[1], r) for r in self.rows] if self.rows else [("DME ME7.2", "0x12", None)] + [(n, "0x%02X" % a, None) for n, a in ds2.MODULES]
        y = H // 2; p.setPen(QColor(BLUE)); p.drawLine(30, y, W - 30, y); p.drawText(30, y - 8, "K-line (DS2 / KWP2000) – złącze OBD")
        n = len(nodes); step = (W - 60) / max(n, 1)
        for i, (name, addr, row) in enumerate(nodes):
            if row is None and i == 0: col = GREEN if self.conn else "#56607a"
            elif row is None: col = "#56607a"
            elif row[2].startswith("—"): col = RED
            elif row[3].startswith("—") or row[3] in ("(nic)",): col = GREEN
            else: col = AMBER
            x = int(30 + step * i + step / 2); yy = y - 70 if i % 2 == 0 else y + 30
            p.setPen(QColor(col)); p.drawLine(x, y, x, yy + (40 if i % 2 == 0 else 0)); p.setBrush(QColor(col).darker(250))
            rr = QRect(x - int(step / 2) + 4, yy, int(step) - 8, 40); p.drawRoundedRect(rr, 6, 6); p.setPen(QColor(TXT))
            p.drawText(rr, Qt.AlignCenter | Qt.TextWordWrap, "%s\n%s" % (name.split(" – ")[0], addr))


class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("AutoDiag Pro %s – REALNY odczyt BMW E39 ME7.2 (bez demo)" % VERSION)
        self.setWindowIcon(QIcon(resource("icon.ico"))); self.art = WindowArt()
        self.bus = Bus(); self.bus.done.connect(self.on_done); self.bus.log.connect(self._trace_line); self.bus.upd.connect(self.on_update)
        self.worker = Worker(self.bus); self.tr = None; self.dev = None; self.ident = None; self.faults = None; self.live = {}; self.rough_samples = []
        self.mod_rows = []; self.dtc_rows = []; self.hist = {}; self.hist_t = []; self.csvlog = None; self.volt_hist = []; self.ff_rows = []; self.vin_rows = []
        self.settings_path = os.path.join(LOG_DIR, 'settings.txt')
        self.trace_path = os.path.join(LOG_DIR, "trace_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")); self.dme_btns = []
        root = QWidget(); root.setObjectName("Root"); root.setStyleSheet(Theme.QSS + SHELL_QSS)
        v = QVBoxLayout(root); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0); v.addWidget(self._top())
        body = QHBoxLayout(); body.setSpacing(0); sd = QScrollArea(); sd.setWidget(self._side()); sd.setWidgetResizable(True); sd.setFrameShape(QFrame.NoFrame); sd.setFixedWidth(240)
        sd.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); sd.setStyleSheet("QScrollArea{background:transparent} QScrollArea > QWidget > QWidget{background:transparent} QScrollBar:vertical{width:5px;background:transparent} QScrollBar::handle:vertical{background:#1f6fff;border-radius:2px}")
        body.addWidget(sd)
        self.stack = QStackedWidget(); self.idx = {}
        self._add("home", self._home())
        self._add("Identyfikacja", self._page_ident()); self._add("Błędy", self._page_dtc()); self._add("Na żywo", self._page_live())
        self._add("Zapłony", self._page_mis()); self._add("Zimny start", self._page_cold()); self._add("Adaptacje", self._page_adapt()); self._add("Log", self._page_log()); self._add("Ustawienia", self._page_settings()); self._add("Moduły", self._page_modules())
        self._add("Smart", self._page_smart()); self._add("WszystkieDTC", self._page_alldtc()); self._add("DataLog", self._page_datalog())
        self._add("Topologia", self._page_topology()); self._add("Bateria", self._page_battery()); self._add("VIN", self._page_vin()); self._add("Raport", self._page_report())
        for key, (title, why) in DISABLED.items(): self._add(key, self._page_disabled(title, why))
        body.addWidget(self.stack, 1); v.addLayout(body, 1); v.addWidget(self._status()); self.setCentralWidget(root)
        m = self.menuBar(); m.setStyleSheet("QMenuBar{background:rgba(4,8,18,190);color:#d5ddef} QMenu{background:#0d0f24;color:#e8ecff}")
        mp = m.addMenu("Pomoc")
        for text, fn in (("Sprawdź aktualizacje", lambda: self.check_update(True)), ("Przywróć poprzednią wersję…", self.rollback), ("O programie", self.about)):
            a = QAction(text, self); a.triggered.connect(fn); mp.addAction(a)
        self.live_timer = QTimer(self); self.live_timer.timeout.connect(self.poll_live)
        self.clock_t = QTimer(self); self.clock_t.timeout.connect(self.tick); self.clock_t.start(1000)
        self.resize(1600, 960); self.refresh_ports(); self._enable(False); self.go("home"); self.refresh(); self.tick()
        self.log("Start AutoDiag Pro %s – bez trybu demo" % VERSION); self._trace_line("Plik śladu: " + self.trace_path)
        QTimer.singleShot(2500, lambda: self.check_update(False))
        if self._load_settings().get("autoconnect") == "1" and any("FTDI" in self.port.itemText(i) for i in range(self.port.count())): QTimer.singleShot(800, self.connect)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform); self.art.paint(p, self.rect(), self.art_target())

    def art_target(self):
        """Ostra grafika tylko w wolnym miejscu: na Home w polu obok karty pojazdu, na innych stronach – brak (tylko rozmyte tło)."""
        if not hasattr(self, "hero") or self.stack.currentIndex() != self.idx.get("home") or not self.hero.isVisible(): return None
        tl = self.hero.mapTo(self, self.hero.rect().topLeft()); r = QRect(tl, self.hero.size())
        clip = QRect(self.stack.mapTo(self, self.stack.rect().topLeft()), self.stack.size()); return r.intersected(clip)

    def resizeEvent(self, e):
        super().resizeEvent(e); self._fit_top()

    def _fit_top(self):
        """Poniżej ~1200 px szerokości: górne menu same ikony (podpis w dymku), niższy pasek."""
        if not hasattr(self, "nav_scroll"): return
        compact = self.width() < 1200
        if compact == self._compact: return
        self._compact = compact
        for _, b in self.nav:
            b._lb.setVisible(not compact); b.setFixedSize(*((40, 40) if compact else (74, 64)))
            b._bl.setContentsMargins(*((2, 2, 2, 2) if compact else (2, 7, 2, 4)))
        self.top.setFixedHeight(56 if compact else 80); self.nav_scroll.setFixedHeight(46 if compact else 70)
        self.logo_lbl.setVisible(not compact)

    # ------------------------------------------------ budowa interfejsu
    def _add(self, key, w): self.idx[key] = self.stack.count(); self.stack.addWidget(w)

    def _top(self):
        top = QFrame(); top.setObjectName("Top"); top.setFixedHeight(80); h = QHBoxLayout(top); h.setContentsMargins(10, 6, 14, 6); h.setSpacing(5)
        h.addWidget(Icon("chip", "#3fa9ff", 44))
        h.addWidget(QLabel("<div style='line-height:95%'><span style='font-size:21pt;font-weight:900;color:#ff3b55'>Auto</span><span style='font-size:21pt;font-weight:900;color:#2b8cff'>Diag</span>"
                           "<span style='font-size:21pt;font-weight:300'> PRO</span><br><span style='font-size:9pt;font-weight:300;letter-spacing:4px'>DIAGNOSTICS</span><br>"
                           "<span style='font-size:7pt;color:#8d9ab3'>BMW E39 • ME7.2 • K+DCAN</span></div>")); h.addSpacing(6); self.nav = []
        navw = QWidget(); navl = QHBoxLayout(navw); navl.setContentsMargins(0, 0, 0, 0); navl.setSpacing(4)
        for n, ic, target in NAV:
            b = QPushButton(); b.setObjectName("NavBtn"); b.setCheckable(True); b.setFixedSize(74, 64)
            bl = QVBoxLayout(b); bl.setContentsMargins(2, 7, 2, 4); bl.setSpacing(3); iw = Icon(ic, "#ffffff" if target not in DISABLED else "#56607a", 24); bl.addWidget(iw, 0, Qt.AlignHCenter)
            lb = QLabel(n.upper()); lb.setAlignment(Qt.AlignCenter); lb.setWordWrap(True); lb.setStyleSheet("font-size:6.5pt;font-weight:700;color:%s" % ("#fff" if target not in DISABLED else "#7a8296")); bl.addWidget(lb)
            for x in (iw, lb): x.setAttribute(Qt.WA_TransparentForMouseEvents)
            b.setToolTip(n); b._lb = lb; b._bl = bl
            b.clicked.connect(lambda _, t=target: self.go(t)); navl.addWidget(b); self.nav.append((target, b)); glow(b, "#1f6fff", 16, 150)
        navl.addStretch(); ns = QScrollArea(); ns.setWidget(navw); ns.setWidgetResizable(True); ns.setFrameShape(QFrame.NoFrame); ns.setFixedHeight(70); self.top = top; self.nav_scroll = ns; self.logo_lbl = h.itemAt(1).widget(); self._compact = None
        ns.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); ns.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded); ns.setMinimumWidth(200)
        ns.setStyleSheet("QScrollArea{background:transparent} QScrollArea > QWidget > QWidget{background:transparent} QScrollBar:horizontal{height:5px;background:transparent} QScrollBar::handle:horizontal{background:#1f6fff;border-radius:2px}")
        h.addWidget(ns, 1); ms = MStripe(4); ms.setFixedWidth(40); h.addWidget(ms); h.addSpacing(8)
        r = QVBoxLayout(); r.setSpacing(0); r.setContentsMargins(0, 0, 0, 0); self.clock = QLabel(); self.clock.setAlignment(Qt.AlignRight); self.clock.setMinimumWidth(92); r.addWidget(self.clock)
        self.online = QLabel(); self.online.setAlignment(Qt.AlignRight); self.online.setMinimumWidth(92); r.addWidget(self.online); h.addLayout(r); return top

    def _side(self):
        side = QFrame(); side.setObjectName("Side"); side.setFixedWidth(235); v = QVBoxLayout(side); v.setContentsMargins(0, 8, 0, 8); v.setSpacing(1); self.sidebtn = []
        for item in SIDE:
            if item is None:
                l = QLabel("WYŁĄCZONE – dlaczego?"); l.setObjectName("SideSep"); v.addWidget(l); continue
            n, ic, target = item; b = QPushButton("        " + n); b.setObjectName("SideBtn"); b.setCheckable(True); b.setMinimumHeight(36)
            if target in DISABLED: b.setStyleSheet("color:#6b7590")
            iw = Icon(ic, "#ffffff" if target not in DISABLED else "#56607a", 20); iw.setParent(b); iw.move(12, 8); iw.setAttribute(Qt.WA_TransparentForMouseEvents)
            b.clicked.connect(lambda _, t=target: self.go(t)); v.addWidget(b); self.sidebtn.append((target, b))
        v.addStretch()
        self.b_upd = QPushButton("⟳  Aktualizuj"); self.b_upd.setObjectName("Ghost"); self.b_upd.clicked.connect(lambda: self.check_update(True)); v.addWidget(self.b_upd)
        return side

    def _conn_row(self):
        h = QGridLayout(); h.setHorizontalSpacing(6); h.setVerticalSpacing(6); self.port = QComboBox(); self.port.setMinimumWidth(150)
        self.port.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon); self.port.setMinimumContentsLength(14)
        self.port.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b_ref = QPushButton("Odśwież"); b_ref.setObjectName("Ghost"); b_ref.clicked.connect(self.refresh_ports)
        self.b_conn = QPushButton("Połącz z DME"); self.b_conn.clicked.connect(self.connect)
        self.b_disc = QPushButton("Rozłącz"); self.b_disc.setObjectName("Ghost"); self.b_disc.clicked.connect(self.disconnect)
        for b in (b_ref, self.b_conn, self.b_disc): b.setStyleSheet("padding:7px 10px"); b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h.addWidget(self.port, 0, 0, 1, 2); h.addWidget(b_ref, 0, 2); h.addWidget(self.b_conn, 1, 0, 1, 2); h.addWidget(self.b_disc, 1, 2)
        h.setColumnStretch(0, 1); h.setColumnStretch(1, 1); h.setColumnStretch(2, 1); return h

    def _vehicle_card(self, parent):
        c = QFrame(parent); c.setObjectName("VCard"); c.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum); g = QVBoxLayout(c); g.setContentsMargins(14, 10, 14, 10); g.setSpacing(5)
        hh = QHBoxLayout(); hh.addWidget(QLabel("<span style='font-size:14pt;font-weight:800'>BMW E39 540i (M62)</span>"), 1); ms = MStripe(4); ms.setFixedWidth(34); hh.addWidget(ms); hh.addStretch(); g.addLayout(hh)
        self.card_ecu = QLabel(); self.card_ecu.setWordWrap(True); g.addWidget(self.card_ecu)
        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet("background:rgba(63,169,255,110)"); g.addWidget(line)
        grid = QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(3); self.card_vals = {}
        for i, k in enumerate(["Numer części BMW", "Hardware", "Indeks kodowania", "Rok produkcji", "Dostawca"]):
            a = QLabel("<span style='color:#8d9ab3'>%s:</span>" % k); a.setMinimumWidth(a.sizeHint().width()); a.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            b = QLabel("—"); b.setWordWrap(True); b.setTextInteractionFlags(Qt.TextSelectableByMouse); self.card_vals[k] = b; grid.addWidget(a, i, 0, Qt.AlignTop); grid.addWidget(b, i, 1)
        grid.setColumnStretch(1, 1); g.addLayout(grid); g.addLayout(self._conn_row())
        q = QGridLayout(); q.setSpacing(6); qi = 0
        for n, fn in [("Skan błędów", self.read_dtc), ("Live", lambda: self.go("Na żywo")), ("Zapłony", lambda: self.go("Zapłony")), ("Adaptacje", lambda: self.go("Adaptacje"))]:
            b = QPushButton(n); b.setObjectName("Ghost"); b.setStyleSheet("padding:6px 8px"); b.clicked.connect(fn); q.addWidget(b, qi // 2, qi % 2); qi += 1
            if n == "Skan błędów": self.dme_btns.append(b)
        g.addLayout(q); self.card_status = QLabel(); self.card_status.setWordWrap(True); self.card_status.setStyleSheet("font-size:9.5pt;font-weight:700"); g.addWidget(self.card_status); return c

    def _tiles(self):
        w = QWidget(); self.tile_grid = h = QGridLayout(w); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(10); self.tile_ws = []; acc = ["#1f6fff", "#00e5d4", "#ff3fb4", "#a64dff", "#3fa9ff"]
        for i, (title, sub, ic, btn, target, red) in enumerate([("Silnik", "Sterownik DME ME7.2", "chip", "Diagnostyka", "Błędy", False),
                ("Dane na żywo", "Z DME, co 0,7 s", "chart", "Live Data", "Na żywo", False), ("Wypadanie zapłonów", "Nierówność cyl. 1–8", "ai", "Zapłony", "Zapłony", False),
                ("Adaptacje", "Mieszanka + lambda", "wrench", "Adaptacje", "Adaptacje", False), ("ECU Programowanie", "Wyłączone (bezpieczeństwo)", "chip", "Dlaczego?", "Flash", True)]):
            f = QFrame(); f.setObjectName("TileRed" if red else "Tile"); v = QVBoxLayout(f); v.setContentsMargins(10, 8, 10, 8); v.setSpacing(6)
            ac = RED if red else acc[i % len(acc)]
            if not red: f.setStyleSheet("#Tile{border:2px solid %s}" % ac)
            r = QHBoxLayout(); r.addWidget(Icon(ic, ac, 42)); r.addWidget(QLabel("<b style='font-size:11.5pt'>%s</b><br><span style='color:#aab4c8;font-size:8.5pt'>%s</span>" % (title, sub)), 1); v.addLayout(r)
            b = QPushButton("⊕  " + btn); b.setObjectName("Ghost"); b.clicked.connect(lambda _, t=target: self.go(t)); v.addWidget(b); self.tile_ws.append(f); glow(f, ac, 30, 220)
        return w

    def _home(self):
        """Grafika ma własny obszar (cała widoczna), karta pojazdu obok (szeroko) albo pod nią (wąsko). Całość przewijana, nic nie jest ucinane."""
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.NoFrame); sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); sc.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        sc.verticalScrollBar().setStyleSheet("QScrollBar:vertical{width:6px;background:transparent} QScrollBar::handle:vertical{background:#1f6fff;border-radius:3px}")
        sc.setStyleSheet("QScrollArea{background:transparent} QScrollArea > QWidget > QWidget{background:transparent}")
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(6, 6, 6, 6); v.setSpacing(8)
        heroes = sorted(os.listdir(resource("hero"))) if os.path.isdir(resource("hero")) else []
        self.hero = Hero(None); self.hero.spacer = True; self.hero.on_art = lambda pth: (self.art.set_art(pth), self.update())
        self.hero.set_art(resource("hero", heroes[0]) if heroes else None); self.hero.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.vcard = self._vehicle_card(None); glow(self.vcard, "#c04dff", 30, 170)
        self.hero_row = QGridLayout(); self.hero_row.setSpacing(8); v.addLayout(self.hero_row); self._hero_wide = None
        v.addWidget(self._tiles()); v.addWidget(self._bottom()); sc.setWidget(w)
        self.home_body = w; self.home_scroll = sc; sc.verticalScrollBar().valueChanged.connect(lambda _: self.update()); sc.resizeEvent = lambda e: (QScrollArea.resizeEvent(sc, e), self._place_card()); return sc

    def _place_card(self):
        if not hasattr(self, "home_scroll"): return
        W = self.home_scroll.viewport().width() - 12; wide = W >= 1250
        if wide != self._hero_wide:
            for x in self.tile_ws: self.tile_grid.removeWidget(x)
            for x, _ in self.bot_ws: self.bot_grid.removeWidget(x)
            for c in range(6): self.tile_grid.setColumnStretch(c, 0); self.bot_grid.setColumnStretch(c, 0)
            if wide:
                for i, x in enumerate(self.tile_ws): self.tile_grid.addWidget(x, 0, i); self.tile_grid.setColumnStretch(i, 1)
                for i, (x, st) in enumerate(self.bot_ws): self.bot_grid.addWidget(x, 0, i); self.bot_grid.setColumnStretch(i, st)
            else:
                for i, x in enumerate(self.tile_ws): self.tile_grid.addWidget(x, i // 3, i % 3); self.tile_grid.setColumnStretch(i % 3, 1)
                order = [(0, 0, 0, 1, 1), (1, 0, 1, 1, 1), (3, 0, 2, 1, 1), (2, 1, 0, 1, 2), (4, 1, 2, 1, 1)]
                for k, r, c, rs, cs in order: self.bot_grid.addWidget(self.bot_ws[k][0], r, c, rs, cs)
                for c in range(3): self.bot_grid.setColumnStretch(c, 1)
            self._hero_wide = wide; self.hero_row.removeWidget(self.hero); self.hero_row.removeWidget(self.vcard)
            # karta zawsze po lewej (przyciski połączenia bez przewijania), po prawej przezroczyste "okno" na grafikę tła
            self.hero_row.addWidget(self.vcard, 0, 0, Qt.AlignTop); self.hero_row.addWidget(self.hero, 0, 1); self.hero_row.setColumnStretch(1, 1)
        cw = int(min(440, max(330, W * 0.27))) if wide else int(min(380, max(320, W * 0.42))); self.vcard.setFixedWidth(cw)
        hw = max(200, W - cw - 8); self.hero.setMinimumHeight(min(560, int(hw / self.art.aspect()))); self.update()
    def _bottom(self):
        w = QWidget(); w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum); self.bot_grid = QGridLayout(w); self.bot_grid.setContentsMargins(0, 0, 0, 0); self.bot_grid.setSpacing(6); self.bot_ws = []
        class _H:  # zbiera panele, układ (1 lub 2 rzędy) ustala _place_card
            def __init__(s2, me): s2.me = me
            def addWidget(s2, wd, st=1): wd.setMinimumHeight(210); wd.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum); s2.me.bot_ws.append((wd, st))
        h = _H(self)
        p = Panel("Status", RED, "DME"); self.health = QLabel(); self.health.setAlignment(Qt.AlignCenter); self.health.setWordWrap(True); p.l.addWidget(self.health, 1)
        p.l.addWidget(QLabel("<span style='color:#8d9ab3;font-size:7.5pt'>Odpytywany jest tylko DME silnika (0x12).</span>")); glow(p, RED, 26, 150); h.addWidget(p, 3)
        p = Panel("Błędy", BLUE, "(DTC z DME)"); self.dtc_ring = Ring(0, RED, "—", "w pamięci", thick=0.08); self.dtc_ring.setMinimumSize(90, 90); p.l.addWidget(self.dtc_ring, 1)
        b = QPushButton("Pokaż błędy"); b.setObjectName("Ghost"); b.clicked.connect(lambda: self.go("Błędy")); p.l.addWidget(b); glow(p, "#00e5d4", 26, 170); h.addWidget(p, 2)
        p = Panel("Live", RED, "Data (z DME)"); g = QGridLayout(); g.setSpacing(5); self.live_tiles = {}
        for i, (key, label, unit, col) in enumerate(LIVE_TILES):
            f = QFrame(); f.setStyleSheet("QFrame{background:rgba(7,13,28,150);border:1px solid rgba(63,169,255,70);border-radius:5px}"); fv = QVBoxLayout(f); fv.setContentsMargins(8, 4, 8, 4); fv.setSpacing(0)
            t = QLabel("<span style='color:#aab4c8;font-size:8pt'>%s</span>" % label); val = QLabel("—"); sp = Spark(col)
            for x in (t, val): x.setStyleSheet("border:none")
            fv.addWidget(t); fv.addWidget(val); fv.addWidget(sp, 1); g.addWidget(f, i // 3, i % 3); self.live_tiles[key] = (val, sp, unit, col)
        p.l.addLayout(g); self.b_live_home = QPushButton("▶  Start odczytu na żywo"); self.b_live_home.setCheckable(True); self.b_live_home.toggled.connect(self.toggle_live)
        self.dme_btns.append(self.b_live_home); p.l.addWidget(self.b_live_home); glow(p, RED, 26, 150); h.addWidget(p, 6)
        p = Panel("Zapłony", BLUE, "nierówność cyl."); self.mis_bars = []
        for c in range(8):
            r = QHBoxLayout(); l = QLabel("Cyl. %d" % (c + 1)); l.setMinimumWidth(42); r.addWidget(l); b = Bar(0, "#33405f"); r.addWidget(b, 1); vl = QLabel("—"); vl.setMinimumWidth(48); r.addWidget(vl)
            p.l.addLayout(r); self.mis_bars.append((b, vl))
        glow(p, "#a64dff", 26, 170); h.addWidget(p, 3)
        p = Panel("Ostatnie", BLUE, "operacje"); self.ops = QTableWidget(0, 3); self.ops.horizontalHeader().hide(); self.ops.verticalHeader().hide(); self.ops.setShowGrid(False)
        self.ops.setEditTriggers(QAbstractItemView.NoEditTriggers); self.ops.verticalHeader().setDefaultSectionSize(20)
        self.ops.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents); self.ops.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); self.ops.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ops.setStyleSheet("QTableWidget{background:transparent;border:none;font-size:8.5pt}"); p.l.addWidget(self.ops); glow(p, "#ff3fb4", 26, 170); h.addWidget(p, 4)
        return w

    def _status(self):
        s = QFrame(); s.setObjectName("Status"); s.setFixedHeight(28); h = QHBoxLayout(s); h.setContentsMargins(12, 0, 12, 0); self.sb = {}
        for k in ("car", "if", "v", "err"):
            l = QLabel(); h.addWidget(l); self.sb[k] = l; sep = QLabel("|"); sep.setStyleSheet("color:#2a3a5c"); h.addWidget(sep)
        h.addStretch(); h.addWidget(QLabel("AutoDiag Pro  •  v%s" % VERSION)); return s

    def _page(self, title, sub, widget, buttons, info=None, extra=None):
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(16, 12, 16, 12)
        t = QLabel("<span style='font-size:18pt;font-weight:800'>%s</span>  <span style='color:%s'>%s</span>" % (title, MUTED, sub)); v.addWidget(t)
        h = QHBoxLayout()
        for text, fn, dme in buttons:
            b = QPushButton(text); b.clicked.connect(fn); h.addWidget(b)
            if dme: self.dme_btns.append(b)
        if extra: h.addWidget(extra); self.dme_btns.append(extra)
        h.addStretch(); v.addLayout(h)
        if info: info.setWordWrap(True); v.addWidget(info)
        pn = Panel(); pn.l.addWidget(widget); v.addWidget(pn, 1); return p

    def _page_ident(self):
        self.t_id = table(["Pole", "Wartość z DME"]); return self._page("Identyfikacja DME", "komenda A2", self.t_id, [("Czytaj identyfikację", self.read_ident, True)])

    def _page_live(self):
        self.t_live = table(["Parametr", "Wartość", "Jednostka", "Status"]); fill(self.t_live, live_ro.snapshot(None)[0]); self.b_live = QPushButton("▶  Start odczytu na żywo"); self.b_live.setCheckable(True)
        self.b_live.toggled.connect(self.toggle_live)
        return self._page("Live Data", "22 40 00 – co 0,7 s", self.t_live, [("Odczytaj raz", self.read_live, True), ("Eksport CSV…", lambda: self.export_csv(self.t_live, "live"), False)], extra=self.b_live)

    def _page_cold(self):
        self.t_cold = table(["Krok", "Wartość", "Status / jednostka"]); fill(self.t_cold, coldstart.run(None)["steps"])
        self.cold_box = QPlainTextEdit(); self.cold_box.setReadOnly(True); self.cold_box.setPlainText(coldstart.format_report(coldstart.run(None)))
        info = QLabel("Tylko odczyt (akumulator, płyn vs powietrze, nierówność cylindrów, błędy ME7.2). Kluczyk poz. 2 albo silnik na biegu jałowym. "
                      "Progi wstępne – do weryfikacji na aucie. Bez połączenia: „—” i brak werdyktu.")
        pg = self._page("Nie odpala na zimno", "kreator – E39 540i M62TU / ME7.2", self.t_cold,
                        [("Uruchom kreator", self.run_cold, True)], info)
        pg.layout().addWidget(self.cold_box); return pg

    def run_cold(self): self.run("cold", lambda: coldstart.run(self.dev))

    def _page_mis(self):
        self.t_mis = table(["Cylinder (pozycja w DME)", "Ostatnia nierówność [1/s]", "Średnia [1/s]", "z-score"])
        self.mis_info = QLabel("Silnik na wolnych obrotach, rozgrzany. Zbierz min. 20 próbek. Kolejność pozycji DME vs numer cylindra M62 niepotwierdzona.")
        return self._page("Wypadanie zapłonów", "22 40 03 – nierówność biegu", self.t_mis,
                          [("Zbierz 20 próbek", self.read_rough, True), ("Wyczyść próbki", self.clear_rough, False)], self.mis_info)

    def _page_adapt(self):
        self.t_ad = table(["Parametr", "Wartość", "Jednostka"])
        return self._page("Adaptacje / lambda", "22 40 04 · 22 40 07", self.t_ad, [("Czytaj adaptacje", self.read_adapt, True), ("Czytaj status lambda", self.read_lambda, True), ("Eksport CSV…", lambda: self.export_csv(self.t_ad, "adaptacje"), False)])

    def _page_log(self):
        self.logbox = QPlainTextEdit(); self.logbox.setReadOnly(True)
        return self._page("Log", "wszystkie wysłane i odebrane bajty", self.logbox, [("Zapisz log do pliku…", self.save_log, False)])

    def _page_modules(self):
        self.t_mod = table(["Moduł", "Adres DS2", "Identyfikacja (00) – surowe bajty", "Pamięć błędów (04) – surowe bajty", "Identyfikacja – tekst"])
        info = QLabel("Prawdziwy odczyt DS2 po K-line, tylko odczyt (nic nie jest zapisywane ani kasowane). Bajty pokazane surowo – "
                      "znaczenie kodów sprawdź w INPA. Moduł bez odpowiedzi = nie ma go w aucie albo jest na innej linii. Wymaga połączenia (Połącz z DME).")
        return self._page("BMW Expert – inne moduły", "DS2: EGS · ABS/ASC · Airbag · IKE · LCM · EHC · IHKA · GM", self.t_mod,
                          [("Skanuj wszystkie moduły", self.scan_modules, True), ("Eksport CSV…", lambda: self.export_csv(self.t_mod, "moduly"), False)], info)

    def scan_modules(self):
        link = self.tr.link if self.tr else None
        self.run("modules", lambda: modules_ro.scan_rows(ds2.Ds2(link, self.trace)))

    def _page_settings(self):
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(16, 12, 16, 12)
        v.addWidget(QLabel("<span style='font-size:18pt;font-weight:800'>Ustawienia</span>"))
        pn = Panel("Wygląd", BLUE, "– grafika tła"); cb = QComboBox()
        if os.path.isdir(resource("hero")): cb.addItems(sorted(os.listdir(resource("hero"))))
        cb.currentTextChanged.connect(lambda n: (self.hero.set_art(resource("hero", n)), setattr(self, "_hero_wide", None), self._place_card())); pn.l.addWidget(cb); v.addWidget(pn)
        pn = Panel("Program", BLUE, "– wersja %s" % VERSION)
        for text, fn in (("Sprawdź aktualizacje", lambda: self.check_update(True)), ("Przywróć poprzednią wersję…", self.rollback), ("O programie", self.about)):
            b = QPushButton(text); b.setObjectName("Ghost"); b.clicked.connect(fn); pn.l.addWidget(b)
        v.addWidget(pn)
        pn = Panel("Połączenie / VCI", BLUE, "– kabel K+DCAN"); self.cb_auto = QCheckBox("Łącz automatycznie z DME po starcie, jeśli wykryto kabel FTDI")
        self.cb_auto.setChecked(self._load_settings().get("autoconnect") == "1"); self.cb_auto.toggled.connect(lambda on: self._save_setting("autoconnect", "1" if on else "0")); pn.l.addWidget(self.cb_auto)
        pn.l.addWidget(QLabel("<span style='color:#8d9ab3'>Port COM wybierasz na stronie Przegląd (przycisk Odśwież). Tylko kabel K+DCAN – J2534/DoIP nie dotyczą E39.</span>")); v.addWidget(pn)
        v.addStretch(); return p

    def _page_disabled(self, title, why):
        p = QWidget(); v = QVBoxLayout(p); v.setContentsMargins(40, 30, 40, 30)
        pn = Panel(title, RED, "– WYŁĄCZONE"); l = QLabel("<p style='font-size:13pt'>%s</p><p style='color:%s'>Ta funkcja jest widoczna w menu, ale celowo nieaktywna. "
                                                          "Program nie udaje działania – nie pokaże żadnych wymyślonych danych.</p>" % (why, MUTED))
        inst = _bmw_tool_status(title)
        if inst: l.setText(l.text() + "<p style='color:%s'>%s</p>" % (MUTED, inst))
        l.setWordWrap(True); pn.l.addWidget(l); b = QPushButton("Wykonaj (niedostępne)"); b.setEnabled(False); pn.l.addWidget(b); v.addWidget(pn); v.addStretch(); return p

    # ------------------------------------------------ logika
    def go(self, target):
        self.stack.setCurrentIndex(self.idx[target])
        for t, b in self.nav + self.sidebtn: b.setChecked(t == target)
        self.update()

    def log(self, msg, ok=True):
        self.ops.insertRow(0)
        for j, (txt, col) in enumerate([(time.strftime("%H:%M:%S"), MUTED), (msg, TXT), ("OK" if ok else "BŁĄD", GREEN if ok else RED)]):
            it = QTableWidgetItem(txt); it.setForeground(QColor(col)); self.ops.setItem(0, j, it)
        while self.ops.rowCount() > 40: self.ops.removeRow(self.ops.rowCount() - 1)
        self._trace_line(("" if ok else "BŁĄD: ") + msg)

    def _trace_line(self, s):
        line = "%s  %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s); self.logbox.appendPlainText(line)
        try:
            with open(self.trace_path, "a", encoding="utf-8") as f: f.write(line + "\n")
        except Exception: pass

    def trace(self, direction, raw, note): self.bus.log.emit("%-10s %s %s" % (direction, me72.hexs(raw), note))

    def _enable(self, on):
        for b in self.dme_btns: b.setEnabled(on)
        self.b_conn.setEnabled(not on); self.b_disc.setEnabled(on)

    def tick(self):
        self.clock.setText("<b style='font-size:12pt'>%s</b> <span style='color:#8d9ab3;font-size:8pt'>&nbsp;%s</span>" % (time.strftime("%H:%M"), time.strftime("%d.%m.%Y")))

    def refresh(self):
        ok = self.dev is not None; n = len(self.faults) if (ok and self.faults is not None) else None
        self.online.setText("<span style='color:%s;font-size:8pt'>● %s</span>" % (GREEN if ok else RED, "DME POŁĄCZONE" if ok else "OFFLINE"))
        idn = self.ident or {}
        for k, lbl in self.card_vals.items(): lbl.setText(idn.get(k, "—") if ok else "—")
        self.card_ecu.setText("<span style='font-size:10pt;color:#c8d2e6'>Sterownik: %s</span>" % ("Bosch ME7.2 (odczytany)" if ok else "—"))
        volt = self.live.get("Napięcie akumulatora (DME)")
        if ok:
            self.card_status.setText("<span style='color:%s'>● POŁĄCZONY Z DME</span> &nbsp; <span style='color:%s'>⚡ %s</span> &nbsp; %s" % (
                GREEN, AMBER, ("%.1f V" % volt) if volt is not None else "— V",
                "błędy: nie odczytano" if n is None else ("<span style='color:%s'>BRAK BŁĘDÓW</span>" % GREEN if n == 0 else "<span style='color:%s'>%d BŁĘDÓW W PAMIĘCI</span>" % (AMBER, n))))
            self.health.setText("<span style='font-size:14pt;font-weight:800;color:%s'>DME: %s</span>" % (GREEN if not n else AMBER, "POŁĄCZONE" if n is None else ("OK" if n == 0 else "%d DTC" % n)))
        else:
            self.card_status.setText("<span style='color:%s;font-size:11pt'>● %s</span><br><span style='color:#8d9ab3'>podłącz kabel K+DCAN, zapłon poz. 2, kliknij „Połącz z DME”</span>" % (RED, NO_DME.upper()))
            self.health.setText("<span style='font-size:14pt;font-weight:800;color:%s'>%s</span>" % (RED, NO_DME.upper()))
        self.dtc_ring.label = "—" if n is None else str(n); self.dtc_ring.value = 0 if not n else 100; self.dtc_ring.update()
        if not ok or not self.live:
            for key, (val, sp, unit, col) in self.live_tiles.items(): val.setText("<span style='color:#8d9ab3;font-size:8pt'>%s</span>" % (NO_DME if ok and self.live == {} and getattr(self, "_live_failed", False) else "—"))
        s = self.sb; s["car"].setText("BMW E39 540i (M62)"); s["if"].setText(("K+DCAN %s · 9600 8E1" % (self.tr.link.name if self.tr and self.tr.link else "")) if ok else NO_DME.upper())
        s["v"].setText(("%.1f V" % volt) if volt is not None else "— V"); s["err"].setText("—" if n is None else ("BRAK BŁĘDÓW" if n == 0 else "%d BŁĘDY" % n))

    def refresh_ports(self):
        self.port.clear(); ports = me72.list_ports()
        for dev, desc in ports: self.port.addItem("%s  %s" % (dev, desc), dev)
        if not ports: self.port.addItem("(brak portów COM – podłącz kabel K+DCAN)", None)
        for i in range(self.port.count()):
            if "FTDI" in self.port.itemText(i): self.port.setCurrentIndex(i)

    def connect(self):
        dev = self.port.currentData()
        if not dev: QMessageBox.warning(self, "Brak portu", "Nie ma portu COM. Podłącz kabel K+DCAN do USB i kliknij „Odśwież”."); return
        self.log("Łączenie z DME przez %s…" % dev)
        def job():
            tr = me72.Me72Transport(me72.SerialLink(dev), self.trace)
            try: return tr, me72.Me72(tr).ident()
            except Exception: tr.close(); raise
        self.worker.submit("connect", job)

    def disconnect(self):
        self.b_live.setChecked(False); self.b_live_home.setChecked(False)
        tr = self.tr; self.tr = self.dev = None; self.ident = None; self.faults = None; self.live = {}
        if tr: self.worker.submit("disconnect", lambda: tr.close())
        self._enable(False); self.log("Rozłączono"); self.refresh()

    def run(self, name, fn):
        if not self.dev: self.on_error(name, me72.NoResponse(NO_DME + ": nie połączono.")); return
        self.worker.submit(name, fn)

    def read_ident(self): self.run("ident", lambda: self.dev.ident())
    def read_dtc(self): self.run("dtc", lambda: self.dev.read_faults())
    def read_live(self): self.run("live", lambda: self.dev.engine())
    def read_adapt(self): self.run("adapt", lambda: self.dev.adaptations())
    def read_lambda(self): self.run("lambda", lambda: self.dev.lambda_status())
    def clear_rough(self): self.rough_samples = []; fill(self.t_mis, []); self.mis_info.setText("Próbki wyczyszczone.")

    def poll_live(self):
        if self.dev and not self.worker.busy(): self.read_live()

    def read_rough(self):
        def job(): return [self.dev.roughness() for _ in range(20)]
        self.mis_info.setText("Zbieram 20 próbek z DME…"); self.run("rough", job)

    def clear_dtc(self):
        if QMessageBox.question(self, "Kasowanie błędów DME", "Skasować pamięć błędów DME (ME7.2)?\n\nNajpierw przepisz/wyeksportuj kody.\n"
                                "ZAPŁON WŁĄCZONY (poz. 2), SILNIK WYŁĄCZONY.\n\nUwaga: komenda 14 FF 00 nie była jeszcze sprawdzona na tym aucie. "
                                "Kasowane jest tylko DME – inne moduły bez zmian.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        self.log("Kasowanie błędów DME: wysyłam 14 FF 00 (TX/RX w logu surowych bajtów)")
        self.run("clear", lambda: self.dev.clear_faults())

    def toggle_live(self, on):
        for b in (self.b_live, self.b_live_home):
            b.blockSignals(True); b.setChecked(on); b.setText("■  Stop odczytu na żywo" if on else "▶  Start odczytu na żywo"); b.blockSignals(False)
        if on and self.dev: self.live_timer.start(700)
        else: self.live_timer.stop()

    def save_log(self):
        p, _ = QFileDialog.getSaveFileName(self, "Zapisz log", os.path.join(LOG_DIR, "log.txt"), "Tekst (*.txt)")
        if p: open(p, "w", encoding="utf-8").write(self.logbox.toPlainText())

    def on_done(self, name, res, err):
        if err is not None: self.on_error(name, err); return
        if name == "connect":
            self.tr, self.ident = res; self.dev = me72.Me72(self.tr); self._enable(True); fill(self.t_id, list(self.ident.items()))
            self.log("Połączono z DME: %s" % self.ident.get("Numer części BMW", "?"))
        elif name == "modules": res = [r + [extras.ds2_ident_text(bytes.fromhex(r[2].replace(" ", ""))) if not r[2].startswith("—") and r[2] != "(nic)" else "—"] for r in res]; self.mod_rows = res; fill(self.t_mod, res); self._modules_done(res); self.log("Skan modułów DS2: %d odpowiedziało" % sum(1 for r in res if not r[2].startswith("—")))
        elif name == "ident": self.ident = res; fill(self.t_id, list(res.items()))
        elif name == "dtc":
            count, recs, warn = res; self.faults = recs
            self.dtc_rows = [("%04X" % c, "%02X" % s, format(s, "08b"), bmw_dtc.describe(c)) for c, s in recs]; fill(self.t_dtc, self.dtc_rows); self._alldtc_refresh()
            self.dtc_info.setText((("DME zgłasza %d błędów. " % count) + " ".join(warn) + " Kody BMW (nie P-kody OBD) – znaczenie sprawdź w INPA. " + bmw_dtc.source_status() + ". "
                                   "Format odpowiedzi niepotwierdzony na tym aucie.") if count else "DME odpowiedziało: brak zapisanych błędów.")
            self.log("Odczyt błędów: %d" % count)
        elif name == "clear": self.dtc_info.setText("DME potwierdziło kasowanie (odpowiedź 54). Odczytuję ponownie…"); QMessageBox.information(self, "Kasowanie błędów DME", "DME potwierdziło kasowanie (54). Za chwilę ponowny odczyt błędów."); self.log("Kasowanie błędów potwierdzone"); self.read_dtc()
        elif name == "live":
            self._live_failed = False; fill(self.t_live, [(n, x, u, "OK – " + live_ro.connection_status(True)) for n, x, u in res]); self.live = {n: x for n, x, _ in res}; self._record(res)
            for key, (val, sp, unit, col) in self.live_tiles.items():
                x = self.live.get(key)
                if x is None: val.setText("—"); continue
                val.setText("<b style='font-size:15pt;color:%s'>%s</b> <span style='color:#8d9ab3'>%s</span>" % (col, ("%.0f" % x) if abs(x) >= 100 else ("%.1f" % x), unit)); sp.push(x)
        elif name in ("adapt", "lambda"): fill(self.t_ad, res); setattr(self, "ad_rows_" + name, res)
        elif name == "ff": self.ff_rows = res; fill(self.t_ff, res); self.log("Szczegóły błędu %s odczytane" % res[0][1])
        elif name == "cold": fill(self.t_cold, res["steps"]); self.cold_box.setPlainText(coldstart.format_report(res)); self.log("Kreator zimnego startu: %d przyczyn" % len(res["verdict"]))
        elif name == "smart": self._smart_done(res)
        elif name == "rough":
            self.rough_samples += res; mean, z, idx, txt = me72.roughness_outlier(self.rough_samples); last = res[-1]
            fill(self.t_mis, [("%s%s" % (me72.rough_label(c + 1), "  ◄ ODSTAJE" if idx == c else ""), last[c], mean[c], "—" if z[c] is None else z[c]) for c in range(8)])
            self.mis_info.setText("Próbek: %d. %s Kolejność pozycji DME vs numer cylindra M62 niepotwierdzona." % (len(self.rough_samples), txt))
            top = max(max(abs(m) for m in mean), 1e-9)
            for c, (b, vl) in enumerate(self.mis_bars):
                b.value = 100 * abs(mean[c]) / top; b.color = RED if idx == c else CYAN; b.update(); vl.setText("%.3f" % mean[c])
            self.log("Zapłony: %s" % txt)
        self.refresh()

    def on_error(self, name, err):
        msg = str(err); self.log("[%s] %s" % (name, msg), False)
        if name == "live":
            self._live_failed = True; self.live = {}; self.toggle_live(False); fill(self.t_live, [("—", NO_DME, "")])
        if name == "connect": self.dev = None
        if name == "smart": self.smart_info.setText("Przerwano: %s" % msg)
        if name == "clear": self.dtc_info.setText("Kasowanie NIE potwierdzone: %s" % msg)
        self.refresh()
        QMessageBox.warning(self, NO_DME if isinstance(err, me72.NoResponse) else "Błąd", msg)


    # ------------------------------------------------ 1.3: strony przeniesione ze starego AutoDiag Pro (tylko prawdziwe odczyty)
    def export_csv(self, t, name):
        if t.rowCount() == 0: QMessageBox.information(self, "Eksport CSV", "Tabela jest pusta – najpierw odczytaj dane z auta."); return
        p, _ = QFileDialog.getSaveFileName(self, "Eksport CSV", os.path.join(LOG_DIR, "%s_%s.csv" % (name, time.strftime("%Y%m%d_%H%M%S"))), "CSV (*.csv)")
        if not p: return
        hd = [t.horizontalHeaderItem(c).text() for c in range(t.columnCount())]
        rows = [[(t.item(r, c).text() if t.item(r, c) else "") for c in range(t.columnCount())] for r in range(t.rowCount())]
        extras.export_table_csv(p, hd, rows); self.log("Zapisano CSV: %s" % p)

    def read_ff(self):
        r = self.t_dtc.currentRow()
        if r < 0 or not self.faults: QMessageBox.information(self, "Szczegóły błędu", "Najpierw odczytaj błędy i zaznacz jeden w tabeli."); return
        code = self.faults[r][0]; self.run("ff", lambda: self.dev.freeze_frame(code))

    def _page_dtc(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0)
        self.t_dtc = table(["Kod BMW (hex)", "Status (hex)", "Status (bity)", "Opis (lista DME 7.2, endtuning.com)"]); self.dtc_info = QLabel(""); v.addWidget(self.t_dtc, 2)
        v.addWidget(QLabel("<b>Szczegóły zaznaczonego błędu (freeze frame, 17 HH LL)</b>")); self.t_ff = table(["Pole", "Wartość z DME"]); v.addWidget(self.t_ff, 1)
        return self._page("Diagnostyka – pamięć błędów", "18 02 FF FF · szczegóły 17 · kasowanie 14 FF 00", w,
                          [("Czytaj błędy", self.read_dtc, True), ("Szczegóły błędu (freeze frame)", self.read_ff, True), ("Eksport CSV…", lambda: self.export_csv(self.t_dtc, "bledy_dme"), False),
                           ("Kasuj błędy DME…", self.clear_dtc, True)], self.dtc_info)

    # --- wszystkie DTC
    def _page_alldtc(self):
        self.t_all = table(["Sterownik", "Adres", "Błędy (odczyt)"]); self.all_info = QLabel("Zbiera błędy DME (KWP) i wszystkich modułów DS2. Kody DS2 surowe – znaczenie w INPA.")
        return self._page("Pokaż wszystkie DTC", "DME + EGS · ABS · Airbag · IKE · LCM · EHC · IHKA · GM", self.t_all,
                          [("Czytaj wszystkie", self.read_all_dtc, True), ("Eksport CSV…", lambda: self.export_csv(self.t_all, "wszystkie_dtc"), False)], self.all_info)

    def read_all_dtc(self): self.read_dtc(); self.scan_modules()

    def _alldtc_refresh(self):
        rows = [("Silnik (DME ME7.2)", "0x12", ("brak błędów" if not self.dtc_rows else ", ".join("%s/%s" % (r[0], r[1]) for r in self.dtc_rows)) if self.faults is not None else "—")]
        rows += [(r[0], r[1], r[3]) for r in self.mod_rows]; fill(self.t_all, rows)

    def _modules_done(self, res):
        self._alldtc_refresh(); self.topo.set_data(self.dev is not None, res)

    # --- Smart Scan / auto-diagnoza
    def _page_smart(self):
        self.t_smart = table(["Krok", "Wynik"]); self.smart_info = QLabel("Jedno kliknięcie: identyfikacja DME, pamięć błędów, dane na żywo, adaptacje, skan wszystkich modułów DS2, potem raport. Wymaga połączenia.")
        return self._page("AUTO-DIAGNOZA (Smart Scan)", "prawdziwe odczyty po kolei", self.t_smart,
                          [("Start auto-diagnozy", self.smart_scan, True), ("Otwórz raport", self.make_report, False)], self.smart_info)

    def smart_scan(self):
        link = self.tr.link if self.tr else None; dev = self.dev; tr = self.trace
        def job():
            out = {}
            for key, fn in (("ident", dev.ident), ("dtc", dev.read_faults), ("live", dev.engine), ("adapt", dev.adaptations), ("lambda", dev.lambda_status),
                            ("modules", lambda: modules_ro.scan_rows(ds2.Ds2(link, tr)))):
                try: out[key] = (fn(), None)
                except Exception as e: out[key] = (None, str(e))
            return out
        self.smart_info.setText("Trwa auto-diagnoza… (ok. 20–40 s)"); self.run("smart", job)

    def _smart_done(self, out):
        names = {"ident": "Identyfikacja DME", "dtc": "Pamięć błędów DME", "live": "Dane na żywo", "adapt": "Adaptacje", "lambda": "Status lambda", "modules": "Moduły DS2"}
        rows = []
        for k, (res, err) in out.items():
            if err: rows.append((names[k], "BŁĄD: " + err.split(".")[0])); continue
            if k in ("ident", "dtc", "live", "adapt", "lambda", "modules"): self.on_done(k, res, None)
            if k == "dtc": rows.append((names[k], "%d błędów" % res[0]))
            elif k == "modules": rows.append((names[k], "%d z %d odpowiedziało" % (sum(1 for r in res if not r[2].startswith("—")), len(res))))
            else: rows.append((names[k], "OK – %d pozycji" % len(res)))
        fill(self.t_smart, rows); self.smart_info.setText("Auto-diagnoza zakończona. Raport: przycisk „Otwórz raport”."); self.log("Auto-diagnoza zakończona")

    # --- Data Log: wykres + zapis CSV
    def _page_datalog(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); r = QHBoxLayout()
        r.addWidget(QLabel("Parametr:")); self.dl_param = QComboBox(); self.dl_param.addItems([n for n, _, _ in [("Obroty", 0, 0), ("Temp. płynu chłodzącego", 0, 0), ("Temp. powietrza dolotowego", 0, 0),
                    ("Prędkość", 0, 0), ("Czas wtrysku", 0, 0), ("Kąt wyprzedzenia zapłonu", 0, 0), ("Przepustnica", 0, 0), ("Masa powietrza (MAF)", 0, 0), ("Moment wskazany", 0, 0), ("Napięcie akumulatora (DME)", 0, 0)]])
        self.dl_param.currentTextChanged.connect(lambda _: self.chart.update()); r.addWidget(self.dl_param, 1); v.addLayout(r)
        self.chart = Chart(self); v.addWidget(self.chart, 1)
        self.b_rec = QPushButton("●  Nagrywaj do CSV"); self.b_rec.setCheckable(True); self.b_rec.toggled.connect(self.toggle_rec)
        self.dl_info = QLabel("Wykres i zapis działają, gdy włączony jest odczyt na żywo (Live Data, co 0,7 s). Plik CSV (Excel, separator ;) w folderze %s." % LOG_DIR)
        return self._page("Data Log", "wykres + zapis CSV z 22 40 00", w, [("▶ Włącz odczyt na żywo", lambda: self.b_live.setChecked(True), True), ("Wyczyść wykres", self.clear_hist, False)], self.dl_info, extra=self.b_rec)

    def clear_hist(self): self.hist = {}; self.hist_t = []; self.chart.update()

    def toggle_rec(self, on):
        if on:
            path = os.path.join(LOG_DIR, "datalog_%s.csv" % time.strftime("%Y%m%d_%H%M%S")); self.csvlog = extras.CsvLogger(path)
            self.b_rec.setText("■  Stop nagrywania"); self.dl_info.setText("Nagrywam do %s" % path); self.b_live.setChecked(True); self.log("Start nagrywania CSV")
        elif self.csvlog:
            self.csvlog.close(); self.dl_info.setText("Zapisano %d wierszy do %s" % (self.csvlog.rows, self.csvlog.path)); self.log("Zapisano CSV: %d wierszy" % self.csvlog.rows)
            self.csvlog = None; self.b_rec.setText("●  Nagrywaj do CSV")

    def _record(self, res):
        self.hist_t.append(time.time())
        for n, x, _ in res: self.hist.setdefault(n, []).append(x)
        if len(self.hist_t) > 900:
            self.hist_t = self.hist_t[-900:]; self.hist = {k: vv[-900:] for k, vv in self.hist.items()}
        v = self.live.get("Napięcie akumulatora (DME)")
        if v is not None: self.volt_hist.append((time.strftime("%H:%M:%S"), v)); self._battery_refresh()
        if self.csvlog: self.csvlog.add(res)
        self.chart.update()

    # --- Topologia
    def _page_topology(self):
        self.topo = Topology(); info = QLabel("Zielony = moduł odpowiedział, pomarańczowy = ma błędy w pamięci, czerwony = brak odpowiedzi, szary = nie skanowano. Dane z ostatniego skanu DS2.")
        return self._page("Topologia", "K-line (DS2/KWP) – moduły E39", self.topo, [("Skanuj moduły", self.scan_modules, True)], info)

    # --- Bateria
    def _page_battery(self):
        self.t_bat = table(["Czas", "Napięcie z DME [V]"]); self.bat_info = QLabel("Napięcie zasilania mierzone przez DME (bajt 25 odpowiedzi 22 40 00). Silnik wył.: 12,4–12,7 V = OK; pracuje: 13,8–14,6 V = ładowanie OK.")
        return self._page("Bateria", "napięcie z DME", self.t_bat, [("Odczytaj teraz", self.read_live, True), ("Eksport CSV…", lambda: self.export_csv(self.t_bat, "bateria"), False)], self.bat_info)

    def _battery_refresh(self):
        rows = list(reversed(self.volt_hist[-200:])); fill(self.t_bat, rows); v = rows[0][1]
        ocena = "niskie – naładuj akumulator" if v < 12.2 else ("OK (silnik wyłączony)" if v < 13.2 else ("ładowanie OK" if v <= 14.8 else "za wysokie – sprawdź regulator alternatora"))
        self.bat_info.setText("Ostatni odczyt: <b>%.2f V</b> – %s. (Bez pomiaru prądu – stan zdrowia akumulatora wymaga testera obciążeniowego.)" % (v, ocena))

    # --- VIN
    def _page_vin(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); self.vin_edit = QLineEdit(); self.vin_edit.setPlaceholderText("Wpisz VIN (17 znaków) z dowodu rejestracyjnego lub z szyby")
        v.addWidget(self.vin_edit); self.t_vin = table(["Pole", "Wartość"]); v.addWidget(self.t_vin, 1)
        info = QLabel("Dekodowanie wpisanego VIN. Odczyt VIN z DME ME7.2 jest wyłączony: nie znamy potwierdzonej komendy dla tego sterownika.")
        return self._page("VIN Auto", "dekodowanie numeru nadwozia", w, [("Dekoduj", self.decode_vin, False)], info)

    def decode_vin(self):
        try: self.vin_rows = extras.decode_vin(self.vin_edit.text()); fill(self.t_vin, self.vin_rows)
        except ValueError as e: QMessageBox.warning(self, "VIN", str(e))

    # --- Raport
    def _page_report(self):
        self.rep_info = QLabel("Raport HTML (otwiera się w przeglądarce, można wydrukować do PDF) – tylko dane odczytane z auta w tej sesji.")
        box = QPlainTextEdit(); box.setReadOnly(True); self.rep_box = box
        return self._page("Raport", "eksport HTML / PDF przez przeglądarkę", box, [("Utwórz raport", self.make_report, False)], self.rep_info)

    def make_report(self):
        sec = [("Identyfikacja DME", ["Pole", "Wartość"], list((self.ident or {}).items())), ("Pamięć błędów DME", ["Kod BMW", "Status", "Bity", "Opis"], self.dtc_rows),
               ("Szczegóły błędu", ["Pole", "Wartość"], self.ff_rows), ("Dane na żywo (ostatni odczyt)", ["Parametr", "Wartość"], list(self.live.items())),
               ("Adaptacje", ["Parametr", "Wartość", "Jedn."], getattr(self, "ad_rows_adapt", [])), ("Status lambda", ["Parametr", "Wartość", ""], getattr(self, "ad_rows_lambda", [])),
               ("Moduły DS2", ["Moduł", "Adres", "Ident (hex)", "Błędy (hex)", "Ident (tekst)"], self.mod_rows),
               ("Wypadanie zapłonów (średnie)", ["Cylinder (pozycja DME)", "Średnia [1/s]"], [(c + 1, m) for c, m in enumerate(me72.roughness_outlier(self.rough_samples)[0])] if self.rough_samples else []),
               ("VIN", ["Pole", "Wartość"], self.vin_rows)]
        path = os.path.join(LOG_DIR, "raport_%s.html" % time.strftime("%Y%m%d_%H%M%S")); open(path, "w", encoding="utf-8").write(extras.report_html(sec))
        self.rep_box.setPlainText("Zapisano: %s" % path); self.log("Raport: %s" % path)
        try: os.startfile(path)
        except Exception: pass

    # --- ustawienia: autołączenie
    def _load_settings(self):
        try: return dict(l.rstrip("\n").split("=", 1) for l in open(self.settings_path, encoding="utf-8") if "=" in l)
        except Exception: return {}

    def _save_setting(self, k, val):
        d = self._load_settings(); d[k] = val
        open(self.settings_path, "w", encoding="utf-8").write("".join("%s=%s\n" % kv for kv in d.items()))

    # ------------------------------------------------ aktualizacje programu (nigdy nie dotyczą sterownika auta)
    def _bg(self, stage, fn, manual):
        def run():
            try: self.bus.upd.emit(stage, fn(), None, manual)
            except Exception as e: self.bus.upd.emit(stage, None, e, manual)
        threading.Thread(target=run, daemon=True).start()

    def check_update(self, manual): self.b_upd.setEnabled(False); self._bg("check", updater.check, manual)

    def on_update(self, stage, res, err, manual):
        self.b_upd.setEnabled(True)
        if err is not None:
            self._trace_line("Aktualizacja: %s" % err)
            if manual: QMessageBox.information(self, "Aktualizacja", str(err))
            return
        if stage == "check":
            if res is None:
                self._trace_line("Aktualizacja: masz najnowszą wersję %s." % VERSION)
                if manual: QMessageBox.information(self, "Aktualizacja", "Masz najnowszą wersję (%s)." % VERSION)
                return
            self.b_upd.setText("⟳  Aktualizuj do %s" % res["version"]); self.log("Dostępna nowa wersja %s" % res["version"])
            if not updater.can_self_update():
                QMessageBox.information(self, "Aktualizacja", "Jest nowa wersja %s, ale program nie jest zainstalowany w\n%s\nPobierz ją ręcznie z GitHub." % (res["version"], updater.APP_DIR)); return
            if QMessageBox.question(self, "Aktualizacja programu", "Dostępna wersja %s (masz %s).\n\n%s\n\nPobrać i zainstalować? Program się zamknie i uruchomi ponownie.\n"
                    "Poprzednia wersja zostanie zachowana.\nAktualizacja dotyczy tylko programu – nic nie jest wgrywane do auta." % (res["version"], VERSION, (res["notes"] or "")[:600])) != QMessageBox.Yes: return
            self.b_upd.setEnabled(False); self.b_upd.setText("Pobieranie…"); self._bg("stage", lambda: (res, updater.download_and_stage(res)), True)
        elif stage == "stage":
            info, stage_dir = res; self._trace_line("Pobrano %s, SHA256 zgodne (%s)." % (info["asset_name"], info["sha256"]))
            self.disconnect(); updater.run_after_exit(updater.swap_script(stage_dir, os.getpid())); QApplication.quit()

    def rollback(self):
        if not updater.can_self_update() or not updater.has_backup():
            QMessageBox.information(self, "Przywracanie", "Brak zapisanej poprzedniej wersji."); return
        if QMessageBox.question(self, "Przywracanie", "Przywrócić poprzednią wersję programu? Program uruchomi się ponownie.") == QMessageBox.Yes:
            self.disconnect(); updater.run_after_exit(updater.rollback_script(os.getpid())); QApplication.quit()

    def about(self):
        QMessageBox.about(self, "O programie", "<b>AutoDiag Pro %s</b><br>BMW E39 540i · Bosch ME7.2 · kabel K+DCAN<br><br>Tylko prawdziwe odczyty z DME, bez trybu demo."
                          "<br>Aktualizacje: github.com/%s<br>Folder programu: %s" % (VERSION, updater.REPO, updater.APP_DIR))


def main():
    app = QApplication(sys.argv); app.setWindowIcon(QIcon(resource("icon.ico")))
    try:
        import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AutoDiagPro.Real")
    except Exception: pass
    w = Main(); w.showMaximized(); sys.exit(app.exec())


if __name__ == "__main__":
    main()
