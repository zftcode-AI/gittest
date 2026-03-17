#!/usr/bin/env python3
"""
验证任务调度器
用于定期执行IP定位准确性验证
"""
import sys
import os
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validator.accuracy_tester import AccuracyTester
from config.settings import VALIDATION_INTERVAL_HOURS, VALIDATION_BATCH_SIZE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValidationScheduler:
    """验证任务调度器"""
    
    def __init__(self):
        self.tester = AccuracyTester()
        self.running = False
        self.thread = None
        self.interval_hours = VALIDATION_INTERVAL_HOURS
        self.batch_size = VALIDATION_BATCH_SIZE
        self.last_run_time = None
        self.next_run_time = None
    
    def run_validation_job(self, country_code: str = None):
        """
        执行验证任务
        
        Args:
            country_code: 指定国家代码，None则验证所有国家
        """
        logger.info(f"开始执行验证任务: country={country_code}")
        
        try:
            result = self.tester.run_batch_validation(
                country_code=country_code,
                sample_size=self.batch_size
            )
            
            logger.info(f"验证任务完成: 测试{result['tested']}个样本, 准确率{result.get('accuracy_rate', 0):.2%}")
            
            self.last_run_time = datetime.now()
            self.next_run_time = self.last_run_time + timedelta(hours=self.interval_hours)
            
            return result
        
        except Exception as e:
            logger.error(f"验证任务执行失败: {e}")
            return None
    
    def run_continuous(self):
        """持续运行调度器"""
        logger.info(f"启动验证调度器，间隔: {self.interval_hours}小时")
        
        self.running = True
        
        while self.running:
            try:
                # 执行验证任务
                self.run_validation_job()
                
                # 等待下一次执行
                if self.running:
                    logger.info(f"下次验证时间: {self.next_run_time}")
                    
                    # 分段睡眠，便于及时响应停止命令
                    sleep_interval = 60  # 每分钟检查一次
                    total_sleep = self.interval_hours * 3600
                    slept = 0
                    
                    while self.running and slept < total_sleep:
                        time.sleep(sleep_interval)
                        slept += sleep_interval
            
            except Exception as e:
                logger.error(f"调度器运行时出错: {e}")
                time.sleep(300)  # 出错后等待5分钟再试
        
        logger.info("验证调度器已停止")
    
    def start(self):
        """启动调度器（后台线程）"""
        if self.thread and self.thread.is_alive():
            logger.warning("调度器已在运行")
            return
        
        self.thread = threading.Thread(target=self.run_continuous)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info("验证调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("验证调度器停止命令已发送")
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            "running": self.running,
            "interval_hours": self.interval_hours,
            "batch_size": self.batch_size,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "next_run_time": self.next_run_time.isoformat() if self.next_run_time else None
        }


class ValidationJob:
    """单次验证任务"""
    
    def __init__(self, tester: AccuracyTester = None):
        self.tester = tester or AccuracyTester()
    
    def validate_by_country(self, country_code: str, sample_size: int = 100) -> dict:
        """
        按国家验证
        
        Args:
            country_code: 国家代码
            sample_size: 样本大小
            
        Returns:
            验证结果
        """
        logger.info(f"执行国家验证任务: {country_code}, 样本数: {sample_size}")
        return self.tester.run_batch_validation(country_code, sample_size)
    
    def validate_all_countries(self, sample_size_per_country: int = 50) -> dict:
        """
        验证所有国家
        
        Args:
            sample_size_per_country: 每个国家的样本数
            
        Returns:
            验证结果汇总
        """
        from utils.database import get_db_manager
        from config.settings import DATABASE_PATH
        
        db = get_db_manager(DATABASE_PATH)
        
        # 获取所有国家
        countries = db.fetchall('''
            SELECT DISTINCT country_code 
            FROM locations 
            WHERE country_code IS NOT NULL AND country_code != ''
            ORDER BY country_code
        ''')
        
        results = {
            "total_countries": len(countries),
            "tested_countries": 0,
            "total_samples": 0,
            "total_accurate": 0,
            "details": []
        }
        
        for country in countries:
            country_code = country['country_code']
            
            try:
                result = self.validate_by_country(country_code, sample_size_per_country)
                
                results['tested_countries'] += 1
                results['total_samples'] += result['tested']
                results['total_accurate'] += result['accurate']
                results['details'].append({
                    "country_code": country_code,
                    "result": result
                })
                
                logger.info(f"国家 {country_code} 验证完成: {result['accuracy_rate']:.2%}")
                
            except Exception as e:
                logger.error(f"验证国家 {country_code} 时出错: {e}")
                continue
        
        # 计算总体准确率
        if results['total_samples'] > 0:
            results['overall_accuracy_rate'] = results['total_accurate'] / results['total_samples']
        
        return results
    
    def generate_report(self) -> dict:
        """生成验证报告"""
        return self.tester.get_accuracy_report()


def run_scheduler():
    """运行调度器（阻塞）"""
    scheduler = ValidationScheduler()
    
    try:
        scheduler.run_continuous()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
        scheduler.stop()


def run_once(country_code: str = None, sample_size: int = 100):
    """运行一次验证任务"""
    job = ValidationJob()
    result = job.validate_by_country(country_code, sample_size)
    return result


def run_all_countries(sample_size_per_country: int = 50):
    """验证所有国家"""
    job = ValidationJob()
    result = job.validate_all_countries(sample_size_per_country)
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='IP验证任务调度器')
    parser.add_argument('--mode', choices=['scheduler', 'once', 'all-countries'], 
                       default='once', help='运行模式')
    parser.add_argument('--country', help='国家代码')
    parser.add_argument('--sample-size', type=int, default=100, help='样本大小')
    parser.add_argument('--interval', type=int, default=24, help='调度间隔(小时)')
    
    args = parser.parse_args()
    
    if args.mode == 'scheduler':
        scheduler = ValidationScheduler()
        scheduler.interval_hours = args.interval
        
        try:
            scheduler.run_continuous()
        except KeyboardInterrupt:
            print("\n停止调度器...")
            scheduler.stop()
    
    elif args.mode == 'once':
        result = run_once(args.country, args.sample_size)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.mode == 'all-countries':
        result = run_all_countries(args.sample_size)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
