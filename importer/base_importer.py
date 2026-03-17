"""
基础数据导入器类
"""
import csv
import logging
from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, List, Tuple
from utils.database import get_db_manager, insert_location, batch_insert_ip_ranges
from utils.ip_utils import cidr_to_range
from config.settings import BATCH_SIZE

logger = logging.getLogger(__name__)


class BaseImporter(ABC):
    """数据导入器基类"""
    
    def __init__(self, db_path: str, source_name: str):
        self.db = get_db_manager(db_path)
        self.source_name = source_name
        self.location_cache = {}  # 缓存location_id避免重复查询
    
    @abstractmethod
    def download_data(self) -> str:
        """下载数据文件，返回文件路径"""
        pass
    
    @abstractmethod
    def parse_location(self, row: Dict[str, str]) -> Dict[str, Any]:
        """解析位置数据"""
        pass
    
    @abstractmethod
    def parse_ip_range(self, row: Dict[str, str]) -> Tuple[str, Dict[str, Any]]:
        """
        解析IP范围数据
        返回: (network_cidr, location_data)
        """
        pass
    
    def get_or_create_location(self, location_data: Dict[str, Any]) -> int:
        """
        获取或创建地理位置记录
        
        Args:
            location_data: 位置数据
            
        Returns:
            location_id
        """
        # 构建缓存键
        cache_key = (
            location_data.get('country_code', ''),
            location_data.get('region_code', ''),
            location_data.get('city_name', ''),
            location_data.get('district')
        )
        
        # 检查缓存
        if cache_key in self.location_cache:
            return self.location_cache[cache_key]
        
        # 查询数据库
        from utils.database import get_location_id
        location_id = get_location_id(
            location_data.get('country_code'),
            location_data.get('region_code'),
            location_data.get('city_name'),
            location_data.get('district'),
            self.db.db_path
        )
        
        if location_id is None:
            # 插入新记录
            location_id = insert_location(location_data, self.db.db_path)
            logger.debug(f"插入新位置: {location_data.get('city_name')}, ID: {location_id}")
        
        # 缓存结果
        self.location_cache[cache_key] = location_id
        return location_id
    
    def import_from_csv(self, csv_path: str, location_parser=None, ip_range_parser=None) -> Tuple[int, int]:
        """
        从CSV文件导入数据
        
        Args:
            csv_path: CSV文件路径
            location_parser: 位置解析函数
            ip_range_parser: IP范围解析函数
            
        Returns:
            (导入的位置数, 导入的IP范围数)
        """
        if location_parser is None:
            location_parser = self.parse_location
        if ip_range_parser is None:
            ip_range_parser = self.parse_ip_range
        
        locations_count = 0
        ip_ranges_batch = []
        ip_ranges_count = 0
        
        logger.info(f"开始导入数据: {csv_path}")
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    # 解析IP范围和位置
                    network_cidr, location_data = ip_range_parser(row)
                    
                    if not network_cidr:
                        continue
                    
                    # 获取或创建位置
                    location_id = self.get_or_create_location(location_data)
                    if location_id:
                        locations_count += 1
                    
                    # 解析IP范围
                    start_ip, end_ip = cidr_to_range(network_cidr)
                    
                    # 准备IP范围数据
                    ip_range_tuple = (
                        network_cidr,
                        start_ip,
                        end_ip,
                        location_id,
                        self.source_name,
                        location_data.get('accuracy_radius'),
                        location_data.get('is_anonymous_proxy', False),
                        location_data.get('is_satellite_provider', False)
                    )
                    ip_ranges_batch.append(ip_range_tuple)
                    
                    # 批量插入
                    if len(ip_ranges_batch) >= BATCH_SIZE:
                        batch_insert_ip_ranges(ip_ranges_batch, self.db.db_path)
                        ip_ranges_count += len(ip_ranges_batch)
                        ip_ranges_batch = []
                        logger.info(f"已导入 {ip_ranges_count} 条IP范围记录")
                
                except Exception as e:
                    logger.error(f"处理行时出错: {row}, 错误: {e}")
                    continue
        
        # 插入剩余的记录
        if ip_ranges_batch:
            batch_insert_ip_ranges(ip_ranges_batch, self.db.db_path)
            ip_ranges_count += len(ip_ranges_batch)
        
        logger.info(f"导入完成: {locations_count} 个位置, {ip_ranges_count} 条IP范围")
        return locations_count, ip_ranges_count
    
    def import_data(self) -> Tuple[int, int]:
        """
        导入数据的主方法
        
        Returns:
            (导入的位置数, 导入的IP范围数)
        """
        # 下载数据
        data_path = self.download_data()
        
        # 导入数据
        return self.import_from_csv(data_path)
