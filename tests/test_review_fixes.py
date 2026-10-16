"""2026-10-12 전체 코드 리뷰에서 나온 8건(원래부터 있던 문제) 수정 확인."""
import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _make_png(path, w=40, h=30):
    from PyQt5.QtGui import QImage, QColor
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(180, 140, 40))
    assert img.save(path)


def _wait_until(cond, ms=2000):
    from PyQt5.QtTest import QTest
    deadline = time.time() + ms / 1000
    while time.time() < deadline:
        if cond():
            return True
        QTest.qWait(20)
    return cond()


@pytest.fixture
def window(tmp_path, monkeypatch):
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    monkeypatch.chdir(tmp_path)
    import jyor_link
    monkeypatch.setattr(jyor_link, "lookup",
                        lambda codes, path=None: {"35584": {"name": "XL삼티", "caliber": "15A", "price": 4400}})
    os.makedirs("images")
    _make_png(os.path.join("images", "xl_tee.png"))
    from main_window import QuickButtonMacro
    w = QuickButtonMacro()
    w._jyor_timer.stop()
    w.show()
    yield w
    w.close()
    app.processEvents()


def _mouse(widget, kind, pos, buttons):
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    ev = QMouseEvent(kind, pos, widget.mapToGlobal(pos), Qt.LeftButton, buttons, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)
    return ev


# ---- 1. 프리셋 전환 때 "저장"은 옛 프리셋 파일에 써야 한다 ----
def test_switching_preset_with_save_writes_old_preset_not_new(window, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    import main_window as mw
    old_name = window.preset_combo.currentText()
    window.create_button("옛버튼", "1", 10, 10)
    window.save_current_set()
    window.save_current_preset()
    # 새 프리셋 B: 버튼 2개짜리 파일을 직접 만들어 둔다
    b_data = {"global_settings": {}, "sets": [{"name": "B세트", "buttons": [
        {"label": "B1", "text": "1", "x": 10, "y": 10}, {"label": "B2", "text": "2", "x": 10, "y": 60}]}]}
    window.preset_manager.save_preset("B", b_data)
    window.preset_manager.current_preset = old_name
    window.update_preset_list()
    monkeypatch.setattr(window, "has_unsaved_changes", lambda: True)
    asked = []
    monkeypatch.setattr(mw.QMessageBox, "question",
                        staticmethod(lambda *a, **k: (asked.append(a[2]), QMessageBox.Yes)[1]))
    window.preset_combo.setCurrentIndex(window.preset_combo.findText("B"))     # → on_preset_changed
    assert asked, "첫 전환이라도 변경사항이 있으면 저장 여부를 물어야 한다"
    with open(os.path.join("presets", "B.json"), encoding="utf-8") as f:
        saved_b = json.load(f)
    with open(os.path.join("presets", f"{old_name}.json"), encoding="utf-8") as f:
        saved_old = json.load(f)
    assert [b["label"] for b in saved_b["sets"][0]["buttons"]] == ["B1", "B2"], "새 프리셋이 옛 내용으로 덮어써짐"
    assert [b["label"] for b in saved_old["sets"][0]["buttons"]] == ["옛버튼"]
    assert [b.main_label for b in window.buttons] == ["B1", "B2"]


# ---- 6. 세트 로드 실패 시 조용히 버리지 말고 알리고 편집을 잠근다 ----
def test_failed_set_load_warns_and_locks_editing(window, monkeypatch):
    import main_window as mw
    from models import ButtonSet
    warned = []
    monkeypatch.setattr(mw.QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a[2])))
    bad = ButtonSet("깨진세트", buttons=[{"label": "정상", "text": "1", "x": 10, "y": 10},
                                      {"label": "깨짐", "text": "1", "x": "abc", "y": 60}])   # setGeometry("abc") → TypeError
    window.button_sets.append(bad)
    window.update_set_list()
    window.change_button_set(1)
    assert window._current_set_load_failed
    assert warned and "저장되지 않습니다" in warned[0]
    assert "로드 실패" in window.windowTitle()
    before = json.loads(json.dumps(bad.to_dict()))
    window.create_button("추가", "1", 10, 110)
    window.save_current_set()
    assert bad.to_dict() == before, "실패한 세트의 원본 데이터는 그대로"
    assert "저장되지 않습니다" in window.statusBar().currentMessage()


# ---- 2. 버튼 복사는 품목번호·개별 스타일을 가져가야 한다 ----
def test_copy_button_keeps_erp_code_and_custom_style(window):
    b = window.create_button("XL삼티", "48921", 10, 10, erp_code="35584")
    window.toggle_button_custom_style(b, True)
    window.copy_button(b)
    new = window.buttons[1]
    assert new.erp_code == "35584"
    assert window.button_data[1]["erp_code"] == "35584"
    assert new.custom_style is True and window.button_data[1]["custom_style"] is True


# ---- 3. custom_style 플래그는 저장되고 다시 읽힌다 ----
def test_custom_style_flag_survives_set_switch(window):
    from models import ButtonSet
    window.button_sets.append(ButtonSet("B"))
    window.update_set_list()
    b = window.create_button("XL삼티", "48921", 10, 10)
    window.toggle_button_custom_style(b, True)
    window.save_current_set()
    assert window.button_sets[0].buttons[0]["custom_style"] is True
    window.change_button_set(1)
    window.change_button_set(0)
    assert window.buttons[0].custom_style is True


# ---- 4. 붙여넣기도 묶음의 상대 간격을 유지한다 ----
def test_paste_keeps_relative_offsets_off_grid(window):
    from PyQt5.QtCore import QPoint
    window.edit_mode_checkbox.setChecked(True)
    a = window.create_button("A", "1", 10, 10)
    b = window.create_button("B", "2", 25, 10)
    a.set_selected(True)
    b.set_selected(True)
    window.copy_selected_widgets_to_clipboard()
    window.paste_widgets_from_clipboard(QPoint(103, 0))
    na, nb = window.buttons[2], window.buttons[3]
    assert na.x() == 100, "기준점(첫 위젯)은 그리드에 스냅"
    assert nb.x() - na.x() == 15, "나머지는 상대 간격 그대로"


# ---- 5. JYOR 조회는 메인 스레드를 막지 않는다 ----
def test_jyor_lookup_runs_in_background(window, monkeypatch):
    import jyor_link

    def slow_lookup(codes, path=None):
        time.sleep(0.4)
        return {"35584": {"name": "XL삼티", "caliber": "15A", "price": 4400}}
    monkeypatch.setattr(jyor_link, "lookup", slow_lookup)
    b = window.create_button("XL삼티", "48921", 10, 10, erp_code="35584")
    t0 = time.time()
    window.refresh_jyor_info()
    assert time.time() - t0 < 0.2, "조회가 UI를 막았다"
    assert b.info_label.text() == ""
    assert _wait_until(lambda: b.info_label.text() == "15A  ₩4,400")


def test_jyor_refresh_while_running_is_coalesced_not_lost(window, monkeypatch):
    import jyor_link
    calls = []

    def slow_lookup(codes, path=None):
        calls.append(sorted(codes))
        time.sleep(0.3)
        return {c: {"name": c, "caliber": "15A", "price": 100} for c in codes}
    monkeypatch.setattr(jyor_link, "lookup", slow_lookup)
    window.create_button("A", "1", 10, 10, erp_code="1")
    window.refresh_jyor_info()
    b2 = window.create_button("B", "2", 10, 60, erp_code="2")     # 실행 중에 버튼이 늘었다
    window.refresh_jyor_info()
    window.refresh_jyor_info()
    assert _wait_until(lambda: b2.info_label.text() == "15A  ₩100")
    assert len(calls) == 2, "실행 중 들어온 요청은 하나로 합쳐 끝난 뒤 한 번만 다시 조회"


def test_no_jyor_lookup_starts_after_close(window):
    """2026-10-16: 조회 중 들어온 '끝나면 한 번 더'가 창을 닫은 뒤 늦게 도착한 끝남 신호로 새 스레드를
    띄우면, 창이 사라질 때 'QThread: Destroyed while thread is still running'으로 프로세스가 죽는다."""
    from PyQt5.QtWidgets import QApplication
    if window._jyor_thread is not None:
        window._jyor_thread.wait(3000)
    QApplication.processEvents()
    before = window._jyor_thread
    window._jyor_pending = True            # 조회 중에 요청이 들어왔고, 끝남 신호는 아직 큐에 있는 상태
    window.close()
    window._on_jyor_thread_finished()      # 닫은 뒤 늦게 도착한 끝남 신호
    window.refresh_jyor_info()             # 닫은 뒤 다른 경로로 온 갱신 요청
    started = window._jyor_thread is not before
    if started:
        window._jyor_thread.wait(3000)     # 실패해도 프로세스는 안 죽게
    assert not started, "창을 닫은 뒤에는 JYOR 조회를 새로 시작하지 않는다"


# ---- 7. 글자 버튼도 안에서 뗄 때만 실행 ----
def test_button_released_outside_does_not_run_macro(window):
    from PyQt5.QtCore import Qt, QPoint, QEvent
    ran = []
    window.execute_macro = lambda text: ran.append(text)
    b = window.create_button("XL삼티", "48921", 100, 100, 150, 40)
    c = b.rect().center()
    _mouse(b, QEvent.MouseButtonPress, c, Qt.LeftButton)
    _mouse(b, QEvent.MouseButtonRelease, QPoint(-40, -40), Qt.NoButton)
    assert ran == []
    _mouse(b, QEvent.MouseButtonPress, c, Qt.LeftButton)
    _mouse(b, QEvent.MouseButtonRelease, c, Qt.NoButton)
    assert ran == ["48921"]


# ---- 8. 큰 사진은 로드 때 줄여 두고, 회전본은 캐시한다 ----
def test_large_image_is_downscaled_on_load_and_orientation_cached(window):
    _make_png(os.path.join("images", "big.png"), 3000, 2000)
    ib = window.create_image_button("big.png", "1", 10, 10, 150, 150)
    assert max(ib._pixmap.width(), ib._pixmap.height()) <= 1024
    assert ib._pixmap.width() / ib._pixmap.height() == pytest.approx(1.5, abs=0.01)
    window.rotate_image_button(ib, 90)
    oriented = ib._oriented
    ib.resize(200, 200)
    assert ib._oriented is oriented, "크기만 바뀌면 회전본을 다시 만들지 않는다"
    window.rotate_image_button(ib, 90)
    assert ib._oriented is not oriented


def test_tests_never_send_real_input(window, real_input_calls):
    """안전장치(conftest) 확인: 실행 모드 매크로가 진짜 마우스·키보드 대신 기록만 남긴다."""
    window.execute_macro("48921")
    names = [n for n, _ in real_input_calls]
    assert "pyautogui.moveTo" in names and "pyautogui.doubleClick" in names
    assert names.count("SendInput") >= 2 * len("48921")
