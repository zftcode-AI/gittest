#!/usr/bin/env python3
"""
IP验证节点客户端
用于与验证节点通信
"""
import sys
import os
import requests
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import VALIDATOR_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ValidatorNodeClient:
    """验证节点客户端"""
    
    def __init__(self, host: str, port: int, api_key: str = None):
        self.host = host
        self.port = port
        self.api_key = api_key or VALIDATOR_API_KEY
        self.base_url = f"http://{host}:{port}"
    
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> Optional[dict]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=30)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败 {url}: {e}")
            return None
    
    def health_check(self) -> bool:
        """健康检查"""
        result = self._make_request("GET", "/health")
        if result and result.get("status") == "healthy":
            return True
        return False
    
    def get_node_info(self) -> Optional[dict]:
        """获取节点信息"""
        return self._make_request("GET", "/node/info")
    
    def ping_test(self, ip: str, count: int = 4) -> Optional[dict]:
        """
        Ping测试
        
        Args:
            ip: 目标IP
            count: 发送包数量
            
        Returns:
            测试结果
        """
        data = {"ip": ip, "count": count}
        return self._make_request("POST", "/validate/ping", data)
    
    def traceroute_test(self, ip: str, max_hops: int = 30) -> Optional[dict]:
        """
        Traceroute测试
        
        Args:
            ip: 目标IP
            max_hops: 最大跳数
            
        Returns:
            测试结果
        """
        data = {"ip": ip, "max_hops": max_hops}
        return self._make_request("POST", "/validate/traceroute", data)
    
    def validate_all(self, ip: str) -> Optional[dict]:
        """
        执行所有验证测试
        
        Args:
            ip: 目标IP
            
        Returns:
            所有测试结果
        """
        data = {"ip": ip}
        return self._make_request("POST", "/validate/all", data)


class ValidatorNodeManager:
    """验证节点管理器"""
    
    def __init__(self, nodes_config: list = None):
        from config.settings import VALIDATOR_NODES
        self.nodes_config = nodes_config or VALIDATOR_NODES
        self.clients = {}
        self._init_clients()
    
    def _init_clients(self):
        """初始化所有节点的客户端"""
        for node in self.nodes_config:
            client = ValidatorNodeClient(
                host=node['host'],
                port=node['port'],
                api_key=VALIDATOR_API_KEY
            )
            self.clients[node['name']] = {
                'client': client,
                'config': node
            }
    
    def get_available_nodes(self) -> list:
        """获取可用节点列表"""
        available = []
        for name, node in self.clients.items():
            if node['client'].health_check():
                available.append({
                    'name': name,
                    'config': node['config']
                })
        return available
    
    def validate_ip(self, ip: str, node_name: str = None) -> dict:
        """
        验证IP地址
        
        Args:
            ip: 目标IP
            node_name: 指定节点名称，None则使用所有可用节点
            
        Returns:
            验证结果
        """
        results = {
            "ip": ip,
            "tested_at": datetime.now().isoformat(),
            "nodes": {}
        }
        
        if node_name:
            # 使用指定节点
            if node_name not in self.clients:
                return {"error": f"节点不存在: {node_name}"}
            
            client_info = self.clients[node_name]
            result = client_info['client'].validate_all(ip)
            if result:
                results['nodes'][node_name] = result
            else:
                results['nodes'][node_name] = {"error": "验证失败"}
        else:
            # 使用所有可用节点
            for name, node in self.clients.items():
                result = node['client'].validate_all(ip)
                if result:
                    results['nodes'][name] = result
                else:
                    results['nodes'][name] = {"error": "验证失败"}
        
        return results
    
    def validate_ip_from_all_nodes(self, ip: str) -> dict:
        """
        从所有节点验证IP地址
        
        Args:
            ip: 目标IP
            
        Returns:
            所有节点的验证结果
        """
        return self.validate_ip(ip, node_name=None)


def test_node_connection(host: str, port: int) -> bool:
    """测试节点连接"""
    client = ValidatorNodeClient(host, port)
    return client.health_check()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='验证节点客户端')
    parser.add_argument('--host', default='localhost', help='节点主机')
    parser.add_argument('--port', type=int, default=5001, help='节点端口')
    parser.add_argument('--action', choices=['health', 'info', 'ping', 'traceroute', 'validate'],
                       default='health', help='操作类型')
    parser.add_argument('--ip', help='目标IP地址')
    
    args = parser.parse_args()
    
    client = ValidatorNodeClient(args.host, args.port)
    
    if args.action == 'health':
        result = client.health_check()
        print(f"健康状态: {'正常' if result else '异常'}")
    
    elif args.action == 'info':
        result = client.get_node_info()
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else "获取信息失败")
    
    elif args.action == 'ping':
        if not args.ip:
            print("请提供 --ip 参数")
            return
        result = client.ping_test(args.ip)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else "测试失败")
    
    elif args.action == 'traceroute':
        if not args.ip:
            print("请提供 --ip 参数")
            return
        result = client.traceroute_test(args.ip)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else "测试失败")
    
    elif args.action == 'validate':
        if not args.ip:
            print("请提供 --ip 参数")
            return
        result = client.validate_all(args.ip)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result else "验证失败")


if __name__ == "__main__":
    main()
