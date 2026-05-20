"""
表格数据模型 - 全新实现，支持运算式行变灰、文字备注
"""

from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QStyledItemDelegate, QLineEdit
from core.utils import number_to_brick
import re
import ast
import operator as op


# ---------- 工具函数 ----------
def _has_operator_or_brick(s):
    """判断字符串是否包含中英文运算符或砖字"""
    return bool(re.search(r'[＋－×＊÷／+\-*/]', s)) or '砖' in s


def _clean_expression(expr):
    """去除文字，只保留数字、运算符、小数点、括号"""
    if not expr:
        return ''
    # 统一中文运算符
    expr = expr.replace('＋', '+').replace('－', '-').replace('×', '*').replace('＊', '*')
    expr = expr.replace('÷', '/').replace('／', '/')
    # 移除非数学字符
    expr = re.sub(r'[^0-9+\-*/().]', '', expr)
    return expr


def _safe_eval(expr_str):
    """安全计算数学表达式"""
    if not expr_str:
        return 0, ''
    expr_str = expr_str.strip()
    if not expr_str:
        return 0, ''
    if expr_str.count('(') != expr_str.count(')'):
        return 0, expr_str

    allowed = {
        ast.Add: op.add, ast.Sub: op.sub,
        ast.Mult: op.mul, ast.Div: op.truediv,
        ast.USub: op.neg
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed:
            return allowed[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in allowed:
            return allowed[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("不支持的操作")

    try:
        tree = ast.parse(expr_str, mode='eval')
        return int(_eval(tree.body)), expr_str
    except:
        try:
            return int(float(expr_str)), expr_str
        except:
            return 0, expr_str


def _parse_expr(raw_str):
    """解析输入，返回 (数值结果, 原始输入)"""
    s = str(raw_str).strip() if raw_str else ''
    if not s:
        return 0, ''

    # 处理砖格式：1砖9408 → (1*10000+9408)
    s = re.sub(r'(\d+)砖(\d*)', r'(\1*10000+\2)', s)
    # 清洗文字
    clean = _clean_expression(s)
    if not clean:
        return 0, s
    return _safe_eval(clean)


# ---------- 编辑器委托 ----------
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
        pal = editor.palette()
        pal.setColor(QPalette.ColorRole.Text, QColor("#555555"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.Highlight, QColor("#000000"))
        editor.setPalette(pal)
        editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.ItemDataRole.EditRole)
        if val:
            editor.setText(str(val))
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


# ---------- 模型 ----------
class SalaryTableModel(QAbstractTableModel):
    HEADERS = ['角色名', '门派', '普通工资', '普通消费', '英雄工资', '英雄消费', '总工资', '团牌', '掉落']

    # 字段在记录元组中的位置（记录至少15个元素，0‑10为基础数据，11‑14为表达式）
    FIELD_MAP = {
        '角色名': 2, '门派': 3,
        '普通工资': 4, '普通消费': 5, '英雄工资': 6, '英雄消费': 7, '总工资': 8,
        '团牌': 9, '掉落': 10
    }

    def __init__(self):
        super().__init__()
        self.records = []          # 每条记录至少15个元素
        self.statistics = None
        self.show_stats = True
        self.editable_columns = []     # 可编辑的列名列表
        self.visible_columns = list(self.HEADERS)
        self.column_order = list(self.HEADERS)
        self.gray_expression_rows = True   # 默认开启运算式行变灰

    # ---------- 常规 ----------
    def set_editable_columns(self, columns):
        self.editable_columns = columns

    def set_visible_columns(self, visible_names):
        self.visible_columns = visible_names
        self.column_order = visible_names
        self.beginResetModel()
        self.endResetModel()

    def set_gray_expression_rows(self, enabled):
        """启用或关闭运算式行变灰，同时强制刷新整个模型"""
        self.gray_expression_rows = enabled
        self.beginResetModel()
        self.endResetModel()

    def _is_row_expression(self, row):
        """判断某行是否含有运算式（检查表达式字段）"""
        if row < 0 or row >= len(self.records):
            return False
        rec = self.records[row]
        for idx in (11, 12, 13, 14):
            expr = rec[idx] if len(rec) > idx else ''
            if expr and _has_operator_or_brick(expr):
                return True
        return False

    def load_data(self, records, statistics):
        self.beginResetModel()
        padded = []
        for r in records:
            r = list(r)
            r.extend([''] * (15 - len(r)))   # 补齐表达式槽位
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
        # 统计行不可编辑
        if self.show_stats and self.statistics and self.statistics.get('count', 0) > 0 and row >= len(self.records):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        col_name = self.visible_columns[col]
        if col_name in self.editable_columns:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # ---------- 数据访问 ----------
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row, col = index.row(), index.column()

        # 统计行
        if self.show_stats and self.statistics and self.statistics.get('count', 0) > 0 and row >= len(self.records):
            if role == Qt.ItemDataRole.BackgroundRole:
                return QColor(255, 255, 255)   # 统计行始终白色
            return self._get_stats_data(row - len(self.records), col, role)

        if row >= len(self.records):
            return None

        record = self.records[row]
        col_name = self.visible_columns[col]

        # 背景色（关键：显式返回颜色，不依赖 QSS）
        if role == Qt.ItemDataRole.BackgroundRole:
            if self.gray_expression_rows and self._is_row_expression(row):
                return QColor(230, 230, 230)   # 浅灰
            else:
                return QColor(255, 255, 255)   # 白色

        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_cell(record, col_name)

        if role == Qt.ItemDataRole.EditRole:
            return self._get_edit_value(record, col_name)

        if role == Qt.ItemDataRole.TextAlignmentRole:
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

        rec = list(self.records[row])
        value_str = str(value).strip() if value else ''
        field_idx = self.FIELD_MAP[col_name]

        if col_name in ('角色名', '门派', '团牌', '掉落'):
            rec[field_idx] = value_str
        elif col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费'):
            expr_idx = {'普通工资': 11, '普通消费': 12, '英雄工资': 13, '英雄消费': 14}[col_name]
            # 确保表达式槽位存在
            while len(rec) <= expr_idx:
                rec.append('')
            rec[expr_idx] = value_str      # 保存原始输入
            result, _ = _parse_expr(value_str)
            rec[field_idx] = result

        # 重新计算总工资
        rec[8] = rec[4] + rec[6] - rec[5] - rec[7]
        self.records[row] = tuple(rec)

        # 刷新整行的显示、背景、对齐
        self.dataChanged.emit(
            self.index(row, 0),
            self.index(row, self.columnCount() - 1),
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.TextAlignmentRole]
        )
        return True

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section < len(self.visible_columns):
                return self.visible_columns[section]
        return None

    # ---------- 显示与编辑辅助 ----------
    def _format_cell(self, record, col_name):
        idx = self.FIELD_MAP[col_name]
        if col_name == '总工资':
            return number_to_brick(record[8])
        if col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费'):
            expr_idx = {'普通工资': 11, '普通消费': 12, '英雄工资': 13, '英雄消费': 14}[col_name]
            raw = record[expr_idx] if len(record) > expr_idx else ''
            if raw:
                if _has_operator_or_brick(raw):
                    return number_to_brick(record[idx])
                else:
                    return raw
            return number_to_brick(record[idx])
        return str(record[idx]) if record[idx] is not None else ''

    def _get_edit_value(self, record, col_name):
        if col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费'):
            expr_idx = {'普通工资': 11, '普通消费': 12, '英雄工资': 13, '英雄消费': 14}[col_name]
            expr = record[expr_idx] if len(record) > expr_idx else ''
            return expr if expr else str(record[self.FIELD_MAP[col_name]])
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
            if col_name in ('门派', '团牌', '掉落'):
                return ''
            if col_name in ('普通工资', '普通消费', '英雄工资', '英雄消费', '总工资'):
                base = {
                    '普通工资': 'normal_salary',
                    '普通消费': 'normal_consume',
                    '英雄工资': 'hero_salary',
                    '英雄消费': 'hero_consume',
                    '总工资': 'total_salary'
                }[col_name]
                key = ('avg_' if is_avg else 'sum_') + base
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
