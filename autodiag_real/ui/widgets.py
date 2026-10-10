"""Wektorowe widżety UI v3 – rysowane QPainterem, ostre w każdej rozdzielczości (HiDPI/4K/8K)."""
import math
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath, QLinearGradient, QPixmap, QBrush
from PySide6.QtCore import Qt, QRectF, QPointF, QSize

RED, BLUE, CYAN, GREEN, AMBER, TXT, MUTED, PANEL = "#ff2340", "#1f6fff", "#3fa9ff", "#27e07a", "#ffb020", "#eef3ff", "#8d9ab3", "#0a0f1c"


class Panel(QFrame):
    """Panel z neonową ramką (kolor ramki = akcent)."""
    def __init__(self, title=None, accent=BLUE, title2=None):
        super().__init__(); self.accent = accent; self.setObjectName("Panel")
        self.setStyleSheet("#Panel{background:rgba(6,10,22,215);border:2px solid %s;border-radius:12px}" % (accent + "dd"))
        self.l = QVBoxLayout(self); self.l.setContentsMargins(12, 8, 12, 10); self.l.setSpacing(6)
        if title:
            t = QLabel("<b>%s</b> <span style='color:%s'>%s</span>" % (title, accent, title2 or "")); t.setStyleSheet("background:transparent;font-size:11pt")
            self.l.addWidget(t)


class Ring(QWidget):
    def __init__(self, value=100, color=BLUE, label="", sub="", thick=0.11):
        super().__init__(); self.value, self.color, self.label, self.sub, self.thick = value, color, label, sub, thick; self.setMinimumSize(60, 60)

    def set(self, value, sub=None):
        self.value = value; self.sub = self.sub if sub is None else sub; self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); s = min(self.width(), self.height()); t = s * self.thick
        r = QRectF((self.width() - s) / 2 + t, (self.height() - s) / 2 + t, s - 2 * t, s - 2 * t)
        p.setPen(QPen(QColor(31, 111, 255, 45), t, Qt.SolidLine, Qt.FlatCap)); p.drawEllipse(r)
        g = QLinearGradient(r.topLeft(), r.bottomRight()); g.setColorAt(0, QColor(CYAN)); g.setColorAt(1, QColor(self.color))
        p.setPen(QPen(QBrush(g), t, Qt.SolidLine, Qt.RoundCap)); p.drawArc(r, 90 * 16, int(-360 * 16 * max(0, min(100, self.value)) / 100))
        f = QFont(); f.setPixelSize(max(6, int(s * 0.22))); f.setBold(True); p.setFont(f); p.setPen(QColor(TXT))
        p.drawText(r.adjusted(0, -s * 0.08 if self.sub else 0, 0, 0), Qt.AlignCenter, self.label or "%d%%" % self.value)
        if self.sub:
            f.setPixelSize(max(5, int(s * 0.12))); f.setBold(False); p.setFont(f); p.setPen(QColor(MUTED)); p.drawText(r.adjusted(0, s * 0.25, 0, 0), Qt.AlignCenter, self.sub)


class Spark(QWidget):
    def __init__(self, color=CYAN, n=60):
        super().__init__(); self.color = color; self.data = []; self.n = n; self.setMinimumHeight(18)

    def push(self, v):
        self.data = (self.data + [v])[-self.n:]; self.update()

    def paintEvent(self, e):
        if len(self.data) < 2: return
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); lo, hi = min(self.data), max(self.data); hi = hi if hi > lo else lo + 1
        w, h = self.width(), self.height(); path = QPainterPath()
        for i, v in enumerate(self.data):
            pt = QPointF(i * w / (self.n - 1), h - 2 - (v - lo) / (hi - lo) * (h - 4))
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        fill = QPainterPath(path); fill.lineTo((len(self.data) - 1) * w / (self.n - 1), h); fill.lineTo(0, h); fill.closeSubpath()
        g = QLinearGradient(0, 0, 0, h); c = QColor(self.color); c.setAlpha(110); g.setColorAt(0, c); c2 = QColor(self.color); c2.setAlpha(0); g.setColorAt(1, c2)
        p.fillPath(fill, g); p.setPen(QPen(QColor(self.color), max(1.2, h / 18))); p.drawPath(path)


class Bar(QWidget):
    def __init__(self, value=100, color=GREEN):
        super().__init__(); self.value, self.color = value, color; self.setFixedHeight(6)
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); r = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen); p.setBrush(QColor(31, 111, 255, 45)); p.drawRoundedRect(r, 3, 3)
        p.setBrush(QColor(self.color)); p.drawRoundedRect(QRectF(0, 0, self.width() * self.value / 100, self.height()), 3, 3)


class Icon(QWidget):
    """Proste ikony wektorowe (bez zewnętrznych plików)."""
    def __init__(self, kind, color=TXT, size=26):
        super().__init__(); self.kind, self.color = kind, color; self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); s = self.width(); p.setPen(QPen(QColor(self.color), max(1.4, s / 14), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.NoBrush)
        k = self.kind; m = s * 0.15; R = QRectF(m, m, s - 2 * m, s - 2 * m)
        if k == "home":
            path = QPainterPath(); path.moveTo(m, s * .5); path.lineTo(s / 2, m); path.lineTo(s - m, s * .5); p.drawPath(path); p.drawRect(QRectF(s * .27, s * .48, s * .46, s * .37))
        elif k == "gear":
            p.drawEllipse(R.adjusted(s * .12, s * .12, -s * .12, -s * .12)); p.drawEllipse(QRectF(s * .4, s * .4, s * .2, s * .2))
            for i in range(8):
                a = i * math.pi / 4; p.drawLine(QPointF(s / 2 + s * .28 * math.cos(a), s / 2 + s * .28 * math.sin(a)), QPointF(s / 2 + s * .38 * math.cos(a), s / 2 + s * .38 * math.sin(a)))
        elif k == "chart":
            for i, hh in enumerate((.3, .55, .4, .7)): p.drawLine(QPointF(m + i * s * .22, s - m), QPointF(m + i * s * .22, s - m - hh * (s - 2 * m)))
        elif k == "roundel":
            p.drawArc(R, 200 * 16, -220 * 16); p.drawLine(QPointF(s / 2, s / 2), QPointF(s * .72, s * .3)); p.drawEllipse(QPointF(s / 2, s / 2), s * .05, s * .05)  # obrotomierz
        elif k == "wrench":
            p.drawLine(QPointF(s * .25, s * .75), QPointF(s * .65, s * .35)); p.drawEllipse(QRectF(s * .55, s * .15, s * .3, s * .3))
        elif k == "ai":
            p.drawRoundedRect(R.adjusted(0, s * .1, 0, 0), s * .12, s * .12); p.drawEllipse(QRectF(s * .3, s * .45, s * .1, s * .1)); p.drawEllipse(QRectF(s * .6, s * .45, s * .1, s * .1)); p.drawLine(QPointF(s / 2, m), QPointF(s / 2, s * .25))
        elif k == "code":
            p.drawPolyline([QPointF(s * .35, s * .3), QPointF(m, s / 2), QPointF(s * .35, s * .7)]); p.drawPolyline([QPointF(s * .65, s * .3), QPointF(s - m, s / 2), QPointF(s * .65, s * .7)])
        elif k == "chip":
            p.drawRect(R.adjusted(s * .12, s * .12, -s * .12, -s * .12))
            for i in range(3):
                x = s * (.35 + i * .15); p.drawLine(QPointF(x, m), QPointF(x, s * .27)); p.drawLine(QPointF(x, s * .73), QPointF(x, s - m))
        elif k == "plug":
            p.drawRect(QRectF(s * .3, s * .3, s * .4, s * .3)); p.drawLine(QPointF(s * .4, m), QPointF(s * .4, s * .3)); p.drawLine(QPointF(s * .6, m), QPointF(s * .6, s * .3)); p.drawLine(QPointF(s / 2, s * .6), QPointF(s / 2, s - m))
        elif k == "db":
            p.drawEllipse(QRectF(m, m, s - 2 * m, s * .25)); p.drawLine(QPointF(m, m + s * .12), QPointF(m, s - m - s * .12)); p.drawLine(QPointF(s - m, m + s * .12), QPointF(s - m, s - m - s * .12)); p.drawArc(QRectF(m, s - m - s * .25, s - 2 * m, s * .25), 180 * 16, 180 * 16)
        elif k == "doc":
            p.drawRect(R.adjusted(s * .1, 0, -s * .1, 0))
            for i in range(3): p.drawLine(QPointF(s * .35, s * (.35 + i * .15)), QPointF(s * .65, s * (.35 + i * .15)))
        elif k == "book":
            p.drawLine(QPointF(s / 2, s * .25), QPointF(s / 2, s - m)); p.drawPolyline([QPointF(s / 2, s * .25), QPointF(m, m), QPointF(m, s * .75), QPointF(s / 2, s - m), QPointF(s - m, s * .75), QPointF(s - m, m), QPointF(s / 2, s * .25)])
        elif k == "car":
            path = QPainterPath(); path.moveTo(m, s * .65); path.lineTo(m, s * .5); path.lineTo(s * .3, s * .3); path.lineTo(s * .7, s * .3); path.lineTo(s - m, s * .5); path.lineTo(s - m, s * .65); path.closeSubpath(); p.drawPath(path)
            p.drawEllipse(QRectF(s * .22, s * .6, s * .16, s * .16)); p.drawEllipse(QRectF(s * .62, s * .6, s * .16, s * .16))
        else:
            p.drawEllipse(R)


class MStripe(QWidget):
    def __init__(self, h=3): super().__init__(); self.setFixedHeight(h)
    def paintEvent(self, e):
        p = QPainter(self); w = self.width() / 3
        for i, c in enumerate(("#4fb3ff", "#1d5fa8", RED)): p.fillRect(QRectF(i * w, 0, w + 1, self.height()), QColor(c))


class Hero(QWidget):
    """Grafika tła w trybie 'cover' z płynnym skalowaniem i winietą."""
    def __init__(self, path):
        super().__init__(); self.set_art(path)

    def set_art(self, path):
        self.pix = QPixmap(path) if path else QPixmap()
        self.card_slot = None  # (fx, fy, fw, fh) – miejsce na kartę pojazdu w ułamkach obrazu
        if path and "_user" in str(path) and not self.pix.isNull():
            # grafika z referencji: pasmo treści 3840x1300 w ramce 16:9 (reszta to rozmyte wypełnienie)
            h = self.pix.height(); self.pix = self.pix.copy(0, int(h * 0.1991), self.pix.width(), int(h * 0.6018)); self.card_slot = (0.108, 0.0, 0.334, 0.40)
        # rozmyte tło do wypełnienia pasów bocznych w trybie "contain"
        self.blur = self.pix.scaled(48, 27, Qt.IgnoreAspectRatio, Qt.SmoothTransformation) if not self.pix.isNull() else QPixmap()
        self.update()

    def image_rect(self):
        """Tryb CONTAIN: cały obraz widoczny (głowy i stopy), wyśrodkowany."""
        r = self.rect()
        if self.pix.isNull(): return QRectF(r)
        pw, ph = self.pix.width(), self.pix.height(); sc = min(r.width() / pw, r.height() / ph); w, h = pw * sc, ph * sc
        return QRectF(r.width() - w, (r.height() - h) / 2, w, h)  # kotwica do prawej: lewa strona wolna na kartę

    def map_frac(self, fx, fy, fw, fh):
        """Prostokąt w ułamkach obrazu -> współrzędne widżetu (tryb contain)."""
        ir = self.image_rect(); return QRectF(ir.x() + ir.width() * fx, ir.y() + ir.height() * fy, ir.width() * fw, ir.height() * fh)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform); r = self.rect()
        if not self.pix.isNull():
            p.drawPixmap(QRectF(r), self.blur, QRectF(self.blur.rect())); p.fillRect(r, QColor(2, 4, 10, 150))
            ir = self.image_rect(); p.drawPixmap(ir, self.pix, QRectF(self.pix.rect()))
            for side in (0, 1):  # miękkie przejście krawędzi obrazu
                x = ir.left() if side == 0 else ir.right() - 80; g = QLinearGradient(x, 0, x + 80, 0)
                a, b = QColor(2, 4, 10, 200), QColor(2, 4, 10, 0)
                g.setColorAt(0, a if side == 0 else b); g.setColorAt(1, b if side == 0 else a); p.fillRect(QRectF(x, ir.top(), 80, ir.height()), g)
        else:
            g = QLinearGradient(0, 0, r.width(), r.height()); g.setColorAt(0, QColor("#120512")); g.setColorAt(1, QColor("#03122a")); p.fillRect(r, g)



def glow(w, color, radius=22, strength=200):
    """Neonowa poświata (QGraphicsDropShadowEffect bez przesunięcia)."""
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    e = QGraphicsDropShadowEffect(w); c = QColor(color); c.setAlpha(strength); e.setColor(c); e.setBlurRadius(radius); e.setOffset(0, 0); w.setGraphicsEffect(e); return w
