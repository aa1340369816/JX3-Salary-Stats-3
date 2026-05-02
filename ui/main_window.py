"""
主窗口 - 剑网三副本工资统计
"""

import os
import json
from PyQt6.QtCore import Qt, QDate, QByteArray
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QTableView, QHeaderView,
    QFileDialog, QLabel, QMenu
)

from core.database import (
    init_database, get_all_records, get_date_list, get_statistics,
    add_record, update_record, delete_record
)
from core.importer import import_excel
from ui.table_model import SalaryTableModel, NoBorderDelegate, ALL_COLUMNS
from ui.dialogs import RecordDialog, show_message, confirm_action


class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('剑网三 副本工资统计')
        self.setMinimumSize(1200, 700)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        self.pending_records = []
        self.pending_deletes = []
        self.undo_stack = []
        
        init_database()
        self._init_ui()
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
        
        # === 自定义标题栏 ===
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
        
        # === 内容区域 ===
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # === 顶部工具栏 ===
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
        
        # === 表格 ===
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # 启用列拖拽
        self.table_view.horizontalHeader().setSectionsMovable(True)
        self.table_view.horizontalHeader().sectionMoved.connect(self._on_column_moved)
        
        # 右键菜单控制列显隐
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self._show_column_menu)
        
        self.table_model = SalaryTableModel()
        self.table_model.set_header_view(self.table_view.horizontalHeader())
        # 工资列可编辑（团牌和掉落暂不开通编辑，如需可加）
        self.table_model.set_editable_columns([0, 1, 2, 3, 4, 5, 6, 7])
        self.table_model.dataChanged.connect(self._on_cell_changed)
        self.table_view.setModel(self.table_model)
        self.table_view.setItemDelegate(NoBorderDelegate(self.table_view))
        
        # 恢复列配置
        self._restore_column_state()
        
        content_layout.addWidget(self.table_view)
        
        main_layout.addWidget(self.content_widget)
        
        # === 状态栏 ===
        self.status_label = QLabel('就绪')
        self.statusBar().addWidget(self.status_label)
        
        self._drag_pos = None
    
    # ==================== 窗口拖动 ====================
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
    
    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._drag_pos = None
    
    def closeEvent(self, event):
        if self.pending_records or self.pending_deletes:
            ok = confirm_action(
                self, '未保存的更改',
                f'有 {len(self.pending_records)} 条待新增\n{len(self.pending_deletes)} 条待删除\n\n确定不保存就关闭吗？'
            )
            if not ok:
                event.ignore()
                return
        event.accept()
    
    # ==================== 列配置管理 ====================
    def _get_column_config_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'column_config.json')
    
    def _load_column_config(self):
        path = self._get_column_config_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_column_config(self, config):
        path = self._get_column_config_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def _save_column_order(self):
        header = self.table_view.horizontalHeader()
        state = header.saveState()
        config = self._load_column_config()
        config['header_state'] = state.toBase64().data().decode()
        self._save_column_config(config)
    
    def _restore_column_state(self):
        config = self._load_column_config()
        if 'header_state' in config:
            try:
                state = QByteArray.fromBase64(config['header_state'].encode())
                self.table_view.horizontalHeader().restoreState(state)
            except:
                pass
        
        # 可见性
        if 'visible' in config:
            visible_names = [name for name, visible in config['visible'].items() if visible]
            if visible_names:
                self.table_model.set_visible_columns(visible_names)
    
    def _on_column_moved(self, logicalIndex, oldVisualIndex, newVisualIndex):
        self._save_column_order()
    
    def _show_column_menu(self, pos):
        menu = QMenu(self)
        header = self.table_view.horizontalHeader()
        model = self.table_model
        visible_cols = model.get_visible_columns()
        
        for name, idx, attr, _ in ALL_COLUMNS:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(name in visible_cols)
            action.setData(name)
            action.toggled.connect(lambda checked, n=name: self._toggle_column(n, checked))
            menu.addAction(action)
        
        menu.exec(header.mapToGlobal(pos))
    
    def _toggle_column(self, name, checked):
        visible = self.table_model.get_visible_columns()
        if checked:
            if name not in visible:
                # 插入到逻辑顺序：根据 ALL_COLUMNS 的顺序
                all_names = [c[0] for c in ALL_COLUMNS]
                insert_idx = 0
                for n in visible:
                    if all_names.index(n) > all_names.index(name):
                        break
                    insert_idx += 1
                visible.insert(insert_idx, name)
        else:
            if name in visible:
                visible.remove(name)
        
        self.table_model.set_visible_columns(visible)
        
        # 保存可见性
        config = self._load_column_config()
        if 'visible' not in config:
            config['visible'] = {}
        config['visible'][name] = checked
        self._save_column_config(config)
    
    # ==================== 数据逻辑 ====================
    def _set_default_week(self):
        today = QDate.currentDate()
        day_of_week = today.dayOfWeek()
        monday = today.addDays(-(day_of_week - 1))
        sunday = monday.addDays(6)
        start_str = f'{monday.month():02d}.{monday.day():02d}'
        end_str = f'{sunday.month():02d}.{sunday.day():02d}'
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
        
        for record in last_week_records:
            character_name = record[2]
            if character_name in existing_names:
                continue
            
            # record: (id, date_range, name, faction, ns, nc, hs, hc, total, team_name, loot)
            team_name = record[9] if len(record) > 9 else ''
            loot = record[10] if len(record) > 10 else ''
            
            new_record = (
                self._default_week_str,
                start_date,
                end_date,
                character_name,
                record[3],  # faction
                0, 0, 0, 0,
                team_name,
                loot
            )
            self.pending_records.append(new_record)
            existing_names.add(character_name)
    
    def _refresh_data(self):
        all_db_records = get_all_records(None)
        
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
        date_filter = None if current_date == '全部' or not current_date else current_date
        
        if date_filter:
            all_records = [r for r in all_db_records if r[1] == date_filter]
        else:
            all_records = list(all_db_records)
        
        # 合并缓存记录
        for i, pr in enumerate(self.pending_records):
            temp_id = -(i + 1)
            total = pr[5] + pr[7] - pr[6] - pr[8] if len(pr) > 8 else 0
            temp_record = (temp_id, pr[0], pr[3], pr[4],
                           pr[5], pr[6], pr[7], pr[8], total,
                           pr[9] if len(pr) > 9 else '',
                           pr[10] if len(pr) > 10 else '')
            if not date_filter or pr[0] == date_filter:
                all_records.append(temp_record)
        
        all_records = [r for r in all_records if r[0] not in self.pending_deletes]
        
        # 更新门派筛选
        current_faction = self.faction_filter_combo.currentText()
        self.faction_filter_combo.blockSignals(True)
        self.faction_filter_combo.clear()
        self.faction_filter_combo.addItem('全部')
        factions = set()
        for r in all_db_records:
            factions.add(r[3])
        for f in sorted(factions):
            self.faction_filter_combo.addItem(f)
        idx = self.faction_filter_combo.findText(current_faction)
        if idx >= 0:
            self.faction_filter_combo.setCurrentIndex(idx)
        self.faction_filter_combo.blockSignals(False)
        
        # 更新日期筛选
        self.date_filter_combo.blockSignals(True)
        self.date_filter_combo.clear()
        self.date_filter_combo.addItem('全部')
        date_list = get_date_list()
        for d in date_list:
            self.date_filter_combo.addItem(d)
        idx = self.date_filter_combo.findText(current_date)
        if idx >= 0:
            self.date_filter_combo.setCurrentIndex(idx)
        else:
            self.date_filter_combo.addItem(current_date)
            self.date_filter_combo.setCurrentText(current_date)
        self.date_filter_combo.blockSignals(False)
        
        faction_filter = self.faction_filter_combo.currentText()
        if faction_filter != '全部':
            all_records = [r for r in all_records if r[3] == faction_filter]
        
        if all_records:
            stats = {
                'count': len(all_records),
                'avg_normal_salary': int(sum(r[4] for r in all_records) / len(all_records)),
                'avg_normal_consume': int(sum(r[5] for r in all_records) / len(all_records)),
                'avg_hero_salary': int(sum(r[6] for r in all_records) / len(all_records)),
                'avg_hero_consume': int(sum(r[7] for r in all_records) / len(all_records)),
                'avg_total_salary': int(sum(r[8] for r in all_records) / len(all_records)),
                'sum_normal_salary': sum(r[4] for r in all_records),
                'sum_normal_consume': sum(r[5] for r in all_records),
                'sum_hero_salary': sum(r[6] for r in all_records),
                'sum_hero_consume': sum(r[7] for r in all_records),
                'sum_total_salary': sum(r[8] for r in all_records),
            }
        else:
            stats = {k:0 for k in ['count','avg_normal_salary','avg_normal_consume','avg_hero_salary','avg_hero_consume','avg_total_salary','sum_normal_salary','sum_normal_consume','sum_hero_salary','sum_hero_consume','sum_total_salary']}
        
        self.table_model.load_data(all_records, stats)
        self.table_view.resizeColumnsToContents()
        
        current_filter = self.date_filter_combo.currentText()
        if current_filter and current_filter != '全部':
            self.setWindowTitle(f'剑网三 副本工资统计 - {current_filter}')
        else:
            self.setWindowTitle('剑网三 副本工资统计 - 全部日期')
        
        unsaved = len(self.pending_records) + len(self.pending_deletes)
        if unsaved > 0:
            self.status_label.setText(f'共 {len(all_records)} 条记录 | 有 {unsaved} 条未保存')
            self.save_btn.setEnabled(True)
        else:
            self.status_label.setText(f'共 {len(all_records)} 条记录')
            self.save_btn.setEnabled(False)
    
    def _filter_data(self):
        self._refresh_data()
    
    def _on_date_filter_changed(self):
        self._refresh_data()
    
    def _on_cell_changed(self, topLeft, bottomRight):
        row = topLeft.row()
        col = topLeft.column()
        
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
        
        # 保存撤销
        if record_id > 0:
            all_db = get_all_records(None)
            for r in all_db:
                if r[0] == record_id:
                    old_record = list(r)
                    while len(old_record) < 11:
                        old_record.append('')
                    self.undo_stack.append({
                        'record_id': record_id,
                        'old_record': tuple(old_record),
                        'is_db': True
                    })
                    break
        else:
            idx = -record_id - 1
            if idx < len(self.pending_records):
                pr = self.pending_records[idx]
                old_record = [record_id, pr[0], pr[3], pr[4], pr[5], pr[6], pr[7], pr[8], 0, pr[9] if len(pr)>9 else '', pr[10] if len(pr)>10 else '']
                self.undo_stack.append({
                    'record_id': record_id,
                    'old_record': tuple(old_record),
                    'is_db': False
                })
        
        if record_id > 0:
            try:
                update_record(
                    record_id, record[1], '', '', record[2], record[3],
                    record[4], record[5], record[6], record[7],
                    record[9] if len(record) > 9 else '',
                    record[10] if len(record) > 10 else ''
                )
                self.status_label.setText('已保存')
            except Exception as e:
                self.status_label.setText(f'保存失败: {e}')
        else:
            idx = -record_id - 1
            if idx < len(self.pending_records):
                self.pending_records[idx] = (
                    self._default_week_str,
                    '', '',
                    record[2], record[3],
                    record[4], record[5], record[6], record[7],
                    record[9] if len(record) > 9 else '',
                    record[10] if len(record) > 10 else ''
                )
        
        self._refresh_data()
    
    def _on_save(self):
        if not self.pending_records and not self.pending_deletes:
            show_message(self, '提示', '没有需要保存的更改')
            return
        
        ok = confirm_action(self, '确认保存', f'待新增 {len(self.pending_records)} 条\n待删除 {len(self.pending_deletes)} 条\n确定保存吗？')
        if not ok:
            return
        
        for rid in self.pending_deletes:
            try:
                if rid > 0:
                    delete_record(rid)
            except Exception as e:
                show_message(self, '错误', f'删除失败: {e}', 'warning')
        
        for pr in self.pending_records:
            try:
                add_record(*pr)
            except Exception as e:
                show_message(self, '错误', f'新增失败: {e}', 'warning')
        
        self.pending_records.clear()
        self.pending_deletes.clear()
        self._refresh_data()
        show_message(self, '保存成功', '所有更改已保存')
    
    def _on_import(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('选择Excel文件')
        dialog.setNameFilter('Excel文件 (*.xlsx *.xls)')
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dialog.setStyleSheet(self.styleSheet())
        
        import os as _os
        desktop = _os.path.join(_os.path.expanduser('~'), 'Desktop')
        if not _os.path.exists(desktop):
            desktop = _os.path.expanduser('~')
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
        
        ok = confirm_action(self, '导入数据', f'发现 {len(records)} 条\n确定=直接保存 | 取消=放入缓存')
        if ok:
            count = 0
            for rec in records:
                try:
                    # 补齐到 11 个字段 (date_range, start, end, name, faction, ns, nc, hs, hc, team, loot)
                    while len(rec) < 11:
                        rec = (*rec, '')
                    add_record(*rec)
                    count += 1
                except Exception as e:
                    show_message(self, '错误', f'保存失败: {e}', 'warning')
            show_message(self, '导入成功', f'成功导入 {count} 条记录')
        else:
            for rec in records:
                while len(rec) < 11:
                    rec = (*rec, '')
                self.pending_records.append(rec)
            show_message(self, '已缓存', f'{len(records)} 条已缓存，请点保存')
        
        self._refresh_data()
    
    def _on_export(self):
        from openpyxl import Workbook
        data_records = [r for r in self.table_model.records if r[2] not in ['平均', '合计']]
        current_date = self.date_filter_combo.currentText()
        
        if not data_records:
            show_message(self, '提示', '当前没有数据可导出', 'warning')
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, '保存Excel文件', f'{current_date}.xlsx', 'Excel文件 (*.xlsx)', options=QFileDialog.Option.DontUseNativeDialog)
        if not file_path:
            return
        
        try:
            wb = Workbook()
            ws = wb.active
            if current_date and current_date != '全部':
                ws.cell(row=1, column=1, value=f'日期{current_date}')
            
            headers = ['角色名', '门派', '团牌', '掉落', '普通工资', '普通消费', '英雄工资', '英雄消费', '总工资']
            for i, h in enumerate(headers, 1):
                ws.cell(row=3, column=i, value=h)
            
            from core.utils import number_to_brick
            for row_idx, r in enumerate(data_records, 4):
                ws.cell(row=row_idx, column=1, value=r[2])
                ws.cell(row=row_idx, column=2, value=r[3])
                ws.cell(row=row_idx, column=3, value=r[9] if len(r) > 9 else '')
                ws.cell(row=row_idx, column=4, value=r[10] if len(r) > 10 else '')
                ws.cell(row=row_idx, column=5, value=number_to_brick(r[4]))
                ws.cell(row=row_idx, column=6, value=number_to_brick(r[5]))
                ws.cell(row=row_idx, column=7, value=number_to_brick(r[6]))
                ws.cell(row=row_idx, column=8, value=number_to_brick(r[7]))
                ws.cell(row=row_idx, column=9, value=number_to_brick(r[8]))
            
            wb.save(file_path)
            show_message(self, '导出成功', f'已保存到 {os.path.basename(file_path)}')
        except Exception as e:
            show_message(self, '导出失败', str(e), 'error')
    
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
        old = last['old_record']
        rid = last['record_id']
        if last['is_db']:
            update_record(rid, old[1], '', '', old[2], old[3], old[4], old[5], old[6], old[7], old[9] if len(old)>9 else '', old[10] if len(old)>10 else '')
        else:
            idx = -rid - 1
            if idx < len(self.pending_records):
                self.pending_records[idx] = (old[1], old[2], old[3], old[4], old[5], old[6], old[7], old[8], old[9] if len(old)>9 else '', old[10] if len(old)>10 else '')
        self._refresh_data()
        self.status_label.setText('已撤销')
