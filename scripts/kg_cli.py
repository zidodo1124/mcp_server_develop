#!/usr/bin/env python
import argparse
import json
from tools.kg_tool import extract_knowledge_graph


def main():
    p = argparse.ArgumentParser(description="KG extractor CLI: 从 PPT 或文本抽取知识图谱")
    p.add_argument("--ppt", help="PPTX 文件路径", dest="ppt_path")
    p.add_argument("--text", help="直接传入文本", dest="text")
    p.add_argument("--write-neo4j", action="store_true", help="将结果写入 Neo4j（需额外参数）")
    p.add_argument("--neo-uri", default="bolt://localhost:7687", help="Neo4j URI")
    p.add_argument("--neo-user", default="neo4j", help="Neo4j 用户")
    p.add_argument("--neo-pass", default="neo4j", help="Neo4j 密码")
    p.add_argument("--export-format", default="graphml", choices=["graphml", "gexf", "png"], help="导出格式")
    p.add_argument("--export-path", default="kg_output", help="导出文件路径（不含扩展名，PNG 会自动使用 .png）")

    args = p.parse_args()

    if not args.ppt_path and not args.text:
        p.error("必须提供 --ppt 或 --text")

    kg = extract_knowledge_graph(ppt_path=args.ppt_path, text=args.text)
    print(json.dumps(kg, ensure_ascii=False, indent=2))

    if args.write_neo4j:
        try:
            from tools.kg_tool import write_kg_to_neo4j

            res = write_kg_to_neo4j(kg, uri=args.neo_uri, user=args.neo_user, password=args.neo_pass)
            print("写入 Neo4j 结果:", res)
        except Exception as e:
            print("写入 Neo4j 失败:", e)

    # 导出可视化
    if args.export_format:
        out_path = args.export_path
        ext = args.export_format
        if ext == "png":
            out_file = f"{out_path}.png"
        elif ext == "gexf":
            out_file = f"{out_path}.gexf"
        else:
            out_file = f"{out_path}.graphml"

        try:
            from tools.kg_tool import export_kg_visualization

            res = export_kg_visualization(kg, path=out_file, format=args.export_format)
            print("导出可视化成功:", res)
        except Exception as e:
            print("导出可视化失败:", e)


if __name__ == "__main__":
    main()
