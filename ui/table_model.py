"""
表格数据模型（含团牌、掉落，安全算式支持，支持文字备注-改进版）
"""

from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit
from core.utils import number_to_brick
import re
import ast
import operator as op


def _has_operator_or_brick(s):
    """判断字符串是否含有运算符或砖字，这些是需要进行数学计算的标记"""
    if re.search(r'[＋－×＊÷／+\-*/]', s):
        return True
    if '砖' in s:
        return True
    return False


def _clean_expr(expr_str):
    """移除所有非数字、非运算符、非小数点的字符，保留表达式骨架"""
    s = str(expr_str) if expr_str else ''
    # 统一中英文运算符
    s = s.replace('＋', '+').replace('－', '-').replace('×', '*').replace('＊', '*')
    s = s.replace('÷', '/').replace('／', '/')
    # 只保留数字、小数点、运算符、括号
    s = re.sub(r'[^0-9+\-*/().]', '', s)
    return s


def _safe_eval(expr_str):
    """安全计算经过去文字处理的算式"""
    if not expr_str or not isinstance(expr_str, str):
        return 0, ''
    s = expr_str.strip()
    if not s:
        return 0, ''

    if s.count('(') != s.count(')'):
        return 0, s

    allowed_ops = {
        ast.Add: op.add, ast.Sub: op.sub,
        ast.Mult: op.mul, ast.Div: op.truediv,
        ast.USub: op.neg,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):
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
        try:
            return int(float(s)), s
        except ValueError:
            return 0, s


def _parse_expr(value_str):
    """解析输入，返回 (计算结果, 清洗后的表达式)"""
    s = str(value_str).strip() if value_str else ''
    if not s:
        return 0, ''

    # 砖格式预处理
    def _replace_brick(m):
        bricks = m.group(1) if m.group(1) else '0'
        remainder = m.group(2) if m.group(2) else '0'
        return f'({bricks}*10000+{remainder})'
    s_brick = re.sub(r'(\d+)砖(\d*)', _replace_brick, s)

    # 清洗文字
    s_clean = _clean_expr(s_brick)
    if not s_clean:
        return 0, s

    return _safe_eval(s_clean)


class NoBorderDelegate(QStyledItemDelegate):
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
        editor.setGeometry(option.rect)

    def eventFilter(self, editor, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.FocusOut:
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)
            return True
        return super().eventFilter(editor, event)


class SalaryTableModel(QAbstractTableModel):
    HEADERS = ['角色名', '门派', '普通工资', '普通消费', '英雄工资', '英雄消费', '总工资', '团牌', '掉落']

    FIELD_MAP = {
        '角色名': 2, '门派': 3,
        '普通工资': 4, '普通消费': 5, '英雄工资': 6, '英雄消费': 7, '总工资': 8,
        '团牌': 9, '掉落': 10
    }

    def __init__(self):
        super().__init__()
        self.records = []
        self.statistics = None
        self.show_stats = True
        self.editable_columns = []
        self.visible_columns = list(self.HEADERS)
        self.column_order = list(self.HEADERS)

    def set_editable_columns(self, columns):
        self.editable_columns = columns

    def set_visible_columns(self, visible_names):
        self.visible_columns = visible_names
        self.column_order = visible_names
        self.beginResetModel()
        self.endResetModel()

    def load_data(self, records, statistics):
        self.beginResetModel()
        padded = []
        for r in records:
            r = list(r)
            r.extend([''] * (15 - len(r)))
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
        row, col = index.row(), index.column()
        if self.show_stats and self.statistics and self.statistics.get('count', 0) > 0 and row >= len(self.records):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        col_name = self.visible_columns[col]
        if col_name in self.editable_columns:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == 13:
            return None
        row, col = index.row(), index.column()
        if self.show_stats and self.statistics and self.statistics.get('count', 0) > 0 and row >= len(self.records):
            return self._get_stats_data(row - len(self.records), col, role)
        if row >= len(self.records):
            return None
        record = self.records[row]
        col_name = self.visible_columns[col]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_cell(record, col_name)
        elif role == Qt.ItemDataRole.EditRole:
            return self._get_edit_value(record, col_name)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费', '总工资'):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        row, col = index.row(), index.column()
        if row >= len(self.records):
            return False
        col_name = self.visible_columns[col]
        if col_name not in self.editable_columns:
            return False
        record = list(self.records[row])
        value_str = str(value).strip() if value else ''
        field_idx = self.FIELD_MAP[col_name]

        if col_name in ('角色名', '门派', '团牌', '掉落'):
            record[field_idx] = value_str
        elif col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费'):
            expr_map = {'普通工资': 11, '普通消费': 12, '英雄工资': 13, '英雄消费': 14}
            expr_idx = expr_map[col_name]
            # 保证记录长度足够
            while len(record) <= expr_idx:
                record.append('')
            # 始终存储原始输入
            record[expr_idx] = value_str

            # 尝试提取数值（无论是否包含运算符）
            result, _ = _parse_expr(value_str)  # 清洗并计算
            record[field_idx] = result          # 数值存入对应工资字段

        # 重新计算总工资
        record[8] = record[4] + record[6] - record[5] - record[7]
        self.records[row] = tuple(record)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
        return True

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section < len(self.visible_columns):
                return self.visible_columns[section]
        return None

    def _format_cell(self, record, col_name):
        idx = self.FIELD_MAP[col_name]
        if col_name == '总工资':
            return number_to_brick(record[8])
        elif col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费'):
            expr_map = {'普通工资': 11, '普通消费': 12, '英雄工资': 13, '英雄消费': 14}
            expr_idx = expr_map[col_name]
            raw = record[expr_idx] if len(record) > expr_idx else ''
            if raw:
                # 如果原始输入包含运算符或砖字 → 显示数值（砖格式）
                if _has_operator_or_brick(raw):
                    return number_to_brick(record[idx])
                else:
                    # 纯文本 → 直接显示原始字符串
                    return raw
            else:
                # 无原始输入（如从数据库加载的旧数据） → 显示数值
                return number_to_brick(record[idx])
        else:
            return str(record[idx]) if record[idx] is not None else ''

    def _get_edit_value(self, record, col_name):
        if col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费'):
            expr_map = {'普通工资': 11, '普通消费': 12, '英雄工资': 13, '英雄消费': 14}
            expr_idx = expr_map[col_name]
            if len(record) > expr_idx and record[expr_idx]:
                return record[expr_idx]
            # 没有存储表达式时，返回数值（旧数据）
            return str(record[self.FIELD_MAP[col_name]])
        else:
            return str(record[self.FIELD_MAP[col_name]])

    def _get_stats_data(self, stats_row, col, role):
        if not self.statistics:
            return None
        col_name = self.visible_columns[col]
        if role == Qt.ItemDataRole.DisplayRole:
            is_avg = (stats_row == 0)
            label = '平均' if is_avg else '合计'
            if col_name == '角色名':
                return label
            elif col_name in ('门派', '团牌', '掉落'):
                return ''
            elif col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费', '总工资'):
                base_key = {
                    '普通工资': 'normal_salary',
                    '普通消费': 'normal_consume',
                    '英雄工资': 'hero_salary',
                    '英雄消费': 'hero_consume',
                    '总工资': 'total_salary'
                }[col_name]
                prefix = 'avg_' if is_avg else 'sum_'
                key = prefix + base_key
                return number_to_brick(self.statistics.get(key, 0))
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费', '总工资'):
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
