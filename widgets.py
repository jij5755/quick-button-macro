import os

from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QPoint, QRect, QSize
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QPixmap, QTransform

from constants import GRID_SIZE, BORDER_MARGIN, MIN_WIDGET_WIDTH, MIN_WIDGET_HEIGHT, IMAGES_DIR


def _new_info_label(parent, over_picture=False):
    """JYOR '구경 · 가격' 한 줄 레이블(클릭은 아래 위젯으로 통과). 사진 위에 얹을 땐 반투명 흰 바탕."""
    label = QLabel("", parent)
    label.setAttribute(Qt.WA_TransparentForMouseEvents)
    label.setAlignment(Qt.AlignCenter)
    bg = "rgba(255, 255, 255, 190)" if over_picture else "transparent"
    label.setStyleSheet(f"color: #0d47a1; background: {bg};")
    f = QFont()
    f.setPointSize(15)
    f.setBold(True)
    label.setFont(f)
    label.hide()
    return label


class SubLabelButton(QPushButton):
    """두 줄 레이블을 표시할 수 있는 버튼 클래스"""
    def __init__(self, main_label="", sub_label="", parent=None):
        super().__init__("", parent)
        self.main_label = main_label
        self.sub_label = sub_label
        self.update_text()

    def update_text(self):
        if self.sub_label:
            # JYOR 정보 줄이 보이면 빈 줄 하나를 더해 두 줄 레이블을 위로 올린다(정보 줄과 겹침 방지, 2026-10-05)
            pad = "\n" if getattr(self, "_info_pad", False) else ""
            self.setText(f"{self.main_label}\n{self.sub_label}{pad}")
            self.setStyleSheet("""
                QPushButton {
                    text-align: center;
                    padding: 4px;
                }
            """)
        else:
            self.setText(self.main_label)

    def set_main_label(self, text):
        self.main_label = text
        self.update_text()

    def set_sub_label(self, text):
        self.sub_label = text
        self.update_text()


class SelectableButton(SubLabelButton):
    """선택 가능한 버튼 클래스"""
    def __init__(self, text, parent=None, x=0, y=0, width=150, height=40, data=None):
        self.data = data or {}
        sub_label = self.data.get("label2", "")
        super().__init__(text, sub_label, parent)

        self.parent = parent
        self.setGeometry(x, y, width, height)
        self.press_pos = None
        self.original_pos = QPoint(x, y)
        self.drag_started = False
        self.is_selected = False
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        self.custom_style = self.data.get("custom_style", False)
        self.custom_size  = self.data.get("custom_size", False)
        self.custom_font  = self.data.get("custom_font", False)
        self.custom_color = self.data.get("custom_color", False)

        self.grid_size = GRID_SIZE

        # JYOR 연동(2026-10-05): 품목번호(erp_code)가 있으면 버튼 아래쪽에 '구경 · 가격' 한 줄(클릭은 버튼으로 통과)
        self.erp_code = str(self.data.get("erp_code", "") or "").strip()
        self.info_label = _new_info_label(self)
        self._place_info()

    def set_info(self, text):
        """JYOR 정보 줄(빈 문자열이면 숨김)."""
        self.info_label.setText(text or "")
        self.info_label.setVisible(bool(text))
        self._place_info()
        if getattr(self, "_info_pad", False) != bool(text):
            self._info_pad = bool(text)
            self.update_text()

    def _place_info(self):
        h = self.info_label.sizeHint().height()
        self.info_label.setGeometry(2, max(0, self.height() - h - 3), max(0, self.width() - 4), h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "info_label"):
            self._place_info()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.press_pos = event.pos()
            if self.parent and self.parent.edit_mode:
                if not (event.modifiers() & Qt.ControlModifier):
                    self.parent.clear_all_selections()
                self.toggle_selected()
                self.drag_started = True
            else:
                if self.parent:
                    super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.press_pos = None
        self.drag_started = False
        if self.parent and not self.parent.edit_mode and event.button() == Qt.LeftButton:
            button_idx = self.parent.buttons.index(self) if self in self.parent.buttons else -1
            if 0 <= button_idx < len(self.parent.button_data):
                text = self.parent.button_data[button_idx]["text"]
                self.parent.execute_macro(text)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.parent and self.parent.edit_mode and self.drag_started and (event.buttons() & Qt.LeftButton):
            pos_delta = event.globalPos() - self.mapToGlobal(self.press_pos)
            if self.is_selected:
                for widget in self.parent.get_all_selected_widgets():
                    new_pos = self.parent.buttons_container.mapFromGlobal(
                        widget.mapToGlobal(QPoint(0, 0)) + pos_delta
                    )
                    widget.move(self.snap_to_grid(new_pos))
            self.parent.update_widget_data()

    def snap_to_grid(self, pos):
        x = round(pos.x() / self.grid_size) * self.grid_size
        y = round(pos.y() / self.grid_size) * self.grid_size
        return QPoint(x, y)

    def toggle_selected(self):
        self.is_selected = not self.is_selected
        self.update_selection_style()

    def set_selected(self, selected):
        self.is_selected = selected
        self.update_selection_style()

    def update_selection_style(self):
        base_style = """
            QPushButton {
                text-align: center;
                padding: 4px;
            }
        """
        if self.is_selected:
            self.setStyleSheet(f"{base_style} QPushButton {{ border: 2px solid #3399FF; background-color: rgba(230, 230, 255, 200); }}")
        else:
            self.setStyleSheet(base_style)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() == Qt.Key_Delete and self.parent and self.parent.edit_mode and self.is_selected:
            self.parent.delete_selected_items()


class SelectableTextBox(QLabel):
    """선택 가능한 텍스트 박스 클래스"""
    def __init__(self, text, parent=None, x=0, y=0, width=200, height=100, data=None):
        super().__init__(text, parent)
        from PyQt5.QtWidgets import QFrame
        self.parent = parent
        self.setGeometry(x, y, width, height)
        self.data = data or {}
        self.press_pos = None
        self.original_pos = QPoint(x, y)
        self.drag_started = False
        self.is_selected = False
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        self.custom_size  = self.data.get("custom_size", False)
        self.custom_font  = self.data.get("custom_font", False)
        self.custom_color = self.data.get("custom_color", False)

        self.grid_size = GRID_SIZE
        self.resizing = False
        self.resize_mode = None
        self.resize_start_pos = None
        self.resize_start_geometry = None
        self.border_margin = BORDER_MARGIN

        self.setWordWrap(True)
        self.setFrameShape(QFrame.Box)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.update_selection_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.press_pos = event.pos()
            if self.parent and self.parent.edit_mode:
                resize_edge = self.get_resize_edge(event.pos())
                if resize_edge:
                    self.resizing = True
                    self.resize_mode = resize_edge
                    self.resize_start_pos = event.globalPos()
                    self.resize_start_geometry = self.geometry()
                    return
                if not (event.modifiers() & Qt.ControlModifier):
                    self.parent.clear_all_selections()
                self.toggle_selected()
                self.drag_started = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            self.resize_mode = None
            if self.parent:
                self.parent.update_widget_data()
        self.press_pos = None
        self.drag_started = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.parent and self.parent.edit_mode:
            if self.resizing and (event.buttons() & Qt.LeftButton):
                self.do_resize(event.globalPos())
                return
            resize_edge = self.get_resize_edge(event.pos())
            if resize_edge:
                if resize_edge in ["top", "bottom"]:
                    self.setCursor(Qt.SizeVerCursor)
                elif resize_edge in ["left", "right"]:
                    self.setCursor(Qt.SizeHorCursor)
                elif resize_edge in ["top-left", "bottom-right"]:
                    self.setCursor(Qt.SizeFDiagCursor)
                elif resize_edge in ["top-right", "bottom-left"]:
                    self.setCursor(Qt.SizeBDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

            if self.drag_started and (event.buttons() & Qt.LeftButton):
                pos_delta = event.globalPos() - self.mapToGlobal(self.press_pos)
                if self.is_selected:
                    for widget in self.parent.get_all_selected_widgets():
                        new_pos = self.parent.buttons_container.mapFromGlobal(
                            widget.mapToGlobal(QPoint(0, 0)) + pos_delta
                        )
                        widget.move(self.snap_to_grid(new_pos))
                self.parent.update_widget_data()
        super().mouseMoveEvent(event)

    def get_resize_edge(self, pos):
        x, y = pos.x(), pos.y()
        width, height = self.width(), self.height()
        margin = self.border_margin
        if x <= margin and y <= margin:
            return "top-left"
        if x >= width - margin and y <= margin:
            return "top-right"
        if x <= margin and y >= height - margin:
            return "bottom-left"
        if x >= width - margin and y >= height - margin:
            return "bottom-right"
        if x <= margin:
            return "left"
        if x >= width - margin:
            return "right"
        if y <= margin:
            return "top"
        if y >= height - margin:
            return "bottom"
        return None

    def do_resize(self, global_pos):
        if not self.resize_start_geometry:
            return
        delta = global_pos - self.resize_start_pos
        new_geometry = QRect(self.resize_start_geometry)
        if "left" in self.resize_mode:
            new_geometry.setLeft(self.resize_start_geometry.left() + delta.x())
        if "right" in self.resize_mode:
            new_geometry.setRight(self.resize_start_geometry.right() + delta.x())
        if "top" in self.resize_mode:
            new_geometry.setTop(self.resize_start_geometry.top() + delta.y())
        if "bottom" in self.resize_mode:
            new_geometry.setBottom(self.resize_start_geometry.bottom() + delta.y())
        if new_geometry.width() < MIN_WIDGET_WIDTH:
            if "left" in self.resize_mode:
                new_geometry.setLeft(new_geometry.right() - MIN_WIDGET_WIDTH)
            else:
                new_geometry.setRight(new_geometry.left() + MIN_WIDGET_WIDTH)
        if new_geometry.height() < MIN_WIDGET_HEIGHT:
            if "top" in self.resize_mode:
                new_geometry.setTop(new_geometry.bottom() - MIN_WIDGET_HEIGHT)
            else:
                new_geometry.setBottom(new_geometry.top() + MIN_WIDGET_HEIGHT)
        x = round(new_geometry.x() / self.grid_size) * self.grid_size
        y = round(new_geometry.y() / self.grid_size) * self.grid_size
        width = max(round(new_geometry.width() / self.grid_size) * self.grid_size, MIN_WIDGET_WIDTH)
        height = max(round(new_geometry.height() / self.grid_size) * self.grid_size, MIN_WIDGET_HEIGHT)
        self.custom_size = True
        self.setGeometry(x, y, width, height)
        if self.parent and hasattr(self.parent, 'buttons_container'):
            self.parent.buttons_container.updateMinimumSize()

    def snap_to_grid(self, pos):
        x = round(pos.x() / self.grid_size) * self.grid_size
        y = round(pos.y() / self.grid_size) * self.grid_size
        return QPoint(x, y)

    def toggle_selected(self):
        self.is_selected = not self.is_selected
        self.update_selection_style()

    def set_selected(self, selected):
        self.is_selected = selected
        self.update_selection_style()

    def update_selection_style(self):
        color = self.data.get('color', '#000000')
        bg_color = self.data.get('bg_color', 'transparent')
        border_style = "2px solid #3399FF" if self.is_selected else "1px solid #A0A0A0"
        self.setStyleSheet(f"color: {color}; background-color: {bg_color}; padding: 8px; border: {border_style};")

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() == Qt.Key_Delete and self.parent and self.parent.edit_mode and self.is_selected:
            self.parent.delete_selected_items()


class SelectableImageButton(SelectableTextBox):
    """이미지 버튼(2026-10-12): 부속 사진을 버튼처럼 놓고, 실행 모드에서 터치하면 매크로를 돌린다.

    편집 모드의 이동·크기 조절·선택은 텍스트 박스와 같다. 글자는 넣지 않는다 — 이름표가 필요하면
    기존 버튼이나 텍스트 박스를 옆에 놓아 조합한다(사용자 요청). 사진은 위젯 크기에 맞춰 비율을 지키며 축소.
    """
    def __init__(self, image_file, parent=None, x=0, y=0, width=150, height=150, data=None):
        super().__init__("", parent, x, y, width, height, data)
        self.image_file = image_file
        self.erp_code = str(self.data.get("erp_code", "") or "").strip()
        # 회전(0/90/180/270)·좌우 반전 — 파일은 그대로 두고 그릴 때만 돌린다(사진 한 장을 여러 방향으로 재사용)
        self.rotation = int(self.data.get("rotation", 0) or 0) % 360
        self.flip = bool(self.data.get("flip", False))
        self._pixmap = QPixmap()
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setAlignment(Qt.AlignCenter)
        self.info_label = _new_info_label(self, over_picture=True)
        self.load_image(image_file)
        self._place_info()

    @staticmethod
    def resolve_path(image_file):
        """프리셋에는 파일명만 있다 → 실행 폴더의 images/ 기준. 절대경로면 그대로."""
        if os.path.isabs(image_file):
            return image_file
        return os.path.join(IMAGES_DIR, image_file)

    def load_image(self, image_file):
        self.image_file = image_file
        path = self.resolve_path(image_file)
        self._pixmap = QPixmap(path) if os.path.exists(path) else QPixmap()
        if self._pixmap.isNull():
            self.setText(f"(사진 없음)\n{image_file}")
        self._fit_pixmap()

    def _fit_pixmap(self):
        if self._pixmap.isNull():
            return
        pm = self._pixmap
        if self.flip or self.rotation:
            t = QTransform()
            if self.flip:
                t.scale(-1, 1)
            if self.rotation:
                t.rotate(self.rotation)
            pm = pm.transformed(t, Qt.SmoothTransformation)
        inner = self.size() - QSize(6, 6)
        self.setPixmap(pm.scaled(inner, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_orientation(self, rotation=None, flip=None):
        """회전(도, 90 단위로 정규화)·반전을 바꾸고 다시 그린다."""
        if rotation is not None:
            self.rotation = int(rotation) % 360
        if flip is not None:
            self.flip = bool(flip)
        self.data["rotation"] = self.rotation
        self.data["flip"] = self.flip
        self._fit_pixmap()

    def set_info(self, text):
        """JYOR 정보 줄(빈 문자열이면 숨김). 사진 아래쪽에 겹쳐 표시."""
        self.info_label.setText(text or "")
        self.info_label.setVisible(bool(text))
        self._place_info()

    def _place_info(self):
        if not hasattr(self, "info_label"):
            return
        h = self.info_label.sizeHint().height()
        self.info_label.setGeometry(2, max(0, self.height() - h - 3), max(0, self.width() - 4), h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_pixmap()
        self._place_info()

    # 글자 선택이 꺼진 QLabel은 마우스 이벤트를 받아들이지 않아(ignore) 부모 컨테이너로 새고,
    # 컨테이너가 영역 선택을 시작하며 방금 고른 사진을 해제해 버린다(2026-10-12 드래그 안 되던 원인).
    # 사진 버튼은 누름·이동·뗌을 모두 자기 것으로 받아들인다.
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        event.accept()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        event.accept()

    def mouseReleaseEvent(self, event):
        was_resizing = self.resizing
        super().mouseReleaseEvent(event)
        event.accept()
        # 실행 모드에서 사진 안에서 손을 떼면 기존 버튼과 똑같이 매크로 실행
        if (self.parent and not self.parent.edit_mode and not was_resizing
                and event.button() == Qt.LeftButton and self.rect().contains(event.pos())):
            idx = self.parent.images.index(self) if self in self.parent.images else -1
            if 0 <= idx < len(self.parent.image_data):
                self.parent.execute_macro(self.parent.image_data[idx]["text"])

    def update_selection_style(self):
        # 실행 모드: 테두리 없이 사진만. 편집 모드: 옅은 점선(자리 확인용). 선택: 파란 실선.
        if self.is_selected:
            border = "2px solid #3399FF"
        elif self.parent and getattr(self.parent, "edit_mode", False):
            border = "1px dashed #A0A0A0"
        else:
            border = "none"
        self.setStyleSheet(f"background-color: transparent; padding: 2px; border: {border};")


class SetListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QListWidget.NoDragDrop)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.scrolling = False
        self.last_pos = None

    def set_edit_mode(self, edit_mode):
        if edit_mode:
            self.setDragDropMode(QListWidget.InternalMove)
            self.setDefaultDropAction(Qt.MoveAction)
        else:
            self.setDragDropMode(QListWidget.NoDragDrop)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton and not self.parent.edit_mode:
            self.scrolling = True
            self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.parent.edit_mode:
            super().mouseMoveEvent(event)
        elif self.scrolling and (event.buttons() & Qt.LeftButton):
            delta = event.pos().y() - self.last_pos.y()
            vsb = self.verticalScrollBar()
            vsb.setValue(vsb.value() - delta)
            self.last_pos = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.scrolling = False
            self.last_pos = None

    def dropEvent(self, event):
        if not self.parent.edit_mode:
            event.ignore()
            return
        self.parent.set_list_drop_event(event)


class DraggableSetItem(QListWidgetItem):
    """드래그 가능한 세트 아이템"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setText(text)
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled)


class ButtonContainerWidget(QWidget):
    """버튼을 담을 컨테이너 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.show_grid = False
        self.grid_size = GRID_SIZE
        self.selecting = False
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.updateMinimumSize()

    def updateMinimumSize(self):
        if not self.parent:
            return
        min_width = 500
        min_height = 400
        for button in getattr(self.parent, 'buttons', []):
            min_width = max(min_width, button.x() + button.width() + 20)
            min_height = max(min_height, button.y() + button.height() + 20)
        for textbox in getattr(self.parent, 'textboxes', []):
            min_width = max(min_width, textbox.x() + textbox.width() + 20)
            min_height = max(min_height, textbox.y() + textbox.height() + 20)
        for image in getattr(self.parent, 'images', []):
            min_width = max(min_width, image.x() + image.width() + 20)
            min_height = max(min_height, image.y() + image.height() + 20)
        self.setMinimumSize(min_width, min_height)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self.parent and self.parent.edit_mode and self.show_grid:
            painter.setPen(QPen(QColor(200, 200, 200, 100), 1))
            for x in range(0, self.width(), self.grid_size):
                painter.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), self.grid_size):
                painter.drawLine(0, y, self.width(), y)
        if self.selecting:
            selection_rect = QRect(self.selection_start, self.selection_end).normalized()
            painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.DashLine))
            painter.setBrush(QColor(0, 120, 215, 50))
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        if self.parent and self.parent.edit_mode and event.button() == Qt.LeftButton:
            self.selecting = True
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            if not (event.modifiers() & Qt.ControlModifier):
                self.parent.clear_all_selections()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.selection_end = event.pos()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.selecting:
            self.selection_end = event.pos()
            if self.parent:
                selection_rect = QRect(self.selection_start, self.selection_end).normalized()
                self.parent.select_widgets_in_rect(selection_rect)
            self.selecting = False
            self.update()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        if self.parent:
            self.parent.show_context_menu(event.pos())
