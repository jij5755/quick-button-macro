"""세트(왼쪽 카테고리)를 바꾸면 버튼 아래 JYOR 정보 줄이 바로 채워져야 한다(2026-10-07).

전에는 30초 타이머가 돌 때까지 빈칸이었다(사용자: '카테고리 옮기면 좀 기다려야 함').
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def window(tmp_path, monkeypatch):
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    monkeypatch.chdir(tmp_path)          # presets/·meta 파일이 작업 폴더 기준이라 임시 폴더에서
    import jyor_link
    monkeypatch.setattr(jyor_link, "lookup",
                        lambda codes, path=None: {"35584": {"name": "XL호스카플링", "caliber": "15A", "price": 4400}})
    from main_window import QuickButtonMacro
    from models import ButtonSet
    w = QuickButtonMacro()
    w._jyor_timer.stop()                 # 30초 타이머가 아니라 세트 변경 자체가 채우는지 본다
    w.button_sets = [
        ButtonSet("A", buttons=[{"label": "다른거", "text": "1", "x": 10, "y": 10}]),
        ButtonSet("B", buttons=[{"label": "XL카플링", "text": "48921", "x": 10, "y": 10, "erp_code": "35584"}]),
    ]
    w.change_button_set(0)
    yield w
    w.close()
    app.processEvents()


def test_switching_set_fills_info_immediately(window):
    window.change_button_set(1)
    assert [b.erp_code for b in window.buttons] == ["35584"]
    assert window.buttons[0].info_label.text() == "15A  ₩4,400"
