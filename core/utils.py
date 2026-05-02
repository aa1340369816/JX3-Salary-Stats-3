"""
工具函数模块
1砖 = 10000
"""


def brick_to_number(text):
    """
    将砖格式字符串转为整数
    '1砖9408' → 19408
    '5000' → 5000
    '' → 0
    """
    if not text or str(text).strip() == '':
        return 0
    
    text = str(text).strip()
    
    if '砖' in text:
        parts = text.split('砖')
        bricks = int(parts[0]) if parts[0] else 0
        remainder = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        return bricks * 10000 + remainder
    
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return 0


def number_to_brick(num):
    """
    将整数转为砖格式字符串
    19408 → '1砖9408'
    5000 → '5000'
    0 → '0'
    """
    if num is None:
        return '0'
    
    num = int(num)
    
    if num == 0:
        return '0'
    
    bricks = num // 10000
    remainder = num % 10000
    
    if bricks > 0:
        if remainder == 0:
            return f'{bricks}砖'
        else:
            return f'{bricks}砖{remainder}'
    else:
        return str(num)


def parse_brick_input(text):
    """解析用户输入的砖格式"""
    return brick_to_number(text)
