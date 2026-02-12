"""
数据库初始化脚本

用于创建表和插入示例数据。
"""

import os
import logging
from dotenv import load_dotenv

from db.database import DatabaseManager, DBMappingService

# 导入埋点模型，确保 create_tables() 会创建埋点表
# 即使不使用埋点功能，也需要导入以创建表结构
try:
    from db.analytics_models import (
        AgentExecutionLog,
        ToolCallLog,
        SQLQueryLog,
        UserSessionLog,
        KnowledgeGraphLog,
        ErrorLog
    )
    _analytics_available = True
except ImportError as e:
    _analytics_available = False

# 加载环境变量
load_dotenv()

# 获取日志器
logger = logging.getLogger("db.init_db")


def init_database():
    """初始化数据库（创建表）"""
    logger.info("正在初始化数据库...")
    db_manager = DatabaseManager()
    db_manager.create_tables()
    logger.info("数据库初始化完成！")


def drop_database():
    """删除数据库表"""
    logger.info("正在删除数据库表...")
    db_manager = DatabaseManager()
    db_manager.drop_tables()
    logger.info("数据库表删除完成！")


def insert_data():
    """插入数据"""
    logger.info("正在插入数据...")

    db_service = DBMappingService()

    data = [
        {
            "db_name": "sg-pay",
            "host": "8.222.32.115",
            "port": 30006,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "sg-pay",
            "db_type": "mysql",
            "description": "sg-pay数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_financial_pay",
            "host": "8.222.32.115",
            "port": 30006,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "dev_db",
            "db_type": "mysql",
            "description": "singa_financial_pay数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_lender",
            "host": "8.222.32.115",
            "port": 30005,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_lender",
            "db_type": "mysql",
            "description": "singa_lender数据库",
            "is_active": True,
        },
        {
            "db_name": "singa",
            "host": "8.222.32.115",
            "port": 30002,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa",
            "db_type": "mysql",
            "description": "singa数据库",
            "is_active": True,
        },
        {
            "db_name": "rc",
            "host": "8.222.32.115",
            "port": 30002,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "rc",
            "db_type": "mysql",
            "description": "rc数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_user",
            "host": "8.222.32.115",
            "port": 30002,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_user",
            "db_type": "mysql",
            "description": "singa_user数据库",
            "is_active": True,
        },
        {
            "db_name": "sg-order",
            "host": "8.222.32.115",
            "port": 30001,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "sg-order",
            "db_type": "mysql",
            "description": "sg-order数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_data",
            "host": "8.222.32.115",
            "port": 30004,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_data",
            "db_type": "mysql",
            "description": "singa_data数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_fenqi",
            "host": "8.222.32.115",
            "port": 30004,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "sg-fenqi",
            "db_type": "mysql",
            "description": "sg-fenqi数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_global",
            "host": "8.222.32.115",
            "port": 30004,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_global",
            "db_type": "mysql",
            "description": "singa_global数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_opt",
            "host": "8.222.32.115",
            "port": 30004,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "sg-opt",
            "db_type": "mysql",
            "description": "sg-opt数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_risk",
            "host": "8.222.32.115",
            "port": 30004,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_risk",
            "db_type": "mysql",
            "description": "singa_risk数据库",
            "is_active": True,
        },
        {
            "db_name": "dataservices",
            "host": "8.222.32.115",
            "port": 30013,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "dataservices",
            "db_type": "mysql",
            "description": "dataservices数据库",
            "is_active": True,
        },
        {
            "db_name": "infoservice",
            "host": "8.222.32.115",
            "port": 30013,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "infoservice",
            "db_type": "mysql",
            "description": "infoservice数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_api_ng",
            "host": "8.222.32.115",
            "port": 30008,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_api_ng",
            "db_type": "mysql",
            "description": "singa_api_ng数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_opt_ng",
            "host": "8.222.32.115",
            "port": 30008,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_opt_ng",
            "db_type": "mysql",
            "description": "singa_opt_ng数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_rc_ng",
            "host": "8.222.32.115",
            "port": 30008,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_rc_ng",
            "db_type": "mysql",
            "description": "singa_rc_ng数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_user_ng",
            "host": "8.222.32.115",
            "port": 30008,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_user_ng",
            "db_type": "mysql",
            "description": "singa_user_ng数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_data_ng",
            "host": "8.222.32.115",
            "port": 30008,
            "username": "dev_user",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_data_ng",
            "db_type": "mysql",
            "description": "singa_data_ng数据库",
            "is_active": True,
        },        {
            "db_name": "singa_order_ng",
            "host": "8.222.32.115",
            "port": 30009,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_order_ng",
            "db_type": "mysql",
            "description": "singa_order_ng数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_pay_ng",
            "host": "8.222.32.115",
            "port": 30009,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_pay_ng",
            "db_type": "mysql",
            "description": "singa_pay_ng数据库",
            "is_active": True,
        },        {
            "db_name": "singa_dataservices_ng",
            "host": "8.222.32.115",
            "port": 30010,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_dataservices_ng",
            "db_type": "mysql",
            "description": "singa_dataservices_ng数据库",
            "is_active": True,
        },
        {
            "db_name": "singa_infoservices_ng",
            "host": "8.222.32.115",
            "port": 30010,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "singa_infoservices_ng",
            "db_type": "mysql",
            "description": "singa_infoservices_ng数据库",
            "is_active": True,
        },        {
            "db_name": "marketing",
            "host": "marketing.rwlb.ap-southeast-5.rds.aliyuncs.com",
            "port": 3306,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "marketing",
            "db_type": "mysql",
            "description": "marketing数据库",
            "is_active": True,
        },
        {
            "db_name": "collection-v2",
            "host": "8.222.32.115",
            "port": 30007,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "collection-v2",
            "db_type": "mysql",
            "description": "collection-v2数据库",
            "is_active": True,
        },        {
            "db_name": "customer_service",
            "host": "rm-d9jg33rj4121pwh7h6o.mysql.ap-southeast-5.rds.aliyuncs.com",
            "port": 3306,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "customer_service",
            "db_type": "mysql",
            "description": "customer_service数据库",
            "is_active": True,
        },
        {
            "db_name": "colleciton_ng",
            "host": "8.222.32.115",
            "port": 30011,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "colleciton_ng",
            "db_type": "mysql",
            "description": "colleciton_ng数据库",
            "is_active": True,
        },        {
            "db_name": "marketing_ng",
            "host": "8.222.32.115",
            "port": 30011,
            "username": "ai_project",
            "password": "I3fgVv6e3MSO7xV95vhu",
            "database": "marketing_ng",
            "db_type": "mysql",
            "description": "marketing_ng数据库",
            "is_active": True,
        }
    ]

    for data in data:
        try:
            mapping = db_service.create(**data)
            logger.info(f"创建映射: {mapping.db_name} -> {mapping.host}:{mapping.port}/{mapping.database}")
        except Exception as e:
            logger.error(f"创建映射失败: {data['db_name']} - {e}")

    logger.info("数据插入完成！")


def query_all_data():
    """查询并显示所有数据"""
    logger.info("当前数据库映射记录：")

    db_service = DBMappingService()
    mappings = db_service.get_all()

    if not mappings:
        logger.info("（无记录）")
        return

    for m in mappings:
        status = "启用" if m.is_active else "禁用"
        logger.info(f"ID: {m.id}, 名称: {m.db_name} ({status}), 连接: {m.username}@{m.host}:{m.port}/{m.database}")


def get_mapping_dict():
    """获���数据库映射字典（用于 server.py）"""
    db_service = DBMappingService()
    mapping_dict = db_service.load_to_mapping_dict()
    logger.info(f"数据库映射字典: {len(mapping_dict)} 条")
    import json
    logger.debug(json.dumps(mapping_dict, indent=2, ensure_ascii=False))
    return mapping_dict


if __name__ == "__main__":
    import sys

    # 配置基本日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "init":
            init_database()
        elif command == "drop":
            drop_database()
        elif command == "data":
            insert_data()
        elif command == "query":
            query_all_data()
        elif command == "mapping":
            get_mapping_dict()
        elif command == "all":
            init_database()
            insert_data()
            query_all_data()
        else:
            logger.error("未知命令")
            logger.info("用法:")
            logger.info("  python init_db.py init    - 创建表")
            logger.info("  python init_db.py drop    - 删除表")
            logger.info("  python init_db.py data    - 插入数据")
            logger.info("  python init_db.py query   - 查询所有数据")
            logger.info("  python init_db.py mapping - 获取映射字典")
            logger.info("  python init_db.py all     - 初始化并插入示例数据")
    else:
        logger.info("用法:")
        logger.info("  python init_db.py init    - 创建表")
        logger.info("  python init_db.py drop    - 删除表")
        logger.info("  python init_db.py data    - 插入数据")
        logger.info("  python init_db.py query   - 查询所有数据")
        logger.info("  python init_db.py mapping - 获取映射字典")
        logger.info("  python init_db.py all     - 初始化并插入示例数据")
