"""
Excel 导入模块
解析剑三副本工资表格（支持新列：团牌、掉落）
"""

import re
import openpyxl
from core.utils import brick_to_number


def parse_date_range(text):
    """从文本中提取日期区间"""
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

        # 统一补零
        start_parts = start.split('.')
        end_parts = end.split('.')
        start_formatted = f'{int(start_parts[0]):02d}.{int(start_parts[1]):02d}'
        end_formatted = f'{int(end_parts[0]):02d}.{int(end_parts[1]):02d}'
        date_range = f'{start_formatted}-{end_formatted}'
        return date_range, start_formatted, end_formatted

    return None, None, None


def is_header_row(row_data):
    """判断是否是标题行"""
    keywords = ['角色名', '门派', '普通工资', '英雄工资']
    row_str = ' '.join([str(cell) for cell in row_data if cell])
    return all(kw in row_str for kw in keywords)


def is_skip_row(row_data):
    """判断是否跳过该行"""
    if not row_data:
        return True
    row_str = ' '.join([str(cell) for cell in row_data if cell])
    if not row_str.strip():
        return True
    first_cell = str(row_data[0]).strip() if row_data else ''
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

        # 列映射（默认按旧格式：A角色名, B门派, C普通工资, D普通消费, E英雄工资, F英雄消费, G总工资）
        col_map = {
            '角色名': 0,
            '门派': 1,
            '普通工资': 2,
            '普通消费': 3,
            '英雄工资': 4,
            '英雄消费': 5,
            '总工资': 6,
        }
        # 新列索引（未在旧表格中出现时默认-1）
        team_col = -1
        loot_col = -1
        header_parsed = False

        for row in sheet.iter_rows(min_row=1, values_only=True):
            if all(cell is None or str(cell).strip() == '' for cell in row):
                continue

            row_data = [cell if cell is not None else '' for cell in row]
            first_cell = str(row_data[0]).strip() if row_data else ''

            # 检测日期行
            if first_cell.startswith('日期') or '日期' in first_cell:
                date_range, start, end = parse_date_range(first_cell)
                if date_range:
                    current_date_range = date_range
                    current_start_date = start
                    current_end_date = end
                continue

            # 解析表头，确定列映射
            if is_header_row(row_data) and not header_parsed:
                header_parsed = True
                # 遍历表头行，找到‘团牌’‘掉落’的索引
                for idx, cell in enumerate(row_data):
                    cell_str = str(cell).strip()
                    if '团牌' in cell_str:
                        team_col = idx
                    elif '掉落' in cell_str:
                        loot_col = idx
                # 同时确保原有列的映射正确（根据实际表头位置）
                for idx, cell in enumerate(row_data):
                    cell_str = str(cell).strip()
                    if cell_str in col_map:
                        col_map[cell_str] = idx
                continue

            if is_skip_row(row_data):
                continue

            if not current_date_range:
                continue

            # 至少需要角色名
            name_idx = col_map.get('角色名', 0)
            if len(row_data) <= name_idx:
                continue
            character_name = str(row_data[name_idx]).strip() if row_data[name_idx] else ''
            if not character_name or character_name in ['平均', '合计', '总计']:
                continue

            faction_idx = col_map.get('门派', 1)
            faction = str(row_data[faction_idx]).strip() if len(row_data) > faction_idx and row_data[faction_idx] else ''

            ns_idx = col_map.get('普通工资', 2)
            nc_idx = col_map.get('普通消费', 3)
            hs_idx = col_map.get('英雄工资', 4)
            hc_idx = col_map.get('英雄消费', 5)

            normal_salary = brick_to_number(row_data[ns_idx]) if len(row_data) > ns_idx else 0
            normal_consume = brick_to_number(row_data[nc_idx]) if len(row_data) > nc_idx else 0
            hero_salary = brick_to_number(row_data[hs_idx]) if len(row_data) > hs_idx else 0
            hero_consume = brick_to_number(row_data[hc_idx]) if len(row_data) > hc_idx else 0

            team_name = ''
            loot = ''
            if team_col >= 0 and len(row_data) > team_col and row_data[team_col]:
                team_name = str(row_data[team_col]).strip()
            if loot_col >= 0 and len(row_data) > loot_col and row_data[loot_col]:
                loot = str(row_data[loot_col]).strip()

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
                team_name,
                loot
            ))

        workbook.close()
        return records, None

    except Exception as e:
        return [], f'导入失败: {str(e)}'
