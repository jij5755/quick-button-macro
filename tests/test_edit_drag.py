"""편집 모드 끌기(2026-10-12 사용자 보고, 원래부터 있던 버그 둘).

1. 영역 선택으로 여러 개를 고른 뒤 바로 끌면 안 움직였다(Ctrl을 눌러야 움직임).
2. 여러 개를 같이 옮기면 스냅 한 칸(10px)씩 어긋났다.
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
    monkeypatch.chdir(tmp_path)
    import jyor_link
    monkeypatch.setattr(jyor_link, "lookup", lambda codes, path=None: {})
    from main_window import QuickButtonMacro
    w = QuickButtonMacro()
    w._jyor_timer.stop()
    w.show()
    w.edit_mode_checkbox.setChecked(True)
    yield w
    w.close()
    app.processEvents()


def _mouse(widget, kind, pos, buttons, modifiers=None):
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    mods = Qt.NoModifier if modifiers is None else modifiers
    ev = QMouseEvent(kind, pos, widget.mapToGlobal(pos), Qt.LeftButton, buttons, mods)
    QApplication.sendEvent(widget, ev)
    return ev


def _drag(widget, dx, dy, steps=1, modifiers=None):
    """위젯 가운데를 누르고 (dx, dy)만큼 steps번에 나눠 끈 뒤 뗀다."""
    from PyQt5.QtCore import Qt, QPoint, QEvent
    c = widget.rect().center()
    _mouse(widget, QEvent.MouseButtonPress, c, Qt.LeftButton, modifiers)
    for i in range(1, steps + 1):
        p = c + QPoint(dx * i // steps, dy * i // steps)
        # 위젯이 움직이면 같은 화면 지점이 위젯 좌표로는 달라진다 — 화면 좌표 기준으로 다시 계산
        local = widget.mapFromGlobal(widget.parent.buttons_container.mapToGlobal(QPoint(0, 0)) + _start[widget] + p)
        _mouse(widget, QEvent.MouseMove, local, Qt.LeftButton, modifiers)
    local = widget.mapFromGlobal(widget.parent.buttons_container.mapToGlobal(QPoint(0, 0)) + _start[widget] + c + QPoint(dx, dy))
    _mouse(widget, QEvent.MouseButtonRelease, local, Qt.NoButton, modifiers)


_start = {}


def _three_buttons(window, xs=(10, 160, 310)):
    buttons = [window.create_button(f"B{i}", str(i), x, 10, 150, 40) for i, x in enumerate(xs)]
    for b in buttons:
        _start[b] = b.pos()
    return buttons


def test_dragging_a_selected_group_without_ctrl_moves_all(window):
    from PyQt5.QtCore import QRect
    a, b, c = _three_buttons(window)
    window.select_widgets_in_rect(QRect(0, 0, 500, 60))
    assert all(x.is_selected for x in (a, b, c))
    _drag(a, 40, 30)
    assert [(x.x(), x.y()) for x in (a, b, c)] == [(50, 40), (200, 40), (350, 40)]
    assert all(x.is_selected for x in (a, b, c)), "끌고 난 뒤에도 묶음 선택은 유지"


def test_click_without_dragging_on_a_group_selects_only_that_one(window):
    from PyQt5.QtCore import QRect
    a, b, c = _three_buttons(window)
    window.select_widgets_in_rect(QRect(0, 0, 500, 60))
    _drag(b, 0, 0)
    assert [x.is_selected for x in (a, b, c)] == [False, True, False]
    assert [(x.x(), x.y()) for x in (a, b, c)] == [(10, 10), (160, 10), (310, 10)]


def test_ctrl_click_toggles_one_without_clearing_others(window):
    from PyQt5.QtCore import Qt, QRect
    a, b, c = _three_buttons(window)
    window.select_widgets_in_rect(QRect(0, 0, 500, 60))
    _drag(b, 0, 0, modifiers=Qt.ControlModifier)
    assert [x.is_selected for x in (a, b, c)] == [True, False, True]


def test_group_move_keeps_relative_offsets_even_off_grid(window):
    """a는 그리드 위(10), b는 그리드에서 5px 벗어남(25). 7px씩 여섯 번 끌어도 둘 사이 간격 15는 그대로."""
    from PyQt5.QtCore import QRect
    a, b = _three_buttons(window, xs=(10, 25))[:2]
    window.select_widgets_in_rect(QRect(0, 0, 400, 60))
    _drag(a, 42, 0, steps=6)
    assert a.x() == 50, "누른 위젯은 그리드에 스냅(42 → 40)"
    assert b.x() - a.x() == 15, "같이 움직인 위젯은 상대 간격 유지"
    assert (a.y(), b.y()) == (10, 10)


def test_single_widget_drag_still_snaps_to_grid(window):
    (a,) = _three_buttons(window, xs=(10,))[:1]
    _drag(a, 23, 17)
    assert (a.x(), a.y()) == (30, 30)
