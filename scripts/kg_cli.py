#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识图谱提取CLI工具（适配分层发散布局新版）
"""
import sys
import os
# 把项目根目录加入Python路径，解决ModuleNotFoundError
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="知识图谱提取CLI（分层发散布局版）")
    # 核心必选参数
    parser.add_argument("--ppt", dest="ppt_path", type=str, help="PPTX文件路径（与--text二选一）")
    parser.add_argument("--text", type=str, help="直接输入的文本（与--ppt二选一）")
    # 导出配置参数
    parser.add_argument("--export-format", type=str, choices=["graphml", "gexf", "png"], default="png", help="导出格式（默认png）")
    parser.add_argument("--export-path", type=str, default="out/ppt_kg_png", help="导出路径（不含后缀）")
    parser.add_argument("--top-k", type=int, default=100, help="抽取实体的最大数量（默认100，增加节点数）")
    # Neo4j 可选参数
    parser.add_argument("--write-neo4j", action="store_true", help="是否写入Neo4j图数据库")
    parser.add_argument("--neo-uri", type=str, default="bolt://localhost:7687", help="Neo4j连接地址")
    parser.add_argument("--neo-user", type=str, default="neo4j", help="Neo4j用户名")
    parser.add_argument("--neo-pass", type=str, default="neo4j", help="Neo4j密码")

    args = parser.parse_args()

    # 基础校验
    if not args.ppt_path and not args.text:
        print("❌ 错误：必须提供 --ppt 或 --text 参数")
        sys.exit(1)

    try:
        # 导入新版核心工具函数
        from tools.kg_tool import process_and_publish_kg

        # 调用新版函数，无旧参数
        result = process_and_publish_kg(
            ppt_path=args.ppt_path,
            text=args.text,
            top_k_entities=args.top_k,
            write_neo4j=args.write_neo4j,
            neo_uri=args.neo_uri,
            neo_user=args.neo_user,
            neo_password=args.neo_pass,
            export_format=args.export_format,
            export_path=args.export_path
        )

        # 美化输出结果
        print("\n✅ 执行完成！======================")
        print(f"📊 知识图谱统计：")
        print(f"   有效节点数：{len(result['kg']['nodes'])}")
        print(f"   唯一边数：{len(result['kg']['edges'])}")
        
        if result['neo_result']:
            print(f"\n🖥️ Neo4j 写入结果：")
            print(f"   {json.dumps(result['neo_result'], ensure_ascii=False, indent=2)}")
        
        print(f"\n💾 导出结果：")
        print(f"   {json.dumps(result['export_result'], ensure_ascii=False, indent=2)}")

        if "path" in result['export_result']:
            print(f"\n📁 生成文件路径：{result['export_result']['path']}")

    except ImportError as e:
        print(f"❌ 导入失败：{e}")
        print("   请确保 tools 目录在项目根目录下，且已安装依赖：")
        print("   pip install python-pptx networkx matplotlib jieba py2neo -i https://pypi.tuna.tsinghua.edu.cn/simple")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 执行失败：{str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()