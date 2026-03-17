#!/usr/bin/env python3
"""
插入测试数据脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_db_manager, init_database
from utils.ip_utils import ip_to_int
from config.settings import DATABASE_PATH

# 初始化数据库
init_database(DATABASE_PATH)

# 获取数据库连接
db = get_db_manager(DATABASE_PATH)

# 插入位置数据
locations = [
    ('CN', 'China', 'BJ', 'Beijing', 'Beijing', None, '100000', 39.9042, 116.4074, 'Asia/Shanghai'),
    ('US', 'United States', 'CA', 'California', 'Mountain View', None, '94043', 37.386, -122.0838, 'America/Los_Angeles'),
    ('JP', 'Japan', '13', 'Tokyo', 'Tokyo', None, '100-0001', 35.6762, 139.6503, 'Asia/Tokyo'),
]

location_ids = {}
for loc in locations:
    cursor = db.execute('''
        INSERT OR IGNORE INTO locations 
        (country_code, country_name, region_code, region_name, city_name, district, postal_code, latitude, longitude, timezone, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (*loc, 'test'))
    
    result = db.fetchone('''
        SELECT id FROM locations 
        WHERE country_code = ? AND region_code = ? AND city_name = ?
    ''', (loc[0], loc[2], loc[4]))
    
    if result:
        location_ids[loc[0]] = result['id']
        print(f"位置 {loc[4]}, {loc[1]} ID: {result['id']}")

# 插入IP范围数据
ip_ranges = [
    ('1.0.1.0/24', '1.0.1.0', '1.0.1.255', 'CN'),
    ('8.8.8.0/24', '8.8.8.0', '8.8.8.255', 'US'),
    ('1.0.32.0/24', '1.0.32.0', '1.0.32.255', 'JP'),
]

for network, start_ip, end_ip, country in ip_ranges:
    start_int = ip_to_int(start_ip)
    end_int = ip_to_int(end_ip)
    loc_id = location_ids.get(country)
    
    if loc_id:
        db.execute('''
            INSERT INTO ip_ranges (network, start_ip, end_ip, location_id, source)
            VALUES (?, ?, ?, ?, ?)
        ''', (network, start_int, end_int, loc_id, 'test'))
        print(f"插入IP范围: {network} -> {country}")

print("\n测试数据插入完成！")
