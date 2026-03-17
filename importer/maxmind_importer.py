"""
MaxMind GeoLite2 数据导入器
"""
import os
import csv
import gzip
import shutil
import logging
import requests
from typing import Dict, Any, Tuple
from importer.base_importer import BaseImporter
from config.settings import (
    MAXMIND_LICENSE_KEY, MAXMIND_DOWNLOAD_URL, MAXMIND_EDITION, DATA_RAW_DIR
)

logger = logging.getLogger(__name__)


class MaxMindImporter(BaseImporter):
    """MaxMind GeoLite2 数据导入器"""
    
    def __init__(self, db_path: str, license_key: str = None):
        super().__init__(db_path, "maxmind")
        self.license_key = license_key or MAXMIND_LICENSE_KEY
        self.data_dir = os.path.join(DATA_RAW_DIR, "maxmind")
        os.makedirs(self.data_dir, exist_ok=True)
    
    def download_data(self) -> str:
        """
        下载MaxMind GeoLite2数据
        
        Returns:
            CSV文件路径
        """
        if not self.license_key:
            raise ValueError("需要提供MaxMind License Key")
        
        # 构建下载URL
        download_url = f"{MAXMIND_DOWNLOAD_URL}?edition_id={MAXMIND_EDITION}&license_key={self.license_key}&suffix=zip"
        
        zip_path = os.path.join(self.data_dir, "GeoLite2-City-CSV.zip")
        
        logger.info(f"正在下载MaxMind数据...")
        
        try:
            response = requests.get(download_url, stream=True, timeout=300)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"下载完成: {zip_path}")
            
            # 解压文件
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.data_dir)
            
            logger.info(f"解压完成到: {self.data_dir}")
            
            # 查找CSV文件
            for root, dirs, files in os.walk(self.data_dir):
                for file in files:
                    if file.endswith('GeoLite2-City-Blocks-IPv4.csv'):
                        return os.path.join(root, file)
            
            raise FileNotFoundError("未找到GeoLite2-City-Blocks-IPv4.csv文件")
            
        except Exception as e:
            logger.error(f"下载MaxMind数据失败: {e}")
            raise
    
    def parse_location(self, row: Dict[str, str]) -> Dict[str, Any]:
        """
        解析位置数据
        
        Args:
            row: CSV行数据
            
        Returns:
            位置数据字典
        """
        return {
            'country_code': row.get('country_iso_code', ''),
            'country_name': row.get('country_name', ''),
            'region_code': row.get('subdivision_1_iso_code', ''),
            'region_name': row.get('subdivision_1_name', ''),
            'city_name': row.get('city_name', ''),
            'district': row.get('subdivision_2_name', ''),
            'postal_code': '',  # MaxMind在Blocks文件中
            'latitude': None,
            'longitude': None,
            'timezone': row.get('timezone', ''),
            'locale_code': row.get('locale_code', 'en'),
            'source': self.source_name
        }
    
    def parse_ip_range(self, row: Dict[str, str]) -> Tuple[str, Dict[str, Any]]:
        """
        解析IP范围数据
        
        Args:
            row: CSV行数据
            
        Returns:
            (network_cidr, location_data)
        """
        network = row.get('network', '')
        
        location_data = {
            'country_code': row.get('country_iso_code', ''),
            'country_name': row.get('country_name', ''),
            'region_code': row.get('subdivision_1_iso_code', ''),
            'region_name': row.get('subdivision_1_name', ''),
            'city_name': row.get('city_name', ''),
            'district': row.get('subdivision_2_name', ''),
            'postal_code': row.get('postal_code', ''),
            'latitude': self._parse_float(row.get('latitude')),
            'longitude': self._parse_float(row.get('longitude')),
            'timezone': row.get('timezone', ''),
            'locale_code': 'en',
            'accuracy_radius': self._parse_int(row.get('accuracy_radius')),
            'is_anonymous_proxy': row.get('is_anonymous_proxy', '0') == '1',
            'is_satellite_provider': row.get('is_satellite_provider', '0') == '1',
            'source': self.source_name
        }
        
        return network, location_data
    
    def _parse_float(self, value: str) -> float:
        """解析浮点数"""
        try:
            return float(value) if value else None
        except (ValueError, TypeError):
            return None
    
    def _parse_int(self, value: str) -> int:
        """解析整数"""
        try:
            return int(value) if value else None
        except (ValueError, TypeError):
            return None
    
    def import_data(self) -> Tuple[int, int]:
        """
        导入MaxMind数据
        
        需要同时处理Blocks和Locations两个文件
        
        Returns:
            (导入的位置数, 导入的IP范围数)
        """
        # 下载数据
        blocks_csv = self.download_data()
        
        # 查找Locations文件
        locations_csv = None
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('GeoLite2-City-Locations-en.csv'):
                    locations_csv = os.path.join(root, file)
                    break
        
        # 首先加载Locations数据到内存
        locations_map = {}
        if locations_csv:
            logger.info(f"加载Locations数据: {locations_csv}")
            with open(locations_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    geoname_id = row.get('geoname_id')
                    if geoname_id:
                        locations_map[geoname_id] = row
        
        # 然后导入Blocks数据，关联Locations
        locations_count = 0
        ip_ranges_batch = []
        ip_ranges_count = 0
        
        logger.info(f"开始导入Blocks数据: {blocks_csv}")
        
        with open(blocks_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    network = row.get('network', '')
                    if not network:
                        continue
                    
                    # 获取地理位置ID
                    geoname_id = row.get('geoname_id') or row.get('registered_country_geoname_id')
                    location_row = locations_map.get(geoname_id, {})
                    
                    # 构建位置数据
                    location_data = {
                        'country_code': location_row.get('country_iso_code', ''),
                        'country_name': location_row.get('country_name', ''),
                        'region_code': location_row.get('subdivision_1_iso_code', ''),
                        'region_name': location_row.get('subdivision_1_name', ''),
                        'city_name': location_row.get('city_name', ''),
                        'district': location_row.get('subdivision_2_name', ''),
                        'postal_code': row.get('postal_code', ''),
                        'latitude': self._parse_float(row.get('latitude')),
                        'longitude': self._parse_float(row.get('longitude')),
                        'timezone': location_row.get('timezone', ''),
                        'locale_code': 'en',
                        'accuracy_radius': self._parse_int(row.get('accuracy_radius')),
                        'is_anonymous_proxy': row.get('is_anonymous_proxy', '0') == '1',
                        'is_satellite_provider': row.get('is_satellite_provider', '0') == '1',
                        'source': self.source_name
                    }
                    
                    # 获取或创建位置
                    location_id = self.get_or_create_location(location_data)
                    if location_id:
                        locations_count += 1
                    
                    # 解析IP范围
                    from utils.ip_utils import cidr_to_range
                    start_ip, end_ip = cidr_to_range(network)
                    
                    # 准备IP范围数据
                    ip_range_tuple = (
                        network,
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
                    from config.settings import BATCH_SIZE
                    from utils.database import batch_insert_ip_ranges
                    if len(ip_ranges_batch) >= BATCH_SIZE:
                        batch_insert_ip_ranges(ip_ranges_batch, self.db.db_path)
                        ip_ranges_count += len(ip_ranges_batch)
                        ip_ranges_batch = []
                        if ip_ranges_count % 100000 == 0:
                            logger.info(f"已导入 {ip_ranges_count} 条IP范围记录")
                
                except Exception as e:
                    logger.error(f"处理行时出错: {row}, 错误: {e}")
                    continue
        
        # 插入剩余的记录
        if ip_ranges_batch:
            from utils.database import batch_insert_ip_ranges
            batch_insert_ip_ranges(ip_ranges_batch, self.db.db_path)
            ip_ranges_count += len(ip_ranges_batch)
        
        logger.info(f"MaxMind数据导入完成: {locations_count} 个位置, {ip_ranges_count} 条IP范围")
        return locations_count, ip_ranges_count


def import_maxmind_data(db_path: str, license_key: str = None) -> Tuple[int, int]:
    """
    导入MaxMind数据的便捷函数
    
    Args:
        db_path: 数据库路径
        license_key: MaxMind License Key
        
    Returns:
        (导入的位置数, 导入的IP范围数)
    """
    importer = MaxMindImporter(db_path, license_key)
    return importer.import_data()
