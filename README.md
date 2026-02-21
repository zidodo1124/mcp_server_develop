## YA_MCPServer_Knowledge_graph_Generator

[内容抽取生成知识图谱的MCP]

### 组员信息

| 姓名 | 学    号 | 分工 | 备注 |
| :--: | :------: | :--: | :--: |
|支盟渊|U202414620|  |      |
|曾子渊|      |      |      |
|龙  武|      |      |      |
|      |      |      |      |

### Tool 列表

| 工具名称 | 功能描述 | 输入 | 输出 | 备注 |
| :------: | :------: | :--: | :--: | :--: |
|  什么待定|          |      |      |      |
|          |          |      |      |      |
|          |          |      |      |      |

### Resource 列表

| 资源名称 | 功能描述 | 输入 | 输出 | 备注 |
| :------: | :------: | :--: | :--: | :--: |
|          |          |      |      |      |
|          |          |      |      |      |
|          |          |      |      |      |

### Prompts 列表

| 指令名称 | 功能描述 | 输入 | 输出 | 备注 |
| :------: | :------: | :--: | :--: | :--: |
|          |          |      |      |      |
|          |          |      |      |      |
|          |          |      |      |      |

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
