"""
数据库操作模块

提供数据库连接和表管理功能。
"""

import os
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .models import Base, DBMapping

# 加载环境变量
load_dotenv()


class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        """初始化数据库管理器，从环境变量读取配置"""
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()

    def _initialize_engine(self):
        """初���化数据库引擎"""
        db_host = os.getenv("DB_host", "localhost")
        db_port = int(os.getenv("DB_port", "3306"))
        db_username = os.getenv("DB_username", "root")
        db_password = os.getenv("DB_password", "")
        db_name = os.getenv("DB_name", "mcp_server")

        # 构建 URL
        from urllib.parse import quote_plus
        safe_password = quote_plus(db_password, safe='')
        database_url = f"mysql+pymysql://{db_username}:{safe_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"

        self.engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)
        print("数据库表创建成功")

    def drop_tables(self):
        """删除所有表"""
        Base.metadata.drop_all(bind=self.engine)
        print("数据库表删除成功")

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    def init_db(self):
        """初始化数据库（创建表）"""
        self.create_tables()


# ============================================================================
# 数据库映射表操作
# ============================================================================

class DBMappingService:
    """数据库映射表服务"""

    def __init__(self, db_manager: DatabaseManager = None):
        """初始化服务

        Args:
            db_manager: 数据库管理器实例，为空则创建默认实例
        """
        if db_manager is None:
            db_manager = DatabaseManager()
        self.db_manager = db_manager

    def create(
        self,
        db_name: str,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        db_type: str = "mysql",
        description: Optional[str] = None,
        is_active: bool = True,
    ) -> DBMapping:
        """创建数据库映射记录

        Args:
            db_name: 数据库显示名称
            host: 数据库主机地址
            port: 数据库端口
            username: 数据库用户名
            password: 数据库密码
            database: 数据库名
            db_type: 数据库类型
            description: 描述信息
            is_active: 是否启用

        Returns:
            创建的 DBMapping 对象
        """
        session = self.db_manager.get_session()
        try:
            mapping = DBMapping(
                db_name=db_name,
                host=host,
                port=port,
                username=username,
                password=password,
                database=database,
                db_type=db_type,
                description=description,
                is_active=is_active,
            )
            session.add(mapping)
            session.commit()
            session.refresh(mapping)
            return mapping
        except SQLAlchemyError as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_by_id(self, id: int) -> Optional[DBMapping]:
        """根据ID获取记录

        Args:
            id: 记录ID

        Returns:
            DBMapping 对象或 None
        """
        session = self.db_manager.get_session()
        try:
            return session.query(DBMapping).filter(DBMapping.id == id).first()
        finally:
            session.close()

    def get_all(self, active_only: bool = False) -> List[DBMapping]:
        """获取所有记录

        Args:
            active_only: 是否只获取启用的记录

        Returns:
            DBMapping 对象列表
        """
        session = self.db_manager.get_session()
        try:
            query = session.query(DBMapping)
            if active_only:
                query = query.filter(DBMapping.is_active == True)
            return query.order_by(DBMapping.id).all()
        finally:
            session.close()

    def get_by_db_name(self, db_name: str) -> Optional[DBMapping]:
        """根据数据库名获取记录

        Args:
            db_name: 数据库显示名称

        Returns:
            DBMapping 对象或 None
        """
        session = self.db_manager.get_session()
        try:
            return session.query(DBMapping).filter(DBMapping.db_name == db_name).first()
        finally:
            session.close()

    def update(
        self,
        id: int,
        db_name: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        db_type: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[DBMapping]:
        """更新记录

        Args:
            id: 记录ID
            其他参数为可选的更新字段

        Returns:
            更新后的 DBMapping 对象或 None
        """
        session = self.db_manager.get_session()
        try:
            mapping = session.query(DBMapping).filter(DBMapping.id == id).first()
            if mapping is None:
                return None

            if db_name is not None:
                mapping.db_name = db_name
            if host is not None:
                mapping.host = host
            if port is not None:
                mapping.port = port
            if username is not None:
                mapping.username = username
            if password is not None:
                mapping.password = password
            if database is not None:
                mapping.database = database
            if db_type is not None:
                mapping.db_type = db_type
            if description is not None:
                mapping.description = description
            if is_active is not None:
                mapping.is_active = is_active

            session.commit()
            session.refresh(mapping)
            return mapping
        except SQLAlchemyError as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete(self, id: int) -> bool:
        """删除记录

        Args:
            id: 记录ID

        Returns:
            是否删除成功
        """
        session = self.db_manager.get_session()
        try:
            mapping = session.query(DBMapping).filter(DBMapping.id == id).first()
            if mapping is None:
                return False
            session.delete(mapping)
            session.commit()
            return True
        except SQLAlchemyError as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def to_dict_list(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """获取所有记录的字典列表

        Args:
            active_only: 是否只获取启用的记录

        Returns:
            字典列表
        """
        mappings = self.get_all(active_only=active_only)
        return [m.to_dict() for m in mappings]

    def load_to_mapping_dict(self) -> Dict[str, Dict[str, Any]]:
        """加载所有启用的数据库映射为字典格式

        返回格式：
        {
            "db_name_1": {"host": "...", "port": 3306, ...},
            "db_name_2": {"host": "...", "port": 3306, ...},
        }

        Returns:
            数据库映射字典
        """
        mappings = self.get_all(active_only=True)
        result = {}
        for m in mappings:
            result[m.db_name] = {
                "host": m.host,
                "port": m.port,
                "username": m.username,
                "password": m.password,
                "database": m.database,
            }
        return result
