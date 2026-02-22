#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识图谱提取CLI工具
修复所有导入和运行时错误
"""

import sys
import os

# 把项目根目录加入Python路径，解决ModuleNotFoundError
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import argparse
import json
import importlib.util


def main():
    parser = argparse.ArgumentParser(description="Knowledge Graph Extraction CLI")
    parser.add_argument("--ppt", dest="ppt_path", type=str, help="Path to PPTX file")
    parser.add_argument("--text", type=str, help="Direct text input")
    parser.add_argument(
        "--export-format",
        type=str,
        choices=["graphml", "gexf", "png"],
        default="graphml",
        help="Export format",
    )
    parser.add_argument(
        "--export-path",
        type=str,
        default="out/kg_output",
        help="Export path (without extension)",
    )
    parser.add_argument(
        "--top-k", type=int, default=50, help="Top K entities to extract"
    )
    parser.add_argument(
        "--min-occur", type=int, default=None, help="最小实体出现次数阈值"
    )
    parser.add_argument("--min-len", type=int, default=None, help="实体最短长度")
    parser.add_argument("--max-len", type=int, default=None, help="实体最长长度")
    parser.add_argument(
        "--min-edge-weight", type=int, default=None, help="最小边权阈值"
    )
    parser.add_argument(
        "--centrality",
        type=str,
        choices=["pagerank", "degree", "betweenness"],
        default=None,
        help="核心节点筛选算法",
    )
    parser.add_argument(
        "--top-n-core", type=int, default=None, help="仅保留Top N核心节点"
    )
    parser.add_argument(
        "--adaptive-topn",
        dest="adaptive_topn",
        action="store_true",
        help="启用自适应TopN",
    )
    parser.add_argument(
        "--no-adaptive-topn",
        dest="adaptive_topn",
        action="store_false",
        help="禁用自适应TopN",
    )
    parser.set_defaults(adaptive_topn=None)
    parser.add_argument(
        "--keep-seed", dest="keep_seed", action="store_true", help="强制保留种子实体"
    )
    parser.add_argument(
        "--no-keep-seed",
        dest="keep_seed",
        action="store_false",
        help="不强制保留种子实体",
    )
    parser.set_defaults(keep_seed=None)
    parser.add_argument(
        "--seed-from-title",
        dest="seed_from_title",
        action="store_true",
        help="从标题自动抽取种子实体",
    )
    parser.add_argument(
        "--no-seed-from-title",
        dest="seed_from_title",
        action="store_false",
        help="不从标题自动抽取种子实体",
    )
    parser.set_defaults(seed_from_title=None)
    parser.add_argument(
        "--entity-blacklist", type=str, default=None, help="额外黑名单，逗号分隔"
    )
    parser.add_argument(
        "--write-neo4j", action="store_true", help="Whether to write to Neo4j"
    )
    parser.add_argument(
        "--neo-uri", type=str, default="bolt://localhost:7687", help="Neo4j URI"
    )
    parser.add_argument("--neo-user", type=str, default="neo4j", help="Neo4j username")
    parser.add_argument("--neo-pass", type=str, default="neo4j", help="Neo4j password")

    args = parser.parse_args()

    # 基础校验
    if not args.ppt_path and not args.text:
        print("❌ 错误：必须提供 --ppt 或 --text 参数")
        return

    try:
        # 导入核心工具函数（优先正常导入，失败时回退到文件导入）
        try:
            from tools.kg_tool import process_and_publish_kg
        except Exception:
            kg_tool_path = os.path.join(ROOT_DIR, "tools", "kg_tool.py")
            spec = importlib.util.spec_from_file_location("kg_tool", kg_tool_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            process_and_publish_kg = module.process_and_publish_kg

        extra_blacklist = None
        if args.entity_blacklist:
            extra_blacklist = [
                s.strip() for s in args.entity_blacklist.split(",") if s.strip()
            ]

        # 使用一站式处理函数
        result = process_and_publish_kg(
            ppt_path=args.ppt_path,
            text=args.text,
            top_k_entities=args.top_k,
            min_occur=args.min_occur,
            min_len=args.min_len,
            max_len=args.max_len,
            min_edge_weight=args.min_edge_weight,
            centrality_metric=args.centrality,
            top_n_core=args.top_n_core,
            adaptive_top_n=args.adaptive_topn,
            keep_seed_entities=args.keep_seed,
            seed_from_title=args.seed_from_title,
            entity_blacklist=extra_blacklist,
            write_neo4j=args.write_neo4j,
            neo_uri=args.neo_uri,
            neo_user=args.neo_user,
            neo_password=args.neo_pass,
            export_format=args.export_format,
            export_path=args.export_path,
        )

        # 打印结果
        print("\n✅ 执行完成！")
        print(f"\n📊 知识图谱统计：")
        print(f"   节点数：{len(result['kg']['nodes'])}")
        print(f"   边数：{len(result['kg']['edges'])}")

        if result["neo_result"]:
            print(f"\n🖥️ Neo4j 写入结果：")
            print(
                f"   {json.dumps(result['neo_result'], ensure_ascii=False, indent=2)}"
            )

        print(f"\n💾 导出结果：")
        print(f"   {json.dumps(result['export_result'], ensure_ascii=False, indent=2)}")

        # 显示文件路径
        if "path" in result["export_result"]:
            print(f"\n📁 生成的文件：{result['export_result']['path']}")

    except ImportError as e:
        print(f"❌ 导入失败：{e}")
        print("   请确保 tools 目录在项目根目录下，且已安装所有依赖：")
        print(
            "   pip install python-pptx networkx matplotlib jieba spacy py2neo -i https://pypi.tuna.tsinghua.edu.cn/simple"
        )
    except Exception as e:
        print(f"\n❌ 执行失败：{str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
