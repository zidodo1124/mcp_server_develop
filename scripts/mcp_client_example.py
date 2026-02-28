#!/usr/bin/env python
"""示例：通过 mcp 客户端调用 MCP 工具 process_and_publish_kg

注意：此脚本假设 MCP server 以 stdio 方式运行在同一进程通信中，
或你可以根据实际 transport 修改为 SSE/HTTP 客户端。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
import os

# ========== 添加这段路径导入代码 ==========
# 获取脚本所在目录的上一级（项目根目录）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
# ======================================

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ppt", dest="ppt_path", help="pptx path")
    p.add_argument("--text", dest="text", help="text input")
    p.add_argument("--export-format", dest="export_format", default="graphml")
    p.add_argument("--export-path", dest="export_path", default="kg_output")
    args = p.parse_args()

    # 简单方式：直接调用脚本实现（不依赖 mcp runtime）
    # 这是在本地环境下的便捷示例：
    from tools.kg_tool import process_and_publish_kg

    res = process_and_publish_kg(
        ppt_path=args.ppt_path,
        text=args.text,
        write_neo4j=False,
        export_format=args.export_format,
        export_path=args.export_path,
    )

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
