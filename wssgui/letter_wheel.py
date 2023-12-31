import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont  # type: ignore
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QImage, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

FONT_FILE = Path("c:") / "Windows" / "Fonts" / "arial.ttf"


class MyQGPixmapItem(QGraphicsPixmapItem):
    def __init__(self, img, i, n, alpha, center, radius):
        super().__init__(img)
        self.idx = i
        self.alpha = alpha
        self.half_width = self.boundingRect().width() / 2
        self.half_height = self.boundingRect().height() / 2
        self.center_x = center.x()
        self.center_y = center.y()
        self.radius = radius
        self.angle = 2 * math.pi * i / n
        self.hit = False
        self.path_item = False

    def __str__(self) -> str:
        return f" {self.alpha} @ ({self.x()}, {self.y()})"

    def calc_position(self, r=False, offset=False):
        if not r:
            r = self.radius
        x = self.center_x + r * math.cos(self.angle)
        if not offset:
            x -= self.half_width
        y = self.center_y + r * math.sin(self.angle)
        if not offset:
            y -= self.half_height
        if not offset:
            self.setPos(x, y)
        else:
            self.offset_xy = QPointF(x, y)


class LetterAreaView(QGraphicsView):
    mouseOverWidget = Signal(QWidget)
    mouseReleaseProc = Signal(set)
    clearHighlight = Signal(bool)

    def __init__(self, scene):
        super().__init__(scene)
        self.mouse_pressed = False
        self.selected_widgets_set = set()
        self.selected_widgets_list = list()
        self.has_highlighted = False
        self.paint_path = QPainterPath()

    def mousePressEvent(self, event):
        # Reset the wheel if a word has been highlighted
        if self.has_highlighted:
            self.has_highlighted = False
            self.clearHighlight.emit(True)
            self.mouse_pressed = False
            return

        # Collect letters for a word
        # Paint a path between them, and emit the letter
        self.mouse_pressed = True
        widget = self.itemAt(event.pos())
        if isinstance(widget, MyQGPixmapItem):
            # First letter in the word only
            if widget not in self.selected_widgets_set:
                # New word, so force a clear
                self.paint_path.clear()
                self.selected_widgets_set.clear()
                self.selected_widgets_set.add(widget)
                self.selected_widgets_list.clear()
                self.selected_widgets_list.append(widget)
                self.mouseOverWidget.emit(widget)

    def mouseMoveEvent(self, event):
        if self.mouse_pressed:
            widget = self.itemAt(event.pos())
            if isinstance(widget, MyQGPixmapItem):
                if widget not in self.selected_widgets_set:
                    self.selected_widgets_list.append(widget)
                    self.selected_widgets_set.add(widget)
                    self.mouseOverWidget.emit(widget)

            if len(self.selected_widgets_list) > 1:
                for i, item in enumerate(self.selected_widgets_list):
                    if i == 0:
                        self.paint_path.moveTo(item.offset_xy)
                    else:
                        self.paint_path.lineTo(item.offset_xy)
                item.path_item = QGraphicsPathItem(self.paint_path)
                item.path_item.setPen(QPen(Qt.green, 3))
                self.scene().addItem(item.path_item)

    def mouseReleaseEvent(self, event):
        for item in self.scene().items():
            if isinstance(item, QGraphicsPathItem):
                if item.pen().color() == Qt.green:
                    self.scene().removeItem(item)
        # Reset status variables
        word = "".join(
            [x.alpha for x in self.selected_widgets_list])
        self.mouseReleaseProc.emit(word)
        self.selected_widgets_set.clear()
        self.selected_widgets_list.clear()
        self.mouse_pressed = False
        self.paint_path.clear()

class LetterArea(QWidget):
    def __init__(self):
        super().__init__()

        self.scene = QGraphicsScene()
        self.view = LetterAreaView(self.scene)
        self.center = QPointF(50, 50)
        self.radius = 80
        # Highlight Paths
        self.last_path_highlighted = False

        # Free Draw Paths
        self.last_path_drawn = False
        self.current_path_drawn = False

        # Create reference letter set
        self.get_letters()

    def create_letter_img(self, char, fnt_file=FONT_FILE):
        fnt = ImageFont.truetype(str(fnt_file), size=24)
        l, t, r, b = fnt.getbbox(char)
        h = b - t
        w = r - l
        img_w, img_h = w + 10, h + 10
        img = Image.new("L", (img_w, img_h), color="white")
        d = ImageDraw.Draw(img)
        d.text((img_w / 2, img_h / 2), char, font=fnt, fill=0, anchor="mm")
        np_image = np.array(img)
        qimage = QImage(
            np_image.data,
            np_image.shape[1],
            np_image.shape[0],
            np_image.strides[0],
            QImage.Format_Grayscale8,
        )
        return QPixmap.fromImage(qimage)

    def get_letters(self):
        self.letters = {
            alpha: self.create_letter_img(alpha)
            for alpha in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        }

    def make_word(self, word):
        letters = [
            MyQGPixmapItem(
                self.letters[alpha], i, len(word), alpha, self.center, self.radius
            )
            for i, alpha in enumerate(word)
        ]

        for letter in letters:
            letter.calc_position()
            letter.calc_position(r=self.radius - 15, offset=True)
            self.scene.addItem(letter)

        path = QPainterPath()
        path.moveTo(letters[0].offset_xy)
        for letter in letters:
            path.lineTo(letter.offset_xy)
        path.closeSubpath()
        self.scene.addPath(path, QPen(Qt.red, 3))
        self.wheel = letters

    def word_path(self, word):
        # Clear any existing highlighted word
        if self.last_path_highlighted:
            self.deselect()

        # Create the new word
        tmp_letters = self.wheel.copy()
        selected = list()
        for w in word:
            for x in tmp_letters:
                if (x.alpha == w) and (not x.hit):
                    x.hit = True
                    selected.append(x)
                    break

        # Highlight the new word
        path = QPainterPath()
        path.moveTo(selected[0].offset_xy)
        for letter in selected[1:]:
            path.lineTo(letter.offset_xy)
        path_item = QGraphicsPathItem(path)
        path_item.setPen(QPen(Qt.blue, 3))
        self.scene.addItem(path_item)
        for x in self.wheel:
            x.hit = False

        # Store the path item for later removal
        self.last_path_highlighted = path_item
        self.view.has_highlighted = True

    def deselect(self):
        if self.last_path_highlighted:
            self.scene.removeItem(self.last_path_highlighted)
            self.last_path_highlighted = False

    def valid_word(self, widget):
        print(f"Current word: {widget.alpha}")
        print(" ".join([x.alpha for x in self.view.selected_widgets_list]))
