# prompts/kg_extract_prompt.py
from typing import Optional
from prompts import YA_MCPServer_Prompt


@YA_MCPServer_Prompt(
    name="extract_knowledge_from_ppt",
    title="Extract Knowledge from PPT",
    description="从AI导论课程PPT中提取核心知识点",
)
async def extract_knowledge_prompt(ppt_path: str) -> str:
    """创建用于从PPT提取知识的提示词。

    Args:
        ppt_path (str): PPT文件的路径。

    Returns:
        str: 知识提取的提示词。
    """
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""请从以下PPT文件中提取核心知识点：

PPT路径：{ppt_path}

任务要求：
1. 识别PPT中的关键概念、术语和实体
2. 提取每个知识点的定义和核心内容
3. 分析知识点之间的关联关系
4. 输出结构化的知识列表

请使用项目中的 extract_knowledge_graph 工具执行此任务。
"""
            }
        }
    ]