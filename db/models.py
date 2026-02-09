"""
数据库映射表模型

用于存储服务端数据库连接配置与标识符的映射关系。
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DBMapping(Base):
    """数据库连接配置映射表"""

    __tablename__ = "db_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    db_name = Column(String(128), nullable=False, comment="数据库传入显示名称")
    host = Column(String(255), nullable=False, comment="数据库主机地址")
    port = Column(Integer, nullable=False, comment="数据库端口")
    username = Column(String(128), nullable=False, comment="数据库用户名")
    password = Column(String(255), nullable=True, comment="数据库密码")
    database = Column(String(128), nullable=False, comment="数据库名")
    db_type = Column(String(32), default="mysql", comment="数据库类型：mysql/postgresql/sqlserver等")
    description = Column(String(500), nullable=True, comment="描述信息")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "db_name": self.db_name,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database": self.database,
            "db_type": self.db_type,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<DBMapping(id={self.id}, db_name='{self.db_name}', host='{self.host}:{self.port}/{self.database}')>"
