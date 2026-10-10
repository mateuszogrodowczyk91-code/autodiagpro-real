"""AutoDiag Pro (wersja REALNA) – tylko prawdziwe odczyty z DME ME7.2. Brak trybu demo, brak symulatora."""
import datetime, os, queue, sys, threading
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit, QMessageBox, QFileDialog)

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from autodiag_real import me72, updater
from autodiag_real.version import VERSION
from PySide6.QtGui import QIcon, QAction


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)

NO_DME = "brak odpowiedzi z DME"
LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AutoDiagPro_real")
os.makedirs(LOG_DIR, exist_ok=True)

DISABLED = [
    ("Programowanie / flash DME", "Wyłączone dla bezpieczeństwa. Błąd przy zapisie może trwale uszkodzić sterownik silnika (auto nie odpali). "
     "Do tego potrzebny jest sprawdzony bootloader i sumy kontrolne – tego w programie nie ma i nie będziemy zgadywać."),
    ("Mapy / tuning", "Wyłączone. Edycja map bez zweryfikowanej definicji dla Twojego numeru oprogramowania to zgadywanie."),
    ("Kodowanie (NCS) / Retrofit", "Wyłączone. Brak zweryfikowanych danych kodowania dla E39 – użyj NCS Expert."),
    ("EWS / immobilizer", "Niedostępne i nie będzie. Obchodzenie zabezpieczenia przed kradzieżą nie jest wspierane."),
    ("Wyłączanie sond / katalizatora / emisji", "Niedostępne i nie będzie. Wyłączanie układów emisji jest nielegalne na drogach publicznych."),
    ("Inne sterowniki (ABS, airbag, skrzynia, licznik)", "Nieobsługiwane. Ta wersja rozmawia tylko z DME silnika ME7.2 (adres 0x12)."),
    ("Testy elementów wykonawczych", "Wyłączone. Komendy sterowania nie są zweryfikowane dla ME7.2."),
    ("AI Mechanic / chmura / Companion / „Autopilot”", "Usunięte. Nie czytały danych z auta albo pokazywały wyniki z symulatora."),
]


class Bus(QObject):
    done = Signal(str, object, object)  # nazwa zadania, wynik, błąd
    upd = Signal(str, object, object, bool)  # etap, wynik, błąd, ręcznie
    log = Signal(str)


class Worker:
    """Jeden wątek rozmawia z kablem; GUI nie zawiesza się."""
    def __init__(self, bus):
        self.bus = bus; self.q = queue.Queue(); self.dev = None
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, name, fn): self.q.put((name, fn))

    def _run(self):
        while True:
            name, fn = self.q.get()
            try: self.bus.done.emit(name, fn(), None)
            except Exception as e: self.bus.done.emit(name, None, e)


def table(headers):
    t = QTableWidget(0, len(headers)); t.setHorizontalHeaderLabels(headers); t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); t.setEditTriggers(QTableWidget.NoEditTriggers); return t


def fill(t, rows):
    t.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            t.setItem(r, c, QTableWidgetItem(("%.2f" % v) if isinstance(v, float) else str(v)))


class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("AutoDiag Pro %s – REALNY odczyt BMW E39 ME7.2 (bez demo)" % VERSION); self.setWindowIcon(QIcon(resource("icon.ico"))); self.resize(1100, 760)
        self.bus = Bus(); self.bus.done.connect(self.on_done); self.bus.log.connect(self._log); self.bus.upd.connect(self.on_update)
        self.worker = Worker(self.bus); self.tr = None; self.dev = None; self.rough_samples = []
        self.trace_path = os.path.join(LOG_DIR, "trace_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        w = QWidget(); v = QVBoxLayout(w)
        top = QHBoxLayout(); self.port = QComboBox(); self.port.setMinimumWidth(320)
        b_ref = QPushButton("Odśwież porty"); b_ref.clicked.connect(self.refresh_ports)
        self.b_conn = QPushButton("Połącz z DME"); self.b_conn.clicked.connect(self.connect)
        self.b_disc = QPushButton("Rozłącz"); self.b_disc.clicked.connect(self.disconnect)
        self.status = QLabel(); self.set_status(False, "Rozłączono")
        for x in (QLabel("Port:"), self.port, b_ref, self.b_conn, self.b_disc): top.addWidget(x)
        self.b_upd = QPushButton("Aktualizuj"); self.b_upd.clicked.connect(lambda: self.check_update(True))
        top.addStretch(); top.addWidget(self.status); top.addWidget(self.b_upd); v.addLayout(top)
        m = self.menuBar().addMenu("Pomoc")
        for text, fn in (("Sprawdź aktualizacje", lambda: self.check_update(True)), ("Przywróć poprzednią wersję…", self.rollback), ("O programie", self.about)):
            a = QAction(text, self); a.triggered.connect(fn); m.addAction(a)
        self.tabs = QTabWidget(); v.addWidget(self.tabs, 1)
        self.t_id = table(["Pole", "Wartość z DME"]); self.tabs.addTab(self._page(self.t_id, [("Czytaj identyfikację", self.read_ident)]), "Identyfikacja")
        self.t_dtc = table(["Kod BMW (hex)", "Status (hex)", "Status (bity)"]); self.dtc_info = QLabel("")
        self.tabs.addTab(self._page(self.t_dtc, [("Czytaj błędy", self.read_dtc), ("Kasuj błędy…", self.clear_dtc)], self.dtc_info), "Pamięć błędów")
        self.t_live = table(["Parametr", "Wartość", "Jednostka"]); self.live_timer = QTimer(self); self.live_timer.timeout.connect(self.read_live)
        self.b_live = QPushButton("Start odczytu na żywo"); self.b_live.setCheckable(True); self.b_live.toggled.connect(self.toggle_live)
        self.tabs.addTab(self._page(self.t_live, [("Odczytaj raz", self.read_live)], extra_btn=self.b_live), "Na żywo")
        self.t_mis = table(["Cylinder (pozycja w DME)", "Ostatnia nierówność [1/s]", "Średnia [1/s]", "z-score"]); self.mis_info = QLabel("Silnik na wolnych obrotach, rozgrzany. Zbierz min. 20 próbek.")
        self.tabs.addTab(self._page(self.t_mis, [("Zbierz 20 próbek", self.read_rough), ("Wyczyść próbki", self.clear_rough)], self.mis_info), "Wypadanie zapłonów")
        self.t_ad = table(["Parametr", "Wartość", "Jednostka"])
        self.tabs.addTab(self._page(self.t_ad, [("Czytaj adaptacje", self.read_adapt), ("Czytaj status lambda", self.read_lambda)]), "Adaptacje / lambda")
        dis = table(["Funkcja", "Dlaczego wyłączona"]); fill(dis, DISABLED); dis.resizeRowsToContents()
        dis.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents); dis.setWordWrap(True)
        self.tabs.addTab(dis, "Wyłączone funkcje")
        self.logbox = QPlainTextEdit(); self.logbox.setReadOnly(True)
        self.tabs.addTab(self._page(self.logbox, [("Zapisz log do pliku…", self.save_log)]), "Log (surowe bajty)")
        self.setCentralWidget(w); self.refresh_ports(); self._enable(False)
        self._log("Start AutoDiag Pro %s. Brak trybu demo. Plik śladu: %s" % (VERSION, self.trace_path))
        QTimer.singleShot(2000, lambda: self.check_update(False))

    # ---------------- aktualizacje programu (nigdy nie dotyczą sterownika auta)
    def _bg(self, stage, fn, manual):
        def run():
            try: self.bus.upd.emit(stage, fn(), None, manual)
            except Exception as e: self.bus.upd.emit(stage, None, e, manual)
        threading.Thread(target=run, daemon=True).start()

    def check_update(self, manual):
        self.b_upd.setEnabled(False); self._bg("check", updater.check, manual)

    def on_update(self, stage, res, err, manual):
        self.b_upd.setEnabled(True)
        if err is not None:
            self._log("Aktualizacja: %s" % err)
            if manual: QMessageBox.information(self, "Aktualizacja", str(err))
            return
        if stage == "check":
            if res is None:
                self._log("Aktualizacja: masz najnowszą wersję %s." % VERSION)
                if manual: QMessageBox.information(self, "Aktualizacja", "Masz najnowszą wersję (%s)." % VERSION)
                return
            self.b_upd.setText("Aktualizuj do %s" % res["version"]); self.b_upd.setStyleSheet("font-weight:bold;color:#0b5ed7")
            if not updater.can_self_update():
                QMessageBox.information(self, "Aktualizacja", "Jest nowa wersja %s, ale program nie jest zainstalowany w\n%s\n"
                                        "Pobierz ją ręcznie z GitHub." % (res["version"], updater.APP_DIR)); return
            if QMessageBox.question(self, "Aktualizacja programu",
                    "Dostępna wersja %s (masz %s).\n\n%s\n\nPobrać i zainstalować? Program się zamknie i uruchomi ponownie.\n"
                    "Poprzednia wersja zostanie zachowana do przywrócenia.\nAktualizacja dotyczy tylko programu – nic nie jest wgrywane do auta."
                    % (res["version"], VERSION, (res["notes"] or "")[:600])) != QMessageBox.Yes: return
            self.b_upd.setEnabled(False); self.b_upd.setText("Pobieranie…")
            self._bg("stage", lambda: (res, updater.download_and_stage(res)), True)
        elif stage == "stage":
            info, stage_dir = res
            self._log("Pobrano %s, SHA256 zgodne (%s). Instaluję po zamknięciu." % (info["asset_name"], info["sha256"]))
            self.disconnect(); updater.run_after_exit(updater.swap_script(stage_dir, os.getpid())); QApplication.quit()

    def rollback(self):
        if not updater.can_self_update() or not updater.has_backup():
            QMessageBox.information(self, "Przywracanie", "Brak zapisanej poprzedniej wersji."); return
        if QMessageBox.question(self, "Przywracanie", "Przywrócić poprzednią wersję programu? Program uruchomi się ponownie.") == QMessageBox.Yes:
            self.disconnect(); updater.run_after_exit(updater.rollback_script(os.getpid())); QApplication.quit()

    def about(self):
        QMessageBox.about(self, "O programie", "<b>AutoDiag Pro (wersja realna) %s</b><br>BMW E39 540i · Bosch ME7.2 · kabel K+DCAN<br><br>"
            "Tylko prawdziwe odczyty z DME, bez trybu demo.<br>Aktualizacje: github.com/%s<br>Folder programu: %s"
            % (VERSION, updater.REPO, updater.APP_DIR))

    def _page(self, widget, buttons, info=None, extra_btn=None):
        p = QWidget(); v = QVBoxLayout(p); h = QHBoxLayout(); self.__dict__.setdefault("dme_btns", [])
        for text, fn in buttons:
            b = QPushButton(text); b.clicked.connect(fn); h.addWidget(b)
            if "Zapisz" not in text and "Wyczyść" not in text: self.dme_btns.append(b)
        if extra_btn: h.addWidget(extra_btn); self.dme_btns.append(extra_btn)
        h.addStretch(); v.addLayout(h)
        if info: info.setWordWrap(True); v.addWidget(info)
        v.addWidget(widget, 1); return p

    def _enable(self, on):
        for b in self.dme_btns: b.setEnabled(on)
        self.b_conn.setEnabled(not on); self.b_disc.setEnabled(on)

    def set_status(self, ok, text):
        self.status.setText("● " + text); self.status.setStyleSheet("color:%s;font-weight:bold" % ("#1a9e3a" if ok else "#c62828"))

    def _log(self, s):
        line = "%s  %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s); self.logbox.appendPlainText(line)
        try:
            with open(self.trace_path, "a", encoding="utf-8") as f: f.write(line + "\n")
        except Exception: pass

    def trace(self, direction, raw, note): self.bus.log.emit("%-10s %s %s" % (direction, me72.hexs(raw), note))

    def refresh_ports(self):
        self.port.clear(); ports = me72.list_ports()
        for dev, desc in ports: self.port.addItem("%s  %s" % (dev, desc), dev)
        if not ports: self.port.addItem("(nie znaleziono portów COM – podłącz kabel K+DCAN)", None)
        for i in range(self.port.count()):
            if "FTDI" in self.port.itemText(i): self.port.setCurrentIndex(i)

    def connect(self):
        dev = self.port.currentData()
        if not dev: QMessageBox.warning(self, "Brak portu", "Nie ma portu COM. Podłącz kabel K+DCAN do USB i kliknij „Odśwież porty”."); return
        self.set_status(False, "Łączenie z %s…" % dev)
        def job():
            tr = me72.Me72Transport(me72.SerialLink(dev), self.trace)
            try: return tr, me72.Me72(tr).ident()
            except Exception: tr.close(); raise
        self.worker.submit("connect", job)

    def disconnect(self):
        self.b_live.setChecked(False)
        tr = self.tr; self.tr = self.dev = None
        if tr: self.worker.submit("disconnect", lambda: tr.close())
        self._enable(False); self.set_status(False, "Rozłączono")

    def run(self, name, fn):
        if not self.dev: self.on_error(name, me72.NoResponse(NO_DME + ": nie połączono.")); return
        self.worker.submit(name, fn)

    def read_ident(self): self.run("ident", lambda: self.dev.ident())
    def read_dtc(self): self.run("dtc", lambda: self.dev.read_faults())
    def read_live(self): self.run("live", lambda: self.dev.engine())
    def read_adapt(self): self.run("adapt", lambda: self.dev.adaptations())
    def read_lambda(self): self.run("lambda", lambda: self.dev.lambda_status())
    def clear_rough(self): self.rough_samples = []; fill(self.t_mis, []); self.mis_info.setText("Próbki wyczyszczone.")

    def read_rough(self):
        def job():
            out = []
            for _ in range(20): out.append(self.dev.roughness())
            return out
        self.mis_info.setText("Zbieram 20 próbek z DME…"); self.run("rough", job)

    def clear_dtc(self):
        if QMessageBox.question(self, "Kasowanie błędów",
                "Na pewno skasować pamięć błędów DME?\n\nNajpierw zapisz/przepisz kody (zakładka Pamięć błędów).\n"
                "Silnik WYŁĄCZONY, zapłon w pozycji 2.\n\nUwaga: komenda kasowania nie była jeszcze sprawdzona na tym aucie.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        self.run("clear", lambda: self.dev.clear_faults())

    def toggle_live(self, on):
        self.b_live.setText("Stop odczytu na żywo" if on else "Start odczytu na żywo")
        if on and self.dev: self.live_timer.start(700)
        else: self.live_timer.stop()

    def save_log(self):
        p, _ = QFileDialog.getSaveFileName(self, "Zapisz log", os.path.join(LOG_DIR, "log.txt"), "Tekst (*.txt)")
        if p: open(p, "w", encoding="utf-8").write(self.logbox.toPlainText())

    def on_done(self, name, res, err):
        if err is not None: self.on_error(name, err); return
        if name == "connect":
            self.tr, ident = res; self.dev = me72.Me72(self.tr); self._enable(True)
            self.set_status(True, "Połączono z DME (%s)" % ident.get("Numer części BMW", "?")); fill(self.t_id, list(ident.items()))
            self._log("Połączono. Identyfikacja odebrana z DME.")
        elif name == "ident": fill(self.t_id, list(res.items()))
        elif name == "dtc":
            count, recs, warn = res
            fill(self.t_dtc, [("%04X" % c, "%02X" % s, format(s, "08b")) for c, s in recs])
            self.dtc_info.setText(("DME zgłasza %d błędów. " % count) + " ".join(warn) +
                " Kody BMW (nie P-kody OBD). Znaczenie sprawdź w INPA. Format odpowiedzi niepotwierdzony na tym aucie." if count else
                "DME odpowiedziało: brak zapisanych błędów.")
        elif name == "clear": self.dtc_info.setText("DME potwierdziło kasowanie (54). Odczytaj błędy ponownie, żeby sprawdzić."); self.read_dtc()
        elif name == "live": fill(self.t_live, [(n, v, u) for n, v, u in res])
        elif name == "adapt": fill(self.t_ad, res)
        elif name == "lambda": fill(self.t_ad, res)
        elif name == "rough":
            self.rough_samples += res; mean, z, idx, txt = me72.roughness_outlier(self.rough_samples)
            last = res[-1]
            fill(self.t_mis, [("%d%s" % (c + 1, "  ◄ ODSTAJE" if idx == c else ""), last[c], mean[c], "—" if z[c] is None else z[c]) for c in range(8)])
            self.mis_info.setText("Próbek: %d. %s Uwaga: kolejność pozycji DME vs. numer cylindra M62 niepotwierdzona." % (len(self.rough_samples), txt))

    def on_error(self, name, err):
        msg = str(err); self._log("BŁĄD [%s]: %s" % (name, msg))
        if isinstance(err, (me72.NoResponse, OSError)) and not isinstance(err, me72.NegativeResponse):
            if name == "live":
                self.b_live.setChecked(False); fill(self.t_live, [("—", NO_DME, "")])
            if name == "connect": self.set_status(False, NO_DME)
        if name in ("live",) and self.b_live.isChecked(): return
        QMessageBox.warning(self, NO_DME if isinstance(err, me72.NoResponse) else "Błąd", msg)


def main():
    app = QApplication(sys.argv); app.setWindowIcon(QIcon(resource("icon.ico")))
    try:
        import ctypes; ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AutoDiagPro.Real")
    except Exception: pass
    w = Main(); w.show(); sys.exit(app.exec())


if __name__ == "__main__":
    main()
