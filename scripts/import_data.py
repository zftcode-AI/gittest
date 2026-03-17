#!/usr/bin/env python3
"""
数据导入脚本
用法: 
    python scripts/import_data.py maxmind --license-key YOUR_KEY
    python scripts/import_data.py maxmind --csv-path /path/to/blocks.csv
"""
import sys
import os
import argparse
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import DATABASE_PATH
from utils.database import init_database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def import_maxmind(license_key: str = None, csv_path: str = None):
    """导入MaxMind数据"""
    from importer.maxmind_importer import MaxMindImporter
    
    importer = MaxMindImporter(DATABASE_PATH, license_key)
    
    if csv_path:
        # 直接从CSV导入
        logger.info(f"从CSV文件导入: {csv_path}")
        locations, ip_ranges = importer.import_from_csv(csv_path)
    else:
        # 下载并导入
        locations, ip_ranges = importer.import_data()
    
    logger.info(f"导入完成: {locations} 个位置, {ip_ranges} 条IP范围")
    return locations, ip_ranges


def main():
    parser = argparse.ArgumentParser(description='IP数据库数据导入工具')
    parser.add_argument('source', choices=['maxmind'], help='数据源')
    parser.add_argument('--license-key', help='MaxMind License Key')
    parser.add_argument('--csv-path', help='CSV文件路径（直接导入本地文件）')
    parser.add_argument('--init-db', action='store_true', help='初始化数据库')
    
    args = parser.parse_args()
    
    # 初始化数据库
    if args.init_db:
        logger.info("初始化数据库...")
        init_database(DATABASE_PATH)
    
    # 导入数据
    if args.source == 'maxmind':
        import_maxmind(args.license_key, args.csv_path)


if __name__ == "__main__":
    main()
