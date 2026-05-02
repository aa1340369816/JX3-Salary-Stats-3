"""
表格数据模型（安全算式支持）
"""

from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit
from core.utils import number_to_brick
import re


def _safe_eval(expr_str):
    """
    安全计算简单四则运算（+ - * /），支持中文运算符。
    避免使用 eval()，只处理数字和运算符。
    """
    if not expr_str or not isinstance(expr_str, str):
        return 0, ''
    s = expr_str.strip()
    if not s:
        return 0, ''

    # 统一中英文运算符
    trans = str.maketrans('＋－×＊÷／', '+-**//')
    s = s.translate(trans).replace(' ', '')

    # 只允许数字、小数点、加减乘除号、括号
    if re.search(r'[^0-9+\-*/().]', s):
        # 有非法字符则尝试直接转为数字
        try:
            return int(float(s)), s
        except ValueError:
            return 0, s

    # 安全检查括号匹配
    if s.count('(') != s.count(')'):
        return 0, s

    # 使用 ast 进行安全求值（支持二元运算和一元负号）
    import ast
    import operator as op

    allowed_ops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.USub: op.neg,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):     # 兼容旧版
            return node.n
        elif isinstance(node, ast.UnaryOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](eval_node(node.operand))
        elif isinstance(node, ast.BinOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](eval_node(node.left), eval_node(node.right))
        else:
            raise ValueError("不支持的表达式")

    try:
        tree = ast.parse(s, mode='eval')
        result = eval_node(tree.body)
        return int(result), s
    except Exception:
        # 如果安全求值失败，回退尝试转数字
        try:
            return int(float(s)), s
        except ValueError:
            return 0, s


def _parse_expr(value_str):
    """解析算式，支持中英文运算符，返回(计算结果, 原始表达式)"""
    return _safe_eval(str(value_str).strip() if value_str else '')


class NoBorderDelegate(QStyledItemDelegate):
    """去掉编辑单元格时的黑框，并让编辑框占满单元格"""
    
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setStyleSheet("""
            QLineEdit { 
                border: none; 
                background: #FFFFFF; 
                padding: 0px 4px;
                color: #555555;
                selection-background-color: #000000;
                selection-color: #FFFFFF;
            }
        """)
        from PyQt6.QtGui import QPalette, QColor
        palette = editor.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor("#555555"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#000000"))
        editor.setPalette(palette)

        editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole)
        if value:
            editor.setText(str(value))
        editor.selectAll()

    def updateEditorGeometry(self, editor, option, index):
        """强制编辑器覆盖整个单元格"""
        editor.setGeometry(option.rect)

    def eventFilter(self, editor, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.FocusOut:
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)
            return True
        return super().eventFilter(editor, event)


class SalaryTableModel(QAbstractTableModel):
    HEADERS = ['角色名', '门派', '普通工资', '普通消费', '英雄工资', '英雄消费', '总工资']

    def __init__(self):
        super().__init__()
        self.records = []          # 每条记录至少包含14个元素：[id, date_range, name, faction, n_sal, n_con, h_sal, h_con, total, ...表达式]
        self.statistics = None
        self.show_stats = True
        self.editable_columns = []

    def set_editable_columns(self, columns):
        self.editable_columns = columns

    def load_data(self, records, statistics):
        self.beginResetModel()
        # 确保每条记录有足够的长度存放表达式（索引9-12）
        padded = []
        for r in records:
            r = list(r)
            r.extend([''] * (13 - len(r)))
            padded.append(tuple(r))
        self.records = padded
        self.statistics = statistics
        self.endResetModel()

    def rowCount(self, parent=None):
        if not self.show_stats or not self.statistics or self.statistics.get('count', 0) == 0:
            return len(self.records)
        return len(self.records) + 2

    def columnCount(self, parent=None):
        return len(self.HEADERS)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        row = index.row()
        col = index.column()

        # 统计行不可编辑
        if self.show_stats and self.statistics and self.statistics.get('count', 0) > 0 and row >= len(self.records):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if col in self.editable_columns:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        # 隐藏焦点虚线框
        if role == 13:
            return None

        row, col = index.row(), index.column()

        # 统计行
        if self.show_stats and self.statistics and self.statistics.get('count', 0) > 0 and row >= len(self.records):
            return self._get_stats_data(row - len(self.records), col, role)

        if row >= len(self.records):
            return None

        record = self.records[row]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_cell(record, col)
        elif role == Qt.ItemDataRole.EditRole:
            return self._get_edit_value(record, col)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight if col >= 2 else Qt.AlignmentFlag.AlignCenter
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        row, col = index.row(), index.column()
        if row >= len(self.records) or col not in self.editable_columns:
            return False

        record = list(self.records[row])
        value_str = str(value).strip() if value else ''

        if col == 0:
            record[2] = value_str
        elif col == 1:
            record[3] = value_str
        elif col in (2, 3, 4, 5):
            result, expr = _parse_expr(value_str)
            field_map = {2: 4, 3: 5, 4: 6, 5: 7}
            record[field_map[col]] = result
            expr_idx = {2: 9, 3: 10, 4: 11, 5: 12}[col]
            # 确保列表长度足够
            while len(record) <= expr_idx:
                record.append('')
            record[expr_idx] = expr

        # 重新计算总工资
        record[8] = record[4] + record[6] - record[5] - record[7]
        self.records[row] = tuple(record)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
        return True

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def _format_cell(self, record, col):
        if col == 0:
            return record[2]
        elif col == 1:
            return record[3]
        elif col == 2:
            return number_to_brick(record[4])
        elif col == 3:
            return number_to_brick(record[5])
        elif col == 4:
            return number_to_brick(record[6])
        elif col == 5:
            return number_to_brick(record[7])
        elif col == 6:
            return number_to_brick(record[8])
        return ''

    def _get_edit_value(self, record, col):
        """编辑时优先显示表达式，否则显示数值"""
        expr_idx_map = {2: 9, 3: 10, 4: 11, 5: 12}
        if col in expr_idx_map and len(record) > expr_idx_map[col] and record[expr_idx_map[col]]:
            return record[expr_idx_map[col]]
        # 返回数字字符串
        values = {2: record[4], 3: record[5], 4: record[6], 5: record[7]}
        return str(values.get(col, ''))

    def _get_stats_data(self, stats_row, col, role):
        if not self.statistics:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            is_avg = (stats_row == 0)
            label = '平均' if is_avg else '合计'

            if col == 0:
                return label
            elif col == 1:
                return ''
            else:
                key_base = ['normal_salary', 'normal_consume', 'hero_salary', 'hero_consume', 'total_salary']
                prefix = 'avg_' if is_avg else 'sum_'
                key = prefix + key_base[col - 2] if col >= 2 else ''
                return number_to_brick(self.statistics.get(key, 0))

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight if col >= 2 else Qt.AlignmentFlag.AlignCenter

        elif role == Qt.ItemDataRole.FontRole:
            font = QFont()
            font.setBold(True)
            return font

        return None

    def get_record_id(self, row):
        if row < len(self.records):
            return self.records[row][0]
        return None
