#!/usr/bin/env python3
"""
IP定位准确性测试器
用于验证IP归属的准确性
"""
import sys
import os
import random
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ip_utils import ip_to_int, int_to_ip, is_valid_ip
from utils.database import (
    get_db_manager, query_ip_location, update_validation_summary, 
    DATABASE_PATH
)
from validator.node_client import ValidatorNodeManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AccuracyTester:
    """IP定位准确性测试器"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db = get_db_manager(db_path)
        self.node_manager = ValidatorNodeManager()
    
    def get_test_ips(self, country_code: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取用于测试的IP样本
        
        Args:
            country_code: 国家代码过滤
            limit: 样本数量
            
        Returns:
            IP样本列表
        """
        if country_code:
            sql = '''
                SELECT r.id as range_id, r.network, r.start_ip, r.end_ip,
                       l.country_code, l.country_name, l.region_code, l.region_name, l.city_name
                FROM ip_ranges r
                JOIN locations l ON r.location_id = l.id
                WHERE l.country_code = ?
                ORDER BY RANDOM()
                LIMIT ?
            '''
            params = (country_code, limit)
        else:
            sql = '''
                SELECT r.id as range_id, r.network, r.start_ip, r.end_ip,
                       l.country_code, l.country_name, l.region_code, l.region_name, l.city_name
                FROM ip_ranges r
                JOIN locations l ON r.location_id = l.id
                ORDER BY RANDOM()
                LIMIT ?
            '''
            params = (limit,)
        
        return self.db.fetchall(sql, params)
    
    def generate_test_ip(self, start_ip: int, end_ip: int) -> str:
        """
        在IP范围内生成一个测试IP
        
        Args:
            start_ip: 起始IP整数
            end_ip: 结束IP整数
            
        Returns:
            IP地址字符串
        """
        # 随机选择IP范围内的地址
        test_ip_int = random.randint(start_ip, end_ip)
        return int_to_ip(test_ip_int)
    
    def cross_validate_ip(self, ip: str, expected_country: str) -> Dict[str, Any]:
        """
        交叉验证IP地址
        
        使用多个验证节点测试IP，判断归属是否准确
        
        Args:
            ip: 测试IP
            expected_country: 预期的国家代码
            
        Returns:
            验证结果
        """
        # 获取所有节点的验证结果
        validation_results = self.node_manager.validate_ip_from_all_nodes(ip)
        
        # 分析结果
        node_count = len(validation_results.get('nodes', {}))
        reachable_count = 0
        
        for node_name, result in validation_results.get('nodes', {}).items():
            if 'error' in result:
                continue
            
            tests = result.get('tests', {})
            ping_result = tests.get('ping', {})
            
            if ping_result.get('success'):
                reachable_count += 1
        
        # 判断准确性
        # 如果IP可达，说明IP是活跃的，归属信息更可能是准确的
        is_accurate = reachable_count > 0
        
        return {
            "ip": ip,
            "expected_country": expected_country,
            "node_count": node_count,
            "reachable_count": reachable_count,
            "is_accurate": is_accurate,
            "validation_details": validation_results,
            "tested_at": datetime.now().isoformat()
        }
    
    def test_ip_range(self, range_id: int, test_count: int = 5) -> Dict[str, Any]:
        """
        测试一个IP范围
        
        Args:
            range_id: IP范围ID
            test_count: 测试IP数量
            
        Returns:
            测试结果
        """
        # 获取IP范围信息
        range_info = self.db.fetchone(
            '''SELECT r.*, l.country_code, l.region_code 
               FROM ip_ranges r 
               JOIN locations l ON r.location_id = l.id 
               WHERE r.id = ?''',
            (range_id,)
        )
        
        if not range_info:
            return {"error": "IP范围不存在"}
        
        # 生成测试IP
        test_ips = []
        for _ in range(test_count):
            test_ip = self.generate_test_ip(range_info['start_ip'], range_info['end_ip'])
            test_ips.append(test_ip)
        
        # 测试每个IP
        results = []
        accurate_count = 0
        
        for test_ip in test_ips:
            result = self.cross_validate_ip(test_ip, range_info['country_code'])
            results.append(result)
            if result.get('is_accurate'):
                accurate_count += 1
        
        # 计算准确率
        accuracy_rate = accurate_count / len(test_ips) if test_ips else 0
        
        return {
            "range_id": range_id,
            "network": range_info['network'],
            "country_code": range_info['country_code'],
            "region_code": range_info['region_code'],
            "test_ips": test_ips,
            "results": results,
            "accuracy_rate": accuracy_rate,
            "is_range_accurate": accuracy_rate >= 0.5,  # 50%以上IP可达则认为范围准确
            "tested_at": datetime.now().isoformat()
        }
    
    def run_batch_validation(self, country_code: str = None, sample_size: int = 100) -> Dict[str, Any]:
        """
        运行批量验证
        
        Args:
            country_code: 国家代码过滤
            sample_size: 样本大小
            
        Returns:
            批量验证结果
        """
        logger.info(f"开始批量验证: country={country_code}, sample_size={sample_size}")
        
        # 获取测试样本
        test_samples = self.get_test_ips(country_code, sample_size)
        logger.info(f"获取到 {len(test_samples)} 个测试样本")
        
        results = {
            "total_samples": len(test_samples),
            "tested": 0,
            "accurate": 0,
            "inaccurate": 0,
            "details": []
        }
        
        for sample in test_samples:
            try:
                # 生成测试IP
                test_ip = self.generate_test_ip(sample['start_ip'], sample['end_ip'])
                
                # 验证IP
                validation_result = self.cross_validate_ip(test_ip, sample['country_code'])
                
                # 记录结果
                is_accurate = validation_result.get('is_accurate', False)
                
                # 保存验证记录到数据库
                self._save_validation_record(
                    sample['range_id'],
                    test_ip,
                    sample['country_code'],
                    is_accurate
                )
                
                # 更新统计
                results['tested'] += 1
                if is_accurate:
                    results['accurate'] += 1
                else:
                    results['inaccurate'] += 1
                
                results['details'].append({
                    "range_id": sample['range_id'],
                    "network": sample['network'],
                    "test_ip": test_ip,
                    "expected_country": sample['country_code'],
                    "is_accurate": is_accurate
                })
                
                if results['tested'] % 10 == 0:
                    logger.info(f"已测试 {results['tested']}/{len(test_samples)}...")
                
            except Exception as e:
                logger.error(f"测试样本时出错: {sample}, 错误: {e}")
                continue
        
        # 计算准确率
        if results['tested'] > 0:
            results['accuracy_rate'] = results['accurate'] / results['tested']
        
        logger.info(f"批量验证完成: 测试{results['tested']}个, 准确{results['accurate']}个, 准确率{results.get('accuracy_rate', 0):.2%}")
        
        return results
    
    def _save_validation_record(self, range_id: int, test_ip: str, 
                                expected_country: str, is_accurate: bool):
        """保存验证记录到数据库"""
        try:
            sql = '''
                INSERT INTO validations 
                (ip_range_id, validator_node, test_ip, expected_country, is_accurate, test_method)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            self.db.execute(sql, (range_id, 'batch_validator', test_ip, expected_country, is_accurate, 'cross_validate'))
            
            # 更新汇总统计
            # 先获取range对应的国家和区域
            range_info = self.db.fetchone(
                'SELECT l.country_code, l.region_code FROM ip_ranges r JOIN locations l ON r.location_id = l.id WHERE r.id = ?',
                (range_id,)
            )
            if range_info:
                update_validation_summary(
                    range_info['country_code'],
                    range_info['region_code'],
                    is_accurate,
                    self.db.db_path
                )
        
        except Exception as e:
            logger.error(f"保存验证记录失败: {e}")
    
    def get_accuracy_report(self, country_code: str = None) -> Dict[str, Any]:
        """
        获取准确性报告
        
        Args:
            country_code: 国家代码过滤
            
        Returns:
            准确性报告
        """
        if country_code:
            # 特定国家的报告
            summary = self.db.fetchall(
                'SELECT * FROM validation_summary WHERE country_code = ?',
                (country_code,)
            )
            
            total_tests = sum(s['total_tests'] for s in summary)
            total_accurate = sum(s['accurate_tests'] for s in summary)
            
        else:
            # 全局报告
            summary = self.db.fetchall('SELECT * FROM validation_summary ORDER BY accuracy_rate ASC')
            
            total_result = self.db.fetchone('''
                SELECT SUM(total_tests) as total, SUM(accurate_tests) as accurate
                FROM validation_summary
            ''')
            total_tests = total_result['total'] or 0
            total_accurate = total_result['accurate'] or 0
        
        overall_rate = total_accurate / total_tests if total_tests > 0 else 0
        
        return {
            "overall": {
                "total_tests": total_tests,
                "accurate_tests": total_accurate,
                "accuracy_rate": overall_rate
            },
            "by_region": [
                {
                    "country_code": s['country_code'],
                    "region_code": s['region_code'],
                    "total_tests": s['total_tests'],
                    "accurate_tests": s['accurate_tests'],
                    "accuracy_rate": s['accuracy_rate'],
                    "last_tested_at": s['last_tested_at']
                } for s in summary
            ],
            "generated_at": datetime.now().isoformat()
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='IP定位准确性测试器')
    parser.add_argument('--action', choices=['test', 'batch', 'report'], 
                       default='report', help='操作类型')
    parser.add_argument('--range-id', type=int, help='IP范围ID')
    parser.add_argument('--ip', help='测试IP地址')
    parser.add_argument('--country', help='国家代码')
    parser.add_argument('--sample-size', type=int, default=100, help='样本大小')
    
    args = parser.parse_args()
    
    tester = AccuracyTester()
    
    if args.action == 'test':
        if args.range_id:
            result = tester.test_ip_range(args.range_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.ip:
            result = tester.cross_validate_ip(args.ip, args.country or 'CN')
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("请提供 --range-id 或 --ip 参数")
    
    elif args.action == 'batch':
        result = tester.run_batch_validation(args.country, args.sample_size)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.action == 'report':
        result = tester.get_accuracy_report(args.country)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
