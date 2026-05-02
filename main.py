"""
剑网三 副本工资统计工具
程序入口
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('JX3SalaryStats')
    app.setStyle('Fusion')
    
    style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style.qss')
    if os.path.exists(style_path):
        with open(style_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
