"""
数据库连接和工具函数
"""
import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple
from config.settings import DATABASE_PATH

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def execute(self, sql: str, params: tuple = ()) -> int:
        """执行SQL语句"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.rowcount
    
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """查询单条记录"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """查询多条记录"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def executemany(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行SQL"""
        with self.get_connection() as conn:
            cursor = conn.executemany(sql, params_list)
            return cursor.rowcount
    
    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.fetchone(sql, (table_name,))
        return result is not None


def init_database(db_path: str = DATABASE_PATH) -> None:
    """
    初始化数据库，创建所有表
    
    Args:
        db_path: 数据库文件路径
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建 locations 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_code TEXT,
            country_name TEXT,
            region_code TEXT,
            region_name TEXT,
            city_name TEXT,
            district TEXT,
            postal_code TEXT,
            latitude REAL,
            longitude REAL,
            timezone TEXT,
            locale_code TEXT,
            source TEXT,
            UNIQUE(country_code, region_code, city_name, district)
        )
    ''')
    
    # 创建 ip_ranges 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ip_ranges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            network TEXT NOT NULL,
            start_ip INTEGER NOT NULL,
            end_ip INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            source TEXT,
            accuracy_radius INTEGER,
            is_anonymous_proxy BOOLEAN DEFAULT 0,
            is_satellite_provider BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES locations(id)
        )
    ''')
    
    # 创建 validations 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS validations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_range_id INTEGER NOT NULL,
            validator_node TEXT,
            validator_location TEXT,
            test_ip TEXT,
            expected_country TEXT,
            detected_country TEXT,
            is_accurate BOOLEAN,
            response_time_ms INTEGER,
            test_method TEXT,
            tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ip_range_id) REFERENCES ip_ranges(id)
        )
    ''')
    
    # 创建 validation_summary 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS validation_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_code TEXT,
            region_code TEXT,
            total_tests INTEGER DEFAULT 0,
            accurate_tests INTEGER DEFAULT 0,
            accuracy_rate REAL,
            last_tested_at TIMESTAMP,
            UNIQUE(country_code, region_code)
        )
    ''')
    
    # 创建索引
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_ip_ranges_start_end 
        ON ip_ranges(start_ip, end_ip)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_ip_ranges_network 
        ON ip_ranges(network)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_ip_ranges_location 
        ON ip_ranges(location_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_locations_country 
        ON locations(country_code)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_locations_city 
        ON locations(city_name)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_validations_range 
        ON validations(ip_range_id)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_validations_accuracy 
        ON validations(is_accurate)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_validations_tested_at 
        ON validations(tested_at)
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"数据库初始化完成: {db_path}")


def get_db_manager(db_path: str = DATABASE_PATH) -> DatabaseManager:
    """获取数据库管理器实例"""
    return DatabaseManager(db_path)


def query_ip_location(ip_int: int, db_path: str = DATABASE_PATH) -> Optional[Dict[str, Any]]:
    """
    查询IP地址的地理位置
    
    Args:
        ip_int: IP地址的整数表示
        db_path: 数据库路径
        
    Returns:
        包含地理位置信息的字典，未找到返回None
    """
    db = get_db_manager(db_path)
    
    sql = '''
        SELECT 
            r.id as range_id,
            r.network,
            r.accuracy_radius,
            r.source as ip_source,
            l.country_code,
            l.country_name,
            l.region_code,
            l.region_name,
            l.city_name,
            l.district,
            l.postal_code,
            l.latitude,
            l.longitude,
            l.timezone,
            l.locale_code
        FROM ip_ranges r
        JOIN locations l ON r.location_id = l.id
        WHERE r.start_ip <= ? AND r.end_ip >= ?
        ORDER BY r.accuracy_radius ASC NULLS LAST
        LIMIT 1
    '''
    
    return db.fetchone(sql, (ip_int, ip_int))


def get_location_id(country_code: str, region_code: str, city_name: str, 
                    district: Optional[str], db_path: str = DATABASE_PATH) -> Optional[int]:
    """
    获取地理位置ID
    
    Args:
        country_code: 国家代码
        region_code: 省/州代码
        city_name: 城市名称
        district: 区/县
        db_path: 数据库路径
        
    Returns:
        location_id，未找到返回None
    """
    db = get_db_manager(db_path)
    
    sql = '''
        SELECT id FROM locations 
        WHERE country_code = ? AND region_code = ? 
        AND city_name = ? AND (district = ? OR (district IS NULL AND ? IS NULL))
    '''
    
    result = db.fetchone(sql, (country_code, region_code, city_name, district, district))
    if result:
        return result['id']
    return None


def insert_location(location_data: Dict[str, Any], db_path: str = DATABASE_PATH) -> int:
    """
    插入地理位置记录
    
    Args:
        location_data: 地理位置数据字典
        db_path: 数据库路径
        
    Returns:
        插入的location_id
    """
    db = get_db_manager(db_path)
    
    sql = '''
        INSERT OR IGNORE INTO locations 
        (country_code, country_name, region_code, region_name, city_name, 
         district, postal_code, latitude, longitude, timezone, locale_code, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    params = (
        location_data.get('country_code'),
        location_data.get('country_name'),
        location_data.get('region_code'),
        location_data.get('region_name'),
        location_data.get('city_name'),
        location_data.get('district'),
        location_data.get('postal_code'),
        location_data.get('latitude'),
        location_data.get('longitude'),
        location_data.get('timezone'),
        location_data.get('locale_code'),
        location_data.get('source')
    )
    
    db.execute(sql, params)
    
    # 获取插入的ID
    result = db.fetchone(
        '''SELECT id FROM locations 
           WHERE country_code = ? AND region_code = ? AND city_name = ? AND district = ?''',
        (location_data.get('country_code'), location_data.get('region_code'), 
         location_data.get('city_name'), location_data.get('district'))
    )
    
    return result['id'] if result else None


def batch_insert_ip_ranges(ranges_data: List[Tuple], db_path: str = DATABASE_PATH, 
                          batch_size: int = 10000) -> int:
    """
    批量插入IP范围记录
    
    Args:
        ranges_data: IP范围数据列表
        db_path: 数据库路径
        batch_size: 批量大小
        
    Returns:
        插入的记录数
    """
    db = get_db_manager(db_path)
    
    sql = '''
        INSERT INTO ip_ranges 
        (network, start_ip, end_ip, location_id, source, accuracy_radius, 
         is_anonymous_proxy, is_satellite_provider)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    '''
    
    total_inserted = 0
    for i in range(0, len(ranges_data), batch_size):
        batch = ranges_data[i:i + batch_size]
        total_inserted += db.executemany(sql, batch)
        logger.info(f"已插入 {total_inserted}/{len(ranges_data)} 条IP范围记录")
    
    return total_inserted


def get_validation_stats(country_code: Optional[str] = None, 
                        db_path: str = DATABASE_PATH) -> List[Dict[str, Any]]:
    """
    获取验证统计信息
    
    Args:
        country_code: 国家代码过滤
        db_path: 数据库路径
        
    Returns:
        验证统计列表
    """
    db = get_db_manager(db_path)
    
    if country_code:
        sql = 'SELECT * FROM validation_summary WHERE country_code = ?'
        return db.fetchall(sql, (country_code,))
    else:
        sql = 'SELECT * FROM validation_summary ORDER BY accuracy_rate ASC'
        return db.fetchall(sql)


def update_validation_summary(country_code: str, region_code: str, 
                              is_accurate: bool, db_path: str = DATABASE_PATH) -> None:
    """
    更新验证汇总统计
    
    Args:
        country_code: 国家代码
        region_code: 省/州代码
        is_accurate: 是否准确
        db_path: 数据库路径
    """
    db = get_db_manager(db_path)
    
    # 先尝试更新
    sql_update = '''
        UPDATE validation_summary 
        SET total_tests = total_tests + 1,
            accurate_tests = accurate_tests + ?,
            accuracy_rate = CAST(accurate_tests + ? AS REAL) / (total_tests + 1),
            last_tested_at = CURRENT_TIMESTAMP
        WHERE country_code = ? AND region_code = ?
    '''
    
    accurate_int = 1 if is_accurate else 0
    rowcount = db.execute(sql_update, (accurate_int, accurate_int, country_code, region_code))
    
    # 如果没有更新到记录，则插入新记录
    if rowcount == 0:
        sql_insert = '''
            INSERT INTO validation_summary 
            (country_code, region_code, total_tests, accurate_tests, accuracy_rate, last_tested_at)
            VALUES (?, ?, 1, ?, ?, CURRENT_TIMESTAMP)
        '''
        db.execute(sql_insert, (country_code, region_code, accurate_int, 
                               1.0 if is_accurate else 0.0))
