#!/usr/bin/env python3
"""
IP验证节点服务端
用法:
    python validator/node_server.py --name beijing --port 5001
"""
import sys
import os
import subprocess
import platform
import socket
import time
import json
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify

from utils.ip_utils import is_valid_ip
from config.settings import VALIDATOR_API_KEY

app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 节点信息
NODE_INFO = {
    "name": "unknown",
    "location": "unknown",
    "host": "localhost",
    "port": 5001,
    "started_at": datetime.now().isoformat()
}


def check_api_key():
    """检查API密钥"""
    api_key = request.headers.get('X-API-Key')
    if api_key != VALIDATOR_API_KEY:
        return jsonify({"error": "无效的API密钥"}), 401
    return None


def ping_host(ip: str, count: int = 4) -> dict:
    """
    Ping测试
    
    Args:
        ip: 目标IP
        count: 发送包数量
        
    Returns:
        测试结果字典
    """
    if not is_valid_ip(ip):
        return {"error": "无效的IP地址"}
    
    system = platform.system().lower()
    
    try:
        if system == "windows":
            cmd = ["ping", "-n", str(count), "-w", "3000", ip]
        else:
            cmd = ["ping", "-c", str(count), "-W", "3", ip]
        
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        elapsed_time = int((time.time() - start_time) * 1000)
        
        success = result.returncode == 0
        
        return {
            "method": "ping",
            "target": ip,
            "success": success,
            "response_time_ms": elapsed_time if success else None,
            "output": result.stdout if success else result.stderr
        }
    
    except subprocess.TimeoutExpired:
        return {
            "method": "ping",
            "target": ip,
            "success": False,
            "error": "超时"
        }
    except Exception as e:
        return {
            "method": "ping",
            "target": ip,
            "success": False,
            "error": str(e)
        }


def traceroute_host(ip: str, max_hops: int = 30) -> dict:
    """
    Traceroute测试
    
    Args:
        ip: 目标IP
        max_hops: 最大跳数
        
    Returns:
        测试结果字典
    """
    if not is_valid_ip(ip):
        return {"error": "无效的IP地址"}
    
    system = platform.system().lower()
    
    try:
        if system == "windows":
            cmd = ["tracert", "-h", str(max_hops), "-w", "3000", ip]
        else:
            cmd = ["traceroute", "-m", str(max_hops), "-w", "3", ip]
        
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        elapsed_time = int((time.time() - start_time) * 1000)
        
        # 解析输出
        output_lines = result.stdout.split('\n')
        hops = []
        for line in output_lines:
            line = line.strip()
            if not line:
                continue
            # 简单解析，提取IP地址
            import re
            ip_matches = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', line)
            if ip_matches:
                hops.append({
                    "line": line,
                    "ips": ip_matches
                })
        
        return {
            "method": "traceroute",
            "target": ip,
            "success": result.returncode == 0,
            "hops_count": len(hops),
            "hops": hops[:10],  # 只返回前10跳
            "response_time_ms": elapsed_time,
            "output": result.stdout[:2000]  # 限制输出长度
        }
    
    except subprocess.TimeoutExpired:
        return {
            "method": "traceroute",
            "target": ip,
            "success": False,
            "error": "超时"
        }
    except Exception as e:
        return {
            "method": "traceroute",
            "target": ip,
            "success": False,
            "error": str(e)
        }


def get_node_info() -> dict:
    """获取节点信息"""
    info = NODE_INFO.copy()
    info['current_time'] = datetime.now().isoformat()
    info['uptime_seconds'] = int((datetime.now() - datetime.fromisoformat(NODE_INFO['started_at'])).total_seconds())
    
    # 获取本机IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info['local_ip'] = s.getsockname()[0]
        s.close()
    except:
        info['local_ip'] = "unknown"
    
    return info


@app.route('/')
def index():
    """节点首页"""
    return jsonify({
        "name": "IP验证节点",
        "version": "1.0.0",
        "node_info": get_node_info(),
        "endpoints": {
            "/health": "健康检查",
            "/node/info": "节点信息",
            "/validate/ping": "Ping测试 (POST)",
            "/validate/traceroute": "Traceroute测试 (POST)"
        }
    })


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "node": get_node_info()
    })


@app.route('/node/info')
def node_info():
    """获取节点信息"""
    return jsonify(get_node_info())


@app.route('/validate/ping', methods=['POST'])
def validate_ping():
    """
    Ping测试
    
    请求体:
        {
            "ip": "8.8.8.8",
            "count": 4
        }
    """
    error = check_api_key()
    if error:
        return error
    
    data = request.get_json()
    if not data or 'ip' not in data:
        return jsonify({"error": "请求体必须包含 'ip' 字段"}), 400
    
    ip = data['ip']
    count = data.get('count', 4)
    
    result = ping_host(ip, count)
    result['node'] = get_node_info()
    
    return jsonify(result)


@app.route('/validate/traceroute', methods=['POST'])
def validate_traceroute():
    """
    Traceroute测试
    
    请求体:
        {
            "ip": "8.8.8.8",
            "max_hops": 30
        }
    """
    error = check_api_key()
    if error:
        return error
    
    data = request.get_json()
    if not data or 'ip' not in data:
        return jsonify({"error": "请求体必须包含 'ip' 字段"}), 400
    
    ip = data['ip']
    max_hops = data.get('max_hops', 30)
    
    result = traceroute_host(ip, max_hops)
    result['node'] = get_node_info()
    
    return jsonify(result)


@app.route('/validate/all', methods=['POST'])
def validate_all():
    """
    执行所有验证测试
    
    请求体:
        {
            "ip": "8.8.8.8"
        }
    """
    error = check_api_key()
    if error:
        return error
    
    data = request.get_json()
    if not data or 'ip' not in data:
        return jsonify({"error": "请求体必须包含 'ip' 字段"}), 400
    
    ip = data['ip']
    
    # 执行ping测试
    ping_result = ping_host(ip)
    
    # 执行traceroute测试
    traceroute_result = traceroute_host(ip)
    
    return jsonify({
        "ip": ip,
        "node": get_node_info(),
        "tests": {
            "ping": ping_result,
            "traceroute": traceroute_result
        },
        "tested_at": datetime.now().isoformat()
    })


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='IP验证节点服务')
    parser.add_argument('--name', default='node1', help='节点名称')
    parser.add_argument('--location', default='unknown', help='节点地理位置')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=5001, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    # 更新节点信息
    NODE_INFO['name'] = args.name
    NODE_INFO['location'] = args.location
    NODE_INFO['host'] = args.host
    NODE_INFO['port'] = args.port
    
    logger.info(f"启动验证节点: {args.name} ({args.location})")
    logger.info(f"监听地址: {args.host}:{args.port}")
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
