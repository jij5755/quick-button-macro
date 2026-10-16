"""테스트 안전장치(2026-10-16): 테스트가 진짜 마우스·키보드·클립보드·창 전환을 건드리지 못하게 막는다.

배경: 실행 모드에서 버튼을 누르는 테스트가 execute_macro를 막지 않아, 테스트를 돌릴 때마다 실제 마우스가
움직여 더블클릭·스페이스·Ctrl+A·'48921' 입력을 하며 사용자 작업에 끼어들었다. 이제 모든 테스트에서
진짜 입력 대신 `real_input_calls` 목록에 기록만 남는다(예외를 던지면 Qt 이벤트 안에서 프로세스가 죽으므로 기록만).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _FakeInput:
    """pyautogui·pyperclip 대역 — 무엇을 부르든 기록만 한다."""

    def __init__(self, name, calls):
        self._name, self._calls = name, calls

    def __getattr__(self, attr):
        def fake(*args, **kwargs):
            self._calls.append((f"{self._name}.{attr}", args))
            return (0, 0) if attr == "position" else None
        return fake


@pytest.fixture(autouse=True)
def real_input_calls(monkeypatch):
    import main_window
    calls = []
    monkeypatch.setattr(main_window, "pyautogui", _FakeInput("pyautogui", calls))
    monkeypatch.setattr(main_window, "pyperclip", _FakeInput("pyperclip", calls))
    monkeypatch.setattr(main_window, "_send_input", lambda *a: calls.append(("SendInput", a)))
    monkeypatch.setattr(main_window.QuickButtonMacro, "switch_to_jyor",
                        lambda self: calls.append(("switch_to_jyor", ())))
    return calls
