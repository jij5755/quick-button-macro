import json
import os
import copy

from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QColor

from constants import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, PRESETS_DIR, META_FILE, GRID_SIZE


class ButtonSet:
    """버튼 세트를 관리하는 클래스"""
    def __init__(self, name, buttons=None, textboxes=None):
        self.name = name
        self.buttons = buttons or []
        self.textboxes = textboxes or []

    def to_dict(self):
        result = {
            "name": self.name,
            "buttons": self.buttons.copy(),
            "textboxes": self.textboxes.copy()
        }
        if hasattr(self, 'individual_style') and self.individual_style:
            result['individual_style'] = True
            if hasattr(self, 'font'):
                result['font'] = self.font
            if hasattr(self, 'text_color'):
                result['text_color'] = self.text_color
            if hasattr(self, 'bg_color'):
                result['bg_color'] = self.bg_color
        return result

    @classmethod
    def from_dict(cls, data):
        buttons = []
        if "buttons" in data:
            for button in data["buttons"]:
                if "label" not in button:
                    button["label"] = "버튼"
                if "label2" not in button:
                    button["label2"] = ""
                if "text" not in button:
                    button["text"] = ""
                if "x" not in button:
                    button["x"] = 10
                if "y" not in button:
                    button["y"] = 10
                if "width" not in button:
                    button["width"] = 150
                if "height" not in button:
                    button["height"] = 40
                if "custom_size" not in button:
                    button["custom_size"] = False
                if "custom_font" not in button:
                    button["custom_font"] = False
                if "custom_color" not in button:
                    button["custom_color"] = False
                buttons.append(button)

        textboxes = []
        if "textboxes" in data:
            for textbox in data["textboxes"]:
                if "text" not in textbox:
                    textbox["text"] = "텍스트 상자"
                if "x" not in textbox:
                    textbox["x"] = 10
                if "y" not in textbox:
                    textbox["y"] = 10
                if "width" not in textbox:
                    textbox["width"] = 200
                if "height" not in textbox:
                    textbox["height"] = 100
                if "font" not in textbox:
                    textbox["font"] = {
                        "family": DEFAULT_FONT_FAMILY,
                        "point_size": DEFAULT_FONT_SIZE,
                        "weight": 400,
                        "italic": False,
                        "bold": False
                    }
                if "color" not in textbox:
                    textbox["color"] = "#000000"
                if "bg_color" not in textbox:
                    textbox["bg_color"] = "transparent"
                if "custom_size" not in textbox:
                    textbox["custom_size"] = False
                if "custom_font" not in textbox:
                    textbox["custom_font"] = False
                if "custom_color" not in textbox:
                    textbox["custom_color"] = False
                textboxes.append(textbox)

        set_obj = cls(data.get("name", "이름 없는 세트"), buttons, textboxes)

        if 'individual_style' in data and data['individual_style']:
            set_obj.individual_style = True
            if 'font' in data:
                set_obj.font = data['font']
            if 'text_color' in data:
                set_obj.text_color = data['text_color']
            if 'bg_color' in data:
                set_obj.bg_color = data['bg_color']

        return set_obj


class WidgetClipboard:
    """선택된 위젯들의 복사/붙여넣기를 관리하는 클래스"""
    def __init__(self):
        self.clipboard_data = None
        self.reference_point = QPoint(0, 0)

    def has_data(self):
        return self.clipboard_data is not None

    def copy_widgets(self, widgets):
        # 순환 import 방지를 위해 함수 내부에서 import
        from widgets import SelectableButton, SelectableTextBox

        if not widgets:
            return False

        widget_data = []
        self.reference_point = widgets[0].pos()

        for widget in widgets:
            relative_pos = widget.pos() - self.reference_point

            if isinstance(widget, SelectableButton):
                button_idx = widget.parent.buttons.index(widget)
                if 0 <= button_idx < len(widget.parent.button_data):
                    button_data = copy.deepcopy(widget.parent.button_data[button_idx])
                    button_data["relative_x"] = relative_pos.x()
                    button_data["relative_y"] = relative_pos.y()
                    widget_data.append({"type": "button", "data": button_data})

            elif isinstance(widget, SelectableTextBox):
                textbox_idx = widget.parent.textboxes.index(widget)
                if 0 <= textbox_idx < len(widget.parent.textbox_data):
                    textbox_data = copy.deepcopy(widget.parent.textbox_data[textbox_idx])
                    textbox_data["relative_x"] = relative_pos.x()
                    textbox_data["relative_y"] = relative_pos.y()
                    widget_data.append({"type": "textbox", "data": textbox_data})

        self.clipboard_data = widget_data
        return True

    def paste_widgets(self, parent, paste_pos):
        if not self.clipboard_data:
            return False

        parent.clear_all_selections()
        created_widgets = []

        for item in self.clipboard_data:
            widget_type = item["type"]
            data = copy.deepcopy(item["data"])

            rel_x = data.pop("relative_x", 0)
            rel_y = data.pop("relative_y", 0)
            absolute_pos = paste_pos + QPoint(rel_x, rel_y)

            x = round(absolute_pos.x() / GRID_SIZE) * GRID_SIZE
            y = round(absolute_pos.y() / GRID_SIZE) * GRID_SIZE

            if widget_type == "button":
                button = parent.create_button(
                    data["label"], data["text"], x, y,
                    data.get("width", 150), data.get("height", 40),
                    data.get("label2", "")
                )
                button.custom_size = data.get("custom_size", False)
                button.custom_font = data.get("custom_font", False)
                button.custom_color = data.get("custom_color", False)
                button.set_selected(True)
                created_widgets.append(button)

            elif widget_type == "textbox":
                font_dict = data.get("font", {})
                font = parent.dict_to_font(font_dict)
                color = QColor(data.get("color", "#000000"))
                bg_color = QColor(data.get("bg_color", "transparent"))
                textbox = parent.create_textbox(
                    data["text"], x, y,
                    data.get("width", 200), data.get("height", 100),
                    font, color, bg_color
                )
                textbox.custom_size = data.get("custom_size", False)
                textbox.custom_font = data.get("custom_font", False)
                textbox.custom_color = data.get("custom_color", False)
                textbox.set_selected(True)
                created_widgets.append(textbox)

        parent.buttons_container.updateMinimumSize()
        return len(created_widgets) > 0


class PresetManager:
    def __init__(self, main_app):
        self.main_app = main_app
        self.presets_dir = PRESETS_DIR
        self.meta_file = META_FILE
        self.current_preset = ""
        self.ensure_preset_dir()
        self.load_meta()

    def ensure_preset_dir(self):
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)

    def load_meta(self):
        if os.path.exists(self.meta_file):
            try:
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    self.current_preset = meta.get("last_preset", "")
            except:
                self.current_preset = ""

    def save_meta(self):
        with open(self.meta_file, 'w', encoding='utf-8') as f:
            json.dump({"last_preset": self.current_preset}, f, ensure_ascii=False)

    def get_preset_list(self):
        preset_files = []
        for file in os.listdir(self.presets_dir):
            if file.endswith(".json"):
                preset_files.append(os.path.splitext(file)[0])
        return preset_files

    def save_preset(self, name, data):
        file_path = os.path.join(self.presets_dir, f"{name}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.current_preset = name
        self.save_meta()

    def load_preset(self, name):
        file_path = os.path.join(self.presets_dir, f"{name}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.current_preset = name
            self.save_meta()
            return data
        return None

    def rename_preset(self, old_name, new_name):
        if old_name == new_name or not old_name or not new_name:
            return False
        old_file_path = os.path.join(self.presets_dir, f"{old_name}.json")
        new_file_path = os.path.join(self.presets_dir, f"{new_name}.json")
        if not os.path.exists(old_file_path):
            return False
        if os.path.exists(new_file_path):
            return False
        try:
            os.rename(old_file_path, new_file_path)
            if self.current_preset == old_name:
                self.current_preset = new_name
                self.save_meta()
            return True
        except Exception as e:
            print(f"프리셋 이름 변경 오류: {e}")
            return False

    def refresh_presets(self):
        current = self.current_preset
        self.load_meta()
        presets = self.get_preset_list()
        if self.current_preset not in presets and current in presets:
            self.current_preset = current
            self.save_meta()
        return presets
