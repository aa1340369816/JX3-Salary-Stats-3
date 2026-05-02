"""
表格数据模型 - 支持动态列、自定义排序、团牌/掉落
"""

from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit, QMenu
from core.utils import number_to_brick


# ===== 算式解析函数 =====
def _parse_expr(value_str):
    """解析算式，支持中英文运算符"""
    if not value_str or str(value_str).strip() == '':
        return 0, ''
    s = str(value_str).strip()
    s = s.replace('＋', '+').replace('－', '-').replace('×', '*').replace('＊', '*').replace('÷', '/').replace('／', '/')
    if any(op in s for op in ['+', '-', '*', '/']):
        try:
            result = int(eval(s))
            return result, s
        except:
            pass
    try:
        return int(float(s)), s
    except:
        return 0, s


# ===== 全局列定义 =====
ALL_COLUMNS = [
    ('角色名', 0, 'character_name', False),
    ('门派', 1, 'faction', False),
    ('团牌', 2, 'team_name', False),
    ('掉落', 3, 'loot', False),
    ('普通工资', 4, 'normal_salary', True),
    ('普通消费', 5, 'normal_consume', True),
    ('英雄工资', 6, 'hero_salary', True),
    ('英雄消费', 7, 'hero_consume', True),
    ('总工资', 8, 'total_salary', False),
]


class NoBorderDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setStyleSheet("""
            QLineEdit { 
                border: none; 
                background: #FFFFFF; 
                padding: 0px;
                color: #000000;
            }
        """)
        editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole)
        if value:
            editor.setText(str(value))
        editor.selectAll()

    def eventFilter(self, editor, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.FocusOut:
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)
            return True
        return super().eventFilter(editor, event)


class SalaryTableModel(QAbstractTableModel):

    def __init__(self):
        super().__init__()
        self.records = []
        self.statistics = None
        self.show_stats = True
        self.editable_columns = []
        self.visible_columns = [c[0] for c in ALL_COLUMNS]  # 当前显示的列名列表
        self.header_view = None  # 关联的 QHeaderView

    def set_header_view(self, header_view):
        self.header_view = header_view

    def set_visible_columns(self, names):
        """设置显示的列"""
        self.layoutAboutToBeChanged.emit()
        self.visible_columns = names
        self.layoutChanged.emit()

    def get_visible_columns(self):
        return self.visible_columns

    def set_editable_columns(self, columns):
        self.editable_columns = columns

    def load_data(self, records, statistics):
        self.beginResetModel()
        padded = []
        for r in records:
            r = list(r)
            while len(r) < 11:  # id + date_range + name + faction + 4 salaries + total + team + loot = 11
                r.append('')
            padded.append(tuple(r))
        self.records = padded
        self.statistics = statistics
        self.endResetModel()

    def rowCount(self, parent=None):
        if not self.show_stats or not self.statistics or self.statistics.get('count', 0) == 0:
            return len(self.records)
        return len(self.records) + 2

    def columnCount(self, parent=None):
        return len(self.visible_columns)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        row = index.row()
        col = index.column()

        if self.show_stats and self.statistics and self.statistics.get('count', 0) > 0 and row >= len(self.records):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        # 找到列名 -> ALL_COLUMNS 定义
        col_name = self.visible_columns[col] if col < len(self.visible_columns) else ''
        for name, idx, attr, is_editable in ALL_COLUMNS:
            if name == col_name and is_editable:
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == 13:
            return None

        row = index.row()
        col = index.column()

        if self.show_stats and self.statistics and self.statistics.get('count', 0) > 0 and row >= len(self.records):
            return self._get_stats_data(row - len(self.records), col, role)

        if row >= len(self.records):
            return None

        record = self.records[row]

        # 根据列名取数据
        if col < len(self.visible_columns):
            col_name = self.visible_columns[col]
            for name, idx, attr, _ in ALL_COLUMNS:
                if name == col_name:
                    field_idx = idx + 2 if idx < 7 else None
                    if role == Qt.ItemDataRole.DisplayRole:
                        if idx <= 1:  # 角色名、门派、团牌、掉落
                            return record[idx + 2] if len(record) > idx + 2 else ''
                        elif idx >= 4 and idx <= 7:  # 工资列
                            return number_to_brick(record[idx]) if len(record) > idx else '0'
                        elif idx == 8:  # 总工资
                            return number_to_brick(record[8]) if len(record) > 8 else '0'
                    elif role == Qt.ItemDataRole.EditRole:
                        if idx <= 1:
                            return record[idx + 2] if len(record) > idx + 2 else ''
                        elif idx >= 4 and idx <= 7:
                            expr_idx = {4: 9, 5: 10, 6: 11, 7: 12}[idx]
                            if len(record) > expr_idx and record[expr_idx]:
                                return record[expr_idx]
                            return str(record[idx]) if len(record) > idx else '0'
                    elif role == Qt.ItemDataRole.TextAlignmentRole:
                        if idx >= 4:  # 工资列右对齐
                            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        return Qt.AlignmentFlag.AlignCenter
                    break

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        col = index.column()

        if row >= len(self.records):
            return False

        record = list(self.records[row])
        value_str = str(value).strip() if value else ''
        col_name = self.visible_columns[col] if col < len(self.visible_columns) else ''

        for name, idx, attr, _ in ALL_COLUMNS:
            if name != col_name:
                continue
            if idx <= 3:  # 角色名、门派、团牌、掉落
                record[idx + 2] = value_str
            elif idx in [4, 5, 6, 7]:  # 工资列
                result, expr = _parse_expr(value_str)
                record[idx] = result
                expr_idx = {4: 9, 5: 10, 6: 11, 7: 12}[idx]
                while len(record) <= expr_idx:
                    record.append('')
                record[expr_idx] = expr
            break

        record[8] = record[4] + record[6] - record[5] - record[7]
        self.records[row] = tuple(record)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
        return True

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section < len(self.visible_columns):
                return self.visible_columns[section]
        return None

    def _format_cell(self, record, col):
        # 仅用于兼容旧代码，实际不再使用
        return ''

    def _get_edit_value(self, record, col):
        # 仅用于兼容旧代码，实际不再使用
        return ''

    def _get_stats_data(self, stats_row, col, role):
        if not self.statistics:
            return None

        if col >= len(self.visible_columns):
            return None
        col_name = self.visible_columns[col]

        if role == Qt.ItemDataRole.DisplayRole:
            is_avg = (stats_row == 0)
            label = '平均' if is_avg else '合计'

            # 角色名、门派、团牌、掉落列显示"平均"/"合计"
            for name, idx, attr, _ in ALL_COLUMNS:
                if name == col_name:
                    if idx <= 3:
                        return label if idx <= 1 else ''
                    # 工资列
                    key_map = {
                        '普通工资': ('avg_normal_salary', 'sum_normal_salary'),
                        '普通消费': ('avg_normal_consume', 'sum_normal_consume'),
                        '英雄工资': ('avg_hero_salary', 'sum_hero_salary'),
                        '英雄消费': ('avg_hero_consume', 'sum_hero_consume'),
                        '总工资': ('avg_total_salary', 'sum_total_salary'),
                    }
                    if name in key_map:
                        k = key_map[name][1 if stats_row == 1 else 0]
                        return number_to_brick(self.statistics[k])
                    break

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            for name, idx, attr, _ in ALL_COLUMNS:
                if name == col_name and idx >= 4:
                    return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter

        elif role == Qt.ItemDataRole.FontRole:
            font = QFont()
            font.setBold(True)
            return font

        return None

    def get_record_id(self, row):
        if row < len(self.records):
            return self.records[row][0]
        return None
