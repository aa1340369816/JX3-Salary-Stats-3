"""
对话框 - 新增/编辑记录 + 统一消息弹窗
"""

from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QPushButton,
    QHBoxLayout, QVBoxLayout, QLabel, QMessageBox, QDateEdit
)
from PyQt6.QtCore import QDate, Qt
from core.utils import parse_brick_input, number_to_brick


FACTIONS = [
    '五毒', '七秀', '万花', '长歌', '药宗',
    '少林', '天策', '纯阳', '藏剑', '苍云',
    '明教', '丐帮', '霸刀', '蓬莱', '凌雪阁', '衍天宗', '刀宗'
]


def show_message(parent, title, text, msg_type='info'):
    """
    统一的消息弹窗 - 无边框，黑白风格
    msg_type: 'info', 'warning', 'question', 'error'
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(400)
    dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
    dialog.setStyleSheet(parent.styleSheet() if parent else '')
    
    layout = QVBoxLayout(dialog)
    layout.setSpacing(16)
    layout.setContentsMargins(20, 20, 20, 20)
    
    # 标题栏
    title_bar = QHBoxLayout()
    title_label = QLabel(title)
    title_label.setStyleSheet('font-family: "JetBrains Mono", monospace; font-size: 14px; font-weight: bold; letter-spacing: 2px;')
    title_bar.addWidget(title_label)
    title_bar.addStretch()
    close_btn = QPushButton('X')
    close_btn.setFixedSize(30, 30)
    close_btn.clicked.connect(dialog.reject)
    title_bar.addWidget(close_btn)
    layout.addLayout(title_bar)
    
    # 分隔线
    sep = QLabel()
    sep.setFixedHeight(2)
    sep.setStyleSheet('background-color: #000000;')
    layout.addWidget(sep)
    
    # 消息内容
    msg_label = QLabel(text)
    msg_label.setWordWrap(True)
    msg_label.setStyleSheet('font-family: "JetBrains Mono", monospace; font-size: 13px; padding: 8px 0px;')
    layout.addWidget(msg_label)
    
    # 按钮
    btn_layout = QHBoxLayout()
    btn_layout.addStretch()
    
    ok_btn = QPushButton('确定')
    ok_btn.setFixedWidth(100)
    ok_btn.clicked.connect(dialog.accept)
    btn_layout.addWidget(ok_btn)
    
    if msg_type == 'question':
        cancel_btn = QPushButton('取消')
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
    
    layout.addLayout(btn_layout)
    
    return dialog.exec() == QDialog.DialogCode.Accepted


def confirm_action(parent, title, text):
    """确认弹窗，返回 True/False"""
    return show_message(parent, title, text, 'question')


class RecordDialog(QDialog):
    
    def __init__(self, parent=None, record=None):
        super().__init__(parent)
        self.record = record
        self.is_edit = record is not None
        
        self.setWindowTitle('编辑记录' if self.is_edit else '新增记录')
        self.setMinimumWidth(420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        
        self._init_ui()
        
        if self.is_edit:
            self._load_record()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 20)
        
        # 标题栏
        title_bar = QHBoxLayout()
        title_label = QLabel('编辑记录' if self.is_edit else '新增记录')
        title_label.setStyleSheet('font-family: "JetBrains Mono", monospace; font-size: 14px; font-weight: bold; letter-spacing: 2px;')
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        close_btn = QPushButton('X')
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.reject)
        title_bar.addWidget(close_btn)
        layout.addLayout(title_bar)
        
        # 分隔线
        sep = QLabel()
        sep.setFixedHeight(2)
        sep.setStyleSheet('background-color: #000000;')
        layout.addWidget(sep)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # 日期
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat('MM.dd')
        
        today = QDate.currentDate()
        day_of_week = today.dayOfWeek()
        monday = today.addDays(-(day_of_week - 1))
        sunday = monday.addDays(6)
        self.start_date_edit.setDate(monday)
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat('MM.dd')
        self.end_date_edit.setDate(sunday)
        
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel('从'))
        date_layout.addWidget(self.start_date_edit)
        date_layout.addWidget(QLabel('到'))
        date_layout.addWidget(self.end_date_edit)
        form_layout.addRow('日期区间:', date_layout)
        
        # 角色名
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('请输入角色名')
        form_layout.addRow('角色名:', self.name_edit)
        
        # 门派
        self.faction_edit = QLineEdit()
        self.faction_edit.setPlaceholderText('请输入门派')
        form_layout.addRow('门派:', self.faction_edit)
        
        # 普通工资
        self.normal_salary_edit = QLineEdit()
        self.normal_salary_edit.setPlaceholderText('如: 4266 或 1砖9408')
        form_layout.addRow('普通工资:', self.normal_salary_edit)
        
        # 普通消费
        self.normal_consume_edit = QLineEdit()
        self.normal_consume_edit.setPlaceholderText('如: 5000 或 0')
        form_layout.addRow('普通消费:', self.normal_consume_edit)
        
        # 英雄工资
        self.hero_salary_edit = QLineEdit()
        self.hero_salary_edit.setPlaceholderText('如: 1砖9408 或 0')
        form_layout.addRow('英雄工资:', self.hero_salary_edit)
        
        # 英雄消费
        self.hero_consume_edit = QLineEdit()
        self.hero_consume_edit.setPlaceholderText('如: 5000 或 0')
        form_layout.addRow('英雄消费:', self.hero_consume_edit)
        
        # 总工资预览
        self.total_preview = QLabel('总工资: 0')
        self.total_preview.setStyleSheet('font-weight: bold; font-size: 14px; padding: 4px 0px;')
        form_layout.addRow('', self.total_preview)
        
        layout.addLayout(form_layout)
        
        # 实时预览
        self.normal_salary_edit.textChanged.connect(self._update_preview)
        self.normal_consume_edit.textChanged.connect(self._update_preview)
        self.hero_salary_edit.textChanged.connect(self._update_preview)
        self.hero_consume_edit.textChanged.connect(self._update_preview)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_btn = QPushButton('取消')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        self.save_btn = QPushButton('保存')
        self.save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _load_record(self):
        _, date_range, name, faction, n_sal, n_con, h_sal, h_con, _ = self.record
        
        parts = date_range.split('-')
        if len(parts) == 2:
            start_parts = parts[0].split('.')
            end_parts = parts[1].split('.')
            if len(start_parts) == 2 and len(end_parts) == 2:
                year = QDate.currentDate().year()
                self.start_date_edit.setDate(QDate(year, int(start_parts[0]), int(start_parts[1])))
                self.end_date_edit.setDate(QDate(year, int(end_parts[0]), int(end_parts[1])))
        
        self.name_edit.setText(name)
        self.faction_edit.setText(faction)
        self.normal_salary_edit.setText(number_to_brick(n_sal))
        self.normal_consume_edit.setText(number_to_brick(n_con))
        self.hero_salary_edit.setText(number_to_brick(h_sal))
        self.hero_consume_edit.setText(number_to_brick(h_con))
        self._update_preview()
    
    def _update_preview(self):
        n_sal = parse_brick_input(self.normal_salary_edit.text())
        n_con = parse_brick_input(self.normal_consume_edit.text())
        h_sal = parse_brick_input(self.hero_salary_edit.text())
        h_con = parse_brick_input(self.hero_consume_edit.text())
        total = n_sal + h_sal - n_con - h_con
        self.total_preview.setText(f'总工资: {number_to_brick(total)}')
    
    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            show_message(self, '提示', '请输入角色名', 'warning')
            return
        
        start_date = self.start_date_edit.date()
        end_date = self.end_date_edit.date()
        
        if start_date > end_date:
            show_message(self, '提示', '起始日期不能晚于结束日期', 'warning')
            return
        
        date_range = f'{start_date.month():02d}.{start_date.day():02d}-{end_date.month():02d}.{end_date.day():02d}'
        start_str = f'{start_date.month():02d}.{start_date.day():02d}'
        end_str = f'{end_date.month():02d}.{end_date.day():02d}'
        
        faction = self.faction_edit.text().strip()
        n_sal = parse_brick_input(self.normal_salary_edit.text())
        n_con = parse_brick_input(self.normal_consume_edit.text())
        h_sal = parse_brick_input(self.hero_salary_edit.text())
        h_con = parse_brick_input(self.hero_consume_edit.text())
        
        self.result_data = (date_range, start_str, end_str, name, faction, n_sal, n_con, h_sal, h_con)
        self.accept()
    
    def get_data(self):
        return self.result_data
