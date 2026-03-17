#!/usr/bin/env python3
"""
数据库初始化脚本
用法: python scripts/init_db.py
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import init_database
from config.settings import DATABASE_PATH


def main():
    """初始化数据库"""
    print(f"正在初始化数据库: {DATABASE_PATH}")
    
    # 确保数据目录存在
    data_dir = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"创建数据目录: {data_dir}")
    
    # 初始化数据库
    init_database(DATABASE_PATH)
    print("数据库初始化完成！")
    
    # 检查数据库文件
    if os.path.exists(DATABASE_PATH):
        size = os.path.getsize(DATABASE_PATH)
        print(f"数据库文件大小: {size} 字节")


if __name__ == "__main__":
    main()
