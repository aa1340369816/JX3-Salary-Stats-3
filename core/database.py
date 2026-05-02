"""
数据库模块 - SQLite存储
数据库文件放在程序同目录下
"""

import sqlite3
import os
import sys

# 数据库放在 exe 同目录（兼容打包和源码运行）
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(APP_DIR, 'salary_data.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS salary_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_range TEXT NOT NULL,
            start_month INTEGER,
            start_day INTEGER,
            end_month INTEGER,
            end_day INTEGER,
            sort_key TEXT,
            character_name TEXT NOT NULL,
            faction TEXT NOT NULL,
            normal_salary INTEGER DEFAULT 0,
            normal_consume INTEGER DEFAULT 0,
            hero_salary INTEGER DEFAULT 0,
            hero_consume INTEGER DEFAULT 0,
            total_salary INTEGER DEFAULT 0,
            team_name TEXT DEFAULT '',
            loot TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 兼容旧表添加新列
    for col, col_type in [
        ('start_month', 'INTEGER'),
        ('start_day', 'INTEGER'),
        ('end_month', 'INTEGER'),
        ('end_day', 'INTEGER'),
        ('sort_key', 'TEXT'),
        ('team_name', "TEXT DEFAULT ''"),
        ('loot', "TEXT DEFAULT ''"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE salary_records ADD COLUMN {col} {col_type}")
        except:
            pass

    conn.commit()
    conn.close()


def make_sort_key(start_month, start_day):
    if start_month is None or start_day is None:
        return '9-99-99'
    year_group = 0 if start_month >= 7 else 1
    return f'{year_group}-{start_month:02d}-{start_day:02d}'


def add_record(date_range, start_date, end_date, character_name, faction,
               normal_salary, normal_consume, hero_salary, hero_consume,
               team_name='', loot=''):
    total = normal_salary + hero_salary - normal_consume - hero_consume

    parts = date_range.split('-')
    start_month, start_day = None, None
    end_month, end_day = None, None
    if len(parts) == 2:
        sp = parts[0].split('.')
        ep = parts[1].split('.')
        if len(sp) == 2:
            start_month = int(sp[0])
            start_day = int(sp[1])
        if len(ep) == 2:
            end_month = int(ep[0])
            end_day = int(ep[1])

    sort_key = make_sort_key(start_month, start_day)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO salary_records 
        (date_range, start_month, start_day, end_month, end_day, sort_key,
         character_name, faction,
         normal_salary, normal_consume, hero_salary, hero_consume, total_salary,
         team_name, loot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date_range, start_month, start_day, end_month, end_day, sort_key,
          character_name, faction,
          normal_salary, normal_consume, hero_salary, hero_consume, total,
          team_name, loot))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id


def update_record(record_id, date_range, start_date, end_date, character_name, faction,
                  normal_salary, normal_consume, hero_salary, hero_consume,
                  team_name='', loot=''):
    total = normal_salary + hero_salary - normal_consume - hero_consume

    parts = date_range.split('-')
    start_month, start_day = None, None
    end_month, end_day = None, None
    if len(parts) == 2:
        sp = parts[0].split('.')
        ep = parts[1].split('.')
        if len(sp) == 2:
            start_month = int(sp[0])
            start_day = int(sp[1])
        if len(ep) == 2:
            end_month = int(ep[0])
            end_day = int(ep[1])

    sort_key = make_sort_key(start_month, start_day)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE salary_records 
        SET date_range=?, start_month=?, start_day=?, end_month=?, end_day=?, sort_key=?,
            character_name=?, faction=?,
            normal_salary=?, normal_consume=?, hero_salary=?, hero_consume=?, total_salary=?,
            team_name=?, loot=?
        WHERE id=?
    ''', (date_range, start_month, start_day, end_month, end_day, sort_key,
          character_name, faction,
          normal_salary, normal_consume, hero_salary, hero_consume, total,
          team_name, loot, record_id))
    conn.commit()
    conn.close()


def delete_record(record_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM salary_records WHERE id=?', (record_id,))
    conn.commit()
    conn.close()


def get_all_records(date_filter=None):
    conn = get_connection()
    cursor = conn.cursor()

    if date_filter:
        cursor.execute('''
            SELECT id, date_range, character_name, faction,
                   normal_salary, normal_consume, hero_salary, hero_consume, total_salary,
                   team_name, loot
            FROM salary_records
            WHERE date_range = ?
            ORDER BY sort_key ASC, id ASC
        ''', (date_filter,))
    else:
        cursor.execute('''
            SELECT id, date_range, character_name, faction,
                   normal_salary, normal_consume, hero_salary, hero_consume, total_salary,
                   team_name, loot
            FROM salary_records
            ORDER BY sort_key ASC, id ASC
        ''')

    records = cursor.fetchall()
    conn.close()
    return records


def get_date_list():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT date_range, sort_key
        FROM salary_records
        ORDER BY sort_key ASC
    ''')
    dates = cursor.fetchall()
    conn.close()
    return [d[0] for d in dates]


def get_statistics(date_filter=None):
    conn = get_connection()
    cursor = conn.cursor()

    if date_filter:
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                AVG(normal_salary), AVG(normal_consume),
                AVG(hero_salary), AVG(hero_consume), AVG(total_salary),
                SUM(normal_salary), SUM(normal_consume),
                SUM(hero_salary), SUM(hero_consume), SUM(total_salary)
            FROM salary_records
            WHERE date_range = ?
        ''', (date_filter,))
    else:
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                AVG(normal_salary), AVG(normal_consume),
                AVG(hero_salary), AVG(hero_consume), AVG(total_salary),
                SUM(normal_salary), SUM(normal_consume),
                SUM(hero_salary), SUM(hero_consume), SUM(total_salary)
            FROM salary_records
        ''')

    row = cursor.fetchone()
    conn.close()

    if not row or row[0] == 0:
        return {
            'count': 0,
            'avg_normal_salary': 0, 'avg_normal_consume': 0,
            'avg_hero_salary': 0, 'avg_hero_consume': 0, 'avg_total_salary': 0,
            'sum_normal_salary': 0, 'sum_normal_consume': 0,
            'sum_hero_salary': 0, 'sum_hero_consume': 0, 'sum_total_salary': 0,
        }

    return {
        'count': row[0],
        'avg_normal_salary': int(row[1]) if row[1] else 0,
        'avg_normal_consume': int(row[2]) if row[2] else 0,
        'avg_hero_salary': int(row[3]) if row[3] else 0,
        'avg_hero_consume': int(row[4]) if row[4] else 0,
        'avg_total_salary': int(row[5]) if row[5] else 0,
        'sum_normal_salary': int(row[6]) if row[6] else 0,
        'sum_normal_consume': int(row[7]) if row[7] else 0,
        'sum_hero_salary': int(row[8]) if row[8] else 0,
        'sum_hero_consume': int(row[9]) if row[9] else 0,
        'sum_total_salary': int(row[10]) if row[10] else 0,
    }
