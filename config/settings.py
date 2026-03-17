"""
IP数据库系统配置文件
"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据库配置
DATABASE_PATH = os.path.join(BASE_DIR, "data", "ip_database.db")
DATA_RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

# MaxMind配置
MAXMIND_LICENSE_KEY = os.getenv("MAXMIND_LICENSE_KEY", "")
MAXMIND_DOWNLOAD_URL = "https://download.maxmind.com/app/geoip_download"
MAXMIND_EDITION = "GeoLite2-City-CSV"

# 数据导入配置
BATCH_SIZE = 10000  # 批量插入大小
IMPORT_CHUNK_SIZE = 50000  # 导入分块大小

# 查询服务配置
API_HOST = "0.0.0.0"
API_PORT = 5000
API_DEBUG = False
CACHE_TTL = 3600  # 缓存时间(秒)
CACHE_MAX_SIZE = 10000  # 最大缓存条目

# 验证节点配置
VALIDATOR_NODES = [
    {"name": "beijing", "host": "localhost", "port": 5001, "location": "北京"},
    {"name": "shanghai", "host": "localhost", "port": 5002, "location": "上海"},
    {"name": "guangzhou", "host": "localhost", "port": 5003, "location": "广州"},
]

VALIDATOR_API_KEY = os.getenv("VALIDATOR_API_KEY", "your-secret-api-key")
VALIDATION_BATCH_SIZE = 100  # 验证批次大小
VALIDATION_INTERVAL_HOURS = 24  # 验证间隔(小时)

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = os.path.join(BASE_DIR, "data", "ipdb.log")
