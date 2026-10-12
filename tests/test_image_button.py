"""이미지 버튼(2026-10-12): 부속 사진을 버튼처럼 배치하고 터치하면 기존 버튼과 똑같이 매크로가 돈다.

사진 파일은 실행 폴더의 images/ 에 두고 프리셋에는 파일명만 저장한다(프리셋을 다른 PC로 옮겨도 깨지지 않게).
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _make_png(path, w=40, h=30):
    from PyQt5.QtGui import QImage, QColor
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(180, 140, 40))
    assert img.save(path)


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
    yield w
    w.close()
    app.processEvents()


def test_create_image_button_shows_picture_and_sits_at_position(window):
    ib = window.create_image_button("xl_tee.png", "48921", 100, 50, 120, 90)
    assert ib in window.images
    assert ib.geometry().getRect() == (100, 50, 120, 90)
    assert ib.pixmap() is not None and not ib.pixmap().isNull()
    assert ib.image_file == "xl_tee.png"


def test_image_button_click_runs_macro_like_a_button(window):
    ran = []
    window.execute_macro = lambda text: ran.append(text)
    ib = window.create_image_button("xl_tee.png", "48921", 10, 10, 120, 90)
    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import Qt
    QTest.mouseClick(ib, Qt.LeftButton)
    assert ran == ["48921"]


def test_image_button_click_in_edit_mode_selects_instead_of_running(window):
    ran = []
    window.execute_macro = lambda text: ran.append(text)
    window.edit_mode_checkbox.setChecked(True)
    ib = window.create_image_button("xl_tee.png", "48921", 10, 10, 120, 90)
    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import Qt
    QTest.mouseClick(ib, Qt.LeftButton)
    assert ran == []
    assert ib.is_selected
    assert ib in window.get_all_selected_widgets()


def _mouse(widget, kind, pos, buttons):
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    ev = QMouseEvent(kind, pos, widget.mapToGlobal(pos), Qt.LeftButton, buttons, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)      # 실제 전달 경로(받아들이지 않으면 부모로 넘어감)를 그대로 탄다
    return ev


def test_image_button_drag_moves_it_in_edit_mode(window):
    """편집 모드에서 사진을 누른 채 끌면 따라와야 한다(2026-10-12 버그: 누름이 컨테이너로 새어 영역 선택이 시작됨)."""
    from PyQt5.QtCore import Qt, QPoint, QEvent
    window.show()
    window.edit_mode_checkbox.setChecked(True)
    ib = window.create_image_button("xl_tee.png", "48921", 100, 100, 120, 90)
    c = ib.rect().center()
    press = _mouse(ib, QEvent.MouseButtonPress, c, Qt.LeftButton)
    assert press.isAccepted(), "누름을 사진 버튼이 받아들여야 컨테이너로 새지 않는다"
    assert ib.is_selected and not window.buttons_container.selecting
    _mouse(ib, QEvent.MouseMove, c + QPoint(40, 30), Qt.LeftButton)
    _mouse(ib, QEvent.MouseButtonRelease, c + QPoint(40, 30), Qt.NoButton)
    assert (ib.x(), ib.y()) == (140, 130)


def test_image_button_shows_jyor_info_line(window):
    ib = window.create_image_button("xl_tee.png", "48921", 10, 10, 120, 90, erp_code="35584")
    window.refresh_jyor_info()
    assert ib.info_label.text() == "15A  ₩4,400"


def test_image_button_survives_set_switch(window):
    from models import ButtonSet
    window.button_sets.append(ButtonSet("B"))
    window.update_set_list()
    window.create_image_button("xl_tee.png", "48921", 100, 50, 120, 90, erp_code="35584")
    window.save_current_set()
    window.change_button_set(1)
    assert window.images == []
    window.change_button_set(0)
    assert len(window.images) == 1
    ib = window.images[0]
    assert ib.image_file == "xl_tee.png"
    assert ib.geometry().getRect() == (100, 50, 120, 90)
    assert window.image_data[0]["text"] == "48921"
    assert ib.erp_code == "35584"


def test_image_button_saved_in_preset_and_loaded_back(window):
    window.create_image_button("xl_tee.png", "48921", 100, 50, 120, 90, erp_code="35584")
    window.save_current_set()
    window.save_current_preset()
    name = window.preset_combo.currentText()
    with open(os.path.join("presets", f"{name}.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["sets"][0]["images"] == [{
        "file": "xl_tee.png", "text": "48921", "erp_code": "35584",
        "x": 100, "y": 50, "width": 120, "height": 90,
        "rotation": 0, "flip": False,
    }]
    # 화면을 비우고 프리셋에서 다시 읽어도 그대로
    window.images[0].deleteLater()
    window.images, window.image_data = [], []
    window.button_sets[0].images = []
    assert window.load_preset(name)
    assert [ib.image_file for ib in window.images] == ["xl_tee.png"]
    assert window.images[0].geometry().getRect() == (100, 50, 120, 90)


def test_preset_without_images_key_still_loads(window):
    """이미지 버튼이 생기기 전에 저장한 프리셋도 그대로 열린다."""
    name = window.preset_combo.currentText()
    path = os.path.join("presets", f"{name}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["sets"][0].pop("images", None)
    data["sets"][0]["buttons"] = [{"label": "XL카플링", "text": "1", "x": 10, "y": 10}]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    assert window.load_preset(name)
    assert window.images == []
    assert [b.main_label for b in window.buttons] == ["XL카플링"]


def test_missing_image_file_gives_placeholder_not_crash(window):
    ib = window.create_image_button("없는파일.png", "48921", 10, 10, 120, 90)
    assert ib in window.images
    assert "없는파일.png" in ib.text()


def test_delete_selected_removes_image_button(window):
    window.edit_mode_checkbox.setChecked(True)
    ib = window.create_image_button("xl_tee.png", "48921", 10, 10, 120, 90)
    ib.set_selected(True)
    window.delete_selected_items()
    assert window.images == [] and window.image_data == []


def test_copy_paste_duplicates_image_button(window):
    from PyQt5.QtCore import QPoint
    window.edit_mode_checkbox.setChecked(True)
    ib = window.create_image_button("xl_tee.png", "48921", 10, 10, 120, 90, erp_code="35584")
    ib.set_selected(True)
    window.copy_selected_widgets_to_clipboard()
    window.paste_widgets_from_clipboard(QPoint(200, 200))
    assert len(window.images) == 2
    new = window.images[1]
    assert new.image_file == "xl_tee.png"
    assert new.geometry().getRect() == (200, 200, 120, 90)
    assert window.image_data[1]["text"] == "48921"
    assert new.erp_code == "35584"


def test_rotate_turns_picture_90_degrees_each_step(window):
    """사진은 40x30(가로로 긴 그림). 90도 돌리면 세로로 길어져야 한다."""
    ib = window.create_image_button("xl_tee.png", "48921", 10, 10, 200, 200)
    assert ib.pixmap().width() > ib.pixmap().height()
    window.rotate_image_button(ib, 90)
    assert ib.rotation == 90
    assert ib.pixmap().width() < ib.pixmap().height()
    window.rotate_image_button(ib, 90)
    window.rotate_image_button(ib, 90)
    window.rotate_image_button(ib, 90)
    assert ib.rotation == 0
    window.rotate_image_button(ib, -90)
    assert ib.rotation == 270


def test_flip_mirrors_picture_left_right(window):
    """왼쪽 절반만 빨간 그림을 좌우 반전하면 오른쪽 절반이 빨갛다."""
    from PyQt5.QtGui import QImage, QColor
    img = QImage(40, 30, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 255))
    for x in range(20):
        for y in range(30):
            img.setPixelColor(x, y, QColor(255, 0, 0))
    assert img.save(os.path.join("images", "half.png"))
    ib = window.create_image_button("half.png", "1", 10, 10, 46, 36)   # 안쪽 여백 6 → 원본 크기 그대로
    shown = ib.pixmap().toImage()
    assert shown.pixelColor(2, 15).red() == 255
    window.flip_image_button(ib)
    assert ib.flip is True
    shown = ib.pixmap().toImage()
    assert shown.pixelColor(2, 15).red() == 0 and shown.pixelColor(shown.width() - 3, 15).red() == 255
    window.flip_image_button(ib)
    assert ib.flip is False


def test_rotation_and_flip_survive_set_switch_and_copy(window):
    from models import ButtonSet
    from PyQt5.QtCore import QPoint
    window.button_sets.append(ButtonSet("B"))
    window.update_set_list()
    ib = window.create_image_button("xl_tee.png", "48921", 10, 10, 120, 90)
    window.rotate_image_button(ib, -90)
    window.flip_image_button(ib)
    window.save_current_set()
    window.change_button_set(1)
    window.change_button_set(0)
    ib = window.images[0]
    assert (ib.rotation, ib.flip) == (270, True)
    # 복사·붙여넣기에도 따라간다
    window.edit_mode_checkbox.setChecked(True)
    ib.set_selected(True)
    window.copy_selected_widgets_to_clipboard()
    window.paste_widgets_from_clipboard(QPoint(300, 300))
    assert (window.images[1].rotation, window.images[1].flip) == (270, True)


def test_resize_cursor_does_not_linger_after_leaving_edit_mode(window):
    """편집 모드에서 가장자리에 올려 ↔ 커서가 됐어도, 편집 모드를 끄면 보통 커서로 돌아와야 한다(2026-10-12 보고)."""
    from PyQt5.QtCore import Qt, QPoint, QEvent
    window.show()
    window.edit_mode_checkbox.setChecked(True)
    ib = window.create_image_button("xl_tee.png", "48921", 100, 100, 120, 90)
    _mouse(ib, QEvent.MouseMove, QPoint(118, 45), Qt.NoButton)      # 오른쪽 가장자리
    assert ib.cursor().shape() == Qt.SizeHorCursor
    window.edit_mode_checkbox.setChecked(False)
    assert ib.cursor().shape() != Qt.SizeHorCursor
    _mouse(ib, QEvent.MouseMove, QPoint(118, 45), Qt.NoButton)      # 실행 모드에서 다시 가장자리에 올려도
    assert ib.cursor().shape() == Qt.PointingHandCursor


def test_textbox_resize_cursor_also_resets_when_edit_mode_off(window):
    from PyQt5.QtCore import Qt, QPoint, QEvent
    from PyQt5.QtGui import QFont, QColor
    window.show()
    window.edit_mode_checkbox.setChecked(True)
    tb = window.create_textbox("이름표", 100, 100, 120, 40, QFont("맑은 고딕", 9), QColor("#000"), QColor("#fff"))
    _mouse(tb, QEvent.MouseMove, QPoint(60, 38), Qt.NoButton)       # 아래 가장자리
    assert tb.cursor().shape() == Qt.SizeVerCursor
    window.edit_mode_checkbox.setChecked(False)
    assert tb.cursor().shape() == Qt.ArrowCursor


def test_press_shrinks_picture_and_release_springs_back(window):
    """실행 모드에서 누르면 사진이 작아지고(눌리는 느낌), 떼면 짧은 애니메이션 뒤 원래 크기로."""
    from PyQt5.QtCore import Qt, QEvent
    from PyQt5.QtTest import QTest
    window.show()
    ib = window.create_image_button("xl_tee.png", "48921", 100, 100, 120, 90)
    full = ib.pixmap().size()
    c = ib.rect().center()
    _mouse(ib, QEvent.MouseButtonPress, c, Qt.LeftButton)
    pressed = ib.pixmap().size()
    assert pressed.width() < full.width() and pressed.height() < full.height()
    _mouse(ib, QEvent.MouseButtonRelease, c, Qt.NoButton)
    QTest.qWait(400)                      # 애니메이션(0.15초)보다 넉넉히
    assert ib.pixmap().size() == full


def test_press_in_edit_mode_does_not_shrink(window):
    from PyQt5.QtCore import Qt, QEvent
    window.show()
    window.edit_mode_checkbox.setChecked(True)
    ib = window.create_image_button("xl_tee.png", "48921", 100, 100, 120, 90)
    full = ib.pixmap().size()
    _mouse(ib, QEvent.MouseButtonPress, ib.rect().center(), Qt.LeftButton)
    assert ib.pixmap().size() == full


def _topmost_at(window, x, y):
    from PyQt5.QtCore import QPoint
    return window.buttons_container.childAt(QPoint(x, y))


def test_label_button_stays_on_top_of_picture_after_set_switch(window):
    """사진 위에 글자 버튼(이름표)을 겹쳐 둔 조합은 세트를 갔다 와도 버튼이 위에 있어야 한다(리뷰 지적)."""
    from models import ButtonSet
    window.show()
    window.button_sets.append(ButtonSet("B"))
    window.update_set_list()
    window.create_image_button("xl_tee.png", "1", 0, 0, 150, 150)
    label = window.create_button("XL삼티", "1", 0, 110, 150, 40)
    assert _topmost_at(window, 75, 130) is label
    window.save_current_set()
    window.change_button_set(1)
    window.change_button_set(0)
    assert _topmost_at(window, 75, 130) is window.buttons[0]
    assert _topmost_at(window, 75, 50) is window.images[0]


def test_paste_keeps_label_button_on_top_of_picture(window):
    from PyQt5.QtCore import QPoint
    window.show()
    window.edit_mode_checkbox.setChecked(True)
    ib = window.create_image_button("xl_tee.png", "1", 0, 0, 150, 150)
    label = window.create_button("XL삼티", "1", 0, 110, 150, 40)
    ib.set_selected(True)
    label.set_selected(True)
    window.copy_selected_widgets_to_clipboard()
    window.paste_widgets_from_clipboard(QPoint(300, 0))
    assert _topmost_at(window, 375, 130) is window.buttons[1]


def test_import_image_copies_file_into_images_folder(window, tmp_path):
    src = tmp_path / "밖에있는사진.png"
    _make_png(str(src))
    stored = window.import_image_file(str(src))
    assert stored == "밖에있는사진.png"
    assert os.path.exists(os.path.join("images", "밖에있는사진.png"))
    # 같은 이름이 이미 있으면 덮어쓰지 않고 번호를 붙인다
    stored2 = window.import_image_file(str(src))
    assert stored2 == "밖에있는사진_2.png"
