import os
import json
import datetime
from typing import List, Optional
from sqlalchemy import create_engine, inspect
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ================= 配置区域 =================
# 1. 数据库连接字符串 (示例为 MySQL)
# 格式: mysql+pymysql://user:password@host:port/dbname
DB_CONNECTION_STR = os.getenv("DB_URL", "mysql+pymysql://root:password@localhost:3306/singa_collection")

# 2. LLM 配置 (兼容 OpenAI SDK 的模型，如 DeepSeek, GPT-4, Qwen)
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-......")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1") # 如果用其他模型，请修改此处
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4-t") # 建议使用智能程度较高的模型

# 3. 提交信息配置
SUBMITTER_NAME = "Sarah"
OWNER_DEPT = "BI部门"

# ================= 数据模型定义 (Pydantic) =================
# 这些模型确保输出格式严格符合你的 JSON 要求

class ColumnMeta(BaseModel):
    column_name: str
    data_type: str
    comment: str = Field(..., description="字段中文注释，如果数据库中没有，请根据字段名推断")
    is_primary_key: bool = False
    related_table: Optional[str] = Field(None, description="推断可能关联的表名")
    related_column: Optional[str] = Field(None, description="推断可能关联的字段")
    dict_code: Optional[str] = Field(None, description="如果是枚举值，推断字典编码")
    enum_values: Optional[List[str]] = Field(None, description="可能的枚举值列表")
    is_pii: bool = Field(False, description="是否包含个人敏感信息(手机号,身份证等)")

class TableMeta(BaseModel):
    table_name: str
    table_comment: str = Field(..., description="表中文注释，如果数据库中没有，请根据表名推断")
    business_domain: str = Field(..., description="根据表名推断业务域，如: collection, marketing")
    granularity: str = Field(..., description="数据粒度，如: per_call, per_user, per_transaction")
    owner: str = Field(..., description="根据业务推断可能的归属组")
    columns: List[ColumnMeta]

# ================= 核心功能函数 =================

def get_raw_schema(engine, table_name):
    """
    使用 SQLAlchemy 获取数据库中的原始物理结构
    """
    inspector = inspect(engine)
    columns = []
    
    # 获取主键
    pk_constraint = inspector.get_pk_constraint(table_name)
    pks = pk_constraint.get('constrained_columns', [])
    
    # 获取所有列
    for col in inspector.get_columns(table_name):
        columns.append({
            "column_name": col['name'],
            "data_type": str(col['type']),
            "comment": col.get('comment', ''), # 数据库原本的注释，可能为空
            "is_primary_key": col['name'] in pks
        })
        
    return columns

def enrich_with_llm(client: OpenAI, table_name: str, raw_columns: list) -> TableMeta:
    """
    调用大模型补全语义信息
    """
    print(f"🤖正在请求 AI 补全表: {table_name} ...")
    
    prompt = f"""你是一个资深的金融科技数据架构师，熟悉信贷、催收、风控等业务。

请根据提供的数据库表结构，补全元数据信息。这是印尼的金融科技公司数据库。

## 严格要求
1. **table_comment**: 必须用中文描述表的业务含义，不能直接使用表名！例如 "360_data_test_pass" → "360金融风控测试通过订单表"
2. **business_domain**: 请先自行判断，如果不能判断的时候必须从以下选项中选择一个：
   - collection (催收)
   - marketing (营销)
   - risk (风控)
   - user (用户)
   - order (订单)
   - payment (支付)
   - finance (财务)
   - credit (征信)
   - operation (运营)
   - system (系统)
3. **granularity**: 请先自行判断，如果不能判断的时候必须从以下选项中选择：per_user, per_order, per_call, per_day, per_record
4. **columns[].comment**: 每个字段必须有中文注释，不能为空或使用字段名

## 输入
表名: {table_name}
列结构: {json.dumps(raw_columns, ensure_ascii=False)}

## 输出格式 (严格遵循)
{{
  "table_name": "{table_name}",
  "table_comment": "中文表注释（必填）",
  "business_domain": "从上述选项中选择",
  "granularity": "从上述选项中选择",
  "owner": "{OWNER_DEPT}",
  "columns": [
    {{
      "column_name": "字段名",
      "data_type": "类型",
      "comment": "中文注释（必填）",
      "is_primary_key": true/false,
      "is_pii": true/false,
      "related_table": "关联表名或null",
      "related_column": "关联字段或null"
    }}
  ]
}}

直接输出 JSON，不要 markdown 代码块。"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一个只输出 JSON 的数据助手。输出必须符合提供的 Schema 结构。"},
                {"role": "user", "content": prompt}
            ],
            # 如果你的 LLM 支持 structured output (如最新的 OpenAI)，可以开启下面这行
            # response_format={"type": "json_object"}, 
            temperature=0.1,
        )
        
        content = response.choices[0].message.content
        # 清理可能存在的 markdown 标记
        content = content.replace("```json", "").replace("```", "").strip()
        
        # 解析 JSON
        data = json.loads(content)
        
        # 处理 LLM 可能返回的嵌套结构
        # 如: {'table_metadata': {...}} 或 {'table': {...}} 或 {'result': {...}}
        if 'columns' not in data:
            # 尝试从常见的嵌套键中提取
            for key in ['table_metadata', 'table', 'result', 'data', 'metadata']:
                if key in data and isinstance(data[key], dict):
                    data = data[key]
                    break
        
        # 如果仍然没有 columns，使用原始列数据
        if 'columns' not in data:
            print(f"  ⚠️ LLM 未返回 columns，使用原始结构")
            data['columns'] = raw_columns
        
        # 补充 LLM 可能遗漏或返回无效值的字段
        data['table_name'] = table_name
        data['owner'] = data.get('owner') or OWNER_DEPT
        
        # 验证 business_domain 是否在有效列表中
        valid_domains = ['collection', 'marketing', 'risk', 'user', 'order', 'payment', 'finance', 'credit', 'operation', 'system']
        bd = data.get('business_domain', '').lower().strip()
        if bd not in valid_domains:
            # 尝试从返回值中提取关键词
            for domain in valid_domains:
                if domain in bd:
                    bd = domain
                    break
            else:
                bd = 'operation'  # 默认为运营
        data['business_domain'] = bd
        
        # 验证 granularity
        valid_granularities = ['per_user', 'per_order', 'per_call', 'per_day', 'per_record']
        gran = data.get('granularity', '').lower().strip()
        if gran not in valid_granularities:
            data['granularity'] = 'per_record'
        
        # 验证 table_comment 不能为空或等于表名
        tc = data.get('table_comment', '').strip()
        if not tc or tc == table_name or tc.lower() == table_name.lower():
            # 尝试生成一个基本的描述
            data['table_comment'] = f"{table_name} 业务数据表"
        
        # 确保 columns 中的每个字段都有必要的属性
        for col in data.get('columns', []):
            col_name = col.get('column_name') or col.get('name', '')
            col['column_name'] = col_name
            col['data_type'] = col.get('data_type') or col.get('type', 'unknown')
            
            # 验证 comment 不能为空或等于字段名
            comment = col.get('comment', '').strip()
            if not comment or comment == col_name or comment.lower() == col_name.lower():
                col['comment'] = col_name  # 至少保留字段名
            
            col.setdefault('is_primary_key', False)
        
        # 确保 LLM 返回的数据补全了 columns 里的内容
        return TableMeta(**data)

    except Exception as e:
        print(f"⚠️ AI 处理表 {table_name} 失败: {e}")
        # 如果 AI 失败，返回一个保底的基础结构
        fallback_columns = []
        for c in raw_columns:
            col_data = {
                'column_name': c.get('column_name', ''),
                'data_type': c.get('data_type', 'unknown'),
                'comment': c.get('comment') or c.get('column_name', ''),
                'is_primary_key': c.get('is_primary_key', False),
            }
            fallback_columns.append(ColumnMeta(**col_data))
        
        return TableMeta(
            table_name=table_name,
            table_comment=f"{table_name} (AI解析失败)",
            business_domain="unknown",
            granularity="unknown",
            owner=OWNER_DEPT,
            columns=fallback_columns
        )

# ================= 主程序 =================

def main():
    # 1. 连接数据库
    try:
        engine = create_engine(DB_CONNECTION_STR)
        connection = engine.connect()
        inspector = inspect(engine)
        db_name = engine.url.database
        print(f"✅ 成功连接数据库: {db_name}")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return

    # 2. 初始化 LLM 客户端
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    # 3. 获取所有表名
    all_tables = inspector.get_table_names()
    
    # 限制处理的表数量（用于测试），设为 None 表示处理全部
    MAX_TABLES = None  # 改为 None 处理全部表
    
    tables_to_process = all_tables[:MAX_TABLES] if MAX_TABLES else all_tables
    print(f"📊 发现 {len(all_tables)} 张表，本次处理 {len(tables_to_process)} 张...")

    processed_tables = []

    # 4. 遍历处理每张表
    for i, table_name in enumerate(tables_to_process, 1):
        print(f"\n[{i}/{len(tables_to_process)}] 处理表: {table_name}")
        # 4.1 获取物理结构
        raw_columns = get_raw_schema(engine, table_name)
        
        # 4.2 调用 LLM 进行增强
        # 提示：如果表非常多，建议在这里加个 sleep 或者进度条
        table_meta = enrich_with_llm(client, table_name, raw_columns)
        
        # 转为字典
        table_dict = table_meta.model_dump(exclude_none=True)
        processed_tables.append(table_dict)
        
        # 打印处理结果
        print(f"  ✓ 业务域: {table_dict.get('business_domain')}")
        print(f"  ✓ 注释: {table_dict.get('table_comment')}")
        print(f"  ✓ 字段数: {len(table_dict.get('columns', []))}")

    # 5. 组装最终 JSON
    final_output = {
        "database": db_name,
        "owner": OWNER_DEPT,
        "submitted_by": SUBMITTER_NAME,
        "submitted_at": datetime.datetime.now().strftime("%Y-%m-%d"),
        "tables": processed_tables
    }

    # 打印完整输出预览
    print("\n" + "=" * 60)
    print("📄 生成的元数据预览:")
    print("=" * 60)
    print(json.dumps(final_output, ensure_ascii=False, indent=2))
    print("=" * 60)

    # 6. 保存文件
    filename = f"../metadata/{db_name}_metadata.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 处理完成！文件已保存为: {filename}")

if __name__ == "__main__":
    main()