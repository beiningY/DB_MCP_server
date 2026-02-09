"""
使用示例脚本

演示如何使用 db_mapping 模块进行数据库操作。
"""

from db.database import DatabaseManager, DBMappingService


def main():
    """主函数"""

    # 1. 初始化数据库管理器
    print("1. 初始化数据库管理器...")
    db_manager = DatabaseManager()
    db_manager.init_db()

    # 2. 创建数据库映射服务
    print("\n2. 创建数据库映射服务...")
    db_service = DBMappingService(db_manager)

    # 3. 创建新的数据库映射记录
    print("\n3. 创建新的数据库映射记录...")
    new_mapping = db_service.create(
        db_name="my_database",
        host="localhost",
        port=3306,
        username="root",
        password="password123",
        database="my_db",
        db_type="mysql",
        description="我的测试数据库",
        is_active=True,
    )
    print(f"   创建成功: {new_mapping}")

    # 4. 查询单条记录
    print("\n4. 根据 ID 查询记录...")
    found_mapping = db_service.get_by_id(new_mapping.id)
    print(f"   查询结果: {found_mapping}")

    # 5. 查询所有记录
    print("\n5. 查询所有记录...")
    all_mappings = db_service.get_all()
    for m in all_mappings:
        print(f"   - {m.db_name}: {m.host}:{m.port}/{m.database}")

    # 6. 更新记录
    print("\n6. 更新记录...")
    updated_mapping = db_service.update(
        id=new_mapping.id,
        description="更新后的描述"
    )
    print(f"   更新成功: {updated_mapping.description}")

    # 7. 获取字典列表
    print("\n7. 获取字典列表...")
    dict_list = db_service.to_dict_list()
    import json
    print(f"   {json.dumps(dict_list, indent=2, ensure_ascii=False)}")

    # 8. 获取映射字典（用于 server.py）
    print("\n8. 获取映射字典...")
    mapping_dict = db_service.load_to_mapping_dict()
    print(f"   {json.dumps(mapping_dict, indent=2, ensure_ascii=False)}")

    # 9. 删除记录
    print("\n9. 删除记录...")
    is_deleted = db_service.delete(new_mapping.id)
    print(f"   删除{'成功' if is_deleted else '失败'}")


if __name__ == "__main__":
    main()
