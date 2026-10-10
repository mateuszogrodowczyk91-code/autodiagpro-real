class Theme:
    """Wspólny motyw AutoDiag Pro: ciemne szkło, neon cyjan / magenta / fiolet. Rozmiary w pt (HiDPI)."""
    CYAN, MAGENTA, VIOLET, GREEN, AMBER = "#3fa9ff", "#ff2340", "#1f6fff", "#27e07a", "#ffb020"
    ACCENT = CYAN
    QSS = """
    *{font-family:'Segoe UI','DejaVu Sans';color:#e8ecff;font-size:10pt}
    QWidget{background:transparent}
    QMainWindow,#Root{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #03060d,stop:.6 #06101f,stop:1 #020409)}
    #Title{font-size:20pt;font-weight:800;color:#ffffff;padding:0 0 4px 0}
    #Card,#Panel{background:rgba(16,18,40,200);border:1px solid rgba(31,111,255,110);border-radius:14px}
    #Card QLabel,#Panel QLabel{background:transparent}
    QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1f6fff,stop:1 #0b3fa8);color:#fff;border:none;border-radius:9px;padding:8px 16px;font-weight:700}
    QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3fa9ff,stop:1 #1f6fff)}
    QPushButton:disabled{background:#1d1f36;color:#60667f}
    QPushButton#Danger{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff2340,stop:1 #a5101f)}
    QPushButton#Ghost{background:rgba(31,111,255,40);border:1px solid rgba(31,111,255,140)}
    QPushButton#Ghost:hover{background:rgba(31,111,255,80)}
    QPushButton#Seg{background:rgba(16,18,40,220);border:1px solid rgba(31,111,255,110);padding:14px 20px;font-size:12pt}
    QPushButton#Seg:checked{background:rgba(63,169,255,50);border:2px solid #3fa9ff}
    QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QTextEdit,QPlainTextEdit{background:rgba(8,9,22,220);border:1px solid rgba(31,111,255,110);border-radius:8px;padding:6px;selection-background-color:#1f6fff}
    QComboBox QAbstractItemView{background:#0d0f24;border:1px solid #1f6fff}
    QTableWidget,QListWidget,QTreeWidget{background:rgba(10,11,28,215);border:1px solid rgba(31,111,255,90);border-radius:10px;gridline-color:rgba(31,111,255,40);alternate-background-color:rgba(31,111,255,18)}
    QTableWidget::item:selected,QListWidget::item:selected,QTreeWidget::item:selected{background:rgba(63,169,255,60)}
    QHeaderView::section{background:rgba(31,111,255,45);color:#c9cff0;border:none;padding:7px;font-weight:700}
    QTableCornerButton::section{background:transparent}
    QTabWidget::pane{border:1px solid rgba(31,111,255,90);border-radius:10px;top:-1px}
    QTabBar::tab{background:rgba(16,18,40,200);padding:8px 18px;margin-right:3px;border-top-left-radius:8px;border-top-right-radius:8px;color:#aab0d0}
    QTabBar::tab:selected{background:rgba(63,169,255,45);color:#fff;border-bottom:2px solid #3fa9ff}
    QProgressBar{background:rgba(8,9,22,220);border:1px solid rgba(31,111,255,90);border-radius:7px;text-align:center}
    QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3fa9ff,stop:1 #1f6fff);border-radius:7px}
    QCheckBox::indicator{width:16px;height:16px;border:1px solid #1f6fff;border-radius:4px;background:#0b0c1e}
    QCheckBox::indicator:checked{background:#3fa9ff}
    QScrollBar:vertical{background:transparent;width:10px}QScrollBar::handle:vertical{background:rgba(31,111,255,120);border-radius:5px;min-height:30px}
    QScrollBar:horizontal{background:transparent;height:10px}QScrollBar::handle:horizontal{background:rgba(31,111,255,120);border-radius:5px}
    QScrollBar::add-line,QScrollBar::sub-line{width:0;height:0}
    QMessageBox{background:#0d0f24}
    #StatusOk{color:#2ee59d;font-weight:700}#StatusBad{color:#ff2340;font-weight:700}
    """
