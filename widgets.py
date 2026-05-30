from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QColor, QPainter, QPen

from constants import GRID_SIZE, BORDER_MARGIN, MIN_WIDGET_WIDTH, MIN_WIDGET_HEIGHT


class SubLabelButton(QPushButton):
    """두 줄 레이블을 표시할 수 있는 버튼 클래스"""
    def __init__(self, main_label="", sub_label="", parent=None):
        super().__init__("", parent)
        self.main_label = main_label
        self.sub_label = sub_label
        self.update_text()

    def update_text(self):
        if self.sub_label:
            self.setText(f"{self.main_label}\n{self.sub_label}")
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
