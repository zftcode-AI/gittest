#!/usr/bin/env python3
"""
IP查询命令行工具
用法:
    python query/cli.py query 8.8.8.8
    python query/cli.py batch-query ips.txt
    python query/cli.py stats
"""
import sys
import os
import json
import argparse
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ip_utils import ip_to_int, is_valid_ip
from utils.database import query_ip_location, get_db_manager, get_validation_stats
from config.settings import DATABASE_PATH


def format_location_result(result: dict) -> str:
    """格式化查询结果"""
    if not result:
        return "未找到该IP的地理位置信息"
    
    output = []
    output.append(f"IP段: {result.get('network', 'N/A')}")
    output.append(f"国家: {result.get('country_name', 'N/A')} ({result.get('country_code', 'N/A')})")
    output.append(f"省/州: {result.get('region_name', 'N/A')} ({result.get('region_code', 'N/A')})")
    output.append(f"城市: {result.get('city_name', 'N/A')}")
    
    if result.get('district'):
        output.append(f"区/县: {result['district']}")
    
    if result.get('postal_code'):
        output.append(f"邮编: {result['postal_code']}")
    
    if result.get('latitude') and result.get('longitude'):
        output.append(f"坐标: {result['latitude']}, {result['longitude']}")
    
    if result.get('timezone'):
        output.append(f"时区: {result['timezone']}")
    
    if result.get('accuracy_radius'):
        output.append(f"准确度半径: {result['accuracy_radius']} km")
    
    output.append(f"数据来源: {result.get('ip_source', 'N/A')}")
    
    return "\n".join(output)


def query_single_ip(ip: str, output_format: str = "text") -> Optional[dict]:
    """
    查询单个IP地址
    
    Args:
        ip: IP地址
        output_format: 输出格式 (text/json)
        
    Returns:
        查询结果字典
    """
    if not is_valid_ip(ip):
        print(f"错误: 无效的IP地址 '{ip}'")
        return None
    
    ip_int = ip_to_int(ip)
    result = query_ip_location(ip_int, DATABASE_PATH)
    
    if output_format == "json":
        if result:
            output = {
                "ip": ip,
                "network": result.get('network'),
                "location": {
                    "country": {
                        "code": result.get('country_code'),
                        "name": result.get('country_name')
                    },
                    "region": {
                        "code": result.get('region_code'),
                        "name": result.get('region_name')
                    },
                    "city": result.get('city_name'),
                    "district": result.get('district'),
                    "postal_code": result.get('postal_code'),
                    "latitude": result.get('latitude'),
                    "longitude": result.get('longitude'),
                    "timezone": result.get('timezone')
                },
                "accuracy": {
                    "radius_km": result.get('accuracy_radius')
                },
                "source": result.get('ip_source')
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"ip": ip, "error": "未找到地理位置信息"}, ensure_ascii=False))
    else:
        print(f"\n查询IP: {ip}")
        print("-" * 40)
        print(format_location_result(result))
    
    return result


def batch_query(input_file: str, output_file: Optional[str] = None):
    """
    批量查询IP地址
    
    Args:
        input_file: 包含IP地址的文件路径
        output_file: 输出文件路径
    """
    if not os.path.exists(input_file):
        print(f"错误: 文件不存在 '{input_file}'")
        return
    
    results = []
    
    with open(input_file, 'r') as f:
        ips = [line.strip() for line in f if line.strip()]
    
    print(f"开始批量查询 {len(ips)} 个IP地址...")
    
    for i, ip in enumerate(ips, 1):
        if not is_valid_ip(ip):
            results.append({
                "ip": ip,
                "error": "无效的IP地址"
            })
            continue
        
        ip_int = ip_to_int(ip)
        result = query_ip_location(ip_int, DATABASE_PATH)
        
        if result:
            results.append({
                "ip": ip,
                "network": result.get('network'),
                "country_code": result.get('country_code'),
                "country_name": result.get('country_name'),
                "region_code": result.get('region_code'),
                "region_name": result.get('region_name'),
                "city": result.get('city_name'),
                "district": result.get('district'),
                "latitude": result.get('latitude'),
                "longitude": result.get('longitude'),
                "timezone": result.get('timezone'),
                "accuracy_radius": result.get('accuracy_radius'),
                "source": result.get('ip_source')
            })
        else:
            results.append({
                "ip": ip,
                "error": "未找到地理位置信息"
            })
        
        if i % 100 == 0:
            print(f"已处理 {i}/{len(ips)}...")
    
    # 输出结果
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {output_file}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    
    print(f"\n查询完成: 成功 {len([r for r in results if 'error' not in r])}, 失败 {len([r for r in results if 'error' in r])}")


def show_stats():
    """显示数据库统计信息"""
    db = get_db_manager(DATABASE_PATH)
    
    # IP范围统计
    ip_range_count = db.fetchone("SELECT COUNT(*) as count FROM ip_ranges")
    print(f"\n数据库统计:")
    print("-" * 40)
    print(f"IP范围总数: {ip_range_count['count']:,}")
    
    # 位置统计
    location_count = db.fetchone("SELECT COUNT(*) as count FROM locations")
    print(f"地理位置数: {location_count['count']:,}")
    
    # 国家分布
    print("\n国家分布 (前10):")
    countries = db.fetchall('''
        SELECT country_code, country_name, COUNT(*) as count 
        FROM locations 
        WHERE country_code IS NOT NULL
        GROUP BY country_code 
        ORDER BY count DESC 
        LIMIT 10
    ''')
    for c in countries:
        print(f"  {c['country_code']} ({c['country_name']}): {c['count']:,}")
    
    # 验证统计
    validation_count = db.fetchone("SELECT COUNT(*) as count FROM validations")
    if validation_count['count'] > 0:
        print(f"\n验证记录数: {validation_count['count']:,}")
        
        # 准确率统计
        accuracy_stats = db.fetchone('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_accurate = 1 THEN 1 ELSE 0 END) as accurate
            FROM validations
        ''')
        if accuracy_stats['total'] > 0:
            accuracy_rate = accuracy_stats['accurate'] / accuracy_stats['total'] * 100
            print(f"验证准确率: {accuracy_rate:.2f}%")


def main():
    parser = argparse.ArgumentParser(description='IP地址查询工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 查询单个IP
    query_parser = subparsers.add_parser('query', help='查询单个IP地址')
    query_parser.add_argument('ip', help='要查询的IP地址')
    query_parser.add_argument('--format', choices=['text', 'json'], default='text', help='输出格式')
    
    # 批量查询
    batch_parser = subparsers.add_parser('batch-query', help='批量查询IP地址')
    batch_parser.add_argument('input_file', help='包含IP地址的文件')
    batch_parser.add_argument('--output', '-o', help='输出文件路径')
    
    # 统计信息
    subparsers.add_parser('stats', help='显示数据库统计信息')
    
    args = parser.parse_args()
    
    if args.command == 'query':
        query_single_ip(args.ip, args.format)
    elif args.command == 'batch-query':
        batch_query(args.input_file, args.output)
    elif args.command == 'stats':
        show_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
