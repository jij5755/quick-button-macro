import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
import os

# main_window.py와 같은 폴더에서 실행되어야 합니다
if __name__ == '__main__':
    app = QApplication(sys.argv)

    try:
        from main_window import QuickButtonMacro
        window = QuickButtonMacro()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"심각한 오류 발생: {e}")
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Critical)
        error_msg.setWindowTitle("오류 발생")
        error_msg.setText("프로그램 실행 중 오류가 발생했습니다.")
        error_msg.setDetailedText(f"오류 내용: {str(e)}")
        error_msg.setStandardButtons(QMessageBox.Ok)
        try:
            if os.path.exists('button_sets.json'):
                import datetime
                backup_filename = f"button_sets_backup_error_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                os.rename('button_sets.json', backup_filename)
                error_msg.setInformativeText(f"설정 파일이 {backup_filename}으로 백업되었습니다.")
        except:
            error_msg.setInformativeText("설정 파일 백업에 실패했습니다.")
        error_msg.exec_()
        sys.exit(1)
