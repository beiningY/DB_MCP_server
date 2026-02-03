"""
SQL 安全验证器
防止 SQL 注入和恶意语句执行

该模块���供 SQL 语句的安全验证功能，确保只允许安全的 SELECT 查询执行。

主要功能：
- 检测危险关键字（DROP、DELETE、INSERT 等）
- 检测 SQL 注入模式（注释、分号注入等）
- 验证 SQL 结构（括号匹配、引号匹配）
- 严格模式检查（危险函数、语句长度、嵌套深度）

使用示例：
    from db_mcp.sql_validator import validate_sql, SQLValidationError

    try:
        is_valid, error_msg = validate_sql("SELECT * FROM users")
        if not is_valid:
            print(f"验证失败: {error_msg}")
    except SQLValidationError as e:
        print(f"验证异常: {e.message}")
"""

import re
from typing import Tuple, List


# ============================================================================
# 配置常量
# ============================================================================

# 危险的关键字（不能出现在 SELECT 查询中）
DANGEROUS_KEYWORDS = [
    "DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE", "ALTER",
    "CREATE", "GRANT", "REVOKE", "EXECUTE", "CALL", "SHOW",
    "DESCRIBE", "EXPLAIN", "HANDLER", "LOAD", "LOCK",
    "REPLACE", "INTO", "VALUES", "SET",  # 防止通过注释或其他方式注入
]

# 允许的语句开头
# WITH 支持 CTE（公用表表达式）
ALLOWED_PREFIXES = ["SELECT", "SELECT(", "WITH"]

# 需要阻止的 SQL 注入模式（正则表达式）
INJECTION_PATTERNS = [
    r";\s*\w+",           # 分号后跟命令（多语句注入）
    r"--[\r\n]",          # 单行注释后换行
    r"/\*.*\*/",          # 块注释
    r"\'\s*(OR|AND)\s*[\w']+\s*[=<>]",  # SQL 注入: ' OR '1'='1
    r'"\s*(OR|AND)\s*[\w"]+\s*[=<>]',    # SQL 注入: " OR "1"="1
]

# 允许的特殊模式（白名单，用于识别合法的 SQL 结构）
ALLOWED_PATTERNS = [
    r"\bCOUNT\s*\(",     # 聚合函数
    r"\bSUM\s*\(",
    r"\bAVG\s*\(",
    r"\bMAX\s*\(",
    r"\bMIN\s*\(",
    r"\bDISTINCT\b",
    r"\bJOIN\b",
    r"\bLEFT\s+JOIN\b",
    r"\bRIGHT\s+JOIN\b",
    r"\bINNER\s+JOIN\b",
    r"\bOUTER\s+JOIN\b",
    r"\bON\b",
    r"\bGROUP\s+BY\b",
    r"\bORDER\s+BY\b",
    r"\bHAVING\b",
    r"\bWHERE\b",
    r"\bAND\b",
    r"\bOR\b",
    r"\bNOT\b",
    r"\bIN\s*\(",
    r"\bEXISTS\b",
    r"\bBETWEEN\b",
    r"\bLIKE\b",
    r"\bIS\s+NULL\b",
    r"\bIS\s+NOT\s+NULL\b",
    r"\bAS\b",
    r"\bFROM\b",
]


# ============================================================================
# 异常类
# ============================================================================

class SQLValidationError(Exception):
    """
    SQL 验证失败异常

    当 SQL 验证失败时抛出此异常。

    Attributes:
        message: 错误消息
        code: 错误代码
    """

    def __init__(self, message: str, code: str = "SQL_VALIDATION_ERROR"):
        """
        初始化异常

        Args:
            message: 错误消息
            code: 错误代码（默认 "SQL_VALIDATION_ERROR"）
        """
        self.message = message
        self.code = code
        super().__init__(message)


# ============================================================================
# 验证函数
# ============================================================================

def normalize_sql(sql: str) -> str:
    """
    规范化 SQL：移除多余空白，标准化大小写

    Args:
        sql: 原始 SQL 语句

    Returns:
        规范化后的 SQL 语句
    """
    if not sql:
        return ""

    # 移除前后空白
    sql = sql.strip()

    # 标准化换行符
    sql = sql.replace('\r\n', '\n').replace('\r', '\n')

    return sql


def check_for_injection(sql: str) -> Tuple[bool, str]:
    """
    检查 SQL 注入模式

    检测多种常见的 SQL 注入模式，包括：
    - 多语句注入（分号）
    - 注释注入
    - 布尔注入（OR/AND 条件）

    Args:
        sql: 要检查的 SQL 语句

    Returns:
        (is_injection, error_message) 元组
        - is_injection: 是否检测到注入
        - error_message: 错误消息（如果检测到注入）
    """
    # 检查注入模式
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return True, f"检测到可能的 SQL 注入模式: {pattern}"

    # 检查危险的关键字（但需要在特定上下文中）
    sql_upper = sql.upper()
    sql_normalized = re.sub(r'\s+', ' ', sql_upper).strip()

    # 检查是否以允许的关键字开头
    allowed_start = False
    for prefix in ALLOWED_PREFIXES:
        if sql_normalized.startswith(prefix):
            allowed_start = True
            break

    if not allowed_start:
        # 尝试找到实际的第一个关键字
        match = re.match(r'^[\s(]*(\w+)', sql_normalized)
        if match:
            actual_first = match.group(1)
            return True, f"仅允许 SELECT 查询，检测到语句: {actual_first}"

    # 检查是否在非 UNION 上下文中出现危险关键字
    for keyword in DANGEROUS_KEYWORDS:
        # 使用单词边界匹配
        pattern = r'\b' + keyword + r'\b'
        matches = list(re.finditer(pattern, sql_upper))

        for match in matches:
            # 检查是否在合法上下文中
            if keyword == "SET":
                # SET 通常用于变量赋值，在 SELECT 中是危险的
                return True, f"检测到危险关键字: {keyword}"
            elif keyword in ("INTO", "VALUES"):
                # INSERT ... INTO 的关键字
                return True, f"检测到危险关键字: {keyword}"
            else:
                return True, f"检测到危险关键字: {keyword}"

    return False, ""


def check_sql_structure(sql: str) -> Tuple[bool, str]:
    """
    检查 SQL 结构是否合法

    检查括号和引号的匹配情况，以及是否包含多语句。

    Args:
        sql: 要检查的 SQL 语句

    Returns:
        (is_valid, error_message) 元组
        - is_valid: 结构是否合法
        - error_message: 错误消息（如果不合法）
    """
    # 检查括号是否匹配
    open_count = sql.count('(')
    close_count = sql.count(')')

    if open_count != close_count:
        return False, f"SQL 括号不匹配: {open_count} 个开括号，{close_count} 个闭括号"

    # 检查引号是否匹配
    # 简单检查：单引号数量应该是偶数
    if sql.count("'") % 2 != 0:
        return False, "SQL 单引号不匹配"

    # 检查是否包含多语句
    if ';' in sql and not sql.rstrip().endswith(';'):
        # 中间有分号，可能包含多语句
        return False, "检测到多语句执行（分号不在末尾）"

    return True, ""


def validate_sql(sql: str, strict_mode: bool = True) -> Tuple[bool, str]:
    """
    验证 SQL 是否安全（仅允许 SELECT 查询）

    这是主要的验证入口点，执行完整的安全检查流程：
    1. 检查 SQL 是否为空
    2. 规范化 SQL
    3. 检查 SQL 结构
    4. 检查 SQL 注入模式
    5. 严格模式下的额外检查

    Args:
        sql: 要验证的 SQL 语句
        strict_mode: 严格模式（额外的安全检查）

    Returns:
        (is_valid, error_message) 元组
        - is_valid: SQL 是否安全有效
        - error_message: 错误消息（如果验证失败）

    Examples:
        >>> is_valid, error = validate_sql("SELECT * FROM users")
        >>> assert is_valid == True

        >>> is_valid, error = validate_sql("DROP TABLE users")
        >>> assert is_valid == False
        >>> assert "危险关键字" in error
    """
    if not sql or not sql.strip():
        return False, "SQL 查询不能为空"

    # 规范化 SQL
    normalized = normalize_sql(sql)

    if not normalized:
        return False, "SQL 查询为空"

    # 检查 SQL 结构
    is_valid, error_msg = check_sql_structure(normalized)
    if not is_valid:
        return False, error_msg

    # 检查 SQL 注入
    is_injection, error_msg = check_for_injection(normalized)
    if is_injection:
        return False, error_msg

    # 严格模式下的额外检查
    if strict_mode:
        # 检查是否包含可疑的函数调用
        dangerous_functions = [
            'LOAD_FILE', 'INTO OUTFILE', 'INTO DUMPFILE',
            'SYSTEM', 'EXEC', 'EVAL', 'SHELL',
        ]
        sql_upper = normalized.upper()
        for func in dangerous_functions:
            if func in sql_upper:
                return False, f"检测到危险函数: {func}"

        # 检查是否有过长的语句（可能是攻击）
        if len(normalized) > 10000:
            return False, "SQL 语句过长（超过 10000 字符）"

        # 检查是否有嵌套过深的子查询
        depth = normalized.count('(')
        if depth > 50:
            return False, f"子查询嵌套过深（{depth} 层）"

    return True, ""


def safe_execute_sql(sql: str, validator_fn=None):
    """
    安全执行 SQL 的包装器

    先验证 SQL 安全性，然后返回验证通过的 SQL。

    Args:
        sql: 要执行的 SQL
        validator_fn: 自定义验证函数（可选）

    Returns:
        验证后的 SQL

    Raises:
        SQLValidationError: 验证失败时抛出

    Examples:
        >>> try:
        ...     safe_sql = safe_execute_sql("SELECT * FROM users")
        ... except SQLValidationError as e:
        ...     print(f"验证失败: {e.message}")
    """
    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        raise SQLValidationError(error_msg)

    if validator_fn:
        validator_fn(sql)

    return sql


# ============================================================================
# 便捷函数
# ============================================================================

def is_select_query(sql: str) -> bool:
    """
    快速检查是否是 SELECT 查询

    Args:
        sql: 要检查的 SQL 语句

    Returns:
        是否是 SELECT 查询
    """
    if not sql:
        return False
    normalized = normalize_sql(sql).upper()
    return normalized.startswith("SELECT") or normalized.startswith("WITH")


def sanitize_limit(limit: int) -> int:
    """
    确保 limit 在合理范围内

    Args:
        limit: 原始 limit 值

    Returns:
        合法范围内的 limit 值（1-10000）
    """
    if limit is None:
        return 100
    if limit <= 0:
        return 1
    if limit > 10000:
        return 10000  # 最大限制
    return limit
