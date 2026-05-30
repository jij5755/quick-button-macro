from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QSpinBox,
    QScrollArea, QWidget, QFrame, QComboBox, QGroupBox,
    QFontDialog, QColorDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPalette

from constants import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE


class TextBoxSettingsDialog(QDialog):
    """텍스트 박스 설정 대화상자"""
    def __init__(self, text="", font=None, color=None, bg_color=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("텍스트 박스 설정")
        self.resize(400, 350)
        self.current_text = text
        self.current_font = font or QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)
        self.current_color = color or QColor("#000000")
        self.current_bg_color = bg_color or QColor("transparent")
        layout = QVBoxLayout()
        text_label = QLabel("텍스트 내용:")
        self.text_edit = QTextEdit(text)
        self.text_edit.setMinimumHeight(100)
        self.preview_label = QLabel("텍스트 박스 미리보기")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFont(self.current_font)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(
            f"color: {self.current_color.name()}; background-color: {self.current_bg_color.name()}; "
            f"padding: 10px; border: 1px solid #A0A0A0; border-radius: 5px;"
        )
        self.preview_label.setMinimumHeight(60)
        self.font_button = QPushButton("글꼴 설정")
        self.font_button.clicked.connect(self.select_font)
        color_layout = QHBoxLayout()
        self.text_color_button = QPushButton("텍스트 색상")
        self.text_color_button.clicked.connect(self.select_text_color)
        self.bg_color_button = QPushButton("배경 색상")
        self.bg_color_button.clicked.connect(self.select_bg_color)
        color_layout.addWidget(self.text_color_button)
        color_layout.addWidget(self.bg_color_button)
        text_color_layout = QHBoxLayout()
        self.text_color_combo = QComboBox()
        for label, value in [("직접 선택",""),("검정","#000000"),("빨강","#FF0000"),("녹색","#00FF00"),
                             ("파랑","#0000FF"),("노랑","#FFFF00"),("자주","#800080"),("청록","#008080"),("오렌지","#FFA500")]:
            self.text_color_combo.addItem(label, value)
        self.text_color_combo.currentIndexChanged.connect(self.preset_text_color_changed)
        text_color_layout.addWidget(QLabel("텍스트 색상:"))
        text_color_layout.addWidget(self.text_color_combo)
        bg_color_layout = QHBoxLayout()
        self.bg_color_combo = QComboBox()
        for label, value in [("직접 선택",""),("투명","transparent"),("하양","#FFFFFF"),("밝은 회색","#F0F0F0"),
                             ("노랑 계열","#FFFFD0"),("연한 파랑","#D0D0FF"),("연한 녹색","#D0FFD0"),("연한 분홍","#FFD0D0")]:
            self.bg_color_combo.addItem(label, value)
        self.bg_color_combo.currentIndexChanged.connect(self.preset_bg_color_changed)
        bg_color_layout.addWidget(QLabel("배경 색상:"))
        bg_color_layout.addWidget(self.bg_color_combo)
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addWidget(text_label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.font_button)
        layout.addLayout(color_layout)
        layout.addLayout(text_color_layout)
        layout.addLayout(bg_color_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        self.text_edit.textChanged.connect(self.update_preview)

    def update_preview(self):
        preview_text = self.text_edit.toPlainText()
        if len(preview_text) > 50:
            preview_text = preview_text[:50] + "..."
        self.preview_label.setText(preview_text)

    def select_font(self):
        font, ok = QFontDialog.getFont(self.current_font, self)
        if ok:
            self.current_font = font
            self.preview_label.setFont(self.current_font)

    def select_text_color(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            self.update_preview_style()
            self.text_color_combo.setCurrentIndex(0)

    def select_bg_color(self):
        color = QColorDialog.getColor(self.current_bg_color, self)
        if color.isValid():
            self.current_bg_color = color
            self.update_preview_style()
            self.bg_color_combo.setCurrentIndex(0)

    def preset_text_color_changed(self, index):
        if index > 0:
            self.current_color = QColor(self.text_color_combo.currentData())
            self.update_preview_style()

    def preset_bg_color_changed(self, index):
        if index > 0:
            self.current_bg_color = QColor(self.bg_color_combo.currentData())
            self.update_preview_style()

    def update_preview_style(self):
        self.preview_label.setStyleSheet(
            f"color: {self.current_color.name()}; background-color: {self.current_bg_color.name()}; "
            f"padding: 8px; border: 1px solid #A0A0A0; border-radius: 5px;"
        )

    def get_values(self):
        return self.text_edit.toPlainText(), self.current_font, self.current_color, self.current_bg_color


class SetFontSettingsDialog(QDialog):
    """세트 리스트 글꼴 설정 대화상자"""
    def __init__(self, current_font, current_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("세트 리스트 글꼴 설정")
        self.resize(400, 250)
        self.current_font = current_font
        self.current_color = current_color
        layout = QVBoxLayout()
        self.preview_label = QLabel("퀵버튼세트 미리보기")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFont(self.current_font)
        palette = self.preview_label.palette()
        palette.setColor(QPalette.WindowText, self.current_color)
        self.preview_label.setPalette(palette)
        self.preview_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        self.preview_label.setMinimumHeight(60)
        self.font_button = QPushButton("글꼴 선택")
        self.font_button.clicked.connect(self.select_font)
        self.color_button = QPushButton("색상 선택")
        self.color_button.clicked.connect(self.select_color)
        color_layout = QHBoxLayout()
        self.color_combo = QComboBox()
        for label, value in [("직접 선택",""),("검정","#000000"),("빨강","#FF0000"),("녹색","#00FF00"),
                             ("파랑","#0000FF"),("노랑","#FFFF00"),("자주","#800080"),("청록","#008080"),("오렌지","#FFA500")]:
            self.color_combo.addItem(label, value)
        self.color_combo.currentIndexChanged.connect(self.preset_color_changed)
        color_layout.addWidget(QLabel("프리셋 색상:"))
        color_layout.addWidget(self.color_combo)
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.font_button)
        layout.addWidget(self.color_button)
        layout.addLayout(color_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def select_font(self):
        font, ok = QFontDialog.getFont(self.current_font, self)
        if ok:
            self.current_font = font
            self.preview_label.setFont(self.current_font)

    def select_color(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            palette = self.preview_label.palette()
            palette.setColor(QPalette.WindowText, self.current_color)
            self.preview_label.setPalette(palette)
            self.color_combo.setCurrentIndex(0)

    def preset_color_changed(self, index):
        if index > 0:
            self.current_color = QColor(self.color_combo.currentData())
            palette = self.preview_label.palette()
            palette.setColor(QPalette.WindowText, self.current_color)
            self.preview_label.setPalette(palette)

    def get_values(self):
        return self.current_font, self.current_color


class ButtonStyleDialog(QDialog):
    """버튼 스타일 통합 설정 대화상자"""
    def __init__(self, label="", label2="", text="", width=150, height=40, font=None, color=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("버튼 스타일 설정")
        self.resize(450, 400)
        self.current_font = font or QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)
        self.current_color = color or QColor("#000000")
        layout = QVBoxLayout()
        text_group = QGroupBox("버튼 텍스트")
        text_layout = QFormLayout()
        self.label_input = QLineEdit(label)
        self.label2_input = QLineEdit(label2)
        self.text_input = QTextEdit(text)
        self.text_input.setAcceptRichText(False)
        self.text_input.setMinimumHeight(70)
        text_layout.addRow("첫째 줄 레이블:", self.label_input)
        text_layout.addRow("둘째 줄 레이블:", self.label2_input)
        text_layout.addRow("붙여넣기 텍스트:", self.text_input)
        text_group.setLayout(text_layout)
        size_group = QGroupBox("버튼 크기")
        size_layout = QFormLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(50, 500)
        self.width_spin.setValue(width)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(30, 300)
        self.height_spin.setValue(height)
        size_layout.addRow("버튼 너비:", self.width_spin)
        size_layout.addRow("버튼 높이:", self.height_spin)
        size_group.setLayout(size_layout)
        style_group = QGroupBox("글꼴 및 색상")
        style_layout = QVBoxLayout()
        self.preview_button = QPushButton(f"{label}\n{label2}" if label2 else label)
        self.preview_button.setFont(self.current_font)
        palette = self.preview_button.palette()
        palette.setColor(QPalette.ButtonText, self.current_color)
        self.preview_button.setPalette(palette)
        self.preview_button.setFixedSize(width, height)
        self.preview_button.setEnabled(False)
        preview_layout = QHBoxLayout()
        preview_layout.addStretch()
        preview_layout.addWidget(self.preview_button)
        preview_layout.addStretch()
        self.font_button = QPushButton("글꼴 설정")
        self.font_button.clicked.connect(self.select_font)
        self.color_button = QPushButton("텍스트 색상 설정")
        self.color_button.clicked.connect(self.select_color)
        color_layout = QHBoxLayout()
        self.color_combo = QComboBox()
        for lbl, val in [("직접 선택",""),("검정","#000000"),("빨강","#FF0000"),("녹색","#00FF00"),
                         ("파랑","#0000FF"),("노랑","#FFFF00"),("자주","#800080"),("청록","#008080"),("오렌지","#FFA500")]:
            self.color_combo.addItem(lbl, val)
        self.color_combo.currentIndexChanged.connect(self.preset_color_changed)
        color_layout.addWidget(QLabel("프리셋 색상:"))
        color_layout.addWidget(self.color_combo)
        style_layout.addLayout(preview_layout)
        style_layout.addWidget(self.font_button)
        style_layout.addWidget(self.color_button)
        style_layout.addLayout(color_layout)
        style_group.setLayout(style_layout)
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addWidget(text_group)
        layout.addWidget(size_group)
        layout.addWidget(style_group)
        layout.addStretch()
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        self.label_input.textChanged.connect(self.update_preview)
        self.label2_input.textChanged.connect(self.update_preview)
        self.width_spin.valueChanged.connect(self.update_preview_size)
        self.height_spin.valueChanged.connect(self.update_preview_size)

    def update_preview(self):
        label = self.label_input.text()
        label2 = self.label2_input.text()
        self.preview_button.setText(f"{label}\n{label2}" if label2 else label)

    def update_preview_size(self):
        self.preview_button.setFixedSize(self.width_spin.value(), self.height_spin.value())

    def select_font(self):
        font, ok = QFontDialog.getFont(self.current_font, self)
        if ok:
            self.current_font = font
            self.preview_button.setFont(self.current_font)

    def select_color(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            palette = self.preview_button.palette()
            palette.setColor(QPalette.ButtonText, self.current_color)
            self.preview_button.setPalette(palette)
            self.color_combo.setCurrentIndex(0)

    def preset_color_changed(self, index):
        if index > 0:
            self.current_color = QColor(self.color_combo.currentData())
            palette = self.preview_button.palette()
            palette.setColor(QPalette.ButtonText, self.current_color)
            self.preview_button.setPalette(palette)

    def get_values(self):
        return {
            "label": self.label_input.text(),
            "label2": self.label2_input.text(),
            "text": self.text_input.toPlainText(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "font": self.current_font,
            "color": self.current_color
        }


class QuickEditDialog(QDialog):
    """퀵버튼 빠른 편집 대화상자"""
    def __init__(self, buttons_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("퀵버튼 빠른 편집")
        self.resize(700, 500)
        self.buttons_data = buttons_data
        self.button_rows = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        self.form_layout = QVBoxLayout(content_widget)
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("레이블(첫째 줄)"), 1)
        header_layout.addWidget(QLabel("레이블(둘째 줄)"), 1)
        header_layout.addWidget(QLabel("붙여넣기 텍스트"), 3)
        header_layout.addWidget(QLabel(""), QLabel().sizeHint().width())
        self.form_layout.addLayout(header_layout)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.form_layout.addWidget(line)
        for button_data in self.buttons_data:
            self.add_button_row(button_data["label"], button_data["text"], button_data.get("label2", ""))
        scroll_area.setWidget(content_widget)
        buttons_layout = QHBoxLayout()
        add_button = QPushButton("버튼 추가")
        add_button.clicked.connect(self.add_new_button)
        save_button = QPushButton("저장")
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(add_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        main_layout.addWidget(scroll_area, 1)
        main_layout.addLayout(buttons_layout)
        self.setLayout(main_layout)

    def add_button_row(self, label="", text="", label2=""):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 5, 0, 5)
        label_edit = QLineEdit(label)
        label_edit.setPlaceholderText("첫째 줄 레이블")
        label2_edit = QLineEdit(label2)
        label2_edit.setPlaceholderText("둘째 줄 레이블 (선택)")
        text_edit = QTextEdit(text)
        text_edit.setPlaceholderText("붙여넣기 텍스트")
        text_edit.setMaximumHeight(80)
        delete_button = QPushButton("✕")
        delete_button.setMaximumWidth(30)
        delete_button.clicked.connect(lambda: self.delete_button_row(row_widget))
        row_layout.addWidget(label_edit, 1)
        row_layout.addWidget(label2_edit, 1)
        row_layout.addWidget(text_edit, 3)
        row_layout.addWidget(delete_button)
        self.form_layout.addWidget(row_widget)
        self.button_rows.append({
            "widget": row_widget,
            "label_edit": label_edit,
            "label2_edit": label2_edit,
            "text_edit": text_edit
        })
        return row_widget

    def add_new_button(self):
        self.add_button_row()

    def delete_button_row(self, row_widget):
        for i, row in enumerate(self.button_rows):
            if row["widget"] == row_widget:
                self.button_rows.pop(i)
                break
        self.form_layout.removeWidget(row_widget)
        row_widget.deleteLater()

    def get_buttons_data(self):
        result = []
        for row in self.button_rows:
            label = row["label_edit"].text().strip() or "버튼"
            label2 = row["label2_edit"].text().strip()
            text = row["text_edit"].toPlainText()
            result.append({
                "label": label, "label2": label2, "text": text,
                "x": 10, "y": 10, "width": 150, "height": 40,
                "custom_size": False, "custom_font": False, "custom_color": False
            })
        return result


class ButtonSettingsDialog(QDialog):
    """버튼 설정 대화상자"""
    def __init__(self, label="", label2="", text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("버튼 설정")
        self.resize(350, 200)
        layout = QFormLayout()
        self.label_input = QLineEdit(label)
        self.label2_input = QLineEdit(label2)
        self.text_input = QTextEdit(text)
        self.text_input.setAcceptRichText(False)
        self.text_input.setMinimumHeight(70)
        layout.addRow("버튼 레이블(첫째 줄):", self.label_input)
        layout.addRow("버튼 레이블(둘째 줄):", self.label2_input)
        layout.addRow("붙여넣기 텍스트:", self.text_input)
        note_label = QLabel("※ 둘째 줄 레이블은 선택사항입니다.")
        note_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addRow(note_label)
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addRow(buttons_layout)
        self.setLayout(layout)

    def get_values(self):
        return self.label_input.text(), self.label2_input.text(), self.text_input.toPlainText()


class SetNameDialog(QDialog):
    """세트 이름 설정 대화상자"""
    def __init__(self, name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("세트 이름 설정")
        self.resize(300, 100)
        layout = QFormLayout()
        self.name_input = QLineEdit(name)
        layout.addRow("세트 이름:", self.name_input)
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addRow(buttons_layout)
        self.setLayout(layout)

    def get_value(self):
        return self.name_input.text()


class ButtonSizeDialog(QDialog):
    """버튼 크기 설정 대화상자"""
    def __init__(self, width, height, parent=None):
        super().__init__(parent)
        self.setWindowTitle("버튼 크기 설정")
        self.resize(300, 150)
        layout = QFormLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(50, 500)
        self.width_spin.setValue(width)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(30, 300)
        self.height_spin.setValue(height)
        layout.addRow("버튼 너비:", self.width_spin)
        layout.addRow("버튼 높이:", self.height_spin)
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addRow(buttons_layout)
        self.setLayout(layout)

    def get_values(self):
        return self.width_spin.value(), self.height_spin.value()


class TextBoxSizeDialog(QDialog):
    """텍스트 박스 크기 설정 대화상자"""
    def __init__(self, width, height, parent=None):
        super().__init__(parent)
        self.setWindowTitle("텍스트 박스 크기 설정")
        self.resize(300, 150)
        layout = QFormLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(50, 500)
        self.width_spin.setValue(width)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(30, 400)
        self.height_spin.setValue(height)
        layout.addRow("너비:", self.width_spin)
        layout.addRow("높이:", self.height_spin)
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addRow(buttons_layout)
        self.setLayout(layout)

    def get_values(self):
        return self.width_spin.value(), self.height_spin.value()


class FontSettingsDialog(QDialog):
    """글꼴 설정 대화상자"""
    def __init__(self, current_font, current_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("글꼴 설정")
        self.resize(400, 250)
        self.current_font = current_font
        self.current_color = current_color
        layout = QVBoxLayout()
        self.preview_label = QLabel("가나다라 AbCd 123")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFont(self.current_font)
        palette = self.preview_label.palette()
        palette.setColor(QPalette.WindowText, self.current_color)
        self.preview_label.setPalette(palette)
        self.preview_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        self.preview_label.setMinimumHeight(60)
        self.font_button = QPushButton("글꼴 선택")
        self.font_button.clicked.connect(self.select_font)
        self.color_button = QPushButton("색상 선택")
        self.color_button.clicked.connect(self.select_color)
        color_layout = QHBoxLayout()
        self.color_combo = QComboBox()
        for lbl, val in [("직접 선택",""),("검정","#000000"),("빨강","#FF0000"),("녹색","#00FF00"),
                         ("파랑","#0000FF"),("노랑","#FFFF00"),("자주","#800080"),("청록","#008080"),("오렌지","#FFA500")]:
            self.color_combo.addItem(lbl, val)
        self.color_combo.currentIndexChanged.connect(self.preset_color_changed)
        color_layout.addWidget(QLabel("프리셋 색상:"))
        color_layout.addWidget(self.color_combo)
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.font_button)
        layout.addWidget(self.color_button)
        layout.addLayout(color_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def select_font(self):
        font, ok = QFontDialog.getFont(self.current_font, self)
        if ok:
            self.current_font = font
            self.preview_label.setFont(self.current_font)

    def select_color(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            palette = self.preview_label.palette()
            palette.setColor(QPalette.WindowText, self.current_color)
            self.preview_label.setPalette(palette)
            self.color_combo.setCurrentIndex(0)

    def preset_color_changed(self, index):
        if index > 0:
            self.current_color = QColor(self.color_combo.currentData())
            palette = self.preview_label.palette()
            palette.setColor(QPalette.WindowText, self.current_color)
            self.preview_label.setPalette(palette)

    def get_values(self):
        return self.current_font, self.current_color
