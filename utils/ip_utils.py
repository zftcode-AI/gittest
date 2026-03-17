"""
IP地址工具函数
"""
import ipaddress
import socket
from typing import Union, Tuple, Optional


def ip_to_int(ip: str) -> int:
    """
    将IP地址转换为整数
    支持IPv4和IPv6
    
    Args:
        ip: IP地址字符串
        
    Returns:
        IP地址对应的整数
        
    Raises:
        ValueError: 无效的IP地址
    """
    try:
        # 尝试IPv4
        return int(ipaddress.IPv4Address(ip))
    except ValueError:
        try:
            # 尝试IPv6
            return int(ipaddress.IPv6Address(ip))
        except ValueError:
            raise ValueError(f"无效的IP地址: {ip}")


def int_to_ip(ip_int: int, is_ipv6: bool = False) -> str:
    """
    将整数转换为IP地址
    
    Args:
        ip_int: IP地址整数
        is_ipv6: 是否为IPv6地址
        
    Returns:
        IP地址字符串
    """
    if is_ipv6 or ip_int > 0xFFFFFFFF:
        return str(ipaddress.IPv6Address(ip_int))
    else:
        return str(ipaddress.IPv4Address(ip_int))


def cidr_to_range(network: str) -> Tuple[int, int]:
    """
    将CIDR格式的网络地址转换为IP范围
    
    Args:
        network: CIDR格式，如 "192.168.1.0/24"
        
    Returns:
        (start_ip, end_ip) 元组
    """
    try:
        net = ipaddress.ip_network(network, strict=False)
        start_ip = int(net.network_address)
        end_ip = int(net.broadcast_address)
        return start_ip, end_ip
    except ValueError as e:
        raise ValueError(f"无效的网络地址: {network}, 错误: {e}")


def range_to_cidr(start_ip: int, end_ip: int) -> list:
    """
    将IP范围转换为CIDR列表
    
    Args:
        start_ip: 起始IP整数
        end_ip: 结束IP整数
        
    Returns:
        CIDR字符串列表
    """
    cidrs = []
    
    # 确定是IPv4还是IPv6
    if end_ip <= 0xFFFFFFFF:
        ip_version = 4
        max_bits = 32
    else:
        ip_version = 6
        max_bits = 128
    
    current = start_ip
    while current <= end_ip:
        # 计算当前IP可以使用的最大前缀长度
        if ip_version == 4:
            addr = ipaddress.IPv4Address(current)
        else:
            addr = ipaddress.IPv6Address(current)
        
        # 找到可以覆盖的最大范围
        for prefix_len in range(max_bits, -1, -1):
            if ip_version == 4:
                network = ipaddress.IPv4Network(f"{addr}/{prefix_len}", strict=False)
            else:
                network = ipaddress.IPv6Network(f"{addr}/{prefix_len}", strict=False)
            
            net_start = int(network.network_address)
            net_end = int(network.broadcast_address)
            
            if net_start >= current and net_end <= end_ip:
                cidrs.append(str(network))
                current = net_end + 1
                break
    
    return cidrs


def is_private_ip(ip: str) -> bool:
    """
    检查IP是否为私有地址
    
    Args:
        ip: IP地址字符串
        
    Returns:
        是否为私有地址
    """
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private
    except ValueError:
        return False


def is_valid_ip(ip: str) -> bool:
    """
    检查字符串是否为有效的IP地址
    
    Args:
        ip: IP地址字符串
        
    Returns:
        是否有效
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def get_ip_version(ip: str) -> int:
    """
    获取IP地址版本
    
    Args:
        ip: IP地址字符串
        
    Returns:
        4 或 6
        
    Raises:
        ValueError: 无效的IP地址
    """
    try:
        addr = ipaddress.ip_address(ip)
        return addr.version
    except ValueError:
        raise ValueError(f"无效的IP地址: {ip}")


def ip_to_binary(ip: str) -> str:
    """
    将IP地址转换为二进制字符串
    
    Args:
        ip: IP地址字符串
        
    Returns:
        二进制字符串
    """
    addr = ipaddress.ip_address(ip)
    if addr.version == 4:
        return format(int(addr), '032b')
    else:
        return format(int(addr), '0128b')


def normalize_ip(ip: str) -> str:
    """
    标准化IP地址格式
    
    Args:
        ip: IP地址字符串
        
    Returns:
        标准化的IP地址
    """
    addr = ipaddress.ip_address(ip)
    return str(addr)


def expand_ipv6(ip: str) -> str:
    """
    展开IPv6地址为完整格式
    
    Args:
        ip: IPv6地址字符串
        
    Returns:
        完整格式的IPv6地址
    """
    addr = ipaddress.IPv6Address(ip)
    return addr.exploded


def compress_ipv6(ip: str) -> str:
    """
    压缩IPv6地址为最短格式
    
    Args:
        ip: IPv6地址字符串
        
    Returns:
        压缩格式的IPv6地址
    """
    addr = ipaddress.IPv6Address(ip)
    return addr.compressed


def get_hostname(ip: str) -> Optional[str]:
    """
    通过IP地址获取主机名
    
    Args:
        ip: IP地址字符串
        
    Returns:
        主机名，如果失败返回None
    """
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror):
        return None


def ip_in_range(ip: str, start_ip: str, end_ip: str) -> bool:
    """
    检查IP是否在指定范围内
    
    Args:
        ip: 要检查的IP
        start_ip: 范围起始IP
        end_ip: 范围结束IP
        
    Returns:
        是否在范围内
    """
    ip_int = ip_to_int(ip)
    start_int = ip_to_int(start_ip)
    end_int = ip_to_int(end_ip)
    return start_int <= ip_int <= end_int


def calculate_subnet(ip: str, prefix_len: int) -> str:
    """
    计算子网地址
    
    Args:
        ip: IP地址
        prefix_len: 前缀长度
        
    Returns:
        子网地址
    """
    version = get_ip_version(ip)
    if version == 4:
        network = ipaddress.IPv4Network(f"{ip}/{prefix_len}", strict=False)
    else:
        network = ipaddress.IPv6Network(f"{ip}/{prefix_len}", strict=False)
    return str(network.network_address)
