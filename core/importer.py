"""
Excel 导入模块 - 支持团牌、掉落的导入
"""

import re
import openpyxl
from core.utils import brick_to_number


def parse_date_range(text):
    pattern = r'日期\s*(\d+\.\d+)\s*[-–—]\s*(\d+\.?\d*)'
    match = re.search(pattern, str(text))
    if match:
        start = match.group(1)
        end_raw = match.group(2)
        if '.' in end_raw:
            end = end_raw
        else:
            month = start.split('.')[0]
            end = f'{month}.{end_raw}'
        start_parts = start.split('.')
        end_parts = end.split('.')
        start_formatted = f'{int(start_parts[0]):02d}.{int(start_parts[1]):02d}'
        end_formatted = f'{int(end_parts[0]):02d}.{int(end_parts[1]):02d}'
        date_range = f'{start_formatted}-{end_formatted}'
        return date_range, start_formatted, end_formatted
    return None, None, None


def is_header_row(row_data):
    row_str = ' '.join([str(cell) for cell in row_data if cell])
    keywords = ['角色名', '门派', '普通工资', '英雄工资']
    return all(kw in row_str for kw in keywords)


def is_skip_row(row_data):
    if not row_data:
        return True
    row_str = ' '.join([str(cell) for cell in row_data if cell])
    if not row_str.strip():
        return True
    first_cell = str(row_data[0]).strip() if row_data and row_data[0] else ''
    skip_keywords = ['平均', '合计', '总计']
    for kw in skip_keywords:
        if kw in first_cell:
            return True
    return False


def import_excel(file_path):
    """导入Excel，返回 (records, error)"""
    try:
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        sheet = workbook.active
        records = []
        current_date_range = None
        current_start_date = None
        current_end_date = None

        # 存储列索引
        col_map = {
            '角色名': 0, '门派': 1, '普通工资': 2, '普通消费': 3,
            '英雄工资': 4, '英雄消费': 5, '团牌': None, '掉落': None
        }
        header_found = False

        for row in sheet.iter_rows(min_row=1, values_only=True):
            if all(cell is None or str(cell).strip() == '' for cell in row):
                continue
            row_data = [cell if cell is not None else '' for cell in row]
            first_cell = str(row_data[0]).strip() if row_data[0] else ''

            if '日期' in first_cell:
                date_range, start, end = parse_date_range(first_cell)
                if date_range:
                    current_date_range = date_range
                    current_start_date = start
                    current_end_date = end
                continue

            # 识别标题行，确定各列索引
            if is_header_row(row_data):
                # 根据标题更新列索引
                for idx, cell in enumerate(row_data):
                    cell_str = str(cell).strip()
                    if '角色名' in cell_str:
                        col_map['角色名'] = idx
                    elif '门派' in cell_str:
                        col_map['门派'] = idx
                    elif '普通工资' in cell_str:
                        col_map['普通工资'] = idx
                    elif '普通消费' in cell_str:
                        col_map['普通消费'] = idx
                    elif '英雄工资' in cell_str:
                        col_map['英雄工资'] = idx
                    elif '英雄消费' in cell_str:
                        col_map['英雄消费'] = idx
                    elif '团牌' in cell_str:
                        col_map['团牌'] = idx
                    elif '掉落' in cell_str:
                        col_map['掉落'] = idx
                header_found = True
                continue

            if is_skip_row(row_data):
                continue

            if not current_date_range:
                continue

            # 提取数据
            def get_cell(col_key):
                idx = col_map.get(col_key)
                if idx is not None and idx < len(row_data):
                    return row_data[idx]
                return ''

            character_name = str(get_cell('角色名')).strip()
            faction = str(get_cell('门派')).strip()
            if not character_name or character_name in ['平均', '合计', '总计', '']:
                continue

            normal_salary = brick_to_number(get_cell('普通工资'))
            normal_consume = brick_to_number(get_cell('普通消费'))
            hero_salary = brick_to_number(get_cell('英雄工资'))
            hero_consume = brick_to_number(get_cell('英雄消费'))
            team_mark = str(get_cell('团牌')).strip()
            drop_info = str(get_cell('掉落')).strip()

            records.append((
                current_date_range,
                current_start_date,
                current_end_date,
                character_name,
                faction,
                normal_salary,
                normal_consume,
                hero_salary,
                hero_consume,
                team_mark,
                drop_info
            ))

        workbook.close()
        return records, None
    except Exception as e:
        return [], f'导入失败: {str(e)}'
