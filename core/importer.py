"""
Excel 导入模块
解析剑三副本工资表格
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
        
        # 统一补零成两位数格式：04.27-05.03
        start_parts = start.split('.')
        end_parts = end.split('.')
        start_formatted = f'{int(start_parts[0]):02d}.{int(start_parts[1]):02d}'
        end_formatted = f'{int(end_parts[0]):02d}.{int(end_parts[1]):02d}'
        date_range = f'{start_formatted}-{end_formatted}'
        return date_range, start_formatted, end_formatted
    
    return None, None, None


def is_header_row(row_data):
    """判断是否是标题行"""
    row_str = ' '.join([str(cell) for cell in row_data if cell])
    keywords = ['角色名', '门派', '普通工资', '英雄工资']
    return all(kw in row_str for kw in keywords)


def is_skip_row(row_data):
    """判断是否跳过该行"""
    if not row_data:
        return True
    
    # 全空行跳过
    row_str = ' '.join([str(cell) for cell in row_data if cell])
    if not row_str.strip():
        return True
    
    # A列是"平均""合计""总计"的跳过
    # 注意：合并单元格可能导致 row_data[0] 是 None
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
        
        for row in sheet.iter_rows(min_row=1, values_only=True):
            # 跳过完全空行
            if all(cell is None or str(cell).strip() == '' for cell in row):
                continue
            
            row_data = [cell if cell is not None else '' for cell in row]
            
            # 检测日期行：合并单元格只有A列有值，B-G列为空
            first_cell = str(row_data[0]).strip() if row_data[0] else ''
            
            if '日期' in first_cell:
                date_range, start, end = parse_date_range(first_cell)
                if date_range:
                    current_date_range = date_range
                    current_start_date = start
                    current_end_date = end
                continue
            
            # 跳过标题行
            if is_header_row(row_data):
                continue
            
            # 跳过统计行
            if is_skip_row(row_data):
                continue
            
            # 没有日期信息则跳过
            if not current_date_range:
                continue
            
            # 至少要有角色名和门派
            if len(row_data) < 2:
                continue
            
            # A列=角色名, B列=门派
            character_name = str(row_data[0]).strip() if row_data[0] else ''
            faction = str(row_data[1]).strip() if row_data[1] else ''
            
            if not character_name or character_name in ['平均', '合计', '总计', '']:
                continue
            
            # C列=普通工资, D列=普通消费, E列=英雄工资, F列=英雄消费
            normal_salary = brick_to_number(row_data[2]) if len(row_data) > 2 else 0
            normal_consume = brick_to_number(row_data[3]) if len(row_data) > 3 else 0
            hero_salary = brick_to_number(row_data[4]) if len(row_data) > 4 else 0
            hero_consume = brick_to_number(row_data[5]) if len(row_data) > 5 else 0
            
            records.append((
                current_date_range,
                current_start_date,
                current_end_date,
                character_name,
                faction,
                normal_salary,
                normal_consume,
                hero_salary,
                hero_consume
            ))
        
        workbook.close()
        return records, None
    
    except Exception as e:
        return [], f'导入失败: {str(e)}'
