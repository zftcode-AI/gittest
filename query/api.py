#!/usr/bin/env python3
"""
IP查询REST API服务
用法:
    python query/api.py
    python query/api.py --host 0.0.0.0 --port 5000
"""
import sys
import os
import json
import time
from datetime import datetime
from functools import wraps

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify

from utils.ip_utils import ip_to_int, is_valid_ip
from utils.database import query_ip_location, get_db_manager, get_validation_stats
from config.settings import DATABASE_PATH, API_HOST, API_PORT, API_DEBUG, CACHE_TTL, CACHE_MAX_SIZE

app = Flask(__name__)

# 简单的内存缓存
cache = {}
cache_timestamps = {}


def cached(ttl=CACHE_TTL):
    """简单的缓存装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 构建缓存键
            cache_key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            
            # 检查缓存
            now = time.time()
            if cache_key in cache:
                if now - cache_timestamps.get(cache_key, 0) < ttl:
                    return cache[cache_key]
            
            # 执行函数
            result = f(*args, **kwargs)
            
            # 更新缓存
            cache[cache_key] = result
            cache_timestamps[cache_key] = now
            
            # 清理过期缓存
            if len(cache) > CACHE_MAX_SIZE:
                oldest_key = min(cache_timestamps, key=cache_timestamps.get)
                del cache[oldest_key]
                del cache_timestamps[oldest_key]
            
            return result
        return decorated_function
    return decorator


def format_ip_response(ip: str, result: dict) -> dict:
    """格式化IP查询响应"""
    if not result:
        return {
            "ip": ip,
            "found": False,
            "message": "未找到该IP的地理位置信息"
        }
    
    return {
        "ip": ip,
        "found": True,
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
        "source": result.get('ip_source'),
        "query_time": datetime.now().isoformat()
    }


@app.route('/')
def index():
    """API首页"""
    return jsonify({
        "name": "IP地址定位API",
        "version": "1.0.0",
        "endpoints": {
            "/api/v1/ip/<ip>": "查询单个IP地址",
            "/api/v1/batch": "批量查询IP地址 (POST)",
            "/api/v1/stats": "获取数据库统计信息",
            "/api/v1/validation-stats": "获取验证统计信息"
        }
    })


@app.route('/api/v1/ip/<ip>')
@cached()
def query_ip(ip: str):
    """
    查询单个IP地址
    
    Path参数:
        ip: IP地址
        
    返回:
        JSON格式的地理位置信息
    """
    if not is_valid_ip(ip):
        return jsonify({
            "error": "无效的IP地址",
            "ip": ip
        }), 400
    
    try:
        ip_int = ip_to_int(ip)
        result = query_ip_location(ip_int, DATABASE_PATH)
        response = format_ip_response(ip, result)
        return jsonify(response)
    except Exception as e:
        return jsonify({
            "error": f"查询失败: {str(e)}",
            "ip": ip
        }), 500


@app.route('/api/v1/batch', methods=['POST'])
def batch_query():
    """
    批量查询IP地址
    
    请求体:
        {
            "ips": ["8.8.8.8", "1.1.1.1", ...]
        }
        
    返回:
        JSON数组，包含每个IP的查询结果
    """
    data = request.get_json()
    
    if not data or 'ips' not in data:
        return jsonify({
            "error": "请求体必须包含 'ips' 字段"
        }), 400
    
    ips = data['ips']
    
    if not isinstance(ips, list):
        return jsonify({
            "error": "'ips' 必须是数组"
        }), 400
    
    if len(ips) > 1000:
        return jsonify({
            "error": "一次最多查询1000个IP地址"
        }), 400
    
    results = []
    for ip in ips:
        if not is_valid_ip(ip):
            results.append({
                "ip": ip,
                "found": False,
                "error": "无效的IP地址"
            })
            continue
        
        try:
            ip_int = ip_to_int(ip)
            result = query_ip_location(ip_int, DATABASE_PATH)
            response = format_ip_response(ip, result)
            results.append(response)
        except Exception as e:
            results.append({
                "ip": ip,
                "found": False,
                "error": str(e)
            })
    
    return jsonify({
        "results": results,
        "total": len(results),
        "found": len([r for r in results if r.get('found')]),
        "query_time": datetime.now().isoformat()
    })


@app.route('/api/v1/stats')
@cached(ttl=300)  # 统计信息缓存5分钟
def get_stats():
    """
    获取数据库统计信息
    
    返回:
        JSON格式的统计信息
    """
    db = get_db_manager(DATABASE_PATH)
    
    # 基础统计
    ip_range_count = db.fetchone("SELECT COUNT(*) as count FROM ip_ranges")
    location_count = db.fetchone("SELECT COUNT(*) as count FROM locations")
    validation_count = db.fetchone("SELECT COUNT(*) as count FROM validations")
    
    # 国家分布 (前20)
    countries = db.fetchall('''
        SELECT country_code, country_name, COUNT(*) as count 
        FROM locations 
        WHERE country_code IS NOT NULL AND country_code != ''
        GROUP BY country_code 
        ORDER BY count DESC 
        LIMIT 20
    ''')
    
    # 数据源分布
    sources = db.fetchall('''
        SELECT source, COUNT(*) as count 
        FROM ip_ranges 
        WHERE source IS NOT NULL
        GROUP BY source
    ''')
    
    return jsonify({
        "database": {
            "ip_ranges": ip_range_count['count'],
            "locations": location_count['count'],
            "validations": validation_count['count']
        },
        "countries": [
            {
                "code": c['country_code'],
                "name": c['country_name'],
                "count": c['count']
            } for c in countries
        ],
        "sources": [
            {
                "name": s['source'],
                "count": s['count']
            } for s in sources
        ],
        "query_time": datetime.now().isoformat()
    })


@app.route('/api/v1/validation-stats')
@cached(ttl=300)
def get_validation_statistics():
    """
    获取验证统计信息
    
    返回:
        JSON格式的验证统计
    """
    stats = get_validation_stats(db_path=DATABASE_PATH)
    
    return jsonify({
        "validation_summary": [
            {
                "country_code": s['country_code'],
                "region_code": s['region_code'],
                "total_tests": s['total_tests'],
                "accurate_tests": s['accurate_tests'],
                "accuracy_rate": s['accuracy_rate'],
                "last_tested_at": s['last_tested_at']
            } for s in stats
        ],
        "query_time": datetime.now().isoformat()
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "接口不存在",
        "message": "请检查API路径是否正确"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "服务器内部错误",
        "message": str(error)
    }), 500


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='IP查询API服务')
    parser.add_argument('--host', default=API_HOST, help='监听地址')
    parser.add_argument('--port', type=int, default=API_PORT, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    print(f"启动IP查询API服务...")
    print(f"监听地址: {args.host}:{args.port}")
    print(f"数据库: {DATABASE_PATH}")
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
