"""
MCP Tools - 数据分析工具定义
"""


def invoke_data_agent(query: str) -> str:
    """
    调用数据分析 Agent 处理用户查询
    
    Args:
        query: 用户的数据分析问题
    
    Returns:
        Agent 的回复内容
    """
    try:
        from agent.data_simple_agent import get_agent
        
        agent = get_agent()
        result = agent.invoke({
            "messages": [{"role": "user", "content": query}]
        })
        
        # 提取最终回复
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content:
                    return msg.content
                elif isinstance(msg, dict) and msg.get("content"):
                    return msg["content"]
        
        return str(result)
    
    except Exception as e:
        return f"Agent 调用失败: {str(e)}"


def register_tools(mcp):
    """
    注册 MCP 工具到服务器
    
    Args:
        mcp: FastMCP 实例
    """
    
    @mcp.tool()
    async def ask_data_agent(query: str) -> str:
        """
        数据分析智能体 - 可以回答数据分析相关问题
        
        功能：
        - 理解自然语言的数据分析需求
        - 自动查询数据库表结构
        - 搜索历史 SQL 和业务知识
        - 生成并执行 SQL 查询
        - 整理分析结果
        
        Args:
            query: 用户的数据分析问题或查询需求
        
        适用场景：
        - 数据查询："查询最近7天的订单数量"
        - 指标分析："计算用户留存率"
        - 业务问题："还款率是如何计算的"
        - 数据探索："有哪些用户相关的表"
        """
        if not query:
            return "错误：查询内容不能为空"
        
        return invoke_data_agent(query)
