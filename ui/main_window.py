"""
主窗口 - 剑网三副本工资统计（优化版 + 启动定位修复）
"""

import os
import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFileDialog, QLabel
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QShortcut, QKeySequence

from core.database import (
    init_database, get_all_records, get_date_list,
    add_record, update_record, delete_record
)
from core.importer import import_excel
from ui.table_model import SalaryTableModel, NoBorderDelegate
from ui.dialogs import RecordDialog, show_message, confirm_action
from core.utils import number_to_brick
from openpyxl import Workbook


def _calc_stats(records):
    if not records:
        return {
            'count': 0,
            'avg_normal_salary': 0, 'avg_normal_consume': 0,
            'avg_hero_salary': 0, 'avg_hero_consume': 0, 'avg_total_salary': 0,
            'sum_normal_salary': 0, 'sum_normal_consume': 0,
            'sum_hero_salary': 0, 'sum_hero_consume': 0, 'sum_total_salary': 0,
        }
    n = len(records)
    sums = [sum(r[i] for r in records) for i in [4, 5, 6, 7, 8]]
    return {
        'count': n,
        'avg_normal_salary': sums[0] // n, 'avg_normal_consume': sums[1] // n,
        'avg_hero_salary': sums[2] // n, 'avg_hero_consume': sums[3] // n,
        'avg_total_salary': sums[4] // n,
        'sum_normal_salary': sums[0], 'sum_normal_consume': sums[1],
        'sum_hero_salary': sums[2], 'sum_hero_consume': sums[3],
        'sum_total_salary': sums[4],
    }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('剑网三 副本工资统计')
        self.setMinimumSize(1100, 650)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.pending_records = []
        self.pending_deletes = []
        self.undo_stack = []

        init_database()
        self._init_ui()                # 单下划线
        self._set_default_week()
        self._refresh_data()

        self.save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        self.save_shortcut.activated.connect(self._on_save)
        self.undo_shortcut = QShortcut(QKeySequence('Ctrl+Z'), self)
        self.undo_shortcut.activated.connect(self._on_undo)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 自定义标题栏
        title_bar = QWidget()
        title_bar.setObjectName('titleBar')
        title_bar.setFixedHeight(40)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(16, 0, 8, 0)
        title_bar_layout.setSpacing(0)
        bar_title = QLabel('JX3 SALARY STATS')
        bar_title.setObjectName('barTitle')
        title_bar_layout.addWidget(bar_title)
        title_bar_layout.addStretch()
        min_btn = QPushButton('_')
        min_btn.setObjectName('minBtn')
        min_btn.setFixedSize(36, 28)
        min_btn.clicked.connect(self.showMinimized)
        title_bar_layout.addWidget(min_btn)
        close_btn = QPushButton('X')
        close_btn.setObjectName('closeBtn')
        close_btn.setFixedSize(36, 28)
        close_btn.clicked.connect(self.close)
        title_bar_layout.addWidget(close_btn)
        main_layout.addWidget(title_bar)

        # 内容区域
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(10, 10, 10, 10)

        # 工具栏
        toolbar_layout = QHBoxLayout()
        title_label = QLabel('剑网三 副本工资统计')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setObjectName('titleLabel')
        toolbar_layout.addWidget(title_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QLabel('日期:'))
        self.date_filter_combo = QComboBox()
        self.date_filter_combo.setMinimumWidth(150)
        self.date_filter_combo.currentTextChanged.connect(self._on_date_filter_changed)
        toolbar_layout.addWidget(self.date_filter_combo)
        toolbar_layout.addWidget(QLabel('门派:'))
        self.faction_filter_combo = QComboBox()
        self.faction_filter_combo.setMinimumWidth(100)
        self.faction_filter_combo.addItem('全部')
        self.faction_filter_combo.currentTextChanged.connect(self._filter_data)
        toolbar_layout.addWidget(self.faction_filter_combo)
        toolbar_layout.addStretch()
        self.import_btn = QPushButton('导入Excel')
        self.import_btn.clicked.connect(self._on_import)
        toolbar_layout.addWidget(self.import_btn)
        self.export_btn = QPushButton('导出Excel')
        self.export_btn.clicked.connect(self._on_export)
        toolbar_layout.addWidget(self.export_btn)
        self.add_btn = QPushButton('新增记录')
        self.add_btn.clicked.connect(self._on_add)
        toolbar_layout.addWidget(self.add_btn)
        self.delete_btn = QPushButton('删除')
        self.delete_btn.clicked.connect(self._on_delete)
        toolbar_layout.addWidget(self.delete_btn)
        self.save_btn = QPushButton('保存')
        self.save_btn.setObjectName('saveBtn')
        self.save_btn.clicked.connect(self._on_save)
        toolbar_layout.addWidget(self.save_btn)
        content_layout.addLayout(toolbar_layout)

        # 表格
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table_model = SalaryTableModel()
        self.table_model.set_editable_columns([0, 1, 2, 3, 4, 5])
        self.table_model.dataChanged.connect(self._on_cell_changed)
        self.table_view.setModel(self.table_model)
        self.table_view.setItemDelegate(NoBorderDelegate(self.table_view))
        content_layout.addWidget(self.table_view)
        main_layout.addWidget(self.content_widget)

        # 状态栏
        self.status_label = QLabel('就绪')
        self.statusBar().addWidget(self.status_label)
        self._drag_pos = None

    # ---------- 窗口拖拽 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ---------- 关闭确认 ----------
    def closeEvent(self, event):
        if self.pending_records or self.pending_deletes:
            ok = confirm_action(self, '未保存的更改',
                                f'有 {len(self.pending_records)} 条待新增\n{len(self.pending_deletes)} 条待删除\n\n确定不保存就关闭吗？')
            if not ok:
                event.ignore()
                return
        event.accept()

    # ---------- 计算当前CD周（北京时间，周一7点刷新） ----------
    def _set_default_week(self):
        utc_now = datetime.datetime.utcnow()
        beijing_now = utc_now + datetime.timedelta(hours=8)
        weekday = beijing_now.weekday()
        hour = beijing_now.hour
        if weekday == 0 and hour < 7:
            monday = beijing_now.date() - datetime.timedelta(days=7)
        else:
            monday = beijing_now.date() - datetime.timedelta(days=weekday)
        sunday = monday + datetime.timedelta(days=6)
        start_str = f'{monday.month:02d}.{monday.day:02d}'
        end_str = f'{sunday.month:02d}.{sunday.day:02d}'
        self._default_week_str = f'{start_str}-{end_str}'
        self._first_load = True

    def _copy_last_week_characters(self):
        date_list = get_date_list()
        if not date_list:
            return
        last_week = None
        for d in reversed(date_list):
            if d != self._default_week_str:
                last_week = d
                break
        if not last_week:
            return
        last_week_records = get_all_records(last_week)
        if not last_week_records:
            return

        existing_names = set()
        current_records = get_all_records(self._default_week_str)
        for r in current_records:
            existing_names.add(r[2])
        for pr in self.pending_records:
            if pr[0] == self._default_week_str:
                existing_names.add(pr[3])

        parts = self._default_week_str.split('-')
        start_date = parts[0]
        end_date = parts[1] if len(parts) > 1 else parts[0]
        for r in last_week_records:
            name = r[2]
            if name not in existing_names:
                new_record = (self._default_week_str, start_date, end_date, name, r[3], 0, 0, 0, 0)
                self.pending_records.append(new_record)
                existing_names.add(name)

    # ---------- 数据刷新 ----------
    def _refresh_data(self):
        # 首次加载：自动定位到当前周
        if hasattr(self, '_first_load') and self._first_load:
            self._first_load = False
            idx = self.date_filter_combo.findText(self._default_week_str)
            if idx >= 0:
                self.date_filter_combo.setCurrentIndex(idx)
            else:
                self.date_filter_combo.addItem(self._default_week_str)
                self.date_filter_combo.setCurrentText(self._default_week_str)
                self._copy_last_week_characters()

        current_date = self.date_filter_combo.currentText()
        date_filter = current_date if current_date and current_date != '全部' else None

        all_db = get_all_records(None)
        if date_filter:
            base_records = [r for r in all_db if r[1] == date_filter]
        else:
            base_records = list(all_db)

        # 合并缓存
        for i, pr in enumerate(self.pending_records):
            temp_id = -(i + 1)
            total = pr[5] + pr[7] - pr[6] - pr[8]
            temp_record = (temp_id, pr[0], pr[3], pr[4], pr[5], pr[6], pr[7], pr[8], total)
            if not date_filter or pr[0] == date_filter:
                base_records.append(temp_record)

        base_records = [r for r in base_records if r[0] not in self.pending_deletes]

        # ===== 全部视图按角色聚合 =====
        if date_filter is None:
            # 按角色聚合
            aggregated = {}
            for r in base_records:
                name = r[2]
                if name in ('平均', '合计'):
                    continue
                if name not in aggregated:
                    # 存储：门派, 普通工资, 普通消费, 英雄工资, 英雄消费
                    aggregated[name] = [r[3], 0, 0, 0, 0]
                agg = aggregated[name]
                agg[1] += r[4]
                agg[2] += r[5]
                agg[3] += r[6]
                agg[4] += r[7]

            base_records = []
            for i, (name, data) in enumerate(aggregated.items()):
                faction = data[0]
                total = data[1] + data[3] - data[2] - data[4]
                base_records.append((-i - 1, '', name, faction, data[1], data[2], data[3], data[4], total))
            # 按角色名排序
            base_records.sort(key=lambda r: r[2])

            # 禁止编辑
            self.table_model.set_editable_columns([])
            # 仅禁用新增和删除（导入/导出/保存仍可用）
            self.add_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        else:
            # 正常周视图：允许编辑，恢复按钮
            self.table_model.set_editable_columns([0, 1, 2, 3, 4, 5])
            self.add_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
        # ===== 聚合结束 =====

        # 更新门派过滤器
        current_faction = self.faction_filter_combo.currentText()
        self.faction_filter_combo.blockSignals(True)
        self.faction_filter_combo.clear()
        self.faction_filter_combo.addItem('全部')
        factions = sorted({r[3] for r in all_db})
        for f in factions:
            self.faction_filter_combo.addItem(f)
        idx = self.faction_filter_combo.findText(current_faction)
        if idx >= 0:
            self.faction_filter_combo.setCurrentIndex(idx)
        else:
            self.faction_filter_combo.setCurrentIndex(0)
        self.faction_filter_combo.blockSignals(False)

        # 更新日期过滤器
        self.date_filter_combo.blockSignals(True)
        self.date_filter_combo.clear()
        self.date_filter_combo.addItem('全部')
        for d in get_date_list():
            self.date_filter_combo.addItem(d)
        idx = self.date_filter_combo.findText(current_date)
        if idx >= 0:
            self.date_filter_combo.setCurrentIndex(idx)
        else:
            if self.date_filter_combo.currentText() != current_date:
                self.date_filter_combo.setCurrentText(current_date)
        self.date_filter_combo.blockSignals(False)

        # 门派过滤
        faction_filter = self.faction_filter_combo.currentText()
        if faction_filter != '全部':
            base_records = [r for r in base_records if r[3] == faction_filter]

        data_records = [r for r in base_records if r[2] not in ('平均', '合计')]
        stats = _calc_stats(data_records)
        self.table_model.load_data(base_records, stats)
        self.table_view.resizeColumnsToContents()

        window_title = '剑网三 副本工资统计'
        if current_date and current_date != '全部':
            window_title += f' - {current_date}'
        else:
            window_title += ' - 全部日期'
        self.setWindowTitle(window_title)

        unsaved = len(self.pending_records) + len(self.pending_deletes)
        if unsaved > 0:
            self.status_label.setText(f'共 {len(data_records)} 条记录 | 有 {unsaved} 条未保存')
            self.save_btn.setEnabled(True)
        else:
            self.status_label.setText(f'共 {len(data_records)} 条记录')
            self.save_btn.setEnabled(False)

    def _filter_data(self):
        self._refresh_data()

    def _on_date_filter_changed(self):
        self._refresh_data()

    # ---------- 单元格编辑 ----------
    def _on_cell_changed(self, topLeft, bottomRight):
        row, col = topLeft.row(), topLeft.column()
        record_id = self.table_model.get_record_id(row)
        if record_id is None:
            return
        record = None
        for r in self.table_model.records:
            if r[0] == record_id:
                record = r
                break
        if record is None:
            return

        field_map = {0: 2, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7}
        if col in field_map:
            old_record = None
            if record_id > 0:
                all_db = get_all_records(None)
                for r in all_db:
                    if r[0] == record_id:
                        old_record = r
                        break
            else:
                idx = -record_id - 1
                if idx < len(self.pending_records):
                    pr = self.pending_records[idx]
                    total = pr[5] + pr[7] - pr[6] - pr[8]
                    old_record = (record_id, pr[0], pr[3], pr[4], pr[5], pr[6], pr[7], pr[8], total)
            if old_record:
                self.undo_stack.append({
                    'record_id': record_id,
                    'old_record': old_record,
                    'is_db': record_id > 0
                })
                if len(self.undo_stack) > 50:
                    self.undo_stack.pop(0)

        if record_id > 0:
            try:
                update_record(record_id, record[1], '', '', record[2], record[3],
                              record[4], record[5], record[6], record[7])
                self.status_label.setText('已保存')
            except Exception as e:
                self.status_label.setText(f'保存失败: {e}')
        else:
            idx = -record_id - 1
            if idx < len(self.pending_records):
                pr = self.pending_records[idx]
                self.pending_records[idx] = (
                    pr[0], pr[1], pr[2], record[2], record[3],
                    record[4], record[5], record[6], record[7]
                )

    # ---------- 保存 ----------
    def _on_save(self):
        if not self.pending_records and not self.pending_deletes:
            show_message(self, '提示', '没有需要保存的更改')
            return
        ok = confirm_action(self, '确认保存',
                            f'待新增 {len(self.pending_records)} 条记录\n待删除 {len(self.pending_deletes)} 条记录\n\n确定保存吗？')
        if not ok:
            return
        errors = []
        for rid in self.pending_deletes:
            try:
                if rid > 0:
                    delete_record(rid)
            except Exception as e:
                errors.append(f'删除失败: {e}')
        for pr in self.pending_records:
            try:
                add_record(*pr)
            except Exception as e:
                errors.append(f'新增失败: {e}')
        self.pending_records.clear()
        self.pending_deletes.clear()
        if errors:
            show_message(self, '部分失败', '\n'.join(errors), 'warning')
        else:
            show_message(self, '保存成功', '所有更改已保存')
        self._refresh_data()

    # ---------- 导入 ----------
    def _on_import(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('选择Excel文件')
        dialog.setNameFilter('Excel文件 (*.xlsx *.xls)')
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dialog.setStyleSheet(self.styleSheet())
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        if not os.path.exists(desktop):
            desktop = os.path.expanduser('~')
        dialog.setDirectory(desktop)
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        file_paths = dialog.selectedFiles()
        if not file_paths:
            return
        file_path = file_paths[0]
        records, error = import_excel(file_path)
        if error:
            show_message(self, '导入失败', error, 'error')
            return
        if not records:
            show_message(self, '提示', '未发现有效数据')
            return
        ok = confirm_action(self, '导入数据',
                            f'发现 {len(records)} 条记录\n\n确定 = 直接保存\n取消 = 放入缓存')
        if ok:
            count = 0
            for rec in records:
                try:
                    add_record(*rec)
                    count += 1
                except Exception as e:
                    show_message(self, '错误', f'保存失败: {e}', 'warning')
            show_message(self, '导入成功', f'成功导入 {count} 条记录')
        else:
            self.pending_records.extend(records)
            show_message(self, '已缓存', f'{len(records)} 条已缓存，请点保存')
        self._refresh_data()

    # ---------- 导出 ----------
    def _on_export(self):
        data_records = [r for r in self.table_model.records if r[2] not in ('平均', '合计')]
        current_date = self.date_filter_combo.currentText()
        if not data_records:
            show_message(self, '提示', '当前没有数据可导出', 'warning')
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, '保存Excel文件', f'{current_date}.xlsx',
            'Excel文件 (*.xlsx)',
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if not file_path:
            return
        try:
            wb = Workbook()
            ws = wb.active
            if current_date and current_date != '全部':
                ws.cell(row=1, column=1, value=f'日期{current_date}')
            else:
                ws.cell(row=1, column=1, value='日期全部')
            headers = ['角色名', '门派', '普通工资', '普通消费', '英雄工资', '英雄消费', '总工资']
            for i, h in enumerate(headers, 1):
                ws.cell(row=3, column=i, value=h)
            for row_idx, record in enumerate(data_records, 4):
                ws.cell(row=row_idx, column=1, value=record[2])
                ws.cell(row=row_idx, column=2, value=record[3])
                for col in range(3, 8):
                    ws.cell(row=row_idx, column=col, value=number_to_brick(record[col+1]))
            wb.save(file_path)
            show_message(self, '导出成功', f'已保存到 {os.path.basename(file_path)}')
        except Exception as e:
            show_message(self, '导出失败', str(e), 'error')

    # ---------- 新增/删除/撤销 ----------
    def _on_add(self):
        dialog = RecordDialog(self)
        if dialog.exec() == RecordDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.pending_records.append(data)
            self._refresh_data()

    def _on_delete(self):
        index = self.table_view.currentIndex()
        if not index.isValid():
            show_message(self, '提示', '请先选中一条记录', 'warning')
            return
        row = index.row()
        record_id = self.table_model.get_record_id(row)
        if record_id is None:
            show_message(self, '提示', '不能删除统计行', 'warning')
            return
        ok = confirm_action(self, '确认删除', '确定要删除这条记录吗？')
        if ok:
            if record_id > 0:
                self.pending_deletes.append(record_id)
            else:
                idx = -record_id - 1
                if idx < len(self.pending_records):
                    self.pending_records.pop(idx)
            self._refresh_data()

    def _on_undo(self):
        if not self.undo_stack:
            self.status_label.setText('没有可撤销的操作')
            return
        last = self.undo_stack.pop()
        rid = last['record_id']
        old = last['old_record']
        is_db = last['is_db']
        if is_db:
            try:
                update_record(rid, old[1], '', '', old[2], old[3],
                              old[4], old[5], old[6], old[7])
            except Exception as e:
                self.status_label.setText(f'撤销失败: {e}')
                return
        else:
            idx = -rid - 1
            if idx < len(self.pending_records):
                pr = list(self.pending_records[idx])
                pr[5], pr[6], pr[7], pr[8] = old[4], old[5], old[6], old[7]
                self.pending_records[idx] = tuple(pr)
        self._refresh_data()
        self.status_label.setText('已撤销')
