import html, re, subprocess, sys, webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt, QRect, QThread, QTimer, QUrl, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap, QTransform
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                             QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
                             QVBoxLayout, QWidget)

import core

ROLE = Qt.ItemDataRole.UserRole
PAGE = 20  # results per Modrinth page
KINDS = {"Mods": "mod", "Modpacks": "modpack", "Resource packs": "resourcepack", "Shaders": "shader"}
SORTS = {"Relevance": "relevance", "Downloads": "downloads", "Newest": "newest", "Updated": "updated"}
QSS = """
QWidget{background:transparent;color:#ecedef;font-size:14px;font-style:normal}
QDialog,QMessageBox,QInputDialog{background:#16181c}
#side{background:rgba(12,14,18,0.88);border-radius:18px}
#panel{background:rgba(16,18,23,0.84);border-radius:18px}
#title{font-size:17px;font-weight:800;color:#1bd96a;padding:16px 8px}
#chip{background:rgba(255,255,255,0.07);border-radius:12px;padding:10px;color:#aab0b8}
QPushButton{background:rgba(255,255,255,0.09);border:1px solid rgba(255,255,255,0.10);border-radius:10px;padding:10px 18px;font-weight:600}
QPushButton:hover{background:rgba(255,255,255,0.16);border-color:rgba(255,255,255,0.24)}
QPushButton:pressed{background:rgba(255,255,255,0.04)}
QPushButton:disabled{color:#7b8088;background:rgba(255,255,255,0.04)}
#nav{text-align:left;background:transparent;border:0;padding:12px 14px;font-weight:600}
#nav:hover{background:rgba(255,255,255,0.09)}
#nav:checked{background:rgba(27,217,106,0.18);color:#3dea84;border:1px solid rgba(27,217,106,0.35)}
#go,#play{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #3cec8b,stop:1 #12b857);border:1px solid #0e9446;color:#04140b;font-weight:800}
#go:hover,#play:hover{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #5af7a0,stop:1 #20cc67)}
#go:pressed,#play:pressed{background:#0f9e4a}
#go:disabled{background:rgba(27,217,106,0.25);color:#9fb;border-color:transparent}
#play{font-size:16px;padding:12px 34px;border-radius:12px}
#card{background:rgba(28,31,37,0.88);border-radius:14px;border:1px solid rgba(255,255,255,0.06)}
#card:hover{background:rgba(35,39,46,0.92);border-color:rgba(27,217,106,0.35)}
QScrollArea{border:0;background:transparent}
QScrollBar:vertical{background:transparent;width:10px;margin:2px}
QScrollBar::handle:vertical{background:rgba(255,255,255,0.20);border-radius:5px;min-height:30px}
QScrollBar::handle:vertical:hover{background:rgba(27,217,106,0.6)}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
QListWidget{background:transparent;border:0;outline:0}
QListWidget::item{background:rgba(28,31,37,0.88);border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:14px;margin:4px}
QListWidget::item:hover{background:rgba(35,39,46,0.92)}
QListWidget::item:selected{background:rgba(27,217,106,0.20);border:1px solid #1bd96a;color:#fff}
QLineEdit,QComboBox,QSpinBox{background:rgba(24,27,32,0.92);border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:8px}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus{border-color:#1bd96a}
QComboBox QAbstractItemView{background:#1b1e24;selection-background-color:#1f4a33;border:1px solid #2d3139}
QPlainTextEdit{background:rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.10);border-radius:10px;font-family:monospace;font-size:12px}
QCheckBox{spacing:8px;padding:4px}
QCheckBox::indicator{width:18px;height:18px;border-radius:5px;border:1px solid rgba(255,255,255,0.25);background:rgba(24,27,32,0.9)}
QCheckBox::indicator:checked{background:#1bd96a;border-color:#0e9446}
#pg{padding:7px 13px;min-width:18px}
#pg[cur="true"]{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #3cec8b,stop:1 #12b857);color:#04140b;font-weight:800;border-color:#0e9446}
#icard{background:rgba(28,31,37,0.88);border-radius:16px;border:1px solid rgba(255,255,255,0.07)}
#icard:hover{background:rgba(36,40,47,0.94);border-color:rgba(255,255,255,0.20)}
#icard[sel="true"]{background:rgba(27,217,106,0.12);border:2px solid #1bd96a}
#fab{background:#1bd96a;color:#04140b;border:0;border-radius:20px;font-size:16px;font-weight:800;padding:0}
#fab:hover{background:#4bf39a}
QMenu{background:#1b1e24;border:1px solid #2d3139;border-radius:10px;padding:6px}
QMenu::item{padding:8px 22px;border-radius:6px}
QMenu::item:selected{background:#1f4a33}
QFileDialog QListView,QFileDialog QTreeView{background:#1b1e24}
QProgressBar{background:rgba(255,255,255,0.08);border:0;border-radius:4px;max-height:7px;color:transparent}
QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1bd96a,stop:1 #7dffb5);border-radius:4px}
"""


def pick_files(parent, title, flt, multiple=True):
    """File chooser that always works (Qt's own dialog, not the desktop portal that can fail on some setups)."""
    d = QFileDialog(parent, title, str(Path.home()), flt)
    d.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    d.setFileMode(QFileDialog.FileMode.ExistingFiles if multiple else QFileDialog.FileMode.ExistingFile)
    d.resize(880, 560)
    return d.selectedFiles() if d.exec() else []


def show_in_files(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        core.open_path(path)


class Backdrop(QWidget):
    """Window background: Minecraft-style images that cross-fade automatically (or one fixed image)."""

    def __init__(self, cfg):
        super().__init__()
        self.cfg, self.paths, self.pix, self.i, self.cur, self.prev, self.t = cfg, [], {}, 0, None, None, 1.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(1500)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.valueChanged.connect(self.tick)
        self.reload()

    def pause(self):
        self.timer.stop()
        self.anim.stop()
        self.prev, self.t = None, 1.0

    def reload(self):
        self.paths = core.background_files()
        self.apply()

    def apply(self):
        self.timer.stop()
        choice = self.cfg.get("bg", "auto")
        names = [p.name for p in self.paths]
        if choice != "auto" and choice in names:
            self.show_index(names.index(choice))
        elif self.paths:
            self.show_index(self.i % len(self.paths))
            if not self.cfg.get("lite"):
                self.timer.start(max(5, int(self.cfg.get("bg_interval", 20))) * 1000)
        self.update()

    def load(self, p):
        if p not in self.pix:
            self.pix[p] = QPixmap(str(p))
        return self.pix[p]

    def show_index(self, i):
        self.i = i
        new = self.load(self.paths[i])
        self.pix = {k: v for k, v in self.pix.items() if v is new or v is self.cur}  # keep only what is on screen
        if self.cur is not None and new is not self.cur and not self.cfg.get("lite"):
            self.prev, self.t = self.cur, 0.0
            self.anim.stop()
            self.anim.start()
        self.cur = new
        self.update()

    def advance(self):
        if self.paths:
            self.show_index((self.i + 1) % len(self.paths))

    def tick(self, v):
        self.t = float(v)
        if self.t >= 1.0:
            self.prev = None
        self.update()

    def draw(self, p, pm, opacity):
        if pm is None or pm.isNull():
            return
        s = pm.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        p.setOpacity(opacity)
        p.drawPixmap(QRect((self.width() - s.width()) // 2, (self.height() - s.height()) // 2, s.width(), s.height()), pm)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(16, 18, 22))
        if self.prev is not None:
            self.draw(p, self.prev, 1.0)
        self.draw(p, self.cur, self.t if self.prev is not None else 1.0)
        p.setOpacity(1.0)
        p.fillRect(self.rect(), QColor(8, 10, 14, int(255 * self.cfg.get("bg_dim", 40) / 100)))


class Task(QThread):
    status, done, fail = pyqtSignal(str, int), pyqtSignal(object), pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn(lambda t, p: self.status.emit(t or "", -1 if p is None else p)))
        except Exception as e:
            self.fail.emit(str(e))


class Icons(QThread):
    got = pyqtSignal(int, bytes)

    def __init__(self, urls):
        super().__init__()
        self.urls, self.stop = urls, False

    def run(self):
        for i, u in enumerate(self.urls):
            if self.stop:
                return
            try:
                if u:
                    self.got.emit(i, core.fetch_bytes(u))
            except Exception:
                pass


class Welcome(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Welcome")
        self.setMinimumWidth(460)
        self.choice = None
        v = QVBoxLayout(self)
        v.setContentsMargins(34, 28, 34, 28)
        v.setSpacing(14)
        v.addWidget(QLabel("<h1 style='color:#1bd96a'>Welcome to ModLauncher</h1>"))
        t = QLabel("Sign in with your Microsoft account to play. You get a short code, enter it on the Microsoft page, and you're in.")
        t.setWordWrap(True)
        v.addWidget(t)
        go = QPushButton("Sign in with Microsoft")
        go.setObjectName("play")
        go.setMinimumHeight(52)
        go.clicked.connect(lambda: self.pick("microsoft"))
        later = QPushButton("Not now")
        later.clicked.connect(self.reject)
        v.addWidget(go)
        v.addWidget(later)

    def pick(self, c):
        self.choice = c
        self.accept()


class FilesDialog(QDialog):
    """Lists mods / resource packs / shaders of an instance; add from your computer or remove."""

    def __init__(self, parent, inst, sub, title, exts):
        super().__init__(parent)
        self.inst, self.sub, self.exts = inst, sub, exts
        self.setWindowTitle(f"{title} - {inst}")
        self.resize(560, 460)
        v = QVBoxLayout(self)
        self.lst = QListWidget()
        v.addWidget(self.lst)
        row = QHBoxLayout()
        row.addWidget(QPushButton("Add from computer…", clicked=self.add))
        row.addWidget(QPushButton("Open folder", clicked=lambda: show_in_files(core.INST / inst / sub)))
        if sub == "mods":
            row.addWidget(QPushButton("Disable / enable", clicked=self.toggle))
        row.addWidget(QPushButton("Remove selected", clicked=self.rm))
        v.addLayout(row)
        self.load()

    def load(self):
        self.lst.clear()
        self.lst.addItems(core.list_files(self.inst, self.sub, self.exts))

    def add(self):
        pat = " ".join("*" + e for e in self.exts)
        files = pick_files(self, "Choose files", f"Files ({pat});;All files (*)")
        for f in files:
            core.add_file(self.inst, self.sub, f)
        self.load()

    def toggle(self):
        if self.lst.currentItem():
            core.toggle_file(self.inst, self.sub, self.lst.currentItem().text())
            self.load()

    def rm(self):
        if self.lst.currentItem():
            core.remove_file(self.inst, self.sub, self.lst.currentItem().text())
            self.load()


class VersionDialog(QDialog):
    def __init__(self, parent, title, versions):
        super().__init__(parent)
        self.setWindowTitle(f"Choose a version - {title}")
        self.resize(640, 460)
        v = QVBoxLayout(self)
        self.lst = QListWidget()
        v.addWidget(self.lst)
        for x in versions:
            gv = ", ".join(x["game_versions"][:4]) + ("…" if len(x["game_versions"]) > 4 else "")
            it = QListWidgetItem(f"{x['name']}\n{x['version_number']} · {x['version_type']} · MC {gv} · "
                                 f"{', '.join(x['loaders'][:3])} · {x['date_published'][:10]}")
            it.setData(ROLE, x)
            self.lst.addItem(it)
        self.lst.setCurrentRow(0)
        self.lst.itemDoubleClicked.connect(lambda _: self.accept())
        ok = QPushButton("Install selected version")
        ok.setObjectName("go")
        ok.clicked.connect(self.accept)
        v.addWidget(ok)

    def chosen(self):
        it = self.lst.currentItem()
        return it.data(ROLE) if it else None


class NewInstance(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("New instance")
        f = QFormLayout(self)
        self.name, self.ver, self.loader = QLineEdit("My instance"), QComboBox(), QComboBox()
        self.loader.addItems(["fabric", "quilt", "vanilla"])
        try:
            self.ver.addItems([v["id"] for v in core.mll.utils.get_version_list() if v["type"] == "release"])
        except Exception:
            self.ver.addItems(["1.21.4"])
        ok = QPushButton("Create")
        ok.setObjectName("go")
        ok.clicked.connect(self.accept)
        for label, w in (("Name", self.name), ("Minecraft", self.ver), ("Loader", self.loader)):
            f.addRow(label, w)
        f.addRow(ok)


class Card(QFrame):
    def __init__(self, hit, on_install):
        super().__init__()
        self.setObjectName("card")
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 14, 12)
        self.icon = QLabel()
        self.icon.setFixedSize(64, 64)
        self.icon.setStyleSheet("background:#2a2d34;border-radius:12px")
        e = html.escape
        t = QLabel(f"<b style='font-size:15px'>{e(hit['title'])}</b> <span style='color:#8b9099'>by {e(hit['author'])}</span>"
                   f"<br><span style='color:#aab0b8'>{e(hit['description'])}</span>"
                   f"<br><span style='color:#8b9099'>⬇ {hit['downloads']:,}</span>")
        t.setWordWrap(True)
        self.btn = QPushButton("Install")
        self.btn.setObjectName("go")
        self.btn.setFixedWidth(130)
        self.btn.clicked.connect(lambda: on_install(hit, self.btn))
        vb = QPushButton("Versions…")
        vb.setFixedWidth(130)
        vb.clicked.connect(lambda: on_install(hit, self.btn, True))
        col = QVBoxLayout()
        col.addWidget(self.btn)
        col.addWidget(vb)
        h.addWidget(self.icon)
        h.addWidget(t, 1)
        h.addLayout(col)

    def set_icon(self, data):
        pm = QPixmap()
        if pm.loadFromData(data):
            self.icon.setPixmap(pm.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


def skin_body(pm, s=8):
    """Front view of a Minecraft skin (Steve/Alex) drawn from the skin texture."""
    k = max(1, pm.width() // 64)
    img = pm.toImage()
    new = pm.height() >= 64 * k
    slim = new and all(img.pixelColor(47 * k, y * k).alpha() == 0 for y in range(20, 32))
    aw = 3 if slim else 4
    out = QPixmap(16 * s, 32 * s)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    fast, ign = Qt.TransformationMode.FastTransformation, Qt.AspectRatioMode.IgnoreAspectRatio

    def part(sx, sy, w, h, dx, dy, flip=False):
        r = pm.copy(sx * k, sy * k, w * k, h * k).scaled(w * s, h * s, ign, fast)
        if flip:
            r = r.transformed(QTransform().scale(-1, 1))
        p.drawPixmap(dx * s, dy * s, r)
    part(8, 8, 8, 8, 4, 0)
    part(20, 20, 8, 12, 4, 8)
    part(44, 20, aw, 12, 4 - aw, 8)
    part(4, 20, 4, 12, 4, 20)
    if new:
        part(36, 52, aw, 12, 12, 8)
        part(20, 52, 4, 12, 8, 20)
    else:
        part(44, 20, aw, 12, 12, 8, True)
        part(4, 20, 4, 12, 8, 20, True)
    part(40, 8, 8, 8, 4, 0)
    if new:
        for args in ((20, 36, 8, 12, 4, 8), (44, 36, aw, 12, 4 - aw, 8), (52, 52, aw, 12, 12, 8),
                     (4, 36, 4, 12, 4, 20), (4, 52, 4, 12, 8, 20)):
            part(*args)
    p.end()
    return out


def make_icon(name, path, size):
    """Rounded instance icon: the instance's own picture, or a colourful tile with the first letter."""
    pm = QPixmap(str(path)) if path and Path(path).exists() else QPixmap()
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(0.0, 0.0, float(size), float(size), 16.0, 16.0)
    p.setClipPath(clip)
    if not pm.isNull():
        s = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((size - s.width()) // 2, (size - s.height()) // 2, s)
    else:
        hue = sum(map(ord, name)) * 37 % 360
        g = QLinearGradient(0, 0, size, size)
        g.setColorAt(0, QColor.fromHsv(hue, 190, 235))
        g.setColorAt(1, QColor.fromHsv((hue + 40) % 360, 220, 150))
        p.fillRect(QRect(0, 0, size, size), QBrush(g))
        f = p.font()
        f.setPixelSize(int(size * 0.5))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 235))
        p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter.value, name[:1].upper())
    p.end()
    return out


class InstCard(QFrame):
    """One instance in the library grid (like Modrinth's): picture, name, loader + version, hover play button."""
    clicked, played, menu_requested = pyqtSignal(str), pyqtSignal(str), pyqtSignal(str, object)

    def __init__(self, name, meta):
        super().__init__()
        self.name = name
        self.setObjectName("icard")
        self.setFixedSize(184, 236)
        self.setProperty("sel", False)
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 10)
        v.setSpacing(4)
        icon = QLabel()
        icon.setFixedSize(152, 152)
        icon.setPixmap(make_icon(name, core.icon_path(name), 152))
        self.fab = QPushButton("▶", icon)
        self.fab.setObjectName("fab")
        self.fab.setFixedSize(40, 40)
        self.fab.move(152 - 48, 152 - 48)
        self.fab.hide()
        self.fab.clicked.connect(lambda: self.played.emit(self.name))
        bold = QFont(self.font())
        bold.setPixelSize(15)
        bold.setBold(True)
        title = QLabel(QFontMetrics(bold).elidedText(name, Qt.TextElideMode.ElideRight, 146))
        title.setStyleSheet("font-weight:700;font-size:15px")
        title.setToolTip(name)
        kind = "Modpack" if meta["loader"] == "modpack" else meta["loader"].title()
        sub = QLabel(f"{kind} {meta['mc']}")
        sub.setStyleSheet("color:#9aa1ab")
        v.addWidget(icon)
        v.addWidget(title)
        v.addWidget(sub)
        v.addStretch()

    def set_selected(self, on):
        self.setProperty("sel", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, e):
        self.fab.show()

    def leaveEvent(self, e):
        self.fab.hide()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.name)

    def mouseDoubleClickEvent(self, e):
        self.played.emit(self.name)

    def contextMenuEvent(self, e):
        self.clicked.emit(self.name)
        self.menu_requested.emit(self.name, e.globalPos())


class Grid(QScrollArea):
    """Scrollable grid that re-flows its cards when the window is resized."""

    def __init__(self, cell_w=184, gap=14):
        super().__init__()
        self.cell_w, self.gap, self.items = cell_w, gap, []
        self.setWidgetResizable(True)
        self.host = QWidget()
        self.lay = QGridLayout(self.host)
        self.lay.setContentsMargins(4, 4, 4, 4)
        self.lay.setSpacing(gap)
        self.lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self.host)

    def set_items(self, widgets):
        for w in self.items:
            w.setParent(None)
            w.deleteLater()
        self.items = list(widgets)
        self.relayout()

    def relayout(self):
        while self.lay.count():
            self.lay.takeAt(0)
        cols = max(1, (self.viewport().width() - 8) // (self.cell_w + self.gap))
        for i, w in enumerate(self.items):
            self.lay.addWidget(w, i // cols, i % cols)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg, self.tasks, self.running, self.cards, self.icons = core.load_cfg(), [], False, [], None
        self.setWindowTitle(f"ModLauncher {core.APP_VERSION}")
        self.setAcceptDrops(True)
        self.in_game = False
        icon = core.ASSETS / "icon.png"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1080, 700)
        root = self.root = Backdrop(self.cfg)
        h = QHBoxLayout(root)
        h.setContentsMargins(14, 14, 14, 14)
        h.setSpacing(14)

        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(216)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 6, 10, 14)
        t = QLabel("⛏ ModLauncher")
        t.setObjectName("title")
        sl.addWidget(t)
        self.stack, grp = QStackedWidget(), QButtonGroup(self)
        for i, n in enumerate(["🎮  Library", "🔎  Browse", "🧍  Skins", "⚡  Performance", "👤  Account"]):
            b = QPushButton(n)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setChecked(i == 0)
            grp.addButton(b, i)
            b.clicked.connect(lambda _, i=i: self.stack.setCurrentIndex(i))
            sl.addWidget(b)
        sl.addStretch()
        self.chip = QLabel()
        self.chip.setObjectName("chip")
        self.chip.setWordWrap(True)
        self.update_btn = self.btn("⬆  Update available", self.open_update, True)
        self.update_btn.hide()
        sl.addWidget(self.update_btn)
        sl.addWidget(self.chip)
        ver = QLabel(f"ModLauncher {core.APP_VERSION}")
        ver.setStyleSheet("color:#6f7680;font-size:12px;padding:2px 6px")
        sl.addWidget(ver)
        for page in (self.lib_page(), self.browse_page(), self.skins_page(), self.perf_page(), self.account_page()):
            self.stack.addWidget(page)

        right = QVBoxLayout()
        right.setContentsMargins(22, 18, 22, 12)
        right.addWidget(self.stack, 1)
        self.bar, self.msg = QProgressBar(), QLabel("Ready")
        right.addWidget(self.bar)
        right.addWidget(self.msg)
        h.addWidget(side)
        panel = QWidget()
        panel.setObjectName("panel")
        panel.setLayout(right)
        h.addWidget(panel, 1)
        self.setCentralWidget(root)
        self.refresh()
        self.show_acct()
        QTimer.singleShot(150, self.first_run)

    # ----- helpers -----
    def run(self, fn, ok=lambda r: None, err=None, quiet=False):
        t = Task(fn)
        t.status.connect(self.on_status)
        t.done.connect(ok)
        t.fail.connect(lambda e: (None if quiet else self.on_fail(e), err(e) if err else None))
        t.finished.connect(lambda: self.tasks.remove(t))
        self.tasks.append(t)
        t.start()

    def on_status(self, text, pct):
        if text:
            self.msg.setText(text)
            if text.startswith("Playing ") and self.running:
                self.enter_game_mode()
        if pct >= 0:
            self.bar.setValue(pct)

    def on_fail(self, e):
        self.leave_game_mode()
        self.msg.setText("Something went wrong")
        QMessageBox.critical(self, "Error", e)

    def btn(self, text, fn, go=False):
        b = QPushButton(text)
        b.clicked.connect(fn)
        if go:
            b.setObjectName("go")
        return b

    def title(self, text):
        return QLabel(f"<h2>{text}</h2>")

    def refresh(self):
        names = core.list_instances()
        keep = self.target.currentText()
        self.target.clear()
        self.target.addItems(names)
        if keep in names:
            self.target.setCurrentText(keep)
        keep_pf = self.pf_inst.currentText()
        self.pf_inst.clear()
        self.pf_inst.addItems(names)
        if keep_pf in names:
            self.pf_inst.setCurrentText(keep_pf)
        self.update_preview()
        metas = {n: core.get_instance(n) for n in names}
        q, flt = self.lib_q.text().strip().lower(), self.lib_filter.currentText()
        want = {"Modpacks": "modpack", "Fabric": "fabric", "Quilt": "quilt", "Vanilla": "vanilla"}.get(flt)
        shown = [n for n in names if (not q or q in n.lower()) and (want is None or metas[n]["loader"] == want)]
        how = self.lib_sort.currentText()
        if how == "Last played":
            shown.sort(key=lambda n: -metas[n].get("last_played", 0))
        elif how == "Name":
            shown.sort(key=str.lower)
        else:
            shown.sort(key=lambda n: tuple(int(x) for x in re.findall(r"\d+", metas[n]["mc"])), reverse=True)
        if self.sel not in names:
            self.sel = None
        self.icards = {}
        for n in shown:
            c = InstCard(n, metas[n])
            c.clicked.connect(self.select)
            c.played.connect(self.play_named)
            c.menu_requested.connect(self.card_menu)
            c.set_selected(n == self.sel)
            self.icards[n] = c
        self.grid.set_items(self.icards.values())
        self.grid.setVisible(bool(shown))
        self.empty.setVisible(not shown)

    # ----- performance -----
    def perf_page(self):
        w, f = QWidget(), QFormLayout()
        w.setLayout(f)
        p = core.perf_cfg(self.cfg)
        total, avail = core.system_ram()
        f.addRow(self.title("⚡ Performance"))
        f.addRow(QLabel(f"Your PC: <b>{total / 1024:.1f} GB</b> RAM ({avail / 1024:.1f} GB free right now)"))
        self.pf_inst, self.pf_ram_mode, self.pf_ram = QComboBox(), QComboBox(), QSpinBox()
        self.pf_profile, self.pf_launch = QComboBox(), QComboBox()
        for box, items in ((self.pf_ram_mode, (("Auto (recommended)", "auto"), ("Manual", "manual"))),
                           (self.pf_profile, (("Balanced · G1GC (recommended)", "balanced"),
                                              ("Smooth · ZGC (Java 21+, uses more RAM)", "zgc"),
                                              ("Low-end PC · SerialGC", "serial"), ("Custom · only my own flags", "custom"))),
                           (self.pf_launch, (("Minimize the launcher", "minimize"), ("Hide the launcher", "hide"), ("Keep it open", "keep")))):
            for label, key in items:
                box.addItem(label, key)
        for box, key in ((self.pf_ram_mode, "ram_mode"), (self.pf_profile, "profile"), (self.pf_launch, "on_launch")):
            box.setCurrentIndex(max(0, box.findData(p[key])))
        self.pf_ram.setRange(1024, 65536)
        self.pf_ram.setSingleStep(256)
        self.pf_ram.setSuffix(" MB")
        self.pf_ram.setValue(p["ram_mb"])
        self.pf_ram.setEnabled(p["ram_mode"] == "manual")
        self.pf_extra = QLineEdit(p["extra"])
        self.pf_extra.setPlaceholderText("extra JVM flags (optional), e.g. -XX:+UseTransparentHugePages")
        self.pf_gm = QCheckBox("Use GameMode when installed (Linux: CPU boost + priority)")
        self.pf_prio = QCheckBox("Raise the game's priority (Windows)")
        self.pf_gl = QCheckBox("OpenGL threading (Mesa / NVIDIA)")
        self.pf_gpu = QCheckBox("Use the dedicated GPU (hybrid laptops)")
        self.pf_lite = QCheckBox("Lightweight launcher: static background, no animations")
        for cb, on in ((self.pf_gm, p["gamemode"]), (self.pf_prio, p["raise_priority"]), (self.pf_gl, p["gl_threading"]),
                       (self.pf_gpu, p["dedicated_gpu"]), (self.pf_lite, bool(self.cfg.get("lite")))):
            cb.setChecked(on)
            cb.toggled.connect(lambda _: self.save_perf())
        for box in (self.pf_inst, self.pf_ram_mode, self.pf_profile, self.pf_launch):
            box.activated.connect(lambda _: self.save_perf())
        self.pf_ram.valueChanged.connect(lambda _: self.save_perf())
        self.pf_extra.editingFinished.connect(self.save_perf)
        self.pf_auto = QLabel()
        self.pf_auto.setWordWrap(True)
        self.pf_preview = QLabel()
        self.pf_preview.setWordWrap(True)
        self.pf_preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.pf_preview.setStyleSheet("font-family:monospace;font-size:12px;color:#9fb0a6;background:rgba(0,0,0,0.25);border-radius:8px;padding:8px")
        f.addRow("Preview for", self.pf_inst)
        f.addRow("Memory", self.pf_ram_mode)
        f.addRow("Manual amount", self.pf_ram)
        f.addRow(self.pf_auto)
        f.addRow("Java profile", self.pf_profile)
        f.addRow("Extra flags", self.pf_extra)
        f.addRow(self.pf_preview)
        f.addRow(QLabel("<h3>While you play</h3>"))
        f.addRow("When the game starts", self.pf_launch)
        for cb in (self.pf_gm, self.pf_prio, self.pf_gl, self.pf_gpu, self.pf_lite):
            f.addRow(cb)
        self.pf_video = QComboBox()
        for label, key in (("Max FPS (render distance 8)", "fps"), ("Balanced (render distance 12)", "balanced"),
                           ("Quality (render distance 16)", "quality")):
            self.pf_video.addItem(label, key)
        f.addRow(QLabel("<h3>In-game video settings</h3>"))
        f.addRow("Preset", self.pf_video)
        f.addRow(self.btn("Apply preset to the selected instance", self.apply_video))
        f.addRow(self.btn("⚡  Install FPS mods (Fabric/Quilt)", self.install_fps_mods, True))
        return w

    def save_perf(self):
        self.cfg["perf"] = {"ram_mode": self.pf_ram_mode.currentData(), "ram_mb": self.pf_ram.value(),
                            "profile": self.pf_profile.currentData(), "extra": self.pf_extra.text().strip(),
                            "on_launch": self.pf_launch.currentData(), "gamemode": self.pf_gm.isChecked(),
                            "raise_priority": self.pf_prio.isChecked(), "gl_threading": self.pf_gl.isChecked(),
                            "dedicated_gpu": self.pf_gpu.isChecked(), "schema": 2}
        lite = self.pf_lite.isChecked()
        changed = lite != bool(self.cfg.get("lite"))
        self.cfg["lite"] = lite
        core.save_cfg(self.cfg)
        self.pf_ram.setEnabled(self.pf_ram_mode.currentData() == "manual")
        self.update_preview()
        if changed:
            self.root.apply()

    def update_preview(self):
        inst = self.pf_inst.currentText()
        if not inst:
            self.pf_auto.setText("Create an instance to preview its settings.")
            self.pf_preview.setText("")
            return
        major = core.java_major(core.get_instance(inst)["version_id"], self.cfg.get("java_path", ""))
        ram = core.pick_ram_mb(self.cfg, inst)
        total, avail = core.system_ram()
        txt = f"“{html.escape(inst)}” will use <b>{ram / 1024:.1f} GB</b> · Java {major}"
        if core.perf_cfg(self.cfg)["ram_mode"] == "manual":
            txt += f" · Auto would pick {core.auto_ram_mb(inst, total, avail) / 1024:.1f} GB"
            if ram > avail - 512:
                txt += (f"<br><span style='color:#ffb454'>⚠ Only {avail / 1024:.1f} GB is free right now. Using more than that makes "
                        "the PC swap and the game stutter; 4–6 GB is plenty for most packs.</span>")
        self.pf_auto.setText(txt)
        self.pf_preview.setText(" ".join(core.jvm_args(self.cfg, inst, major)))

    def install_fps_mods(self):
        inst = self.pf_inst.currentText()
        if not inst:
            return QMessageBox.information(self, "No instance", "Create an instance first.")
        if core.get_instance(inst)["loader"] not in ("fabric", "quilt"):
            return QMessageBox.information(self, "Fabric or Quilt only", "FPS mods are installed into Fabric/Quilt instances. "
                                           "Modpacks are left alone so nothing conflicts.")
        ask = QMessageBox.question(self, "Install FPS mods", f"Install Sodium, Lithium, FerriteCore, ModernFix, ImmediatelyFast and "
                                   f"Entity Culling into “{inst}”?")
        if ask == QMessageBox.StandardButton.Yes:
            self.run(lambda e: core.install_fps_mods(inst, e), lambda r: QMessageBox.information(self, "FPS mods", r))

    def apply_video(self):
        inst = self.pf_inst.currentText()
        if not inst:
            return QMessageBox.information(self, "No instance", "Create an instance first.")
        if self.running:
            return QMessageBox.information(self, "Game is running", "Close the game first, it would overwrite the settings when it exits.")
        core.apply_video_preset(inst, self.pf_video.currentData())
        self.msg.setText(f"Video preset applied to “{inst}”")

    def sync_perf(self):
        p = core.perf_cfg(self.cfg)
        for box, key in ((self.pf_ram_mode, "ram_mode"), (self.pf_profile, "profile"), (self.pf_launch, "on_launch")):
            box.setCurrentIndex(max(0, box.findData(p[key])))
        self.pf_ram.setValue(p["ram_mb"])
        self.pf_extra.setText(p["extra"])
        for cb, key in ((self.pf_gm, "gamemode"), (self.pf_prio, "raise_priority"), (self.pf_gl, "gl_threading"), (self.pf_gpu, "dedicated_gpu")):
            cb.setChecked(p[key])
        self.save_perf()

    def safe_settings(self):
        p = core.perf_cfg(self.cfg)
        p.update(ram_mode="auto", profile="balanced", extra="", gamemode=False, gl_threading=False, dedicated_gpu=False)
        self.cfg["perf"] = p
        self.sync_perf()
        self.msg.setText("Safe settings applied. Try playing again.")

    def show_crash(self, r):
        d = QDialog(self)
        d.setWindowTitle("The game closed unexpectedly")
        d.resize(780, 580)
        v = QVBoxLayout(d)
        head = QLabel("<h3>The game closed unexpectedly</h3>" + "".join(f"<p>• {html.escape(h)}</p>" for h in r["hints"]))
        head.setWordWrap(True)
        v.addWidget(head)
        box = QPlainTextEdit(r["text"])
        box.setReadOnly(True)
        v.addWidget(box, 1)
        row = QHBoxLayout()
        row.addWidget(self.btn("Apply safe settings", lambda: (self.safe_settings(), d.accept()), True))
        row.addWidget(self.btn("Copy report", lambda: QApplication.clipboard().setText(r["text"])))
        row.addWidget(self.btn("Open instance folder", lambda: show_in_files(r["folder"])))
        row.addStretch()
        row.addWidget(self.btn("Close", d.accept))
        v.addLayout(row)
        d.exec()

    def enter_game_mode(self):
        """While the game runs the launcher goes quiet: no animations, no timers, window minimized/hidden."""
        if self.in_game:
            return
        self.in_game = True
        self.root.pause()
        if self.icons:
            self.icons.stop = True
        how = core.perf_cfg(self.cfg)["on_launch"]
        if how == "hide":
            self.hide()
        elif how == "minimize":
            self.showMinimized()

    def leave_game_mode(self):
        if not self.in_game:
            return
        self.in_game = False
        self.root.apply()
        if self.isHidden() or self.isMinimized():
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def check_updates(self, manual=False):
        self.run(lambda e: core.check_update(), lambda r: self.on_update(r, manual), quiet=not manual)

    def on_update(self, r, manual):
        if not r:
            if manual:
                QMessageBox.information(self, "Updates", f"You're up to date ({core.APP_VERSION}).")
            return
        self.upd = r
        self.update_btn.setText(f"⬆  Update {r['tag']}")
        self.update_btn.show()
        if not manual and self.cfg.get("skip_update") == r["tag"]:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Update available")
        box.setText(f"<b>ModLauncher {r['tag']}</b> is available (you have {core.APP_VERSION}).")
        if r["notes"]:
            box.setInformativeText(r["notes"])
        get = box.addButton("Open download page", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        skip = box.addButton("Skip this version", QMessageBox.ButtonRole.ActionRole)
        box.exec()
        if box.clickedButton() is get:
            self.open_update()
        elif box.clickedButton() is skip:
            self.cfg["skip_update"] = r["tag"]
            core.save_cfg(self.cfg)

    def open_update(self):
        if getattr(self, "upd", None):
            webbrowser.open(self.upd["url"])

    def first_run(self):
        if not self.cfg.get("account"):
            self.welcome()
        self.new_search(quiet=True)
        self.load_skin()
        self.check_updates()

    # ----- library -----
    def lib_page(self):
        w, v = QWidget(), QVBoxLayout()
        w.setLayout(v)
        self.sel, self.icards = None, {}
        v.addWidget(self.title("Library"))
        top = QHBoxLayout()
        self.lib_q = QLineEdit()
        self.lib_q.setPlaceholderText("🔍  Search your instances")
        self.lib_q.textChanged.connect(lambda _: self.refresh())
        top.addWidget(self.lib_q, 1)
        top.addWidget(self.btn("Import file…", self.import_files))
        top.addWidget(self.btn("＋  New instance", self.new_inst, True))
        v.addLayout(top)
        flt = QHBoxLayout()
        self.lib_sort, self.lib_filter = QComboBox(), QComboBox()
        self.lib_sort.addItems(["Last played", "Name", "Minecraft version"])
        self.lib_filter.addItems(["All types", "Modpacks", "Fabric", "Quilt", "Vanilla"])
        for cb in (self.lib_sort, self.lib_filter):
            cb.activated.connect(lambda _: self.refresh())
            flt.addWidget(cb)
        flt.addStretch()
        v.addLayout(flt)
        self.grid = Grid()
        self.empty = QLabel("No instances yet.\nPress “New instance”, or install a modpack from Browse.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet("color:#9aa1ab;font-size:15px")
        v.addWidget(self.grid, 1)
        v.addWidget(self.empty, 1)
        bar = QHBoxLayout()
        for b in (self.play_btn(), self.btn("Mods", lambda: self.show_files("mods", "Mods", (".jar", ".litemod", ".disabled"))),
                  self.btn("Resource packs", lambda: self.show_files("resourcepacks", "Resource packs", (".zip",))),
                  self.btn("Shaders", lambda: self.show_files("shaderpacks", "Shaders", (".zip",))),
                  self.btn("Open folder", self.open_folder), self.btn("Delete", self.del_inst)):
            bar.addWidget(b)
        bar.addStretch()
        v.addLayout(bar)
        return w

    def select(self, name):
        self.sel = name
        for n, c in self.icards.items():
            c.set_selected(n == name)

    def play_named(self, name):
        self.select(name)
        self.play()

    def card_menu(self, name, pos):
        menu = QMenu(self)
        for text, fn in (("▶  Play", lambda: self.play_named(name)),
                         ("Mods", lambda: self.show_files("mods", "Mods", (".jar", ".litemod", ".disabled"))),
                         ("Resource packs", lambda: self.show_files("resourcepacks", "Resource packs", (".zip",))),
                         ("Shaders", lambda: self.show_files("shaderpacks", "Shaders", (".zip",))),
                         ("Open folder", self.open_folder), ("Change icon…", lambda: self.change_icon(name)),
                         ("Delete", self.del_inst)):
            menu.addAction(text).triggered.connect(fn)
        menu.exec(pos)

    def change_icon(self, name):
        f = (pick_files(self, "Choose an icon", "Images (*.png *.jpg *.jpeg *.webp);;All files (*)", False) or [""])[0]
        pm = QPixmap(f) if f else QPixmap()
        if not pm.isNull():
            pm.save(str(core.icon_path(name)), "PNG")
            self.refresh()

    def play_btn(self):
        b = self.btn("▶  Play", self.play)
        b.setObjectName("play")
        fx = QGraphicsDropShadowEffect(b)
        fx.setColor(QColor(27, 217, 106, 170))
        fx.setBlurRadius(30)
        fx.setOffset(0, 0)
        b.setGraphicsEffect(fx)
        return b

    def cur(self):
        return self.sel if self.sel in core.list_instances() else None

    def play(self):
        name = self.cur()
        if not name or self.running:
            return
        if not self.cfg.get("account"):
            return self.welcome()
        self.running = True
        self.run(lambda e: core.play(name, self.cfg, e), lambda r: self.after_play(r),
                 lambda e: setattr(self, "running", False))

    def after_play(self, result=None):
        self.running = False
        self.leave_game_mode()
        self.msg.setText("Game closed")
        self.bar.setValue(0)
        self.refresh()
        if result:
            self.show_crash(result)

    def new_inst(self):
        d = NewInstance(self)
        if d.exec():
            name, ver, ld = d.name.text().strip(), d.ver.currentText(), d.loader.currentText()
            if name:
                self.run(lambda e: core.create_instance(name, ver, ld, e), lambda _: (self.refresh(), self.msg.setText("Instance ready")))

    def show_files(self, sub, title, exts):
        if self.cur():
            FilesDialog(self, self.cur(), sub, title, exts).exec()

    def import_pack(self):
        f = (pick_files(self, "Choose a modpack", "Modrinth modpack (*.mrpack)", False) or [""])[0]
        if f:
            self.run(lambda e: core.import_mrpack(f, e), lambda _: (self.refresh(), self.msg.setText("Modpack imported")))

    def import_files(self):
        files = pick_files(self, "Choose files to import",
                           "Supported (*.mrpack *.zip *.jar *.litemod);;Modpacks (*.mrpack *.zip);;Mods (*.jar *.litemod);;All files (*)")
        if files:
            self.smart_import(files)

    def smart_import(self, paths):
        """Detects modpacks (.mrpack / CurseForge .zip), mods, resource packs and shaders and puts them in the right place."""
        inst = self.cur() or self.target.currentText()
        subs = {"mod": "mods", "resourcepack": "resourcepacks", "shader": "shaderpacks"}
        for f in paths:
            kind = core.classify(f)
            if kind == "modpack":
                self.run(lambda e, f=f: core.import_mrpack(f, e),
                         lambda _: (self.refresh(), self.msg.setText("Modpack imported")), lambda e: self.refresh())
            elif kind in subs:
                if not inst:
                    QMessageBox.information(self, "No instance", "Create or select an instance first, then import again.")
                    return
                core.add_file(inst, subs[kind], f)
                self.msg.setText(f"Added {Path(f).name} to {inst} ({subs[kind]})")
            else:
                QMessageBox.warning(self, "Unsupported file", f"Can't tell what {Path(f).name} is.\nSupported: modpacks (.mrpack, "
                                    "CurseForge .zip), mods (.jar), and resource pack / shader .zip files.")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.smart_import([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def open_folder(self):
        if self.cur():
            show_in_files(core.INST / self.cur())

    def del_inst(self):
        n = self.cur()
        if n and QMessageBox.question(self, "Delete", f"Delete {n} and all its files?") == QMessageBox.StandardButton.Yes:
            core.delete_instance(n)
            self.refresh()

    # ----- browse -----
    def browse_page(self):
        w, v = QWidget(), QVBoxLayout()
        w.setLayout(v)
        self.page, self.total = 0, 0
        v.addWidget(self.title("Browse Modrinth"))
        row = QHBoxLayout()
        self.q, self.kind, self.sort, self.target = QLineEdit(), QComboBox(), QComboBox(), QComboBox()
        self.q.setPlaceholderText("Search Modrinth...")
        self.q.returnPressed.connect(self.new_search)
        self.kind.addItems(KINDS)
        self.sort.addItems(SORTS)
        for c in (self.kind, self.sort, self.target):
            c.activated.connect(lambda _: self.new_search())
        row.addWidget(self.q, 1)
        row.addWidget(self.kind)
        row.addWidget(self.sort)
        row.addWidget(self.btn("Search", self.new_search, True))
        v.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Install into instance:"))
        row2.addWidget(self.target, 1)
        v.addLayout(row2)
        self.host, self.hl = QWidget(), QVBoxLayout()
        self.hl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.host.setLayout(self.hl)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(self.host)
        self.sc = sc
        v.addWidget(sc, 1)
        self.pager = QHBoxLayout()
        self.pager.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addLayout(self.pager)
        return w

    def new_search(self, quiet=False):
        self.page = 0
        self.load_page(quiet is True)

    def load_page(self, quiet=False):
        inst = self.target.currentText()
        m = core.get_instance(inst) if inst else {}
        kind, sort, q = KINDS[self.kind.currentText()], SORTS[self.sort.currentText()], self.q.text()
        off = self.page * PAGE
        self.msg.setText("Searching...")
        self.run(lambda e: core.search(q, kind, m.get("mc"), m.get("loader"), sort, off, PAGE), self.show_hits, quiet=quiet)

    def goto(self, page):
        self.page = page
        self.load_page()

    def build_pager(self):
        while self.pager.count():
            it = self.pager.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        pages = min(500, max(1, -(-self.total // PAGE)))
        if pages <= 1:
            return
        cur = self.page

        def add(text, page, enabled=True, current=False):
            b = QPushButton(text)
            b.setObjectName("pg")
            b.setEnabled(enabled)
            b.setProperty("cur", current)
            b.clicked.connect(lambda: self.goto(page))
            self.pager.addWidget(b)
        add("◀ Previous", cur - 1, cur > 0)
        last = None
        for n in sorted({0, pages - 1} | set(range(max(0, cur - 2), min(pages, cur + 3)))):
            if last is not None and n - last > 1:
                self.pager.addWidget(QLabel("…"))
            add(str(n + 1), n, True, n == cur)
            last = n
        add("Next ▶", cur + 1, cur < pages - 1)
        self.pager.addWidget(QLabel(f"   Page {cur + 1} of {pages}  ·  {self.total:,} results"))

    def show_hits(self, res):
        hits, self.total = res
        if self.icons:
            self.icons.stop = True
        while self.hl.count():
            self.hl.takeAt(0).widget().deleteLater()
        self.cards = []
        for h in hits:
            c = Card(h, self.install)
            self.hl.addWidget(c)
            self.cards.append(c)
        self.icons = Icons([h.get("icon_url") for h in hits])
        self.icons.got.connect(lambda i, d: self.cards[i].set_icon(d) if i < len(self.cards) else None)
        self.icons.start()
        self.msg.setText(f"{self.total:,} results")
        self.build_pager()
        self.sc.verticalScrollBar().setValue(0)

    def install(self, hit, btn, pick=False):
        if not pick:
            return self.install_now(hit, btn, None)
        modpack = KINDS[self.kind.currentText()] == "modpack"
        inst = self.target.currentText()
        if not modpack and not inst:
            return QMessageBox.information(self, "No instance", "Create an instance first (Library → New instance).")
        m = core.get_instance(inst) if (inst and not modpack) else {}
        btn.setEnabled(False)
        btn.setText("Loading versions…")
        reset = lambda *_: (btn.setEnabled(True), btn.setText("Install"))

        def chosen(vs):
            if not vs:
                reset()
                return QMessageBox.information(self, "No versions", "No compatible versions were found for this instance.")
            d = VersionDialog(self, hit["title"], vs)
            if d.exec() and d.chosen():
                self.install_now(hit, btn, d.chosen())
            else:
                reset()
        kind = KINDS[self.kind.currentText()]
        self.run(lambda e: core.list_versions(hit["project_id"], m.get("mc"), m.get("loader") if kind == "mod" else None,
                                              relax=kind != "mod"), chosen, reset)

    def install_now(self, hit, btn, version):
        modpack = KINDS[self.kind.currentText()] == "modpack"
        inst = self.target.currentText()
        if not modpack and not inst:
            return QMessageBox.information(self, "No instance", "Create an instance first (Library → New instance).")
        btn.setEnabled(False)
        btn.setText("Installing…")
        kind = KINDS[self.kind.currentText()]
        if modpack:
            fn = lambda e: core.install_modpack(hit["project_id"], e, version, hit.get("icon_url"))
        elif kind == "mod":
            fn = lambda e: core.install_mod(hit["project_id"], inst, e, version=version)
        else:
            fn = lambda e: core.install_pack(hit["project_id"], inst, kind, e, version)
        self.run(fn, lambda _: (btn.setText("Installed ✓"), self.refresh(), self.msg.setText(f"Installed {hit['title']}")),
                 lambda e: (btn.setEnabled(True), btn.setText("Install")))

    # ----- skins -----
    def skins_page(self):
        w, v = QWidget(), QVBoxLayout()
        w.setLayout(v)
        v.addWidget(self.title("Skins"))
        top = QHBoxLayout()
        top.setSpacing(28)
        self.skin_view = QLabel()
        self.skin_view.setFixedSize(156, 284)
        self.skin_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.skin_view.setStyleSheet("background:rgba(28,31,37,0.88);border-radius:16px")
        top.addWidget(self.skin_view)
        side, box = QVBoxLayout(), QWidget()
        self.skin_note = QLabel("Sign in with Microsoft (Account page) to change your skin.")
        self.skin_note.setWordWrap(True)
        self.variant = QComboBox()
        self.variant.addItems(["Classic (Steve)", "Slim (Alex)"])
        side.addWidget(self.skin_note)
        side.addWidget(QLabel("Arm style"))
        side.addWidget(self.variant)
        side.addWidget(self.btn("Choose skin file…", self.pick_skin, True))
        side.addWidget(self.btn("Copy a player's skin…", self.copy_skin))
        side.addWidget(self.btn("Refresh", self.load_skin))
        side.addStretch()
        box.setLayout(side)
        box.setMaximumWidth(360)
        top.addWidget(box)
        top.addStretch()
        v.addLayout(top)
        v.addStretch()
        return w

    def have_ms(self):
        return bool(self.cfg.get("account"))

    def need_ms(self):
        if not self.have_ms():
            QMessageBox.information(self, "Microsoft account needed", "Sign in with Microsoft to change your skin.")
        return self.have_ms()

    def load_skin(self):
        if self.have_ms():
            self.run(lambda e: core.get_skin(self.cfg), self.show_skin, lambda e: None)

    def show_skin(self, data):
        pm = QPixmap()
        if data and pm.loadFromData(data):
            self.skin_view.setPixmap(skin_body(pm, 8))
            self.skin_note.setText("Your current skin")
            k = max(1, pm.width() // 64)
            fast, ign = Qt.TransformationMode.FastTransformation, Qt.AspectRatioMode.IgnoreAspectRatio
            head = pm.copy(8 * k, 8 * k, 8 * k, 8 * k).scaled(72, 72, ign, fast)
            p = QPainter(head)
            p.drawPixmap(0, 0, pm.copy(40 * k, 8 * k, 8 * k, 8 * k).scaled(72, 72, ign, fast))
            p.end()
            self.acc_head.setPixmap(head)

    def pick_skin(self):
        if not self.need_ms():
            return
        f = (pick_files(self, "Choose a skin", "Skin (*.png)", False) or [""])[0]
        if f:
            png, var = Path(f).read_bytes(), ("slim" if self.variant.currentIndex() else "classic")

            def job(e):
                core.set_skin(self.cfg, png, var)
                return core.get_skin(self.cfg)
            self.run(job, lambda d: (self.show_skin(d), self.msg.setText("Skin updated")))

    def copy_skin(self):
        if not self.need_ms():
            return
        name, ok = QInputDialog.getText(self, "Copy skin", "Player name:")
        if ok and name.strip():
            def job(e):
                png, var = core.player_skin(name.strip())
                core.set_skin(self.cfg, png, var)
                return core.get_skin(self.cfg)
            self.run(job, lambda d: (self.show_skin(d), self.msg.setText("Skin updated")))

    # ----- account -----
    def account_page(self):
        w, v = QWidget(), QVBoxLayout()
        w.setLayout(v)
        c = self.cfg
        v.addWidget(self.title("Account"))
        card = QFrame()
        card.setObjectName("card")
        ch = QHBoxLayout(card)
        ch.setContentsMargins(18, 16, 18, 16)
        ch.setSpacing(16)
        self.acc_head = QLabel()
        self.acc_head.setFixedSize(72, 72)
        info = QVBoxLayout()
        self.acc_name, self.acc_state = QLabel(), QLabel()
        info.addWidget(self.acc_name)
        info.addWidget(self.acc_state)
        ch.addWidget(self.acc_head)
        ch.addLayout(info, 1)
        self.b_in = self.btn("Sign in with Microsoft", self.ms, True)
        self.b_change = self.btn("Change account", self.change_account)
        self.b_out = self.btn("Log out", self.logout)
        for b in (self.b_in, self.b_change, self.b_out):
            ch.addWidget(b)
        v.addWidget(card)
        self.f_dc, self.f_java = QLineEdit(c["discord_app_id"]), QLineEdit(c["java_path"])
        self.f_java.setPlaceholderText("empty = use Mojang's bundled Java")
        self.f_bg, self.f_int, self.f_dim = QComboBox(), QSpinBox(), QSpinBox()
        self.f_int.setRange(5, 300)
        self.f_int.setValue(c["bg_interval"])
        self.f_dim.setRange(0, 90)
        self.f_dim.setValue(c["bg_dim"])
        self.fill_bg()
        self.f_bg.activated.connect(lambda _: self.save_bg())
        self.f_int.valueChanged.connect(lambda _: self.save_bg())
        self.f_dim.valueChanged.connect(lambda _: self.save_bg())
        form = QFormLayout()
        form.addRow(QLabel("<h3>Settings</h3>"))
        form.addRow("Discord app ID", self.f_dc)
        form.addRow("Java path", self.f_java)
        form.addRow(self.btn("Save settings", self.save))
        form.addRow(QLabel("<h3>Appearance</h3>"))
        form.addRow("Background", self.f_bg)
        form.addRow("Switch every (seconds)", self.f_int)
        form.addRow("Darkness (%)", self.f_dim)
        form.addRow(self.btn("Add my own background…", self.add_bg))
        form.addRow(QLabel("<h3>About</h3>"))
        form.addRow(f"Version {core.APP_VERSION}", self.btn("Check for updates", lambda: self.check_updates(True)))
        v.addLayout(form)
        v.addStretch()
        return w

    def fill_bg(self):
        self.f_bg.clear()
        self.f_bg.addItem("Auto (slideshow)", "auto")
        for p in core.background_files():
            self.f_bg.addItem(p.stem.replace("_", " ").title(), p.name)
        self.f_bg.setCurrentIndex(max(0, self.f_bg.findData(self.cfg["bg"])))

    def save_bg(self):
        self.cfg.update(bg=self.f_bg.currentData(), bg_interval=self.f_int.value(), bg_dim=self.f_dim.value())
        core.save_cfg(self.cfg)
        self.root.apply()

    def add_bg(self):
        files = pick_files(self, "Choose background images", "Images (*.png *.jpg *.jpeg *.webp)")
        for f in files:
            core.add_background(f)
        if files:
            self.root.reload()
            self.fill_bg()
            self.msg.setText(f"Added {len(files)} background(s)")

    def show_acct(self):
        a = self.cfg.get("account")
        if a:
            name = html.escape(a["name"])
            self.acc_head.setPixmap(make_icon(a["name"], None, 72))  # replaced by the real skin face once it loads
            self.acc_name.setText(f"<span style='font-size:20px;font-weight:800'>{name}</span>")
            self.acc_state.setText("<span style='color:#3dea84'>● You are signed in</span>  <span style='color:#9aa1ab'>· Microsoft account</span>")
            self.chip.setText(f"<b style='color:#e6e6e6'>{name}</b><br><span style='color:#3dea84'>● Signed in</span>")
        else:
            self.acc_head.clear()
            self.acc_name.setText("<span style='font-size:20px;font-weight:800'>Not signed in</span>")
            self.acc_state.setText("<span style='color:#9aa1ab'>Sign in with Microsoft to play</span>")
            self.chip.setText("<b style='color:#e6e6e6'>Not signed in</b><br><span style='color:#9aa1ab'>Open Account to sign in</span>")
        self.b_in.setVisible(not a)
        self.b_change.setVisible(bool(a))
        self.b_out.setVisible(bool(a))

    def save(self):
        self.cfg.update(discord_app_id=self.f_dc.text().strip(), java_path=self.f_java.text().strip())
        core.save_cfg(self.cfg)
        self.msg.setText("Settings saved")

    def welcome(self):
        d = Welcome(self)
        d.exec()
        if d.choice == "microsoft":
            self.ms()

    def ms(self):
        if not self.cfg.get("ms_client_id"):
            return QMessageBox.information(self, "Sign-in unavailable", "Microsoft sign-in isn't available in this build.")
        self.msg.setText("Contacting Microsoft…")
        self.run(lambda e: core.device_start(self.cfg), self.show_device)

    def change_account(self):
        self.ms()  # the current account stays until the new sign-in succeeds

    def logout(self):
        if QMessageBox.question(self, "Log out", "Log out of this Microsoft account?") != QMessageBox.StandardButton.Yes:
            return
        self.cfg["account"] = None
        core.save_cfg(self.cfg)
        self.skin_view.clear()
        self.skin_note.setText("Sign in with Microsoft (Account page) to change your skin.")
        self.show_acct()
        self.msg.setText("Logged out")

    def show_device(self, dc):
        flag = {"stop": False}
        d = QDialog(self)
        d.setWindowTitle("Sign in to Microsoft")
        d.setMinimumWidth(460)
        v = QVBoxLayout(d)
        v.setContentsMargins(26, 22, 26, 22)
        v.setSpacing(12)
        v.addWidget(QLabel("<h2>Sign in to Microsoft</h2>Your browser is opening. Enter this code there and log in:"))
        code = QLabel(f"<span style='font-size:36px;font-weight:bold;letter-spacing:5px;color:#1bd96a'>{dc['user_code']}</span>")
        code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(code)
        row = QHBoxLayout()
        row.addWidget(self.btn("Open Microsoft page", lambda: webbrowser.open(dc["verification_uri"]), True))
        row.addWidget(self.btn("Copy code", lambda: QApplication.clipboard().setText(dc["user_code"])))
        v.addLayout(row)
        wait = QLabel("Waiting for you to finish… this window closes by itself." + (
            "<br><small>To use a different account, choose “Use another account” on the Microsoft page.</small>" if self.cfg.get("account") else ""))
        wait.setWordWrap(True)
        v.addWidget(wait)
        d.rejected.connect(lambda: flag.update(stop=True))
        self.login_dlg = d
        d.show()
        webbrowser.open(dc["verification_uri"])

        def done(acct):
            if acct:
                d.accept()
                self.got_account(acct)
        self.run(lambda e: core.device_poll(self.cfg, dc, flag), done, lambda e: d.reject())

    def got_account(self, acct):
        self.cfg["account"] = acct
        core.save_cfg(self.cfg)
        self.show_acct()
        self.msg.setText(f"You are signed in as {acct['name']}")
        self.load_skin()
        QMessageBox.information(self, "Signed in", f"✔ You are signed in as {acct['name']}.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = app.font()
    font.setFamilies(["Noto Sans", "Segoe UI", "Ubuntu", "DejaVu Sans", "Liberation Sans", "Arial"])
    font.setItalic(False)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)
    app.setStyleSheet(QSS)
    w = Win()
    w.show()
    sys.exit(app.exec())
