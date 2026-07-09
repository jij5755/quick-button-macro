import sys
import json
import os
import copy

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QMenu, QAction, QInputDialog, QLineEdit, QMessageBox,
    QDialog, QFormLayout, QLabel, QSpinBox, QGridLayout, QScrollArea,
    QSizePolicy, QFrame, QFontDialog, QColorDialog, QComboBox,
    QSplitter, QListWidget, QListWidgetItem, QTextEdit, QCheckBox, QGroupBox
)
from PyQt5.QtCore import Qt, QPoint, QSize, QTimer, QMimeData, QEvent, QRect
from PyQt5.QtGui import QFont, QColor, QPalette, QDrag, QCursor, QPainter, QPixmap, QPen, QKeyEvent
import pyautogui
import pyperclip
import time
import ctypes

# ---------------------------------------------------------------------------
# Windows SendInput 기반 유니코드 키 입력
# 바코드 스캐너(키보드 웨지)처럼 실제 키 입력 이벤트를 한 글자씩 보냅니다.
# pyautogui.write()와 달리 한글 등 유니코드도 그대로 입력됩니다.
# (KEYEVENTF_UNICODE 방식 - POS/ERP의 키 입력만 받는 필드에서도 동작)
# ---------------------------------------------------------------------------
_PUL = ctypes.POINTER(ctypes.c_ulong)


class _KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", _PUL)]


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", _PUL)]


class _HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


# 유니온에는 실제 INPUT 구조체처럼 세 멤버가 모두 있어야 한다.
# ki만 넣으면 sizeof(INPUT)가 Windows 기대값보다 작아져
# SendInput이 ERROR_INVALID_PARAMETER로 조용히 실패한다(입력 무시됨).
class _Input_I(ctypes.Union):
    _fields_ = [("ki", _KeyBdInput),
                ("mi", _MouseInput),
                ("hi", _HardwareInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", _Input_I)]


_INPUT_KEYBOARD = 1
_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002
_VK_RETURN = 0x0D


def _send_input(wVk, wScan, dwFlags):
    extra = ctypes.c_ulong(0)
    ii = _Input_I()
    ii.ki = _KeyBdInput(wVk, wScan, dwFlags, 0, ctypes.pointer(extra))
    inp = _Input(_INPUT_KEYBOARD, ii)
    sent = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    if sent != 1:
        raise ctypes.WinError(ctypes.windll.kernel32.GetLastError())


def type_unicode(text, interval=0.005):
    """문자열을 유니코드 키 입력으로 한 글자씩 전송 (한글 지원)."""
    for ch in text:
        code = ord(ch)
        # 보충 평면(이모지 등) 문자는 서로게이트 쌍으로 분해해 전송
        if code > 0xFFFF:
            code -= 0x10000
            for unit in (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)):
                _send_input(0, unit, _KEYEVENTF_UNICODE)
                _send_input(0, unit, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP)
        else:
            _send_input(0, code, _KEYEVENTF_UNICODE)
            _send_input(0, code, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP)
        if interval:
            time.sleep(interval)


def press_enter():
    """Enter 키를 실제 가상키 입력으로 전송."""
    _send_input(_VK_RETURN, 0, 0)
    _send_input(_VK_RETURN, 0, _KEYEVENTF_KEYUP)


from constants import (
    DEFAULT_BUTTON_WIDTH, DEFAULT_BUTTON_HEIGHT,
    DEFAULT_TEXTBOX_WIDTH, DEFAULT_TEXTBOX_HEIGHT,
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, DEFAULT_TEXT_COLOR,
    GRID_SIZE, SAVE_FILENAME
)
from models import ButtonSet, WidgetClipboard, PresetManager
from widgets import SelectableButton, SelectableTextBox, SetListWidget, DraggableSetItem, ButtonContainerWidget
from dialogs import (
    ButtonSettingsDialog, ButtonStyleDialog, TextBoxSettingsDialog,
    SetFontSettingsDialog, FontSettingsDialog, ButtonSizeDialog,
    TextBoxSizeDialog, SetNameDialog, QuickEditDialog
)

class QuickButtonMacro(QMainWindow):
    """퀵버튼 매크로 메인 클래스"""
    def __init__(self):
        super().__init__()
        
        self.target_position = (500, 500)  # 기본 마우스 위치
        self.button_width = 150
        self.button_height = 40
        self.button_font = QFont("맑은 고딕", 9)  # 기본 글꼴
        self.button_color = QColor("#000000")  # 기본 텍스트 색상
        
        # 텍스트 박스 관련 변수 추가
        self.textbox_width = 200
        self.textbox_height = 100
        self.textboxes = []  # 현재 세트의 활성 텍스트 박스 객체
        self.textbox_data = []  # 현재 세트의 텍스트 박스 데이터
        
        # 세트 리스트 폰트 및 색상
        self.set_list_font = QFont("맑은 고딕", 10, QFont.Bold)  # 세트 리스트 기본 글꼴
        self.set_list_color = QColor("#FF0000")  # 세트 리스트 기본 색상 (빨강)
        
        # 교차 배경색 추가
        self.even_row_color = QColor("#F0F0F0")  # 짝수 행 배경색 (옅은 회색)
        self.odd_row_color = QColor("#FFFFFF")   # 홀수 행 배경색 (흰색)
        self.use_alternating_colors = True       # 교차 배경색 사용 여부
        
        # 편집 모드 설정
        self.edit_mode = False
        
        # 세트 관련 변수 초기화
        self.button_sets = []  # ButtonSet 객체 리스트
        self.clipboard_handler = WidgetClipboard()
        self.current_set_index = 0  # 현재 선택된 세트 인덱스
        self.buttons = []  # 현재 세트의 활성 버튼 객체들
        self.button_data = []  # 현재 세트의 버튼 데이터
        # 세트 로드가 중간에 실패하면 True - 화면의 부분 상태로 세트 데이터를 덮어쓰지 않기 위한 플래그
        self._current_set_load_failed = False
        
        # UI 초기화
        self.init_ui()
        
        # 설정 로드
        try:
            self.load_sets()
        except Exception as e:
            print(f"설정 로드 중 예외 발생: {e}")
            # 오류 발생 시 기본 세트 생성
            self.button_sets = [ButtonSet("기본 세트")]
            self.update_set_list()
        
        # 세트가 없으면 기본 세트 생성
        if not self.button_sets:
            self.button_sets.append(ButtonSet("기본 세트"))
            self.update_set_list()
        
        # 초기 세트 선택
        if self.set_list.count() > 0:
            self.set_list.setCurrentRow(0)
            try:
                self.change_button_set(0)
            except Exception as e:
                print(f"초기 세트 선택 중 오류: {e}")
        
        # 컨테이너 위젯에 키보드 포커스 설정
        self.buttons_container.setFocusPolicy(Qt.StrongFocus)
        self.buttons_container.setFocus()

    def resizeEvent(self, event):
        """창 크기 변경 시 처리"""
        super().resizeEvent(event)

        # 컨테이너 크기 업데이트
        if hasattr(self, 'buttons_container'):
            self.buttons_container.updateMinimumSize()

    def copy_selected_widgets_to_clipboard(self):
        """선택된 위젯들을 클립보드에 복사"""
        selected_widgets = self.get_all_selected_widgets()
        if not selected_widgets:
            return
            
        # 클립보드 핸들러를 통해 복사 수행
        if self.clipboard_handler.copy_widgets(selected_widgets):
            # 상태 표시줄에 메시지 표시 (2초 후 자동 사라짐)
            self.statusBar().showMessage(f"{len(selected_widgets)}개 항목이 복사되었습니다.", 2000)

    def paste_widgets_from_clipboard(self, position):
        """클립보드의 위젯 데이터를 현재 위치에 붙여넣기"""
        if self.clipboard_handler.paste_widgets(self, position):
            # 붙여넣기 후 위젯 데이터 갱신
            self.save_current_set()
            self.save_sets()
            self.buttons_container.update()  # 화면 갱신
            self.statusBar().showMessage("항목을 붙여넣었습니다.", 2000)
        else:
            self.statusBar().showMessage("붙여넣기할 항목이 없습니다.", 2000)
    
    def _get_current_global_settings(self):
        """현재 전역 설정 가져오기"""
        return {
            'target_position': self.target_position,
            'button_width': self.button_width,
            'button_height': self.button_height,
            'textbox_width': self.textbox_width,
            'textbox_height': self.textbox_height,
            'button_font': self.font_to_dict(self.button_font),
            'button_color': self.button_color.name(),
            'set_list_font': self.font_to_dict(self.set_list_font),
            'set_list_color': self.set_list_color.name(),
            'even_row_color': self.even_row_color.name(),
            'odd_row_color': self.odd_row_color.name(),
            'use_alternating_colors': self.use_alternating_colors,
            'edit_mode': self.edit_mode,
            'splitter_sizes': self.splitter.sizes(),
            # 창 위치와 크기 정보 추가
            'window_position': [self.pos().x(), self.pos().y()],
            'window_size': [self.size().width(), self.size().height()]
        }

    def save_all_sets_styles(self):
        """모든 세트의 스타일 정보를 저장"""
        for i in range(self.set_list.count()):
            item = self.set_list.item(i)
            if i < len(self.button_sets) and item:
                # 개별 스타일 사용 여부 확인
                if hasattr(item, 'individual_style') and item.individual_style:
                    self.button_sets[i].individual_style = True
                    
                    # 글꼴 정보 저장
                    font = item.font()
                    self.button_sets[i].font = {
                        'family': font.family(),
                        'point_size': font.pointSize(),
                        'weight': font.weight(),
                        'italic': font.italic(),
                        'bold': font.bold()
                    }
                    
                    # 색상 정보 저장
                    self.button_sets[i].text_color = item.foreground().color().name()
                    self.button_sets[i].bg_color = item.background().color().name()
                else:
                    # 개별 스타일 설정 제거 (있는 경우)
                    if hasattr(self.button_sets[i], 'individual_style'):
                        delattr(self.button_sets[i], 'individual_style')
                    if hasattr(self.button_sets[i], 'font'):
                        delattr(self.button_sets[i], 'font')
                    if hasattr(self.button_sets[i], 'text_color'):
                        delattr(self.button_sets[i], 'text_color')
                    if hasattr(self.button_sets[i], 'bg_color'):
                        delattr(self.button_sets[i], 'bg_color')

    def update_preset_list(self):
        """프리셋 콤보박스 업데이트"""
        self.preset_combo.blockSignals(True)
        current_preset = self.preset_combo.currentText()
        self.preset_combo.clear()
        presets = self.preset_manager.get_preset_list()
        
        # 프리셋이 없으면 기본 프리셋 생성
        if not presets:
            self.create_default_preset()
            presets = self.preset_manager.get_preset_list()
        
        for preset in presets:
            self.preset_combo.addItem(preset)
        
        # 이전 선택 복원 또는 마지막 사용 프리셋 선택
        if current_preset and current_preset in presets:
            index = self.preset_combo.findText(current_preset)
            self.preset_combo.setCurrentIndex(index)
        elif self.preset_manager.current_preset in presets:
            index = self.preset_combo.findText(self.preset_manager.current_preset)
            self.preset_combo.setCurrentIndex(index)
        elif presets:
            self.preset_combo.setCurrentIndex(0)
            
        self.preset_combo.blockSignals(False)

    def has_unsaved_changes(self):
        """변경사항 감지 - 실제 변경 사항이 있을 때만 True 반환"""
        # 현재 프리셋이 없으면 변경 사항 없음
        if not self.preset_manager.current_preset:
            return False
            
        # 마지막 로드 시점의 전역 설정과 세트 데이터 비교가 필요
        # 간단한 구현으로 세트 수와 버튼 수만 비교
        try:
            # 현재 프리셋 파일 로드
            preset_file = os.path.join(self.preset_manager.presets_dir, 
                                    f"{self.preset_manager.current_preset}.json")
            if not os.path.exists(preset_file):
                return True  # 파일이 없으면 저장 필요
                
            with open(preset_file, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                
            # 기본적인 세트 수 비교
            if 'sets' not in saved_data or len(saved_data['sets']) != len(self.button_sets):
                return True
                
            # 각 세트의 버튼 수와 텍스트 박스 수만 간단히 비교
            for i, set_obj in enumerate(self.button_sets):
                if i >= len(saved_data['sets']):
                    return True
                    
                saved_set = saved_data['sets'][i]
                
                # 버튼 수 비교
                if len(set_obj.buttons) != len(saved_set.get('buttons', [])):
                    return True
                    
                # 텍스트 박스 수 비교
                if len(set_obj.textboxes) != len(saved_set.get('textboxes', [])):
                    return True
            
            # 변경 사항 없음으로 판단
            return False
        except Exception:
            # 오류 발생 시 안전을 위해 변경 있음으로 처리
            return True


    def on_preset_changed(self, index):
        """프리셋 변경 처리"""
        if index < 0:
            return
        
        # 프로그램 시작 시 초기 로드 시에는 묻지 않음
        if not hasattr(self, '_initial_preset_loaded'):
            self._initial_preset_loaded = True
            preset_name = self.preset_combo.currentText()
            if preset_name:
                self.load_preset(preset_name)
            return
        
        # 현재 선택된 프리셋 이름 저장 (나중에 사용)
        new_preset_name = self.preset_combo.currentText()
        # 이전 프리셋 이름 저장
        old_preset_name = self.preset_manager.current_preset
        
        # 현재 편집 중인 세트 저장 여부 확인
        if self.has_unsaved_changes():
            reply = QMessageBox.question(self, '변경사항 저장', 
                    f"'{old_preset_name}' 프리셋에 변경사항이 있습니다. 저장하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            
            if reply == QMessageBox.Cancel:
                # 취소 선택 시 이전 선택으로 되돌림
                self.preset_combo.blockSignals(True)
                old_index = self.preset_combo.findText(old_preset_name)
                if old_index >= 0:
                    self.preset_combo.setCurrentIndex(old_index)
                self.preset_combo.blockSignals(False)
                return
            
            if reply == QMessageBox.Yes:
                # 임시로 current_preset을 이전 프리셋으로 복원하여 저장
                temp_current = self.preset_manager.current_preset
                self.preset_manager.current_preset = old_preset_name
                self.save_current_preset()
                self.preset_manager.current_preset = temp_current
        
        # 새 프리셋 로드
        self.load_preset(new_preset_name)


    def create_default_preset(self):
        """기본 프리셋 생성"""
        # 기존 세트 데이터 준비
        self.save_current_set()
        
        sets_data = []
        for set_obj in self.button_sets:
            sets_data.append(set_obj.to_dict())
        
        # 데이터가 없으면 기본 세트 추가
        if not sets_data:
            sets_data = [ButtonSet("기본 세트").to_dict()]
        
        # 프리셋 데이터 생성
        preset_data = {
            'global_settings': self._get_current_global_settings(),
            'sets': sets_data
        }
        
        # 프리셋 저장
        self.preset_manager.save_preset("기본 프리셋", preset_data)
        
        # 상태 메시지 표시
        self.statusBar().showMessage("기본 프리셋이 생성되었습니다.", 2000)

    def create_new_preset(self):
        """새 프리셋 생성 (빈 상태)"""
        dialog = QInputDialog(self)
        dialog.setWindowTitle("새 프리셋 생성")
        dialog.setLabelText("프리셋 이름:")
        dialog.setInputMode(QInputDialog.TextInput)
        
        if dialog.exec_():
            preset_name = dialog.textValue().strip()
            if not preset_name:
                QMessageBox.warning(self, "오류", "프리셋 이름을 입력해 주세요.")
                return
            
            # 이름 중복 확인
            presets = self.preset_manager.get_preset_list()
            if preset_name in presets:
                QMessageBox.warning(self, "중복 이름", f"'{preset_name}' 프리셋이 이미 존재합니다.")
                return
            
            # 변경사항 저장 여부 확인 (새 프리셋 생성 전에 처리)
            current_preset = self.preset_manager.current_preset
            if self.has_unsaved_changes() and current_preset:
                reply = QMessageBox.question(self, '변경사항 저장', 
                        f"'{current_preset}' 프리셋에 변경사항이 있습니다. 저장하시겠습니까?",
                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                
                if reply == QMessageBox.Cancel:
                    return
                
                if reply == QMessageBox.Yes:
                    self.save_current_preset()
            
            # 빈 세트로 새 프리셋 생성
            default_data = {
                'global_settings': self._get_current_global_settings(),
                'sets': [ButtonSet("기본 세트").to_dict()]
            }
            
            # 새 프리셋 저장
            self.preset_manager.save_preset(preset_name, default_data)
            
            # 프리셋 목록 업데이트
            self.update_preset_list()
            
            # 시그널 차단 후 새 프리셋 선택 (중복 저장 대화상자 방지)
            self.preset_combo.blockSignals(True)
            index = self.preset_combo.findText(preset_name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            self.preset_combo.blockSignals(False)
            
            # 새 프리셋 수동 로드
            self.load_preset(preset_name)
            
            # 상태 메시지 표시
            self.statusBar().showMessage(f"새 프리셋 '{preset_name}'이(가) 생성되었습니다.", 2000)


    def save_current_preset(self):
        """현재 프리셋 저장"""
        if not self.preset_combo.currentText():
            self.duplicate_preset()  # 선택된 프리셋이 없으면 새 이름으로 저장
            return
        
        # 현재 세트 데이터 저장
        if self.current_set_index < len(self.button_sets) and (self.buttons or self.textboxes):
            self.save_current_set()
        
        # 모든 세트의 스타일 정보 저장 (추가된 부분)
        self.save_all_sets_styles()
        
        # 프리셋 데이터 준비
        sets_data = []
        for set_obj in self.button_sets:
            sets_data.append(set_obj.to_dict())
        
        preset_data = {
            'global_settings': self._get_current_global_settings(),
            'sets': sets_data
        }
        
        # 프리셋 저장
        preset_name = self.preset_combo.currentText()
        self.preset_manager.save_preset(preset_name, preset_data)
        
        # 상태 메시지 표시
        self.statusBar().showMessage(f"프리셋 '{preset_name}'이(가) 저장되었습니다.", 2000)

    def duplicate_preset(self):
        """현재 프리셋 복제"""
        # 현재 세트 데이터 저장
        if self.current_set_index < len(self.button_sets) and (self.buttons or self.textboxes):
            self.save_current_set()
        
        # 프리셋 데이터 준비
        sets_data = []
        for set_obj in self.button_sets:
            sets_data.append(set_obj.to_dict())
        
        preset_data = {
            'global_settings': self._get_current_global_settings(),
            'sets': sets_data
        }
        
        # 새 이름 입력 받기
        base_name = self.preset_combo.currentText() or "새 프리셋"
        dialog = QInputDialog(self)
        dialog.setWindowTitle("프리셋 복제")
        dialog.setLabelText("새 프리셋 이름:")
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setTextValue(f"{base_name} 복사본")
        
        if dialog.exec_():
            new_name = dialog.textValue().strip()
            if not new_name:
                QMessageBox.warning(self, "오류", "프리셋 이름을 입력해 주세요.")
                return
            
            # 이름 중복 확인 및 저장
            presets = self.preset_manager.get_preset_list()
            if new_name in presets:
                QMessageBox.warning(self, "중복 이름", f"'{new_name}' 프리셋이 이미 존재합니다.")
                return
            
            # 새 이름으로 프리셋 저장
            self.preset_manager.save_preset(new_name, preset_data)
            
            # 프리셋 목록 업데이트 및 새 프리셋 선택
            self.update_preset_list()
            index = self.preset_combo.findText(new_name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            
            # 상태 메시지 표시
            self.statusBar().showMessage(f"프리셋이 '{new_name}'으로 복제되었습니다.", 2000)

    def load_preset(self, preset_name):
        """프리셋 로드"""
        data = self.preset_manager.load_preset(preset_name)
        if not data:
            QMessageBox.warning(self, "프리셋 로드 실패",
                                f"'{preset_name}' 프리셋 파일을 읽을 수 없습니다.\n"
                                f"'{os.path.join(self.preset_manager.presets_dir, 'backup')}' 폴더의 백업을 확인해 주세요.")
            return False
        
        try:
            # 전역 설정 로드
            if 'global_settings' in data:
                self._load_global_settings(data['global_settings'])
            
            # 세트 데이터 로드
            if 'sets' in data and isinstance(data['sets'], list):
                # 기존 세트와 위젯 초기화
                for button in self.buttons:
                    button.deleteLater()
                for textbox in self.textboxes:
                    textbox.deleteLater()
                
                self.buttons = []
                self.button_data = []
                self.textboxes = []
                self.textbox_data = []
                
                # 세트 로드
                self.button_sets = []
                for set_data in data['sets']:
                    self._validate_and_fix_set_data(set_data)
                    set_obj = ButtonSet.from_dict(set_data)
                    self.button_sets.append(set_obj)
                
                # UI 업데이트
                self.update_set_list()
                self.current_set_index = 0
                
                # 첫 번째 세트 선택
                if self.set_list.count() > 0:
                    self.set_list.setCurrentRow(0)
                    self.change_button_set(0)
                
                # 상태 메시지 표시
                self.statusBar().showMessage(f"프리셋 '{preset_name}'을(를) 로드했습니다.", 2000)
                
                return True
            
        except Exception as e:
            print(f"프리셋 로드 오류: {e}")
            QMessageBox.warning(self, "로드 오류", f"프리셋 '{preset_name}' 로드 중 오류가 발생했습니다.\n{str(e)}")
        
        return False
    
    def rename_current_preset(self):
        """현재 선택된 프리셋 이름 변경"""
        current_preset = self.preset_combo.currentText()
        if not current_preset:
            QMessageBox.warning(self, "오류", "선택된 프리셋이 없습니다.")
            return
            
        dialog = QInputDialog(self)
        dialog.setWindowTitle("프리셋 이름 변경")
        dialog.setLabelText("새 프리셋 이름:")
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setTextValue(current_preset)
        
        if dialog.exec_():
            new_name = dialog.textValue().strip()
            if not new_name:
                QMessageBox.warning(self, "오류", "프리셋 이름을 입력해 주세요.")
                return
                
            if new_name == current_preset:
                return  # 이름이 변경되지 않음
                
            # 이름 중복 확인
            presets = self.preset_manager.get_preset_list()
            if new_name in presets:
                QMessageBox.warning(self, "중복 이름", f"'{new_name}' 프리셋이 이미 존재합니다.")
                return
                
            # 프리셋 이름 변경
            if self.preset_manager.rename_preset(current_preset, new_name):
                # 프리셋 목록 업데이트 및 새 이름 선택
                self.update_preset_list()
                index = self.preset_combo.findText(new_name)
                if index >= 0:
                    self.preset_combo.setCurrentIndex(index)
                    
                # 상태 메시지 표시
                self.statusBar().showMessage(f"프리셋 이름이 '{new_name}'(으)로 변경되었습니다.", 2000)
            else:
                QMessageBox.warning(self, "이름 변경 실패", "프리셋 이름을 변경하는 중 오류가 발생했습니다.")

    def refresh_preset_list(self):
        """프리셋 목록 새로고침"""
        # 현재 선택된 프리셋 저장
        current_preset = self.preset_combo.currentText()
        
        # 프리셋 목록 새로고침
        presets = self.preset_manager.refresh_presets()
        
        # UI 업데이트
        self.update_preset_list()
        
        # 이전 선택 복원
        if current_preset in presets:
            index = self.preset_combo.findText(current_preset)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
        
        # 상태 메시지 표시
        self.statusBar().showMessage("프리셋 목록을 새로고침했습니다.", 2000)


    def migrate_legacy_data(self):
        """기존 button_sets.json을 프리셋으로 변환"""
        if os.path.exists('button_sets.json') and not self.preset_manager.get_preset_list():
            try:
                # button_sets.json 파일 로드
                with open('button_sets.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # "기존 데이터" 이름으로 프리셋 저장
                self.preset_manager.save_preset("기존 데이터", data)
                
                # 프리셋 목록 업데이트
                self.update_preset_list()

                # 변환된 프리셋을 콤보박스에서 선택하고 즉시 로드
                self.preset_combo.blockSignals(True)
                index = self.preset_combo.findText("기존 데이터")
                if index >= 0:
                    self.preset_combo.setCurrentIndex(index)
                self.preset_combo.blockSignals(False)
                self.load_preset("기존 데이터")

                # 상태 메시지 표시
                self.statusBar().showMessage("기존 데이터가 '기존 데이터' 프리셋으로 변환되었습니다.", 3000)

                return True
            except Exception as e:
                print(f"기존 데이터 마이그레이션 오류: {e}")
                return False
        
        return False

    # 기존 _legacy_save_sets 메서드 추가 (save_sets 메서드 코드를 복사)
    def _legacy_save_sets(self):
        """기존 방식으로 세트 데이터 저장 (button_sets.json)"""
        try:
            # 현재 세트 데이터 저장
            if self.current_set_index < len(self.button_sets) and (self.buttons or self.textboxes):
                self.save_current_set()
            
            # 모든 세트를 사전 형태로 변환
            sets_data = []
            for set_obj in self.button_sets:
                sets_data.append(set_obj.to_dict())
            
            # 전역 설정 및 세트 데이터 저장
            with open('button_sets.json', 'w', encoding='utf-8') as f:
                json.dump({
                    'global_settings': self._get_current_global_settings(),
                    'sets': sets_data
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"레거시 저장 오류: {e}")
            QMessageBox.warning(self, "저장 오류", f"세트 데이터 저장 중 오류가 발생했습니다.\n{str(e)}")

    def closeEvent(self, event):
        """어플리케이션 종료 전 설정 저장"""
        try:
            # 현재 세트 데이터 저장
            if self.current_set_index < len(self.button_sets) and (self.buttons or self.textboxes):
                self.save_current_set()
            
            # 프리셋에 저장
            if hasattr(self, 'preset_manager') and self.preset_combo.currentText():
                self.save_current_preset()
            else:
                # 이전 방식으로 저장
                self._legacy_save_sets()
        except Exception as e:
            print(f"종료 전 저장 오류: {e}")
    
        event.accept()

    def init_ui(self):
        self.setWindowTitle('퀵버튼 매크로')
        self.setGeometry(100, 100, 800, 500)
        
        # 메인 위젯 생성
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 메인 레이아웃 생성
        main_layout = QVBoxLayout()
        
        # 상단 메뉴 영역
        header_layout = QHBoxLayout()
        
        # 편집 모드 토글 체크박스
        self.edit_mode_checkbox = QCheckBox("편집 모드")
        self.edit_mode_checkbox.toggled.connect(self.toggle_edit_mode)

            # 프리셋 관리 UI 추가
        self.preset_manager = PresetManager(self)
        
        # 프리셋 콤보박스
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(150)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        
        # 프리셋 관리 버튼
        self.save_preset_btn = QPushButton("💾")
        self.save_preset_btn.setToolTip("현재 프리셋 저장")
        self.save_preset_btn.setMaximumWidth(30)
        self.save_preset_btn.clicked.connect(self.save_current_preset)
        
        self.duplicate_preset_btn = QPushButton("📋")
        self.duplicate_preset_btn.setToolTip("프리셋 복제")
        self.duplicate_preset_btn.setMaximumWidth(30)
        self.duplicate_preset_btn.clicked.connect(self.duplicate_preset)
        
        self.new_preset_btn = QPushButton("🆕")
        self.new_preset_btn.setToolTip("새 프리셋 생성")
        self.new_preset_btn.setMaximumWidth(30)
        self.new_preset_btn.clicked.connect(self.create_new_preset)

        # 프리셋 이름 변경 버튼
        self.rename_preset_btn = QPushButton("✏️")
        self.rename_preset_btn.setToolTip("프리셋 이름 변경")
        self.rename_preset_btn.setMaximumWidth(30)
        self.rename_preset_btn.clicked.connect(self.rename_current_preset)

        # 프리셋 목록 새로고침 버튼
        self.refresh_preset_btn = QPushButton("🔄")
        self.refresh_preset_btn.setToolTip("프리셋 목록 새로고침")
        self.refresh_preset_btn.setMaximumWidth(30)
        self.refresh_preset_btn.clicked.connect(self.refresh_preset_list)
        
        set_position_button = QPushButton('마우스 위치 설정')
        set_position_button.clicked.connect(self.set_target_position)
        add_button = QPushButton('버튼 추가')
        add_button.clicked.connect(self.add_button_dialog)
        
        # 텍스트 박스 추가 버튼
        add_textbox_button = QPushButton('텍스트 박스 추가')
        add_textbox_button.clicked.connect(self.add_textbox_dialog)
        
        set_button_size = QPushButton('버튼 크기 설정')
        set_button_size.clicked.connect(self.set_button_size)
        set_font_button = QPushButton('버튼 글꼴 설정')
        set_font_button.clicked.connect(self.set_button_font)
        
        # 상단 메뉴 레이아웃에 위젯 추가
        header_layout.addWidget(self.edit_mode_checkbox)
        header_layout.addWidget(self.preset_combo)
        header_layout.addWidget(self.save_preset_btn)
        header_layout.addWidget(self.duplicate_preset_btn)
        header_layout.addWidget(self.new_preset_btn)
        header_layout.addWidget(self.rename_preset_btn)
        header_layout.addWidget(self.refresh_preset_btn)
       
        header_layout.addWidget(set_position_button)
        header_layout.addWidget(add_button)
        header_layout.addWidget(add_textbox_button)
        header_layout.addWidget(set_button_size)
        header_layout.addWidget(set_font_button)
        
        # 스플리터 생성 (좌: 세트 리스트, 우: 버튼 영역)
        self.splitter = QSplitter(Qt.Horizontal)
        
        # 좌측 패널: 세트 리스트
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        set_header_layout = QHBoxLayout()
        add_set_button = QPushButton("세트 추가")
        add_set_button.clicked.connect(self.add_set)
        set_list_font_button = QPushButton("세트 목록 글꼴")
        set_list_font_button.clicked.connect(self.set_list_font_settings)
        
        set_header_layout.addWidget(QLabel("퀵버튼 세트"))
        set_header_layout.addWidget(add_set_button)
        set_header_layout.addWidget(set_list_font_button)
        
        self.set_list = SetListWidget(self)
        self.set_list.setSelectionMode(QListWidget.SingleSelection)  # 단일 항목만 선택 가능하도록 설정

        self.set_list.currentRowChanged.connect(self.on_set_selected)
        self.set_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.set_list.customContextMenuRequested.connect(self.show_set_menu)
        
        # 세트 드래그앤드롭 설정
        self.set_list.dropEvent = self.set_list_drop_event
        
        left_layout.addLayout(set_header_layout)
        left_layout.addWidget(self.set_list)
        
        # 우측 패널: 버튼 영역
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        # 편집 모드 도움말 레이블
        self.edit_mode_label = QLabel("편집 모드: 위젯을 자유롭게 배치하고 Delete 키로 선택한 위젯을 삭제할 수 있습니다.")
        self.edit_mode_label.setAlignment(Qt.AlignCenter)
        self.edit_mode_label.setStyleSheet("color: #FF0000; font-weight: bold;")
        self.edit_mode_label.setVisible(False)  # 초기에는 숨김
        
        # 일반 모드 도움말 레이블
        self.normal_mode_label = QLabel("팁: 편집 모드를 활성화하면 버튼과 텍스트 박스를 자유롭게 배치할 수 있습니다.")
        self.normal_mode_label.setAlignment(Qt.AlignCenter)
        self.normal_mode_label.setStyleSheet("color: #666; font-style: italic;")
        
        # 스크롤 영역 생성
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 버튼 컨테이너 위젯 생성
        self.buttons_container = ButtonContainerWidget(self)
        self.buttons_container.setMinimumSize(500, 400)  # 최소 크기 설정
        self.buttons_container.setContextMenuPolicy(Qt.CustomContextMenu)
        self.buttons_container.customContextMenuRequested.connect(self.show_context_menu)
        
        # 스크롤 영역에 컨테이너 위젯 설정
        scroll_area.setWidget(self.buttons_container)
        
        # 우측 패널 레이아웃 조합
        right_layout.addWidget(self.edit_mode_label)
        right_layout.addWidget(self.normal_mode_label)
        right_layout.addWidget(scroll_area, 1)
        
        # 스플리터에 패널 추가
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)

        # 왼쪽 패널에 최소 크기 설정
        left_panel.setMinimumWidth(50)  # 최소 150px
        # 오른쪽 패널도 최소 크기 설정
        right_panel.setMinimumWidth(300)  # 최소 300px

        # 스플리터 크기 조정 (좌측:우측 = 1:3)
        self.splitter.setSizes([200, 600])

        # 메인 레이아웃에 요소 추가
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.splitter, 1)
        
        main_widget.setLayout(main_layout)
        
        # 키보드 이벤트 필터 설치
        self.installEventFilter(self)
    
    def toggle_edit_mode(self, enabled):
        """편집 모드 토글"""
        self.edit_mode = enabled
        
        # 편집 모드 레이블 표시 상태 업데이트
        self.edit_mode_label.setVisible(enabled)
        self.normal_mode_label.setVisible(not enabled)
        
        # 컨테이너 위젯의 그리드 표시 상태 업데이트
        self.buttons_container.show_grid = enabled

        # 세트 리스트의 드래그 앤 드롭/스크롤 모드 설정
        self.set_list.set_edit_mode(enabled)
        
        # 모든 위젯의 선택 상태 해제
        self.clear_all_selections()
        
        # 편집 모드 표시 업데이트 - 현재 세트 인덱스 유효성 확인 추가
        try:
            self.update_edit_mode_display()
        except Exception as e:
            print(f"편집 모드 표시 업데이트 중 오류: {e}")
            # 오류 발생 시 기본 타이틀 설정
            if self.edit_mode:
                self.setWindowTitle('퀵버튼 매크로 [편집 모드]')
            else:
                self.setWindowTitle('퀵버튼 매크로')
        
        # 버튼 컨테이너 위젯 갱신
        self.buttons_container.update()
    
    def update_edit_mode_display(self):
        """편집 모드에 따른 UI 상태 업데이트"""
        if self.edit_mode:
            # 편집 모드 스타일
            self.buttons_container.setStyleSheet("background-color: #f0f0f0;")
            
            # 현재 세트 인덱스 유효성 검사
            if 0 <= self.current_set_index < len(self.button_sets):
                self.setWindowTitle(f'퀵버튼 매크로 - {self.button_sets[self.current_set_index].name} [편집 모드]')
            else:
                self.setWindowTitle('퀵버튼 매크로 [편집 모드]')
        else:
            # 실행 모드 스타일
            self.buttons_container.setStyleSheet("")
            
            # 현재 세트 인덱스 유효성 검사
            if 0 <= self.current_set_index < len(self.button_sets):
                self.setWindowTitle(f'퀵버튼 매크로 - {self.button_sets[self.current_set_index].name}')
            else:
                self.setWindowTitle('퀵버튼 매크로')
    
    def toggle_button_custom_style(self, button, enabled):
        """버튼의 통합 개별 스타일 상태 토글"""
        button_idx = self.buttons.index(button)
        if button_idx < 0 or button_idx >= len(self.buttons):
            return
        
        # 통합 스타일 플래그 설정
        button.custom_style = enabled
        self.button_data[button_idx]["custom_style"] = enabled
        
        # 하위 호환성을 위한 개별 플래그도 함께 설정
        if enabled:
            # 통합 스타일을 활성화하면 모든 개별 설정도 활성화
            button.custom_size = True
            button.custom_font = True
            button.custom_color = True
            self.button_data[button_idx]["custom_size"] = True
            self.button_data[button_idx]["custom_font"] = True
            self.button_data[button_idx]["custom_color"] = True
        else:
            # 통합 스타일을 비활성화하면 모든 개별 설정도 비활성화
            button.custom_size = False
            button.custom_font = False
            button.custom_color = False
            self.button_data[button_idx]["custom_size"] = False
            self.button_data[button_idx]["custom_font"] = False
            self.button_data[button_idx]["custom_color"] = False
        
        # 버튼 스타일 업데이트
        button.update_selection_style()
        
        # 설정 저장
        self.save_current_set()
        self.save_sets()

    def edit_button_style(self, button):
        """버튼 통합 스타일 편집"""
        button_idx = self.buttons.index(button)
        if button_idx < 0 or button_idx >= len(self.buttons):
            return
        
        current_data = self.button_data[button_idx]
        
        # 현재 스타일 정보 가져오기
        dialog = ButtonStyleDialog(
            button.main_label,
            button.sub_label,
            current_data["text"],
            button.width(),
            button.height(),
            button.font(),
            button.palette().color(QPalette.ButtonText),
            parent=self
        )
        
        if dialog.exec_():
            values = dialog.get_values()
            
            # 버튼 텍스트 및 크기 업데이트
            button.set_main_label(values["label"])
            button.set_sub_label(values["label2"])
            button.setFixedSize(values["width"], values["height"])
            
            # 버튼 글꼴 및 색상 업데이트
            button.setFont(values["font"])
            palette = button.palette()
            palette.setColor(QPalette.ButtonText, values["color"])
            button.setPalette(palette)
            
            # 버튼 데이터 업데이트
            self.button_data[button_idx]["label"] = values["label"]
            self.button_data[button_idx]["label2"] = values["label2"]
            self.button_data[button_idx]["text"] = values["text"]
            self.button_data[button_idx]["width"] = values["width"]
            self.button_data[button_idx]["height"] = values["height"]
            
            # 스타일이 변경되었으므로 통합 스타일 플래그 활성화
            if not button.custom_style:
                button.custom_style = True
                self.button_data[button_idx]["custom_style"] = True
                
                # 하위 호환성을 위한 개별 플래그도 설정
                button.custom_size = True
                button.custom_font = True
                button.custom_color = True
                self.button_data[button_idx]["custom_size"] = True
                self.button_data[button_idx]["custom_font"] = True
                self.button_data[button_idx]["custom_color"] = True
            
            # 스타일 및 선택 상태 업데이트
            button.update_selection_style()
            
            # 세트 데이터 갱신
            self.save_current_set()
            self.save_sets()

    def keyPressEvent(self, event):
        """키보드 이벤트 처리"""
        # Delete 키 처리 - 편집 모드일 때만
        if event.key() == Qt.Key_Delete and self.edit_mode:
            self.delete_selected_items()
        # Ctrl+C 복사 처리
        elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_C and self.edit_mode:
            self.copy_selected_widgets_to_clipboard()
        # Ctrl+V 붙여넣기 처리
        elif event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_V and self.edit_mode:
            # 마우스 커서 위치를 붙여넣기 위치로 사용
            cursor_pos = QCursor.pos()
            container_pos = self.buttons_container.mapFromGlobal(cursor_pos)
            self.paste_widgets_from_clipboard(container_pos)
        else:
            super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        """이벤트 필터 - 편집 모드 단축키(Delete, Ctrl+C/V)만 가로채고 나머지는 그대로 전달"""
        if event.type() == QEvent.KeyPress and self.edit_mode:
            key = event.key()
            ctrl = bool(event.modifiers() & Qt.ControlModifier)
            if key == Qt.Key_Delete or (ctrl and key in (Qt.Key_C, Qt.Key_V)):
                self.keyPressEvent(event)
                return True
        return super().eventFilter(obj, event)
    
    def get_all_selected_widgets(self):
        """선택된 모든 위젯(버튼, 텍스트 박스) 반환"""
        selected_widgets = []
        
        # 선택된 버튼 추가
        for button in self.buttons:
            if button.is_selected:
                selected_widgets.append(button)
        
        # 선택된 텍스트 박스 추가
        for textbox in self.textboxes:
            if textbox.is_selected:
                selected_widgets.append(textbox)
        
        return selected_widgets
    
    def clear_all_selections(self):
        """모든 위젯 선택 해제"""
        # 버튼 선택 해제
        for button in self.buttons:
            button.set_selected(False)
        
        # 텍스트 박스 선택 해제
        for textbox in self.textboxes:
            textbox.set_selected(False)
    
    def select_widgets_in_rect(self, rect):
        """지정된 영역 내의 위젯 선택"""
        # 영역 내 버튼 선택
        for button in self.buttons:
            button_rect = button.geometry()
            if rect.intersects(button_rect):
                button.set_selected(True)
        
        # 영역 내 텍스트 박스 선택
        for textbox in self.textboxes:
            textbox_rect = textbox.geometry()
            if rect.intersects(textbox_rect):
                textbox.set_selected(True)
    
    def delete_selected_items(self):
        """선택된 모든 위젯 삭제"""
        # 삭제할 버튼 목록 생성 (역순으로 처리하기 위해)
        buttons_to_delete = [(i, button) for i, button in enumerate(self.buttons) if button.is_selected]
        
        # 버튼 삭제 (인덱스가 변경되지 않도록 역순으로 처리)
        if buttons_to_delete:
            for idx, button in sorted(buttons_to_delete, key=lambda x: x[0], reverse=True):
                # 버튼과 데이터 삭제
                self.button_data.pop(idx)
                self.buttons.pop(idx)
                button.deleteLater()
        
        # 삭제할 텍스트 박스 목록 생성
        textboxes_to_delete = [(i, textbox) for i, textbox in enumerate(self.textboxes) if textbox.is_selected]
        
        # 텍스트 박스 삭제 (역순으로 처리)
        if textboxes_to_delete:
            for idx, textbox in sorted(textboxes_to_delete, key=lambda x: x[0], reverse=True):
                # 텍스트 박스와 데이터 삭제
                self.textbox_data.pop(idx)
                self.textboxes.pop(idx)
                textbox.deleteLater()
        
        # 세트 데이터 갱신 및 저장
        if buttons_to_delete or textboxes_to_delete:
            self.save_current_set()
            self.save_sets()
        
        # 컨테이너 크기 업데이트
        self.buttons_container.updateMinimumSize()
    
    def toggle_custom_setting(self, button, setting_type, enabled):
        """버튼의 개별 설정 상태 토글"""
        button_idx = self.buttons.index(button)
        if button_idx < 0 or button_idx >= len(self.buttons):
            return
        
        if setting_type == "size":
            button.custom_size = enabled
            self.button_data[button_idx]["custom_size"] = enabled
        elif setting_type == "font":
            button.custom_font = enabled
            self.button_data[button_idx]["custom_font"] = enabled
        elif setting_type == "color":
            button.custom_color = enabled
            self.button_data[button_idx]["custom_color"] = enabled
        
        # 버튼에 시각적 표시 (테두리 색상 변경)
        button.update_selection_style()
        
        # 설정 저장
        self.save_current_set()
        self.save_sets()
    
    def toggle_textbox_custom_setting(self, textbox, setting_type, enabled):
        """텍스트 박스의 개별 설정 상태 토글"""
        textbox_idx = self.textboxes.index(textbox)
        if textbox_idx < 0 or textbox_idx >= len(self.textboxes):
            return
        
        if setting_type == "size":
            textbox.custom_size = enabled
            self.textbox_data[textbox_idx]["custom_size"] = enabled
        elif setting_type == "font":
            textbox.custom_font = enabled
            self.textbox_data[textbox_idx]["custom_font"] = enabled
        elif setting_type == "color":
            textbox.custom_color = enabled
            self.textbox_data[textbox_idx]["custom_color"] = enabled
        
        # 텍스트 박스에 시각적 표시
        textbox.update_selection_style()
        
        # 설정 저장
        self.save_current_set()
        self.save_sets()
    
    def reset_all_custom_settings(self):
        """모든 버튼과 텍스트 박스의 개별 설정 초기화"""
        # 확인 대화상자
        reply = QMessageBox.question(
            self, 
            '개별 설정 초기화', 
            '모든 버튼과 텍스트 박스의 개별 설정을 초기화하시겠습니까?\n이 작업은 되돌릴 수 없습니다.',
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 모든 버튼의 개별 설정 초기화
        for i, button in enumerate(self.buttons):
            button.custom_size = False
            button.custom_font = False
            button.custom_color = False
            self.button_data[i]["custom_size"] = False
            self.button_data[i]["custom_font"] = False
            self.button_data[i]["custom_color"] = False
            button.update_selection_style()
        
        # 모든 텍스트 박스의 개별 설정 초기화
        for i, textbox in enumerate(self.textboxes):
            textbox.custom_size = False
            textbox.custom_font = False
            textbox.custom_color = False
            self.textbox_data[i]["custom_size"] = False
            self.textbox_data[i]["custom_font"] = False
            self.textbox_data[i]["custom_color"] = False
            textbox.update_selection_style()
        
        # 메시지 표시
        QMessageBox.information(self, '초기화 완료', '모든 위젯의 개별 설정이 초기화되었습니다.')
        
        # 설정 저장
        self.save_current_set()
        self.save_sets()
    
    def update_widget_data(self):
        """위젯 위치 데이터 업데이트"""
        # 세트 데이터 갱신 및 저장
        self.save_current_set()
        self.save_sets()
    
    def set_list_drop_event(self, event):
        """세트 리스트 드롭 이벤트 처리"""
        # 드롭 전 세트 이름 목록 저장 (안전장치)
        original_set_names = [self.button_sets[i].name for i in range(len(self.button_sets))]
        
        # 표준 드롭 이벤트 처리
        QListWidget.dropEvent(self.set_list, event)
        
        # 드롭 후 현재 세트 목록 확인
        current_items = []
        for i in range(self.set_list.count()):
            current_items.append(self.set_list.item(i).text())
        
        # 세트가 누락되었는지 확인
        missing_sets = [name for name in original_set_names if name not in current_items]
        
        # 누락된 세트가 있으면 복원
        if missing_sets:
            print(f"누락된 세트 발견: {missing_sets}")
            # 원래 세트 목록 유지하고 순서만 변경
            self.set_list.clear()
            for name in original_set_names:
                self.set_list.addItem(DraggableSetItem(name))
            
            # 사용자에게 알림
            QMessageBox.warning(self, "주의", "세트 순서 변경 중 오류가 발생했습니다.\n원래 순서를 유지합니다.")
            return
        
        # 세트 순서 재정렬
        self.reorder_sets()
        
        # 자동 저장
        self.save_sets()
    
    def reorder_sets(self):
        """세트 리스트 드래그앤드롭 후 데이터 재정렬"""
        # 모든 세트의 이름 보존 (참조용)
        original_set_names = [set_obj.name for set_obj in self.button_sets]
        
        # 새 순서로 세트 재배열
        new_sets = []
        new_set_names = []
        
        # UI에서 현재 표시된 순서대로 세트 정렬
        for i in range(self.set_list.count()):
            item = self.set_list.item(i)
            set_name = item.text()
            new_set_names.append(set_name)
            
            # 이름으로 버튼 세트 찾기
            found = False
            for set_obj in self.button_sets:
                if set_obj.name == set_name:
                    new_sets.append(set_obj)
                    found = True
                    break
            
            if not found:
                print(f"경고: '{set_name}' 세트를 찾을 수 없습니다.")
        
        # 세트가 누락되었는지 확인
        missing_sets = [name for name in original_set_names if name not in new_set_names]
        if missing_sets:
            print(f"누락된 세트 발견 (reorder_sets): {missing_sets}")
            # 누락된 세트 복원
            for name in missing_sets:
                for set_obj in self.button_sets:
                    if set_obj.name == name and set_obj not in new_sets:
                        new_sets.append(set_obj)
                        break
        
        # 현재 세트 인덱스 업데이트
        current_set_name = self.button_sets[self.current_set_index].name if self.current_set_index < len(self.button_sets) else None
        
        # 세트 목록 업데이트
        self.button_sets = new_sets
        
        # 현재 세트 인덱스 찾기
        if current_set_name:
            for i, set_obj in enumerate(self.button_sets):
                if set_obj.name == current_set_name:
                    self.current_set_index = i
                    break
        else:
            # 잘못된 인덱스인 경우 첫 번째 세트로 설정
            self.current_set_index = 0 if self.button_sets else -1
    
    def update_set_list(self):
        """세트 리스트 UI 업데이트"""
        self.set_list.clear()
        
        for i, set_obj in enumerate(self.button_sets):
            item = DraggableSetItem(set_obj.name)
            
            # 개별 스타일 설정이 있는지 확인
            if hasattr(set_obj, 'individual_style') and set_obj.individual_style:
                # 개별 스타일 속성 적용
                item.individual_style = True
                
                if hasattr(set_obj, 'font'):
                    font_dict = set_obj.font
                    font = QFont(font_dict.get('family', "맑은 고딕"))
                    font.setPointSize(font_dict.get('point_size', 10))
                    font.setWeight(font_dict.get('weight', QFont.Normal))
                    font.setItalic(font_dict.get('italic', False))
                    font.setBold(font_dict.get('bold', False))
                    item.setFont(font)
                
                if hasattr(set_obj, 'text_color'):
                    item.setForeground(QColor(set_obj.text_color))
                
                if hasattr(set_obj, 'bg_color'):
                    item.setBackground(QColor(set_obj.bg_color))
            else:
                # 기본 스타일 적용
                item.setForeground(self.set_list_color)
                item.setFont(self.set_list_font)
            
            self.set_list.addItem(item)
        
        # 교차 배경색 적용
        self.apply_alternating_row_colors()
    
    def apply_alternating_row_colors(self):
        """세트 리스트에 교차 배경색 적용"""
        # Qt 기본 교차색 기능은 쓰지 않고 항목별로 직접 색을 칠한다
        self.set_list.setAlternatingRowColors(False)

        for i in range(self.set_list.count()):
            item = self.set_list.item(i)

            # 개별 스타일이 적용된 항목은 건너뛰기
            if hasattr(item, 'individual_style') and item.individual_style:
                continue

            if self.use_alternating_colors:
                # 짝수/홀수 행에 사용자가 지정한 배경색 적용
                item.setBackground(self.even_row_color if i % 2 == 0 else self.odd_row_color)
            else:
                # 교차 배경색 미사용 시 기본 흰색
                item.setBackground(QColor("#FFFFFF"))

    
    def set_list_row_colors(self):
        """세트 리스트 행 배경색 설정 대화상자"""
        dialog = QDialog(self)
        dialog.setWindowTitle("세트 리스트 배경색 설정")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # 교차 배경색 사용 여부 체크박스
        use_colors_checkbox = QCheckBox("교차 배경색 사용")
        use_colors_checkbox.setChecked(self.use_alternating_colors)
        
        # 짝수 행 색상 선택 버튼
        even_row_layout = QHBoxLayout()
        even_row_label = QLabel("짝수 행 배경색:")
        even_row_color_button = QPushButton()
        even_row_color_button.setFixedSize(50, 25)
        even_row_color_button.setStyleSheet(f"background-color: {self.even_row_color.name()};")
        
        even_row_layout.addWidget(even_row_label)
        even_row_layout.addWidget(even_row_color_button)
        even_row_layout.addStretch()
        
        # 홀수 행 색상 선택 버튼
        odd_row_layout = QHBoxLayout()
        odd_row_label = QLabel("홀수 행 배경색:")
        odd_row_color_button = QPushButton()
        odd_row_color_button.setFixedSize(50, 25)
        odd_row_color_button.setStyleSheet(f"background-color: {self.odd_row_color.name()};")
        
        odd_row_layout.addWidget(odd_row_label)
        odd_row_layout.addWidget(odd_row_color_button)
        odd_row_layout.addStretch()
        
        # 미리보기 위젯
        preview_label = QLabel("미리보기:")
        preview_list = QListWidget()
        for i in range(5):
            item = QListWidgetItem(f"세트 {i+1} 미리보기")
            if i % 2 == 0:
                item.setBackground(self.even_row_color)
            else:
                item.setBackground(self.odd_row_color)
            preview_list.addItem(item)
        preview_list.setFixedHeight(120)
        
        # 색상 선택 이벤트 연결
        def select_even_row_color():
            color = QColorDialog.getColor(self.even_row_color, dialog)
            if color.isValid():
                even_row_color_button.setStyleSheet(f"background-color: {color.name()};")
                # 미리보기 업데이트
                for i in range(0, preview_list.count(), 2):
                    preview_list.item(i).setBackground(color)
        
        def select_odd_row_color():
            color = QColorDialog.getColor(self.odd_row_color, dialog)
            if color.isValid():
                odd_row_color_button.setStyleSheet(f"background-color: {color.name()};")
                # 미리보기 업데이트
                for i in range(1, preview_list.count(), 2):
                    preview_list.item(i).setBackground(color)
        
        # 체크박스 상태 변경 이벤트 연결
        def toggle_color_controls(checked):
            even_row_color_button.setEnabled(checked)
            odd_row_color_button.setEnabled(checked)
            # 미리보기 업데이트
            if not checked:
                for i in range(preview_list.count()):
                    preview_list.item(i).setBackground(QColor("#FFFFFF"))
            else:
                for i in range(preview_list.count()):
                    if i % 2 == 0:
                        preview_list.item(i).setBackground(QColor(even_row_color_button.palette().button().color()))
                    else:
                        preview_list.item(i).setBackground(QColor(odd_row_color_button.palette().button().color()))
        
        even_row_color_button.clicked.connect(select_even_row_color)
        odd_row_color_button.clicked.connect(select_odd_row_color)
        use_colors_checkbox.toggled.connect(toggle_color_controls)
        
        # 초기 상태 설정
        even_row_color_button.setEnabled(self.use_alternating_colors)
        odd_row_color_button.setEnabled(self.use_alternating_colors)
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        ok_button = QPushButton("확인")
        cancel_button = QPushButton("취소")
        
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        
        # 레이아웃 구성
        layout.addWidget(use_colors_checkbox)
        layout.addLayout(even_row_layout)
        layout.addLayout(odd_row_layout)
        layout.addWidget(preview_label)
        layout.addWidget(preview_list)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # 대화상자 실행 및 결과 처리
        if dialog.exec_():
            # 설정 저장
            self.use_alternating_colors = use_colors_checkbox.isChecked()
            
            # 색상 버튼의 배경색 가져오기
            even_color_str = even_row_color_button.styleSheet().split("background-color: ")[1].split(";")[0]
            odd_color_str = odd_row_color_button.styleSheet().split("background-color: ")[1].split(";")[0]
            
            self.even_row_color = QColor(even_color_str)
            self.odd_row_color = QColor(odd_color_str)
            
            # 세트 리스트에 교차 배경색 적용
            self.apply_alternating_row_colors()
            
            # 설정 저장
            self.save_sets()
    
    def on_set_selected(self, current_row):
        """세트 선택 이벤트 처리"""
        if current_row >= 0 and current_row < len(self.button_sets):
            # 현재 세트 데이터 저장 (이전 세트에서 변경된 내용 반영)
            if self.current_set_index < len(self.button_sets) and (self.buttons or self.textboxes):
                self.save_current_set()
            
            # 새 세트로 변경
            self.change_button_set(current_row)
    
    def save_current_set(self):
        """현재 세트의 데이터 저장"""
        # 현재 세트의 인덱스가 유효한지 확인
        if self.current_set_index < 0 or self.current_set_index >= len(self.button_sets):
            return

        # 세트 로드가 실패한 상태면 화면에 위젯 일부만 남아 있으므로
        # 그대로 저장하면 세트의 원본 데이터가 부분 상태로 덮어써진다
        if self._current_set_load_failed:
            return
            
        # 현재 버튼 상태를 button_data에 저장
        set_buttons = []
        for i, button in enumerate(self.buttons):
            if i < len(self.button_data):
                # 위치 및 크기 정보 업데이트
                pos = button.pos()
                size = button.size()
                
                set_buttons.append({
                    "label": button.main_label,  # 첫 번째 줄 레이블 저장
                    "label2": button.sub_label,  # 두 번째 줄 레이블 저장
                    "text": self.button_data[i]["text"],
                    "x": pos.x(),
                    "y": pos.y(),
                    "width": size.width(),
                    "height": size.height(),
                    "custom_size": button.custom_size,  # 개별 설정 상태 저장
                    "custom_font": button.custom_font,
                    "custom_color": button.custom_color
                })
        
        # 현재 텍스트 박스 상태 저장
        set_textboxes = []
        for i, textbox in enumerate(self.textboxes):
            if i < len(self.textbox_data):
                # 위치 및 크기 정보 업데이트
                pos = textbox.pos()
                size = textbox.size()
                
                # 글꼴 정보 추출
                font_dict = self.font_to_dict(textbox.font())
                color = textbox.palette().color(QPalette.WindowText).name()
                
                # 배경색 추출 - styleSheet에서 추출
                bg_color = self.textbox_data[i].get("bg_color", "transparent")
                
                set_textboxes.append({
                    "text": textbox.text(),
                    "x": pos.x(),
                    "y": pos.y(),
                    "width": size.width(),
                    "height": size.height(),
                    "font": font_dict,
                    "color": color,
                    "bg_color": bg_color,
                    "custom_size": textbox.custom_size,  # 개별 설정 상태 저장
                    "custom_font": textbox.custom_font,
                    "custom_color": textbox.custom_color
                })
        
        # 세트 데이터 업데이트
        self.button_sets[self.current_set_index].buttons = set_buttons
        self.button_sets[self.current_set_index].textboxes = set_textboxes

        set_index = self.current_set_index
        item = self.set_list.item(set_index) if set_index < self.set_list.count() else None
        if item and hasattr(item, 'individual_style') and item.individual_style:
            self.button_sets[set_index].individual_style = True
            
            # 글꼴 정보 저장
            font = item.font()
            self.button_sets[set_index].font = {
                'family': font.family(),
                'point_size': font.pointSize(),
                'weight': font.weight(),
                'italic': font.italic(),
                'bold': font.bold()
            }
            
            # 색상 정보 저장
            self.button_sets[set_index].text_color = item.foreground().color().name()
            self.button_sets[set_index].bg_color = item.background().color().name()
        else:
            # 개별 스타일 설정 제거 (있는 경우)
            if hasattr(self.button_sets[set_index], 'individual_style'):
                delattr(self.button_sets[set_index], 'individual_style')
            if hasattr(self.button_sets[set_index], 'font'):
                delattr(self.button_sets[set_index], 'font')
            if hasattr(self.button_sets[set_index], 'text_color'):
                delattr(self.button_sets[set_index], 'text_color')
            if hasattr(self.button_sets[set_index], 'bg_color'):
                delattr(self.button_sets[set_index], 'bg_color')
    
    def change_button_set(self, set_index):
        """버튼 세트 변경"""
        # 인덱스 유효성 검사
        if set_index < 0 or set_index >= len(self.button_sets):
            print(f"유효하지 않은 세트 인덱스: {set_index}, 세트 수: {len(self.button_sets)}")
            return
        
        # 이전 버튼 정리
        for button in self.buttons:
            button.deleteLater()
        
        self.buttons = []
        self.button_data = []
        
        # 이전 텍스트 박스 정리
        for textbox in self.textboxes:
            textbox.deleteLater()
        
        self.textboxes = []
        self.textbox_data = []
        
        # 새 세트 로드
        self.current_set_index = set_index
        current_set = self.button_sets[set_index]
        self._current_set_load_failed = True  # 로드가 끝까지 성공해야 False로 전환

        try:
            # 세트의 버튼 생성
            for button_info in current_set.buttons:
                # 위치 및 크기 정보 추출
                x = button_info.get("x", 10)
                y = button_info.get("y", 10)
                width = button_info.get("width", self.button_width)
                height = button_info.get("height", self.button_height)
                
                # 두 번째 줄 레이블 정보 추출 (하위 호환성)
                label2 = button_info.get("label2", "")
                
                # 개별 설정 상태 추출
                custom_size = button_info.get("custom_size", False)
                custom_font = button_info.get("custom_font", False)
                custom_color = button_info.get("custom_color", False)
                
                self.create_button(button_info["label"], button_info["text"], x, y, width, height, label2)
                
                # 마지막에 생성된 버튼의 개별 설정 상태 설정
                if len(self.buttons) > 0:
                    button = self.buttons[-1]
                    button.custom_size = custom_size
                    button.custom_font = custom_font
                    button.custom_color = custom_color
                    button.update_selection_style()
            
            # 세트의 텍스트 박스 생성
            if hasattr(current_set, 'textboxes'):
                for textbox_info in current_set.textboxes:
                    # 위치 및 크기 정보 추출
                    x = textbox_info.get("x", 10)
                    y = textbox_info.get("y", 10)
                    width = textbox_info.get("width", self.textbox_width)
                    height = textbox_info.get("height", self.textbox_height)
                    
                    # 글꼴 정보 추출
                    font_dict = textbox_info.get("font", self.font_to_dict(self.button_font))
                    font = self.dict_to_font(font_dict)
                    
                    # 색상 정보 추출
                    color = QColor(textbox_info.get("color", "#000000"))
                    bg_color = QColor(textbox_info.get("bg_color", "transparent"))
                    
                    # 개별 설정 상태 추출
                    custom_size = textbox_info.get("custom_size", False)
                    custom_font = textbox_info.get("custom_font", False)
                    custom_color = textbox_info.get("custom_color", False)
                    
                    self.create_textbox(textbox_info["text"], x, y, width, height, font, color, bg_color)
                    
                    # 마지막에 생성된 텍스트 박스의 개별 설정 상태 설정
                    if len(self.textboxes) > 0:
                        textbox = self.textboxes[-1]
                        textbox.custom_size = custom_size
                        textbox.custom_font = custom_font
                        textbox.custom_color = custom_color
                        textbox.update_selection_style()
            
            # 모든 위젯 생성 성공 - 이제 화면 상태가 세트 데이터와 일치함
            self._current_set_load_failed = False

            # 타이틀 업데이트
            self.update_edit_mode_display()

            # 컨테이너 크기 업데이트
            self.buttons_container.updateMinimumSize()

            # 자동 저장
            self.save_sets()
        except Exception as e:
            print(f"버튼 세트 변경 중 오류: {e}")
            # 오류 발생 시 기본 타이틀 설정
            if self.edit_mode:
                self.setWindowTitle(f'퀵버튼 매크로 - {current_set.name} [편집 모드]')
            else:
                self.setWindowTitle(f'퀵버튼 매크로 - {current_set.name}')
    
    def add_set(self):
        """새 버튼 세트 추가"""
        dialog = SetNameDialog(parent=self)
        if dialog.exec_():
            set_name = dialog.get_value()
            if set_name:
                # 이름 중복 확인 및 고유 이름 생성
                original_name = set_name
                name_counter = 1
                
                # 이름이 중복될 경우 번호를 붙여 고유한 이름 생성
                while any(set_obj.name == set_name for set_obj in self.button_sets):
                    name_counter += 1
                    set_name = f"{original_name} {name_counter}"
                
                # 이름이 변경된 경우 사용자에게 알림
                if set_name != original_name:
                    QMessageBox.information(self, "이름 자동 변경", f"이미 같은 이름의 세트가 있어 '{set_name}'(으)로 이름이 변경되었습니다.")
                
                # 새 세트 추가
                self.button_sets.append(ButtonSet(set_name))
                
                # UI 업데이트
                self.update_set_list()
                
                # 새 세트 선택
                self.set_list.setCurrentRow(len(self.button_sets) - 1)
                
                # 자동 저장
                self.save_sets()
    
    def edit_set(self, set_index):
        """세트 이름 편집"""
        if set_index < 0 or set_index >= len(self.button_sets):
            return
        
        current_name = self.button_sets[set_index].name
        dialog = SetNameDialog(current_name, parent=self)
        
        if dialog.exec_():
            new_name = dialog.get_value()
            if new_name and new_name != current_name:  # 이름이 변경된 경우에만 처리
                # 이름 중복 확인 및 고유 이름 생성
                original_name = new_name
                name_counter = 1
                
                # 현재 편집 중인 세트를 제외한 다른 세트와 이름 중복 확인
                while any(set_obj.name == new_name and self.button_sets.index(set_obj) != set_index 
                           for set_obj in self.button_sets):
                    name_counter += 1
                    new_name = f"{original_name} {name_counter}"
                
                # 이름이 자동으로 변경된 경우 사용자에게 알림
                if new_name != original_name:
                    QMessageBox.information(self, "이름 자동 변경", f"이미 같은 이름의 세트가 있어 '{new_name}'(으)로 이름이 변경되었습니다.")
                
                # 세트 이름 변경
                self.button_sets[set_index].name = new_name
                
                # UI 업데이트
                self.update_set_list()
                self.set_list.setCurrentRow(set_index)
                
                # 타이틀 업데이트
                if set_index == self.current_set_index:
                    self.update_edit_mode_display()
                
                # 자동 저장
                self.save_sets()
    
    def delete_set(self, set_index):
        """세트 삭제"""
        if set_index < 0 or set_index >= len(self.button_sets):
            return
        
        # 마지막 세트는 삭제 불가
        if len(self.button_sets) <= 1:
            QMessageBox.warning(self, "삭제 불가", "최소 하나의 세트는 유지해야 합니다.")
            return
        
        # 확인 대화상자
        reply = QMessageBox.question(self, '세트 삭제', 
                                     f'"{self.button_sets[set_index].name}" 세트를 삭제하시겠습니까?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # 현재 선택된 세트가 삭제 대상이면 다른 세트로 전환
            if set_index == self.current_set_index:
                next_index = max(0, set_index - 1) if set_index > 0 else min(1, len(self.button_sets) - 1)
                self.change_button_set(next_index)
            
            # 세트 삭제
            del self.button_sets[set_index]
            
            # UI 업데이트
            self.update_set_list()
            
            # 인덱스 조정
            if self.current_set_index > set_index:
                self.current_set_index -= 1
            
            # 현재 세트에 맞는 항목 선택
            self.set_list.setCurrentRow(self.current_set_index)
            
            # 자동 저장
            self.save_sets()
    
    def copy_set(self, set_index):
        """세트 복사"""
        if set_index < 0 or set_index >= len(self.button_sets):
            return
        
        # 원본 세트 복사
        original_set = self.button_sets[set_index]
        base_name = f"{original_set.name} 복사본"
        
        # 이름 중복 확인 및 고유 이름 생성
        new_set_name = base_name
        name_counter = 1
        
        # 이름이 중복될 경우 번호를 붙여 고유한 이름 생성
        while any(set_obj.name == new_set_name for set_obj in self.button_sets):
            name_counter += 1
            new_set_name = f"{base_name} {name_counter}"
        
        # 이름이 기본 복사본 이름과 다르면 사용자에게 알림
        if new_set_name != base_name:
            QMessageBox.information(self, "이름 자동 생성", f"이미 같은 이름의 세트가 있어 '{new_set_name}'(으)로 이름이 생성되었습니다.")
        
        # 복사할 버튼 데이터 생성
        new_buttons = copy.deepcopy(original_set.buttons)
        new_textboxes = copy.deepcopy(original_set.textboxes) if hasattr(original_set, 'textboxes') else []
        
        # 새 세트 추가
        self.button_sets.append(ButtonSet(new_set_name, new_buttons, new_textboxes))
        
        # UI 업데이트
        self.update_set_list()
        
        # 새 세트 선택
        self.set_list.setCurrentRow(len(self.button_sets) - 1)
        
        # 자동 저장
        self.save_sets()
    
    def quick_edit_buttons(self, set_index):
        """퀵버튼 빠른 편집 기능"""
        if set_index < 0 or set_index >= len(self.button_sets):
            return
        
        # 현재 세트의 데이터 저장 (다른 세트 편집 시)
        if self.current_set_index != set_index and self.current_set_index < len(self.button_sets) and (self.buttons or self.textboxes):
            self.save_current_set()
        
        # 선택한 세트의 버튼 데이터 가져오기
        button_set = self.button_sets[set_index]
        buttons_data = []
        
        # x, y 위치 정보 제거한 데이터 생성
        for button_info in button_set.buttons:
            # 개별 설정 상태도 보존
            buttons_data.append({
                "label": button_info["label"],
                "label2": button_info.get("label2", ""),
                "text": button_info["text"],
                "custom_size": button_info.get("custom_size", False),
                "custom_font": button_info.get("custom_font", False),
                "custom_color": button_info.get("custom_color", False)
            })
        
        # 편집 대화상자 표시
        dialog = QuickEditDialog(buttons_data, self)
        
        if dialog.exec_():
            # 대화상자에서 편집된 버튼 데이터 가져오기
            new_buttons_data = dialog.get_buttons_data()
            
            # 이전 버튼의 위치 정보와 개별 설정 상태 유지하면서 새 데이터 적용
            updated_buttons = []
            for i, new_button in enumerate(new_buttons_data):
                if i < len(button_set.buttons):
                    # 기존 버튼의 위치와 크기 정보 유지
                    old_button = button_set.buttons[i]
                    new_button["x"] = old_button.get("x", 10)
                    new_button["y"] = old_button.get("y", 10)
                    new_button["width"] = old_button.get("width", self.button_width)
                    new_button["height"] = old_button.get("height", self.button_height)
                    
                    # 개별 설정 상태도 유지
                    new_button["custom_size"] = old_button.get("custom_size", False)
                    new_button["custom_font"] = old_button.get("custom_font", False)
                    new_button["custom_color"] = old_button.get("custom_color", False)
                updated_buttons.append(new_button)
            
            # 남은 버튼은 기본 위치에 배치
            for i in range(len(button_set.buttons), len(new_buttons_data)):
                x = 10 + (i % 3) * (self.button_width + 10)
                y = 10 + (i // 3) * (self.button_height + 10)
                new_buttons_data[i]["x"] = x
                new_buttons_data[i]["y"] = y
            
            # 버튼 세트 업데이트 - 텍스트 박스는 유지
            button_set.buttons = new_buttons_data
            
            # 현재 세트가 편집된 세트라면 UI 업데이트
            if self.current_set_index == set_index:
                # 기존 버튼 정리
                for button in self.buttons:
                    button.deleteLater()
                
                self.buttons = []
                self.button_data = []
                
                # 새 버튼 생성
                for button_info in new_buttons_data:
                    self.create_button(
                        button_info["label"], 
                        button_info["text"],
                        button_info["x"],
                        button_info["y"],
                        button_info["width"],
                        button_info["height"],
                        button_info.get("label2", "")  # 두 번째 줄 레이블
                    )
                    
                    # 마지막 생성된 버튼의 개별 설정 상태 설정
                    if len(self.buttons) > 0:
                        button = self.buttons[-1]
                        button.custom_size = button_info.get("custom_size", False)
                        button.custom_font = button_info.get("custom_font", False)
                        button.custom_color = button_info.get("custom_color", False)
                        button.update_selection_style()
            
            # 변경 사항 저장
            self.save_sets()

    def quick_edit_selected_buttons(self):
        """선택된 여러 버튼을 빠르게 편집하는 기능"""
        # 선택된 모든 버튼 가져오기
        selected_buttons = [button for button in self.buttons if button.is_selected]

        if not selected_buttons:
            QMessageBox.warning(self, "빠른 편집", "선택된 버튼이 없습니다.")
            return

        # 빠른 편집 대화상자용 데이터 준비
        buttons_data = []
        for button in selected_buttons:
            button_idx = self.buttons.index(button)
            if button_idx >= 0 and button_idx < len(self.button_data):
                buttons_data.append({
                    "label": button.main_label,
                    "label2": button.sub_label,
                    "text": self.button_data[button_idx]["text"],
                    "custom_size": button.custom_size,
                    "custom_font": button.custom_font,
                    "custom_color": button.custom_color
                })

        # 버튼이 없으면 종료
        if not buttons_data:
            return

        # 편집 대화상자 표시
        dialog = QuickEditDialog(buttons_data, self)
        if dialog.exec_():
            # 대화상자에서 편집된 버튼 데이터 가져오기
            updated_buttons_data = dialog.get_buttons_data()

            # 만약 버튼 수가 변경되었다면 첫 버튼 수까지만 적용
            max_count = min(len(selected_buttons), len(updated_buttons_data))

            # 업데이트된 데이터를 선택된 버튼들에 적용
            for i in range(max_count):
                button = selected_buttons[i]
                updated_data = updated_buttons_data[i]
                button_idx = self.buttons.index(button)
                
                # 버튼 텍스트 업데이트
                button.set_main_label(updated_data["label"])
                button.set_sub_label(updated_data.get("label2", ""))
                
                # 버튼 데이터 업데이트
                if button_idx >= 0 and button_idx < len(self.button_data):
                    self.button_data[button_idx]["label"] = updated_data["label"]
                    self.button_data[button_idx]["label2"] = updated_data.get("label2", "")
                    self.button_data[button_idx]["text"] = updated_data["text"]

            # 변경 사항 저장
            self.save_current_set()
            self.save_sets()

            # 완료 메시지
            count = len(selected_buttons)
            QMessageBox.information(self, "빠른 편집", f"{count}개의 선택된 버튼이 성공적으로 편집되었습니다.")

    
    def show_set_menu(self, position):
        """세트 컨텍스트 메뉴 표시"""
        # 선택된 세트 인덱스 가져오기
        selected_item = self.set_list.itemAt(position)
        if not selected_item:
            # 빈 공간 클릭 시 일반 메뉴 표시
            menu = QMenu()
            add_set_action = QAction("세트 추가", self)
            add_set_action.triggered.connect(self.add_set)
            row_color_action = QAction("세트 리스트 배경색 설정", self)
            row_color_action.triggered.connect(self.set_list_row_colors)
            menu.addAction(add_set_action)
            menu.addAction(row_color_action)
            menu.exec_(self.set_list.mapToGlobal(position))
            return

        set_index = self.set_list.row(selected_item)

        # 메뉴 생성
        menu = QMenu()
        edit_action = QAction("이름 변경", self)
        edit_action.triggered.connect(lambda: self.edit_set(set_index))
        delete_action = QAction("삭제", self)
        delete_action.triggered.connect(lambda: self.delete_set(set_index))
        copy_action = QAction("복사", self)
        copy_action.triggered.connect(lambda: self.copy_set(set_index))
        
        # 개별 스타일 설정 토글 액션 추가
        individual_style_action = QAction("개별 스타일 설정 사용", self)
        individual_style_action.setCheckable(True)
        individual_style_action.setChecked(getattr(selected_item, 'individual_style', False))
        individual_style_action.triggered.connect(lambda checked: self.toggle_individual_style(set_index, checked))
        
        # 새 메뉴 항목 추가
        quick_edit_action = QAction("퀵버튼 빠른 편집", self)
        quick_edit_action.triggered.connect(lambda: self.quick_edit_buttons(set_index))

        # 배경색 설정 메뉴 추가
        row_color_action = QAction("세트 리스트 배경색 설정", self)
        row_color_action.triggered.connect(self.set_list_row_colors)

        # 개별 설정 초기화 메뉴 (현재 세트에만 적용)
        reset_custom_settings = QAction("개별 설정 초기화", self)
        reset_custom_settings.triggered.connect(self.reset_all_custom_settings)

        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addAction(copy_action)
        menu.addSeparator()  # 구분선 추가
        menu.addAction(quick_edit_action)
        menu.addAction(individual_style_action)  # 개별 스타일 설정 메뉴 추가
        
        # 개별 스타일이 활성화된 경우에만 스타일 설정 메뉴 표시
        if getattr(selected_item, 'individual_style', False):
            customize_style_action = QAction("스타일 설정", self)
            customize_style_action.triggered.connect(lambda: self.customize_set_style(set_index))
            menu.addAction(customize_style_action)
        
        menu.addAction(row_color_action)

        # 현재 세트에서만 개별 설정 초기화 메뉴 표시
        if set_index == self.current_set_index:
            menu.addAction(reset_custom_settings)

        # 메뉴 표시
        menu.exec_(self.set_list.mapToGlobal(position))

    def toggle_individual_style(self, set_index, enabled):
        """세트 항목의 개별 스타일 설정 토글"""
        item = self.set_list.item(set_index)
        if not item:
            return
        
        # 개별 스타일 속성 설정
        item.individual_style = enabled
        
        # ButtonSet 객체에도 개별 스타일 속성 설정
        if set_index < len(self.button_sets):
            if enabled:
                self.button_sets[set_index].individual_style = True
                
                # 현재 폰트와 색상도 함께 저장
                font = item.font()
                self.button_sets[set_index].font = {
                    'family': font.family(),
                    'point_size': font.pointSize(),
                    'weight': font.weight(),
                    'italic': font.italic(),
                    'bold': font.bold()
                }
                self.button_sets[set_index].text_color = item.foreground().color().name()
                self.button_sets[set_index].bg_color = item.background().color().name()
            else:
                # 개별 스타일 설정 제거
                if hasattr(self.button_sets[set_index], 'individual_style'):
                    delattr(self.button_sets[set_index], 'individual_style')
                if hasattr(self.button_sets[set_index], 'font'):
                    delattr(self.button_sets[set_index], 'font')
                if hasattr(self.button_sets[set_index], 'text_color'):
                    delattr(self.button_sets[set_index], 'text_color')
                if hasattr(self.button_sets[set_index], 'bg_color'):
                    delattr(self.button_sets[set_index], 'bg_color')
        
        if not enabled:
            # 개별 스타일 비활성화 시 기본 스타일로 복원
            item.setFont(self.set_list_font)
            item.setForeground(self.set_list_color)
            item.setBackground(QColor("#FFFFFF"))
        
        # 설정 저장
        self.save_sets()

    def customize_set_style(self, set_index):
        """세트 항목의 스타일 설정 대화상자 표시"""
        item = self.set_list.item(set_index)
        if not item:
            return
        
        # 세트 스타일 설정 대화상자 생성
        dialog = QDialog(self)
        dialog.setWindowTitle("세트 스타일 설정")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # 글꼴 설정
        font_group = QGroupBox("글꼴 설정")
        font_layout = QVBoxLayout()
        
        # 현재 글꼴 표시
        current_font = item.font()
        font_label = QLabel(f"현재 글꼴: {current_font.family()}, {current_font.pointSize()}pt")
        font_layout.addWidget(font_label)
        
        # 글꼴 선택 버튼
        font_button = QPushButton("글꼴 선택")
        font_button.clicked.connect(lambda: self._select_set_font(font_label, dialog))
        font_layout.addWidget(font_button)
        
        font_group.setLayout(font_layout)
        
        # 색상 설정
        color_group = QGroupBox("색상 설정")
        color_layout = QVBoxLayout()
        
        # 글꼴 색상 미리보기
        text_color_preview = QLabel("글꼴 색상")
        text_color_preview.setStyleSheet(f"color: {item.foreground().color().name()}; font-weight: bold;")
        color_layout.addWidget(text_color_preview)
        
        # 글꼴 색상 선택 버튼
        text_color_button = QPushButton("글꼴 색상 선택")
        text_color_button.clicked.connect(lambda: self._select_set_text_color(text_color_preview, dialog))
        color_layout.addWidget(text_color_button)
        
        # 배경 색상 미리보기
        bg_color_preview = QLabel("배경 색상")
        bg_color_preview.setStyleSheet(f"background-color: {item.background().color().name()}; padding: 5px;")
        color_layout.addWidget(bg_color_preview)
        
        # 배경 색상 선택 버튼
        bg_color_button = QPushButton("배경 색상 선택")
        bg_color_button.clicked.connect(lambda: self._select_set_bg_color(bg_color_preview, dialog))
        color_layout.addWidget(bg_color_button)
        
        color_group.setLayout(color_layout)
        
        # 미리보기
        preview_group = QGroupBox("미리보기")
        preview_layout = QVBoxLayout()
        
        preview_label = QLabel(item.text())
        preview_label.setFont(current_font)
        preview_label.setStyleSheet(
            f"color: {item.foreground().color().name()}; "
            f"background-color: {item.background().color().name()}; "
            f"padding: 8px; border: 1px solid #A0A0A0;"
        )
        preview_layout.addWidget(preview_label)
        
        preview_group.setLayout(preview_layout)
        
        # 버튼
        button_layout = QHBoxLayout()
        save_button = QPushButton("저장")
        cancel_button = QPushButton("취소")
        
        save_button.clicked.connect(lambda: self._save_set_style(
            set_index, 
            dialog.findChild(QLabel, "font_label").font(),
            QColor(text_color_preview.property("current_color")),
            QColor(bg_color_preview.property("current_color")),
            dialog
        ))
        
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        # 레이아웃 구성
        layout.addWidget(font_group)
        layout.addWidget(color_group)
        layout.addWidget(preview_group)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # 현재 설정을 대화상자의 데이터로 저장
        font_label.setObjectName("font_label")
        font_label.setFont(current_font)
        text_color_preview.setProperty("current_color", item.foreground().color().name())
        bg_color_preview.setProperty("current_color", item.background().color().name())
        
        # 미리보기 업데이트 함수
        def update_preview():
            preview_label.setFont(font_label.font())
            preview_label.setStyleSheet(
                f"color: {text_color_preview.property('current_color')}; "
                f"background-color: {bg_color_preview.property('current_color')}; "
                f"padding: 8px; border: 1px solid #A0A0A0;"
            )
        
        # 이벤트 연결
        font_button.clicked.connect(update_preview)
        text_color_button.clicked.connect(update_preview)
        bg_color_button.clicked.connect(update_preview)
        
        # 대화상자 표시
        dialog.exec_()

    def _select_set_font(self, label, dialog):
        """세트 항목의 글꼴 선택"""
        font, ok = QFontDialog.getFont(label.font(), dialog)
        if ok:
            label.setFont(font)
            label.setText(f"현재 글꼴: {font.family()}, {font.pointSize()}pt")

    def _select_set_text_color(self, label, dialog):
        """세트 항목의 글꼴 색상 선택"""
        current_color = QColor(label.property("current_color"))
        color = QColorDialog.getColor(current_color, dialog)
        if color.isValid():
            label.setProperty("current_color", color.name())
            label.setStyleSheet(f"color: {color.name()}; font-weight: bold;")

    def _select_set_bg_color(self, label, dialog):
        """세트 항목의 배경 색상 선택"""
        current_color = QColor(label.property("current_color"))
        color = QColorDialog.getColor(current_color, dialog)
        if color.isValid():
            label.setProperty("current_color", color.name())
            label.setStyleSheet(f"background-color: {color.name()}; padding: 5px;")

    def _save_set_style(self, set_index, font, text_color, bg_color, dialog):
        """세트 항목의 스타일 설정 저장"""
        item = self.set_list.item(set_index)
        if not item:
            dialog.reject()
            return
        
        # 스타일 적용
        item.setFont(font)
        item.setForeground(text_color)
        item.setBackground(bg_color)
        
        # 개별 스타일 플래그 설정 (혹시 누락된 경우)
        item.individual_style = True
        
        # ButtonSet 객체에도 개별 스타일 정보 저장
        if set_index < len(self.button_sets):
            self.button_sets[set_index].individual_style = True
            
            # 글꼴 정보 저장
            font_dict = {
                'family': font.family(),
                'point_size': font.pointSize(),
                'weight': font.weight(),
                'italic': font.italic(),
                'bold': font.bold()
            }
            self.button_sets[set_index].font = font_dict
            
            # 색상 정보 저장
            self.button_sets[set_index].text_color = text_color.name()
            self.button_sets[set_index].bg_color = bg_color.name()
        
        # 설정 저장
        self.save_sets()
        
        # 대화상자 닫기
        dialog.accept()


    
    def create_button(self, label, text, x=10, y=10, width=None, height=None, label2=""):
        """버튼 생성"""
        if width is None:
            width = self.button_width
        if height is None:
            height = self.button_height
        
        # 버튼 데이터 생성
        button_data = {
            "label": label, 
            "label2": label2, 
            "text": text,
            "custom_style": False,  # 통합 스타일 플래그 추가
            "custom_size": False,  # 기본 상태는 개별 설정 비활성화
            "custom_font": False,
            "custom_color": False
        }
        
        # 버튼 생성
        button = SelectableButton(label, self, x, y, width, height, button_data)
        
        # 버튼 글꼴 및 색상 설정
        button.setFont(self.button_font)
        palette = button.palette()
        palette.setColor(QPalette.ButtonText, self.button_color)
        button.setPalette(palette)
        
        # HTML 콘텐츠 활성화
        button.setStyleSheet("QPushButton { text-align: center; }")
        
        # 우클릭 메뉴 설정
        button.setContextMenuPolicy(Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(lambda pos, b=button: 
                                                 self.show_button_menu(pos, b))
        
        # 버튼을 컨테이너 위젯에 추가
        button.setParent(self.buttons_container)
        button.show()
        
        # 버튼 데이터 저장
        self.buttons.append(button)
        self.button_data.append(button_data)
        
        return button
    
    def create_textbox(self, text, x=10, y=10, width=None, height=None, font=None, color=None, bg_color=None):
        """텍스트 박스 생성"""
        if width is None:
            width = self.textbox_width
        if height is None:
            height = self.textbox_height
        if font is None:
            font = self.button_font
        if color is None:
            color = QColor("#000000")
        if bg_color is None:
            bg_color = QColor("transparent")
        
        # 텍스트 박스 데이터 생성
        textbox_data = {
            "text": text,
            "font": self.font_to_dict(font),
            "color": color.name(),
            "bg_color": bg_color.name(),
            "custom_size": False,  # 기본 상태는 개별 설정 비활성화
            "custom_font": False,
            "custom_color": False
        }
        
        # 텍스트 박스 생성
        textbox = SelectableTextBox(text, self, x, y, width, height, textbox_data)
        
        # 글꼴 및 색상 설정
        textbox.setFont(font)
        palette = textbox.palette()
        palette.setColor(QPalette.WindowText, color)
        textbox.setPalette(palette)
        
        # 스타일시트 설정 (배경색 포함)
        textbox.setStyleSheet(f"color: {color.name()}; background-color: {bg_color.name()}; padding: 8px; border: 1px solid #A0A0A0;")
        
        # 우클릭 메뉴 설정
        textbox.setContextMenuPolicy(Qt.CustomContextMenu)
        textbox.customContextMenuRequested.connect(lambda pos, tb=textbox: 
                                                  self.show_textbox_menu(pos, tb))
        
        # 텍스트 박스를 컨테이너 위젯에 추가
        textbox.setParent(self.buttons_container)
        textbox.show()
        
        # 텍스트 박스 데이터 저장
        self.textboxes.append(textbox)
        self.textbox_data.append(textbox_data)
        
        return textbox
    
    def add_button_dialog(self):
        """새 버튼 추가 대화상자"""
        dialog = ButtonSettingsDialog(parent=self)
        if dialog.exec_():
            label, label2, text = dialog.get_values()
            if label:  # 텍스트는 비어있어도 허용
                # 새 버튼 위치 계산
                x = 10
                y = 10
                
                # 마지막 버튼 위치 기준으로 계산
                if self.buttons:
                    last_button = self.buttons[-1]
                    x = last_button.x() + self.button_width + 10
                    y = last_button.y()
                    
                    # 화면 너비를 초과하면 다음 줄로
                    if x + self.button_width > self.buttons_container.width():
                        x = 10
                        y = last_button.y() + self.button_height + 10
                
                self.create_button(label, text, x, y, None, None, label2)
                
                # 세트 데이터 갱신
                self.save_current_set()
                self.save_sets()
    
    def add_textbox_dialog(self):
        """새 텍스트 박스 추가 대화상자"""
        dialog = TextBoxSettingsDialog(parent=self)
        if dialog.exec_():
            text, font, color, bg_color = dialog.get_values()
            if text:  # 텍스트가 비어 있어도 괜찮음
                # 새 텍스트 박스 위치 계산
                x = 10
                y = 10
                
                # 마지막 텍스트 박스 위치 기준으로 계산
                if self.textboxes:
                    last_textbox = self.textboxes[-1]
                    x = last_textbox.x() + self.textbox_width + 10
                    y = last_textbox.y()
                    
                    # 화면 너비를 초과하면 다음 줄로
                    if x + self.textbox_width > self.buttons_container.width():
                        x = 10
                        y = last_textbox.y() + self.textbox_height + 10
                # 버튼이 있고 텍스트 박스가 없는 경우, 버튼 아래에 배치
                elif self.buttons:
                    # 버튼들 중 가장 낮은 위치 찾기
                    lowest_y = max([button.y() + button.height() for button in self.buttons])
                    x = 10
                    y = lowest_y + 20  # 버튼 아래 여백 추가
                
                self.create_textbox(text, x, y, self.textbox_width, self.textbox_height, font, color, bg_color)
                
                # 세트 데이터 갱신
                self.save_current_set()
                self.save_sets()
    
    def edit_button(self, button):
        """버튼 편집"""
        button_idx = self.buttons.index(button)
        if button_idx < 0 or button_idx >= len(self.buttons):
            return
            
        current_data = self.button_data[button_idx]
        dialog = ButtonSettingsDialog(
            button.main_label,  # 첫 번째 줄 레이블
            button.sub_label,   # 두 번째 줄 레이블
            current_data["text"],
            parent=self
        )
        
        if dialog.exec_():
            label, label2, text = dialog.get_values()
            if label:  # 텍스트는 비어있어도 허용
                # 버튼 레이블 업데이트
                button.set_main_label(label)
                button.set_sub_label(label2)
                
                # 버튼 데이터 업데이트
                self.button_data[button_idx]["label"] = label
                self.button_data[button_idx]["label2"] = label2
                self.button_data[button_idx]["text"] = text
                
                # 세트 데이터 갱신
                self.save_current_set()
                self.save_sets()
    
    def edit_textbox(self, textbox):
        """텍스트 박스 편집"""
        textbox_idx = self.textboxes.index(textbox)
        if textbox_idx < 0 or textbox_idx >= len(self.textboxes):
            return
            
        current_data = self.textbox_data[textbox_idx]
        
        # 현재 글꼴, 색상 정보 가져오기
        font = textbox.font()
        color = textbox.palette().color(QPalette.WindowText)
        
        # 배경색 가져오기 (데이터에서)
        bg_color = QColor(current_data.get("bg_color", "transparent"))
        
        dialog = TextBoxSettingsDialog(textbox.text(), font, color, bg_color, parent=self)
        
        if dialog.exec_():
            text, new_font, new_color, new_bg_color = dialog.get_values()
            
            # 텍스트 박스 업데이트
            textbox.setText(text)
            textbox.setFont(new_font)
            
            palette = textbox.palette()
            palette.setColor(QPalette.WindowText, new_color)
            textbox.setPalette(palette)
            
            # 스타일시트 업데이트 (배경색 포함)
            textbox.setStyleSheet(f"color: {new_color.name()}; background-color: {new_bg_color.name()}; padding: 8px; border: 1px solid #A0A0A0;")
            
            # 텍스트 박스 데이터 업데이트
            self.textbox_data[textbox_idx]["text"] = text
            self.textbox_data[textbox_idx]["font"] = self.font_to_dict(new_font)
            self.textbox_data[textbox_idx]["color"] = new_color.name()
            self.textbox_data[textbox_idx]["bg_color"] = new_bg_color.name()
            
            # 폰트나 색상이 변경됐으면 자동으로 개별 설정 활성화
            if self.textbox_data[textbox_idx]["font"] != self.font_to_dict(self.button_font) or \
               self.textbox_data[textbox_idx]["color"] != self.button_color.name():
                textbox.custom_font = True
                self.textbox_data[textbox_idx]["custom_font"] = True
                
            # 개별 설정 상태에 따라 스타일 업데이트
            textbox.update_selection_style()
            
            # 텍스트 박스 데이터 저장
            textbox.data = self.textbox_data[textbox_idx]
            
            # 세트 데이터 갱신
            self.save_current_set()
            self.save_sets()
    
    def delete_button(self, button):
        """버튼 삭제"""
        button_idx = self.buttons.index(button)
        if button_idx < 0 or button_idx >= len(self.buttons):
            return
            
        # 버튼 삭제
        self.buttons.pop(button_idx)
        self.button_data.pop(button_idx)
        button.deleteLater()
        
        # 세트 데이터 갱신
        self.save_current_set()
        self.save_sets()
    
    def delete_textbox(self, textbox):
        """텍스트 박스 삭제"""
        textbox_idx = self.textboxes.index(textbox)
        if textbox_idx < 0 or textbox_idx >= len(self.textboxes):
            return
            
        # 텍스트 박스 삭제
        self.textboxes.pop(textbox_idx)
        self.textbox_data.pop(textbox_idx)
        textbox.deleteLater()
        
        # 세트 데이터 갱신
        self.save_current_set()
        self.save_sets()
    
    def copy_button(self, button):
        """버튼 복사"""
        button_idx = self.buttons.index(button)
        if button_idx < 0 or button_idx >= len(self.buttons):
            return
            
        # 버튼 데이터 복사
        button_data = self.button_data[button_idx].copy()
        
        # 새 위치 계산
        x = button.x() + 20
        y = button.y() + 20
        
        # 화면 경계 검사
        if x + self.button_width > self.buttons_container.width():
            x = 10
        if y + self.button_height > self.buttons_container.height():
            y = 10
        
        # 새 버튼 생성
        new_button = self.create_button(
            button.main_label, 
            button_data["text"], 
            x, y,
            button.width(),
            button.height(),
            button.sub_label
        )
        
        # 개별 설정 상태 복사
        new_button.custom_size = button.custom_size
        new_button.custom_font = button.custom_font
        new_button.custom_color = button.custom_color
        
        # 새 버튼 데이터에도 개별 설정 상태 적용
        new_button_idx = len(self.buttons) - 1
        self.button_data[new_button_idx]["custom_size"] = button.custom_size
        self.button_data[new_button_idx]["custom_font"] = button.custom_font
        self.button_data[new_button_idx]["custom_color"] = button.custom_color
        
        # 개별 설정 시각화 업데이트
        new_button.update_selection_style()
        
        # 세트 데이터 갱신
        self.save_current_set()
        self.save_sets()
    
    def copy_textbox(self, textbox):
        """텍스트 박스 복사"""
        textbox_idx = self.textboxes.index(textbox)
        if textbox_idx < 0 or textbox_idx >= len(self.textboxes):
            return
            
        # 텍스트 박스 데이터 복사
        textbox_data = self.textbox_data[textbox_idx].copy()
        
        # 새 위치 계산
        x = textbox.x() + 20
        y = textbox.y() + 20
        
        # 화면 경계 검사
        if x + self.textbox_width > self.buttons_container.width():
            x = 10
        if y + self.textbox_height > self.buttons_container.height():
            y = 10
        
        # 글꼴 및 색상 정보 가져오기
        font = textbox.font()
        color = textbox.palette().color(QPalette.WindowText)
        bg_color = QColor(textbox_data.get("bg_color", "transparent"))
        
        # 새 텍스트 박스 생성
        new_textbox = self.create_textbox(textbox.text(), x, y, textbox.width(), textbox.height(), font, color, bg_color)
        
        # 개별 설정 상태 복사
        new_textbox.custom_size = textbox.custom_size
        new_textbox.custom_font = textbox.custom_font
        new_textbox.custom_color = textbox.custom_color
        
        # 새 텍스트 박스 데이터에도 개별 설정 상태 적용
        new_textbox_idx = len(self.textboxes) - 1
        self.textbox_data[new_textbox_idx]["custom_size"] = textbox.custom_size
        self.textbox_data[new_textbox_idx]["custom_font"] = textbox.custom_font
        self.textbox_data[new_textbox_idx]["custom_color"] = textbox.custom_color
        
        # 개별 설정 시각화 업데이트
        new_textbox.update_selection_style()
        
        # 세트 데이터 갱신
        self.save_current_set()
        self.save_sets()
    
    def set_textbox_size(self, textbox):
        """텍스트 박스 크기 설정"""
        textbox_idx = self.textboxes.index(textbox)
        if textbox_idx < 0 or textbox_idx >= len(self.textboxes):
            return
        
        dialog = TextBoxSizeDialog(textbox.width(), textbox.height(), parent=self)
        if dialog.exec_():
            width, height = dialog.get_values()
            
            # 텍스트 박스 크기 변경
            textbox.setFixedSize(width, height)
            
            # 개별 크기 설정 상태 활성화
            textbox.custom_size = True
            self.textbox_data[textbox_idx]["custom_size"] = True
            textbox.update_selection_style()
            
            # 데이터 갱신
            self.save_current_set()
            self.save_sets()
    
    def show_button_menu(self, position, button):
        """버튼 컨텍스트 메뉴 표시"""
        menu = QMenu()
        
        edit_action = QAction("편집", self)
        edit_action.triggered.connect(lambda: self.edit_button(button))
        
        delete_action = QAction("삭제", self)
        delete_action.triggered.connect(lambda: self.delete_button(button))
        
        copy_action = QAction("복사", self)
        copy_action.triggered.connect(lambda: self.copy_button(button))

        # 선택된 버튼이 여러 개인지 확인
        selected_buttons = [b for b in self.buttons if b.is_selected]
        if len(selected_buttons) > 1:
            # 다중 선택된 버튼들을 위한 빠른 편집 메뉴
            quick_edit_selected_action = QAction(f"{len(selected_buttons)}개 버튼 빠른 편집", self)
            quick_edit_selected_action.triggered.connect(self.quick_edit_selected_buttons)
            menu.addAction(quick_edit_selected_action)

        
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addAction(copy_action)
        
        # 개별 설정 메뉴 추가
        menu.addSeparator()
        
        # 통합 스타일 설정 토글 메뉴
        custom_style_action = QAction("개별 스타일 사용", self)
        custom_style_action.setCheckable(True)
        custom_style_action.setChecked(getattr(button, "custom_style", False))
        custom_style_action.triggered.connect(lambda checked: self.toggle_button_custom_style(button, checked))
        
        menu.addAction(custom_style_action)
        
        # 개별 스타일이 활성화된 경우에만 스타일 설정 메뉴 표시
        if getattr(button, "custom_style", False):
            style_action = QAction("스타일 설정", self)
            style_action.triggered.connect(lambda: self.edit_button_style(button))
            menu.addAction(style_action)
        
        # 편집 모드 전환 메뉴
        menu.addSeparator()
        toggle_mode_action = QAction("편집 모드 전환", self)
        toggle_mode_action.triggered.connect(lambda: self.edit_mode_checkbox.toggle())
        menu.addAction(toggle_mode_action)

        # 복사 기능 추가
        menu.addSeparator()
        copy_action = QAction("복사 (Ctrl+C)", self)
        copy_action.triggered.connect(self.copy_selected_widgets_to_clipboard)
        menu.addAction(copy_action)
        
        menu.exec_(button.mapToGlobal(position))
    
    def show_textbox_menu(self, position, textbox):
        """텍스트 박스 컨텍스트 메뉴 표시"""
        menu = QMenu()
        
        edit_action = QAction("편집", self)
        edit_action.triggered.connect(lambda: self.edit_textbox(textbox))
        
        delete_action = QAction("삭제", self)
        delete_action.triggered.connect(lambda: self.delete_textbox(textbox))
        
        copy_action = QAction("복사", self)
        copy_action.triggered.connect(lambda: self.copy_textbox(textbox))
        
        size_action = QAction("크기 설정", self)
        size_action.triggered.connect(lambda: self.set_textbox_size(textbox))
        
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addAction(copy_action)
        menu.addAction(size_action)
        
        # 개별 설정 메뉴 추가
        menu.addSeparator()
        
        # 개별 크기 설정 토글 메뉴
        custom_size_action = QAction("크기 개별 설정", self)
        custom_size_action.setCheckable(True)
        custom_size_action.setChecked(textbox.custom_size)
        custom_size_action.triggered.connect(lambda checked: self.toggle_textbox_custom_setting(textbox, "size", checked))
        
        # 개별 폰트 설정 토글 메뉴
        custom_font_action = QAction("폰트 개별 설정", self)
        custom_font_action.setCheckable(True)
        custom_font_action.setChecked(textbox.custom_font)
        custom_font_action.triggered.connect(lambda checked: self.toggle_textbox_custom_setting(textbox, "font", checked))
        
        # 개별 색상 설정 토글 메뉴
        custom_color_action = QAction("색상 개별 설정", self)
        custom_color_action.setCheckable(True)
        custom_color_action.setChecked(textbox.custom_color)
        custom_color_action.triggered.connect(lambda checked: self.toggle_textbox_custom_setting(textbox, "color", checked))
        
        menu.addAction(custom_size_action)
        menu.addAction(custom_font_action)
        menu.addAction(custom_color_action)
        
        # 편집 모드 전환 메뉴
        menu.addSeparator()
        
        toggle_mode_action = QAction("편집 모드 전환", self)
        toggle_mode_action.triggered.connect(lambda: self.edit_mode_checkbox.toggle())
        menu.addAction(toggle_mode_action)
        
        # 복사 기능 추가 - 이 부분이 새로 추가됨
        menu.addSeparator()
        
        copy_to_clipboard_action = QAction("복사 (Ctrl+C)", self)
        copy_to_clipboard_action.triggered.connect(self.copy_selected_widgets_to_clipboard)
        menu.addAction(copy_to_clipboard_action)
        
        menu.exec_(textbox.mapToGlobal(position))

    
    def show_context_menu(self, position):
        """빈 공간 컨텍스트 메뉴 표시"""
        menu = QMenu()
        
        add_button_action = QAction("버튼 추가", self)
        add_button_action.triggered.connect(self.add_button_dialog)
        
        add_textbox_action = QAction("텍스트 박스 추가", self)
        add_textbox_action.triggered.connect(self.add_textbox_dialog)
        
        # 편집 모드 전환 메뉴
        toggle_mode_action = QAction("편집 모드 전환", self)
        toggle_mode_action.triggered.connect(lambda: self.edit_mode_checkbox.toggle())
        
        # 선택 취소 메뉴 (편집 모드일 때만)
        clear_selection_action = QAction("선택 취소", self)
        clear_selection_action.triggered.connect(self.clear_all_selections)
        clear_selection_action.setEnabled(self.edit_mode)
        
        # 개별 설정 초기화 메뉴
        reset_custom_settings = QAction("모든 개별 설정 초기화", self)
        reset_custom_settings.triggered.connect(self.reset_all_custom_settings)
        
        menu.addAction(add_button_action)
        menu.addAction(add_textbox_action)
        menu.addSeparator()
        menu.addAction(toggle_mode_action)
        
        if self.edit_mode:
            menu.addAction(clear_selection_action)
            menu.addAction(reset_custom_settings)
            
            # 복사/붙여넣기 메뉴 추가
            menu.addSeparator()
            copy_action = QAction("선택항목 복사 (Ctrl+C)", self)
            copy_action.triggered.connect(self.copy_selected_widgets_to_clipboard)
            copy_action.setEnabled(len(self.get_all_selected_widgets()) > 0)
            
            paste_action = QAction("붙여넣기 (Ctrl+V)", self)
            paste_action.triggered.connect(lambda: self.paste_widgets_from_clipboard(position))
            paste_action.setEnabled(self.clipboard_handler.has_data())
            
            menu.addAction(copy_action)
            menu.addAction(paste_action)
        
        menu.exec_(self.buttons_container.mapToGlobal(position))
    
    def set_target_position(self):
        """마우스 목표 위치 설정"""
        QMessageBox.information(self, "마우스 위치 설정",
                               "확인을 누른 뒤 3초 후 마우스 포인터가 위치한 곳이 목표 위치로 설정됩니다.")

        # GUI를 멈추지 않고 3초 후에 현재 마우스 위치를 저장
        QTimer.singleShot(3000, self._capture_target_position)

    def _capture_target_position(self):
        """3초 대기 후 현재 마우스 위치를 목표 위치로 저장"""
        self.target_position = pyautogui.position()
        QMessageBox.information(self, "설정 완료",
                               f"마우스 위치가 {self.target_position}으로 설정되었습니다.")

        # 설정 저장
        self.save_sets()
    
    def set_button_size(self):
        """버튼 크기 설정"""
        dialog = ButtonSizeDialog(self.button_width, self.button_height, parent=self)
        if dialog.exec_():
            width, height = dialog.get_values()
            self.button_width = width
            self.button_height = height
            
            # 선택된 버튼만 크기 변경 (편집 모드에서)
            if self.edit_mode:
                selected_buttons = [b for b in self.buttons if b.is_selected]
                if selected_buttons:
                    for button in selected_buttons:
                        button.setFixedSize(width, height)
                        
                        # 개별 크기 설정 상태 활성화
                        button_idx = self.buttons.index(button)
                        button.custom_size = True
                        self.button_data[button_idx]["custom_size"] = True
                        button.update_selection_style()
                    
                    # 설정 저장
                    self.update_widget_data()
                    return
            
            # 모든 버튼 크기 업데이트 (개별 설정된 버튼 제외)
            for i, button in enumerate(self.buttons):
                if not button.custom_size:
                    button.setFixedSize(width, height)
            
            # 설정 저장
            self.update_widget_data()
    
    def set_button_font(self):
        """버튼 글꼴 설정"""
        dialog = FontSettingsDialog(self.button_font, self.button_color, parent=self)
        if dialog.exec_():
            font, color = dialog.get_values()
            self.button_font = font
            self.button_color = color
            
            # 선택된 버튼만 글꼴 변경 (편집 모드에서)
            if self.edit_mode:
                selected_buttons = [b for b in self.buttons if b.is_selected]
                if selected_buttons:
                    for button in selected_buttons:
                        button.setFont(self.button_font)
                        palette = button.palette()
                        palette.setColor(QPalette.ButtonText, self.button_color)
                        button.setPalette(palette)
                        
                        # 개별 글꼴 설정 상태 활성화
                        button_idx = self.buttons.index(button)
                        button.custom_font = True
                        self.button_data[button_idx]["custom_font"] = True
                        button.update_selection_style()
                    
                    # 설정 저장
                    self.update_widget_data()
                    return
            
            # 모든 버튼 글꼴 및 색상 업데이트 (개별 설정된 버튼 제외)
            for i, button in enumerate(self.buttons):
                if not button.custom_font:
                    button.setFont(self.button_font)
                    palette = button.palette()
                    palette.setColor(QPalette.ButtonText, self.button_color)
                    button.setPalette(palette)
            
            # 설정 저장
            self.update_widget_data()
    
    def set_list_font_settings(self):
        """세트 리스트 글꼴 설정"""
        dialog = SetFontSettingsDialog(self.set_list_font, self.set_list_color, parent=self)
        if dialog.exec_():
            font, color = dialog.get_values()
            self.set_list_font = font
            self.set_list_color = color
            
            # 모든 세트 아이템 글꼴 및 색상 업데이트
            self.update_set_list()
            
            # 설정 저장
            self.save_sets()
    
    def execute_macro(self, text):
        """매크로 실행 - 텍스트 붙여넣기 및 관련 동작 수행"""
        # 편집 모드에서는 매크로 실행 안함
        if self.edit_mode:
            return
        
        # 디버깅 메시지
        print(f"매크로 실행: {text[:20]}...")
            
        # 클립보드에도 백업해 둠 (필요 시 수동 Ctrl+V 가능)
        pyperclip.copy(text)

        try:
            # 마우스 이동 및 입력칸 포커스
            pyautogui.moveTo(self.target_position)
            pyautogui.doubleClick()

            # 스페이스바 누르기
            pyautogui.press('space')

            # 기존 값이 있으면 전체 선택하여 덮어쓰기
            pyautogui.hotkey('ctrl', 'a')

            # 바코드 스캐너처럼 실제 키 입력으로 한 글자씩 타이핑 (한글 지원)
            # 붙여넣기(Ctrl+V)를 거부하는 POS/ERP 필드에서도 입력됩니다.
            type_unicode(text)

            # Enter 키를 눌러 실행 또는 다음 줄로 이동
            press_enter()

        except Exception as e:
            print(f"매크로 실행 중 오류 발생: {e}")
            QMessageBox.warning(self, "매크로 실행 오류", f"매크로 실행 중 오류가 발생했습니다.\n{str(e)}")
    
    def font_to_dict(self, font):
        """QFont 객체를 사전으로 변환"""
        return {
            'family': font.family(),
            'point_size': font.pointSize(),
            'weight': font.weight(),
            'italic': font.italic(),
            'bold': font.bold()
        }
    
    def dict_to_font(self, font_dict):
        """사전에서 QFont 객체 생성"""
        font = QFont(font_dict['family'])
        font.setPointSize(font_dict['point_size'])
        font.setWeight(font_dict['weight'])
        font.setItalic(font_dict['italic'])
        font.setBold(font_dict['bold'])
        return font
    
    def save_sets(self):
        """모든 세트 데이터 저장"""
        try:
            # 프리셋 관리자 없거나 선택된 프리셋이 없는 경우 기존 방식으로 저장
            if not hasattr(self, 'preset_manager') or not self.preset_combo.currentText():
                self._legacy_save_sets()
                return
            
            # 프리셋 저장 함수 호출
            self.save_current_preset()
        except Exception as e:
            print(f"저장 오류: {e}")
            QMessageBox.warning(self, "저장 오류", f"세트 데이터 저장 중 오류가 발생했습니다.\n{str(e)}")
    
    def load_sets(self):
        """저장된 세트 데이터 로드"""
        # 프리셋 관리자 초기화
        if not hasattr(self, 'preset_manager'):
            self.preset_manager = PresetManager(self)
        
        # 프리셋 목록 업데이트 
        self.update_preset_list()
        
        # 기존 데이터 마이그레이션 시도
        if self.migrate_legacy_data():
            return
        
        # 마지막 프리셋이 있으면 로드
        if self.preset_manager.current_preset:
            preset_found = False
            for i in range(self.preset_combo.count()):
                if self.preset_combo.itemText(i) == self.preset_manager.current_preset:
                    preset_found = True
                    self.preset_combo.setCurrentIndex(i)
                    if self.load_preset(self.preset_manager.current_preset):
                        return
            
            # 저장된 프리셋을 찾지 못함
            if not preset_found and self.preset_combo.count() > 0:
                self.preset_combo.setCurrentIndex(0)
                self.load_preset(self.preset_combo.currentText())
                return
        
        # 여기까지 왔다면 기본 방식으로 로드
        # 기본 세트 준비 (오류 발생 시 사용)
        default_set = ButtonSet("기본 세트")
        
        # 파일 존재 확인
        if os.path.exists('button_sets.json'):
            try:
                # 디버깅 메시지
                print("button_sets.json 파일 로드 시도...")
                
                # 파일 읽기
                with open('button_sets.json', 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                # 빈 파일인지 확인
                if not file_content.strip():
                    print("파일이 비어 있습니다. 기본 세트를 생성합니다.")
                    self.button_sets.append(default_set)
                    self.update_set_list()
                    return
                
                try:
                    # JSON 파싱
                    data = json.loads(file_content)
                    
                    # 전역 설정 로드
                    if 'global_settings' in data:
                        try:
                            self._load_global_settings(data['global_settings'])
                        except Exception as settings_error:
                            print(f"전역 설정 로드 오류: {settings_error}")
                    
                    # 세트 데이터 로드
                    if 'sets' in data and isinstance(data['sets'], list):
                        self.button_sets = []  # 기존 세트 초기화
                        
                        for set_data in data['sets']:
                            try:
                                # 버튼 데이터 유효성 검사 및 보완
                                self._validate_and_fix_set_data(set_data)
                                
                                # 세트 객체 생성 및 추가
                                set_obj = ButtonSet.from_dict(set_data)
                                self.button_sets.append(set_obj)
                            except Exception as set_error:
                                print(f"세트 데이터 처리 오류: {set_error}")
                    else:
                        print("유효한 세트 데이터가 없습니다. 기본 세트를 생성합니다.")
                        self.button_sets.append(default_set)
                
                except json.JSONDecodeError as json_error:
                    print(f"JSON 파싱 오류: {json_error}")
                    # 파일 백업 및 기본 세트 생성
                    self._backup_corrupted_file('button_sets.json')
                    self.button_sets.append(default_set)
            
            except Exception as e:
                print(f"파일 로드 중 일반 오류: {e}")
                # 파일 백업 및 기본 세트 생성
                self._backup_corrupted_file('button_sets.json')
                self.button_sets.append(default_set)
        
        # 기존 버튼 파일 형식과의 호환성 처리
        elif os.path.exists('buttons.json'):
            try:
                with open('buttons.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 기본 설정 로드
                self._load_legacy_settings(data)
                
                # 버튼 데이터를 기본 세트로 변환
                default_set = ButtonSet("기본 세트")
                if 'buttons' in data:
                    # 위치와 크기 정보 추가
                    updated_buttons = []
                    for i, button_info in enumerate(data['buttons']):
                        row = i // 3
                        col = i % 3
                        x = 10 + col * (self.button_width + 10)
                        y = 10 + row * (self.button_height + 10)
                        
                        updated_buttons.append({
                            "label": button_info.get("label", "버튼"),
                            "label2": button_info.get("label2", ""), # 두 번째 줄 레이블 추가
                            "text": button_info.get("text", ""),
                            "x": x,
                            "y": y,
                            "width": self.button_width,
                            "height": self.button_height,
                            "custom_size": False,  # 개별 설정 필드 추가
                            "custom_font": False,
                            "custom_color": False
                        })
                    
                    default_set.buttons = updated_buttons
                
                self.button_sets.append(default_set)
            
            except Exception as e:
                print(f"legacy 파일 로드 오류: {e}")
                self.button_sets.append(default_set)
        
        else:
            # 아무 파일도 없는 경우 기본 세트 생성
            print("설정 파일이 없습니다. 기본 세트를 생성합니다.")
            self.button_sets.append(default_set)
        
        # 세트가 없는 경우 기본 세트 추가
        if not self.button_sets:
            print("로드된 세트가 없습니다. 기본 세트를 생성합니다.")
            self.button_sets.append(default_set)
        
        # 편집 모드 표시 업데이트 및 세트 리스트 업데이트
        self.update_edit_mode_display()
        self.update_set_list()
        
        # 교차 배경색 적용 (설정 로드 후)
        self.apply_alternating_row_colors()

        # 세트 리스트 모드 설정
        self.set_list.set_edit_mode(self.edit_mode)
    
    def _load_global_settings(self, global_settings):
        """전역 설정 로드"""
        # 마우스 위치 로드
        if 'target_position' in global_settings:
            try:
                pos = global_settings['target_position']
                if isinstance(pos, (list, tuple)) and len(pos) == 2:
                    self.target_position = tuple(pos)
            except:
                pass

        # 창 위치 로드
        if 'window_position' in global_settings:
            try:
                pos = global_settings['window_position']
                if isinstance(pos, list) and len(pos) == 2:
                    # 화면 영역을 벗어나지 않도록 확인
                    from PyQt5.QtWidgets import QApplication
                    screen_geometry = QApplication.desktop().availableGeometry()
                    x = max(0, min(pos[0], screen_geometry.width() - 100))
                    y = max(0, min(pos[1], screen_geometry.height() - 100))
                    self.move(x, y)
            except Exception as e:
                print(f"창 위치 로드 오류: {e}")

        # 창 크기 로드
        if 'window_size' in global_settings:
            try:
                size = global_settings['window_size']
                if isinstance(size, list) and len(size) == 2:
                    # 최소 크기 제한
                    width = max(400, size[0])
                    height = max(300, size[1])
                    self.resize(width, height)
            except Exception as e:
                print(f"창 크기 로드 오류: {e}")    
        
        # 버튼 크기 로드
        if 'button_width' in global_settings:
            try:
                width = int(global_settings['button_width'])
                if 50 <= width <= 500:
                    self.button_width = width
            except:
                pass
        
        if 'button_height' in global_settings:
            try:
                height = int(global_settings['button_height'])
                if 30 <= height <= 300:
                    self.button_height = height
            except:
                pass
        
        # 텍스트 박스 크기 로드
        if 'textbox_width' in global_settings:
            try:
                width = int(global_settings['textbox_width'])
                if 50 <= width <= 800:
                    self.textbox_width = width
            except:
                pass
        
        if 'textbox_height' in global_settings:
            try:
                height = int(global_settings['textbox_height'])
                if 30 <= height <= 500:
                    self.textbox_height = height
            except:
                pass
        
        # 버튼 글꼴 및 색상 로드
        if 'button_font' in global_settings:
            try:
                self.button_font = self.dict_to_font(global_settings['button_font'])
            except:
                pass
        
        if 'button_color' in global_settings:
            try:
                color_str = global_settings['button_color']
                if isinstance(color_str, str):
                    self.button_color = QColor(color_str)
            except:
                pass
        
        # 세트 리스트 글꼴 및 색상 로드
        if 'set_list_font' in global_settings:
            try:
                self.set_list_font = self.dict_to_font(global_settings['set_list_font'])
            except:
                pass
        
        if 'set_list_color' in global_settings:
            try:
                color_str = global_settings['set_list_color']
                if isinstance(color_str, str):
                    self.set_list_color = QColor(color_str)
            except:
                pass
        
        # 교차 배경색 설정 로드
        if 'even_row_color' in global_settings:
            try:
                color_str = global_settings['even_row_color']
                if isinstance(color_str, str):
                    self.even_row_color = QColor(color_str)
            except:
                pass
        
        if 'odd_row_color' in global_settings:
            try:
                color_str = global_settings['odd_row_color']
                if isinstance(color_str, str):
                    self.odd_row_color = QColor(color_str)
            except:
                pass
        
        if 'use_alternating_colors' in global_settings:
            try:
                self.use_alternating_colors = bool(global_settings['use_alternating_colors'])
            except:
                pass
        
        # 스플리터 크기 로드
        if 'splitter_sizes' in global_settings:
            try:
                sizes = global_settings['splitter_sizes']
                if isinstance(sizes, list) and len(sizes) == 2:
                    # 왼쪽 패널 너비를 최소 150px, 최대 전체의 70%로 제한
                    total_width = sum(sizes)
                    left_width = int(max(150, min(sizes[0], total_width * 0.7)))
                    right_width = total_width - left_width
                    clamped_sizes = [left_width, right_width]

                    # 타이머를 사용해서 UI가 완전히 로드된 후 크기 적용
                    QTimer.singleShot(100, lambda: self.splitter.setSizes(clamped_sizes))
            except Exception as e:
                print(f"스플리터 크기 로드 오류: {e}")

        # 편집 모드 로드 - 항상 비활성화 상태로 시작
        self.edit_mode = False
        self.edit_mode_checkbox.setChecked(False)
    
    def _load_legacy_settings(self, data):
        """이전 버전 설정 로드"""
        # 마우스 위치 로드
        if 'target_position' in data:
            try:
                pos = data['target_position']
                if isinstance(pos, (list, tuple)) and len(pos) == 2:
                    self.target_position = tuple(pos)
            except:
                pass
        
        # 버튼 크기 로드
        if 'button_width' in data:
            try:
                width = int(data['button_width'])
                if 50 <= width <= 500:
                    self.button_width = width
            except:
                pass
        
        if 'button_height' in data:
            try:
                height = int(data['button_height'])
                if 30 <= height <= 300:
                    self.button_height = height
            except:
                pass
        
        # 글꼴 및 색상 로드
        if 'button_font' in data:
            try:
                self.button_font = self.dict_to_font(data['button_font'])
            except:
                pass
        
        if 'button_color' in data:
            try:
                color_str = data['button_color']
                if isinstance(color_str, str):
                    self.button_color = QColor(color_str)
            except:
                pass
    
    def _validate_and_fix_set_data(self, set_data):
        """세트 데이터 검증 및 수정"""
        # 세트 이름 확인
        if 'name' not in set_data or not isinstance(set_data['name'], str):
            set_data['name'] = '이름 없는 세트'
        
        # 버튼 데이터 확인
        if 'buttons' not in set_data or not isinstance(set_data['buttons'], list):
            set_data['buttons'] = []
        
        # 텍스트 박스 데이터 확인 (하위 호환성)
        if 'textboxes' not in set_data:
            set_data['textboxes'] = []
        
        if not isinstance(set_data['textboxes'], list):
            set_data['textboxes'] = []
        
        # 각 버튼 데이터 확인 및 수정
        for i, button in enumerate(set_data['buttons']):
            # 기본 위치 계산 (그리드 형태)
            row = i // 3
            col = i % 3
            default_x = 10 + col * (self.button_width + 10)
            default_y = 10 + row * (self.button_height + 10)
            
            # 필수 필드 확인 및 복구
            if not isinstance(button, dict):
                set_data['buttons'][i] = {
                    "label": "버튼",
                    "label2": "",  # 두 번째 줄 레이블
                    "text": "",
                    "x": default_x,
                    "y": default_y,
                    "width": self.button_width,
                    "height": self.button_height,
                    "custom_style": False,  # 통합 스타일 설정 필드 추가
                    "custom_size": False,  # 개별 설정 필드
                    "custom_font": False,
                    "custom_color": False
                }
                continue
            
            # 레이블 확인
            if 'label' not in button or not isinstance(button['label'], str):
                button['label'] = "버튼"
            
            # 두 번째 줄 레이블 확인 (하위 호환성)
            if 'label2' not in button:
                button['label2'] = ""
            elif not isinstance(button['label2'], str):
                button['label2'] = ""
            
            # 텍스트 확인
            if 'text' not in button or not isinstance(button['text'], str):
                button['text'] = ""
            
            # 위치 정보 확인
            if 'x' not in button or not isinstance(button['x'], (int, float)):
                button['x'] = default_x
            if 'y' not in button or not isinstance(button['y'], (int, float)):
                button['y'] = default_y
            
            # 크기 정보 확인
            if 'width' not in button or not isinstance(button['width'], (int, float)):
                button['width'] = self.button_width
            if 'height' not in button or not isinstance(button['height'], (int, float)):
                button['height'] = self.button_height
            
            if 'custom_style' not in button:
                button['custom_style'] = False  

            # 개별 설정 필드 확인
            if 'custom_size' not in button:
                button['custom_size'] = False
            if 'custom_font' not in button:
                button['custom_font'] = False
            if 'custom_color' not in button:
                button['custom_color'] = False
            if 'custom_style' not in button:
                button['custom_style'] = False
        
        # 각 텍스트 박스 데이터 확인 및 수정
        for i, textbox in enumerate(set_data['textboxes']):
            # 기본 위치 계산 (버튼 영역 아래에 배치)
            row = i // 2
            col = i % 2
            default_x = 10 + col * (self.textbox_width + 10)
            default_y = 200 + row * (self.textbox_height + 10)  # 버튼 영역 아래에 배치
            
            # 필수 필드 확인 및 복구
            if not isinstance(textbox, dict):
                set_data['textboxes'][i] = {
                    "text": "텍스트 상자",
                    "x": default_x,
                    "y": default_y,
                    "width": self.textbox_width,
                    "height": self.textbox_height,
                    "font": self.font_to_dict(self.button_font),
                    "color": "#000000",
                    "bg_color": "transparent",
                    "custom_size": False,  # 개별 설정 필드
                    "custom_font": False,
                    "custom_color": False
                }
                continue
            
            # 텍스트 확인
            if 'text' not in textbox or not isinstance(textbox['text'], str):
                textbox['text'] = "텍스트 상자"
            
            # 위치 정보 확인
            if 'x' not in textbox or not isinstance(textbox['x'], (int, float)):
                textbox['x'] = default_x
            if 'y' not in textbox or not isinstance(textbox['y'], (int, float)):
                textbox['y'] = default_y
            
            # 크기 정보 확인
            if 'width' not in textbox or not isinstance(textbox['width'], (int, float)):
                textbox['width'] = self.textbox_width
            if 'height' not in textbox or not isinstance(textbox['height'], (int, float)):
                textbox['height'] = self.textbox_height
            
            # 글꼴 정보 확인
            if 'font' not in textbox or not isinstance(textbox['font'], dict):
                textbox['font'] = self.font_to_dict(self.button_font)
            
            # 색상 정보 확인
            if 'color' not in textbox or not isinstance(textbox['color'], str):
                textbox['color'] = "#000000"
            
            # 배경색 정보 확인
            if 'bg_color' not in textbox or not isinstance(textbox['bg_color'], str):
                textbox['bg_color'] = "transparent"
            
            # 개별 설정 필드 확인
            if 'custom_size' not in textbox:
                textbox['custom_size'] = False
            if 'custom_font' not in textbox:
                textbox['custom_font'] = False
            if 'custom_color' not in textbox:
                textbox['custom_color'] = False
    
    def _backup_corrupted_file(self, filename):
        """손상된 파일 백업"""
        try:
            import datetime
            backup_filename = f"{filename.split('.')[0]}_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            os.rename(filename, backup_filename)
            print(f"손상된 파일을 {backup_filename}으로 백업했습니다.")
            QMessageBox.information(self, "파일 백업", f"손상된 설정 파일이 {backup_filename}으로 백업되었습니다.")
        except Exception as backup_error:
            print(f"백업 오류: {backup_error}")
            try:
                # 백업 실패 시 파일 삭제 시도
                os.remove(filename)
                print(f"{filename} 파일을 삭제했습니다.")
            except:
                pass

