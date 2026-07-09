import json
import os
import copy
import shutil
import time
import datetime

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
    BACKUP_KEEP = 20          # 프리셋당 보관할 백업 개수
    BACKUP_MIN_INTERVAL = 600 # 백업 최소 간격 (초) - 저장이 잦아도 백업은 10분에 한 번만

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
        self._atomic_write_json(self.meta_file, {"last_preset": self.current_preset})

    @staticmethod
    def _atomic_write_json(file_path, data, indent=None):
        """임시 파일에 완전히 쓴 뒤 교체 - 쓰기 도중 중단돼도 기존 파일이 깨지지 않음"""
        tmp_path = f"{file_path}.tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)

    def _backup_dir(self):
        return os.path.join(self.presets_dir, "backup")

    def _list_backups(self, name):
        """해당 프리셋의 백업 파일명을 오래된 순으로 반환"""
        backup_dir = self._backup_dir()
        if not os.path.isdir(backup_dir):
            return []
        prefix = f"{name}_"
        return sorted(
            f for f in os.listdir(backup_dir)
            if f.startswith(prefix) and f.endswith(".json")
            and f[len(prefix):-5].replace("_", "").isdigit()
        )

    def _backup_preset_file(self, name, file_path):
        """저장 직전의 기존 프리셋 파일을 백업 폴더에 보관"""
        if not os.path.exists(file_path):
            return
        backups = self._list_backups(name)
        backup_dir = self._backup_dir()
        if backups:
            newest = os.path.join(backup_dir, backups[-1])
            if time.time() - os.path.getmtime(newest) < self.BACKUP_MIN_INTERVAL:
                return
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(file_path, os.path.join(backup_dir, f"{name}_{stamp}.json"))
        # 오래된 백업 정리
        for old in self._list_backups(name)[:-self.BACKUP_KEEP]:
            try:
                os.remove(os.path.join(backup_dir, old))
            except OSError:
                pass

    def _restore_from_backup(self, name, file_path):
        """손상된 프리셋 파일을 가장 최근의 정상 백업으로 복구"""
        backup_dir = self._backup_dir()
        for fname in reversed(self._list_backups(name)):
            backup_path = os.path.join(backup_dir, fname)
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                continue  # 이 백업도 손상 - 그 이전 백업 시도
            # 손상된 원본은 진단용으로 보존하고 백업으로 교체
            try:
                os.replace(file_path, f"{file_path}.corrupt")
            except OSError:
                pass
            shutil.copy2(backup_path, file_path)
            print(f"프리셋 '{name}'을(를) 백업 '{fname}'으로 복구했습니다.")
            return data
        return None

    def get_preset_list(self):
        preset_files = []
        for file in os.listdir(self.presets_dir):
            if file.endswith(".json"):
                preset_files.append(os.path.splitext(file)[0])
        return preset_files

    def save_preset(self, name, data):
        file_path = os.path.join(self.presets_dir, f"{name}.json")
        try:
            self._backup_preset_file(name, file_path)
        except Exception as e:
            print(f"프리셋 백업 실패 (저장은 계속 진행): {e}")
        self._atomic_write_json(file_path, data, indent=2)
        self.current_preset = name
        self.save_meta()

    def load_preset(self, name):
        file_path = os.path.join(self.presets_dir, f"{name}.json")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"프리셋 '{name}' 파일 손상: {e}")
            data = self._restore_from_backup(name, file_path)
            if data is None:
                return None
        self.current_preset = name
        self.save_meta()
        return data

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
