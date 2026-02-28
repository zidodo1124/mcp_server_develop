# prompts/kg_generate_prompt.py
from typing import Optional
from prompts import YA_MCPServer_Prompt


@YA_MCPServer_Prompt(
    name="generate_knowledge_graph",
    title="Generate Knowledge Graph",
    description="根据提取的知识生成知识点图谱并导出",
)
async def generate_kg_prompt(
    ppt_path: str,
    export_format: str = "png",
    export_path: str = "./kg_output",
    min_edge_cooccurrence: int = 4
) -> str:
    """创建用于生成知识图谱的提示词。

    Args:
        ppt_path (str): PPT文件路径。
        export_format (str): 导出格式，可选 png/graphml/gexf，默认为 png。
        export_path (str): 导出文件路径（不含扩展名），默认为 "./kg_output"。
        min_edge_cooccurrence (int): 边的最小共现阈值，默认为 4。

    Returns:
        str: 知识图谱生成的提示词。
    """
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""请从PPT中提取知识并生成知识点图谱：

配置参数：
- PPT路径：{ppt_path}
- 导出格式：{export_format}
- 导出路径：{export_path}
- 边共现阈值：{min_edge_cooccurrence}

执行命令：
```bash
python scripts/kg_cli.py --ppt "{ppt_path}" --export-format {export_format} --export-path {export_path}或者通过MCP客户端调用 process_and_publish_kg 工具：

先提取知识图谱

再导出可视化文件

请执行此任务并返回生成的图谱文件路径。
"""
}
}
]