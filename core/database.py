"""
数据库模块 - SQLite存储（含团牌、掉落字段）
"""

import sqlite3
import os
import sys
from contextlib import contextmanager

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(APP_DIR, 'salary_data.db')


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _parse_date(date_str):
    parts = date_str.split('-')
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
    return start_month, start_day, end_month, end_day


def make_sort_key(start_month, start_day):
    if start_month is None or start_day is None:
        return '9-99-99'
    year_group = 0 if start_month >= 7 else 1
    return f'{year_group}-{start_month:02d}-{start_day:02d}'


def init_database():
    with get_connection() as conn:
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
                team_mark TEXT DEFAULT '',
                drop_info TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        new_columns = [
            ('start_month', 'INTEGER'),
            ('start_day', 'INTEGER'),
            ('end_month', 'INTEGER'),
            ('end_day', 'INTEGER'),
            ('sort_key', 'TEXT'),
            ('team_mark', "TEXT DEFAULT ''"),
            ('drop_info', "TEXT DEFAULT ''")
        ]
        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE salary_records ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass
        conn.commit()


def add_record(date_range, start_date, end_date, character_name, faction,
               normal_salary, normal_consume, hero_salary, hero_consume,
               team_mark='', drop_info=''):
    total = normal_salary + hero_salary - normal_consume - hero_consume
    start_month, start_day, end_month, end_day = _parse_date(date_range)
    sort_key = make_sort_key(start_month, start_day)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO salary_records 
            (date_range, start_month, start_day, end_month, end_day, sort_key,
             character_name, faction,
             normal_salary, normal_consume, hero_salary, hero_consume, total_salary,
             team_mark, drop_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date_range, start_month, start_day, end_month, end_day, sort_key,
              character_name, faction,
              normal_salary, normal_consume, hero_salary, hero_consume, total,
              team_mark, drop_info))
        conn.commit()
        return cursor.lastrowid


def update_record(record_id, date_range, start_date, end_date, character_name, faction,
                  normal_salary, normal_consume, hero_salary, hero_consume,
                  team_mark='', drop_info=''):
    total = normal_salary + hero_salary - normal_consume - hero_consume
    start_month, start_day, end_month, end_day = _parse_date(date_range)
    sort_key = make_sort_key(start_month, start_day)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE salary_records 
            SET date_range=?, start_month=?, start_day=?, end_month=?, end_day=?, sort_key=?,
                character_name=?, faction=?,
                normal_salary=?, normal_consume=?, hero_salary=?, hero_consume=?, total_salary=?,
                team_mark=?, drop_info=?
            WHERE id=?
        ''', (date_range, start_month, start_day, end_month, end_day, sort_key,
              character_name, faction,
              normal_salary, normal_consume, hero_salary, hero_consume, total,
              team_mark, drop_info, record_id))
        conn.commit()


def delete_record(record_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM salary_records WHERE id=?', (record_id,))
        conn.commit()


def get_all_records(date_filter=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if date_filter:
            cursor.execute('''
                SELECT id, date_range, character_name, faction,
                       normal_salary, normal_consume, hero_salary, hero_consume, total_salary,
                       team_mark, drop_info
                FROM salary_records
                WHERE date_range = ?
                ORDER BY sort_key ASC, id ASC
            ''', (date_filter,))
        else:
            cursor.execute('''
                SELECT id, date_range, character_name, faction,
                       normal_salary, normal_consume, hero_salary, hero_consume, total_salary,
                       team_mark, drop_info
                FROM salary_records
                ORDER BY sort_key ASC, id ASC
            ''')
        return cursor.fetchall()


def get_date_list():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT date_range, sort_key
            FROM salary_records
            ORDER BY sort_key ASC
        ''')
        return [row[0] for row in cursor.fetchall()]


def get_statistics(date_filter=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if date_filter:
            cursor.execute('''
                SELECT 
                    COUNT(*), AVG(normal_salary), AVG(normal_consume),
                    AVG(hero_salary), AVG(hero_consume), AVG(total_salary),
                    SUM(normal_salary), SUM(normal_consume),
                    SUM(hero_salary), SUM(hero_consume), SUM(total_salary)
                FROM salary_records
                WHERE date_range = ?
            ''', (date_filter,))
        else:
            cursor.execute('''
                SELECT 
                    COUNT(*), AVG(normal_salary), AVG(normal_consume),
                    AVG(hero_salary), AVG(hero_consume), AVG(total_salary),
                    SUM(normal_salary), SUM(normal_consume),
                    SUM(hero_salary), SUM(hero_consume), SUM(total_salary)
                FROM salary_records
            ''')
        row = cursor.fetchone()

    if not row or row[0] == 0:
        return {
            'count': 0,
            'avg_normal_salary': 0, 'avg_normal_consume': 0,
            'avg_hero_salary': 0, 'avg_hero_consume': 0, 'avg_total_salary': 0,
            'sum_normal_salary': 0, 'sum_normal_consume': 0,
            'sum_hero_salary': 0, 'sum_hero_consume': 0, 'sum_total_salary': 0,
        }

    def safe_int(val):
        return int(val) if val else 0

    return {
        'count': row[0],
        'avg_normal_salary': safe_int(row[1]),
        'avg_normal_consume': safe_int(row[2]),
        'avg_hero_salary': safe_int(row[3]),
        'avg_hero_consume': safe_int(row[4]),
        'avg_total_salary': safe_int(row[5]),
        'sum_normal_salary': safe_int(row[6]),
        'sum_normal_consume': safe_int(row[7]),
        'sum_hero_salary': safe_int(row[8]),
        'sum_hero_consume': safe_int(row[9]),
        'sum_total_salary': safe_int(row[10]),
    }
