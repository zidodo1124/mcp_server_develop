## YA_MCPServer_Knowledge_graph_Generator

[内容抽取生成知识图谱的MCP]

### 组员信息

| 姓名 | 学    号 | 分工 | 备注 |
| :--: | :------: | :--: | :--: |
|支盟渊|U202414620|  |在两个项目中有工作，仅在本项目（不转大创）中进行了工作记录|
|曾子渊|U202414616|      |      |
|龙  武|U202414603|      |      |

### Tool 列表

## 工具列表

| 工具名称 | 功能描述 | 输入 | 输出 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| `extract_knowledge_graph` | 从AI架构与系统PPT中抽取精准知识图谱，无空节点、关键字准确 | `ppt_path` (可选), `text` (可选), `top_k_entities`, `min_occur`, `min_len`, `max_len`, `min_edge_cooccurrence`, `centrality_metric`, `core_node_count`, `subcore_node_count`, `periphery_node_count`, `core_radius`, `subcore_radius`, `periphery_radius`, `entity_blacklist` (均为可选参数) | 字典：`{"nodes": [...], "edges": [...], "slides_summary": [...]}` | 内部使用自定义配置和实体清洗规则；核心算法包括实体提取、共现过滤、节点重要性排序 |
| `write_kg_to_neo4j` | 将AI知识图谱写入Neo4j，merge节点与关系 | `kg` (字典), `uri`, `user`, `password`, `node_label`, `rel_type` | 字典：`{"nodes_created": int, "rels_created": int}` | 依赖 `py2neo` 库；需提前安装并运行Neo4j数据库 |
| `export_kg_visualization` | 三层布局+强关联边+动态节点大小，导出可视化文件 | `kg` (字典), `path` (导出路径), `format` ("graphml"/"gexf"/"png") | 字典：`{"path": str, "format": str, "node_count": int, "edge_count": int}` 或错误信息 | 支持导出GraphML、GEXF、PNG格式；PNG生成依赖 `matplotlib` 和 `networkx`，采用核心-次核心-外围三层布局 |
| `process_and_publish_kg` | 一站式处理：抽取图谱 + 导出可视化 + 可选写入Neo4j | 包含 `extract_knowledge_graph` 的所有参数，以及 `write_neo4j` (bool), `neo_uri`, `neo_user`, `neo_password`, `export_format`, `export_path` | 字典：`{"kg": {...}, "neo_result": {...}, "export_result": {...}, "status": str}` | 整合前三个工具，实现端到端处理；状态字段指示整体成功或部分失败 |

### Resource 列表

| 资源名称 | 功能描述 | 输入 | 输出 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| `readme_file` | 返回项目的README.md文件内容 | 无 | README.md 文件内容（字符串）或 `{"error": "File not found"}` | 资源URI: `file:///README.md`；从项目根目录读取README文件 |
| `get_server_logs` | 返回服务器日志文件的内容 | `path` (str): 日志文件路径 | 日志文件内容（字符串）或 `{"error": "File not found"}` | 资源模板URI: `file:///logs/{path}`；从 `logs/` 目录读取指定日志文件 |
| `get_ppt_file` | 获取指定路径的PPT文件内容（文本提取） | `filename` (str): PPT文件名 | PPT文本内容，包含每页幻灯片的文字 | 资源模板URI: `file:///ppt/{filename}`；需要安装 `python-pptx` |
| `list_ppt_files` | 列出所有可用的PPT文件 | 无 | PPT文件列表，包含文件名、大小、修改时间 | 资源URI: `file:///ppt/list`；自动创建PPT目录 |
| `get_kg_output` | 获取生成的知识图谱输出文件 | `filename` (str): 输出文件名 | 文件内容（文本或图片base64编码） | 资源模板URI: `file:///kg/output/{filename}`；支持PNG/GraphML/GEXF格式 |
| `list_kg_outputs` | 列出所有生成的知识图谱输出文件 | 无 | 输出文件列表，包含文件名、大小、类型 | 资源URI: `file:///kg/list`；自动创建输出目录 |
| `preview_kg_graph` | 预览知识图谱图片 | `filename` (str): PNG文件名 | PNG图片的base64编码 | 资源模板URI: `file:///kg/preview/{filename}`；只支持PNG格式预览 |

### Prompts 列表


| 指令名称 | 功能描述 | 输入 | 输出 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| `greet_user` | 生成一个问候消息 | `name` (str): 用户的名字 | 字符串：`"你好，{name}！欢迎使用 YA MCP Server。"` | 基础问候指令 |
| `extract_knowledge_from_ppt` | 从AI导论课程PPT中提取核心知识点 | `ppt_path` (str): PPT文件路径 | 知识提取提示词 | 调用 `extract_knowledge_graph` 工具 |
| `generate_knowledge_graph` | 根据提取的知识生成知识点图谱并导出 | `ppt_path` (str): PPT文件路径<br>`export_format` (str): 导出格式（默认"png"）<br>`export_path` (str): 导出路径（默认"./kg_output"）<br>`min_edge_cooccurrence` (int): 边共现阈值（默认4） | 知识图谱生成提示词 | 调用 `process_and_publish_kg` 工具，支持PNG/GraphML/GEXF格式 |

### 项目结构

- `core`: [XXXX]
- `tools`: [XXXX]
- `config.yaml`: [XXXX(添加 XX 额外配置)]
- [XXXX(其他新添加的文件与目录介绍)]

### 其他需要说明的情况

- 在 `sops` 模块中添加的密钥变量分别用于什么功能
- 是否使用了 PyTorch、Tensorflow 等深度学习框架
- 是否使用了机器学习、深度学习模型
# mcp_server_develop
For zmy,zzy,lw,these three person to develop their mcp server

## 使用示例

### 1) 命令行提取并导出

使用 CLI 从 PPT 或文本抽取并导出可视化文件：

```bash
pip install python-pptx jieba networkx matplotlib py2neo
python scripts/kg_cli.py --ppt path/to/ai_chapter.pptx --export-format png --export-path out/kg_image
```

### 2) 在 MCP 中调用（示例脚本）

项目提供了一个 MCP 工具 `process_and_publish_kg`，你可以通过 MCP 客户端触发它。下面是一个用 `mcp` 客户端通过 stdio 运行的示例脚本（`scripts/mcp_client_example.py`）：

```bash
python scripts/mcp_client_example.py --ppt path/to/ai_chapter.pptx --export-format graphml
```

示例行为：调用 `process_and_publish_kg`，返回 `kg`、`neo_result`、`export_result`。

请参阅 `scripts/mcp_client_example.py` 了解细节。
