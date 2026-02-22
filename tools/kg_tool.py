from typing import Optional, List, Dict
import os
import sys
# 确保模块能被正确导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tools import YA_MCPServer_Tool
except ImportError:
    # 兼容测试环境的装饰器模拟
    def YA_MCPServer_Tool(**kwargs):
        def decorator(func):
            return func
        return decorator

try:
    from modules.YA_Common.utils.logger import get_logger
except ImportError:
    # 兼容无自定义logger的环境
    import logging
    def get_logger(name):
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(name)

logger = get_logger("YA_MCPServer_KG_Tool")


def _extract_text_from_pptx(path: str) -> List[str]:
    try:
        from pptx import Presentation
    except Exception:
        raise RuntimeError("python-pptx is required to parse PPTX files")

    # 校验文件是否存在
    if not os.path.exists(path):
        raise FileNotFoundError(f"PPT文件不存在：{path}")
    
    prs = Presentation(path)
    slides_text = []
    for slide in prs.slides:
        parts = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text = shape.text.strip()
                if text:
                    parts.append(text)
        slide_text = "\n".join(parts)
        # 仅保留非空幻灯片文本
        if slide_text:
            slides_text.append(slide_text)
        else:
            logger.warning("跳过空白幻灯片")
    return slides_text


def _simple_entity_extraction(text: str, top_k: int = 50) -> List[str]:
    # 空文本直接返回空列表
    if not text.strip():
        return []
    
    # Try spaCy first for better entity extraction
    try:
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception:
            nlp = spacy.blank("en")

        doc = nlp(text)
        ents = [ent.text.strip() for ent in doc.ents if ent.text.strip()]
        if ents:
            seen = set()
            out = []
            for e in ents:
                if e not in seen:
                    seen.add(e)
                    out.append(e)
            return out[:top_k]
    except Exception:
        pass

    # Fallback: simple heuristics (English/Chinese aware)
    try:
        import jieba
        words = [w for w in jieba.cut_for_search(text) if len(w.strip()) > 1]
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words][:top_k]
    except Exception:
        import re
        tokens = [t for t in re.split(r"\W+", text) if len(t) > 2]
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [t for t, _ in sorted_tokens][:top_k]


def _split_sentences_chinese(text: str) -> List[str]:
    import re
    if not text:
        return []
    text = text.strip()
    parts = re.split(r"(?<=[。！？；\n])\s*", text)
    sentences = [p.strip() for p in parts if p and len(p.strip()) > 2]
    return sentences


def _extract_key_sentences(text: str, top_k: int = 3) -> List[str]:
    if not text.strip():
        return []
    
    try:
        import jieba.analyse as analyse
    except Exception:
        return []

    try:
        tags = analyse.extract_tags(text, topK=20, withWeight=True)
    except Exception:
        tags = []

    kw_weights = {w[0]: w[1] for w in tags}
    sentences = _split_sentences_chinese(text)
    
    if not sentences:
        sentences = [s for s in text.splitlines() if s.strip()]

    scored = []
    for s in sentences:
        score = 0.0
        for kw, wt in kw_weights.items():
            if kw in s:
                score += wt
        scored.append((score, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [s for _, s in scored if _ > 0][:top_k]
    if not selected:
        selected = sentences[:top_k]
    return selected


@YA_MCPServer_Tool(
    name="extract_knowledge_graph",
    title="Extract Knowledge Graph",
    description="从 PPT 或文本中抽取实体并基于共现构建简单知识图谱",
)
def extract_knowledge_graph(ppt_path: Optional[str] = None, text: Optional[str] = None, top_k_entities: int = 50) -> Dict:
    """
    传入 `ppt_path`（.pptx 文件路径）或直接传入 `text`，返回知识图谱数据结构。
    核心修复：强制返回字典，永不返回 None
    """
    if not ppt_path and not text:
        raise ValueError("ppt_path 或 text 其中之一必须提供")

    slides = []
    if ppt_path:
        slides = _extract_text_from_pptx(ppt_path)
    else:
        slides = [text] if text and text.strip() else []

    # 强制过滤空文本，确保slides中只有有效内容
    slides = [s for s in slides if s.strip()]

    # 初始化变量，避免未定义
    slide_entities: List[List[str]] = []
    slide_summaries: List[Dict] = []
    all_entities = {}

    # 处理有效幻灯片文本
    for s in slides:
        ents = _simple_entity_extraction(s, top_k=top_k_entities)
        key_sentences = _extract_key_sentences(s, top_k=3)
        slide_entities.append(ents)
        slide_summaries.append({"text": s, "key_points": key_sentences})
        for e in ents:
            all_entities[e] = all_entities.get(e, 0) + 1

    # 构建节点
    nodes = []
    id_map = {}
    for idx, (ent, cnt) in enumerate(sorted(all_entities.items(), key=lambda x: x[1], reverse=True)):
        nid = str(idx + 1)
        id_map[ent] = nid
        nodes.append({"id": nid, "label": ent, "count": cnt})

    # 构建共现关系边
    from collections import defaultdict
    edge_counts = defaultdict(int)
    for ents in slide_entities:
        uniq = list(dict.fromkeys(ents))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                key = tuple(sorted((a, b)))
                edge_counts[key] += 1

    edges = []
    for (a, b), w in edge_counts.items():
        if a in id_map and b in id_map:  # 防止key不存在
            edges.append({
                "source": id_map[a], 
                "target": id_map[b], 
                "weight": w, 
                "relation": "cooccurrence"
            })

    # 强制构造结果字典，确保永不返回None
    result = {
        "nodes": nodes,
        "edges": edges,
        "slides_summary": slide_summaries
    }

    logger.info(f"Extracted KG: {len(nodes)} nodes, {len(edges)} edges")
    return result  # 必须执行这一行！


@YA_MCPServer_Tool(
    name="write_kg_to_neo4j",
    title="Write KG to Neo4j",
    description="将抽取的知识图谱写入 Neo4j 图数据库（merge 节点与关系）",
)
def write_kg_to_neo4j(
    kg: Dict,
    uri: str = "bolt://localhost:7687",
    user: str = "neo4j",
    password: str = "neo4j",
    node_label: str = "Entity",
    rel_type: str = "RELATED_TO",
) -> Dict:
    # 空图谱直接返回
    if not kg or not kg.get("nodes") or not kg.get("edges"):
        logger.warning("空图谱，跳过写入Neo4j")
        return {"nodes_created": 0, "rels_created": 0}
    
    try:
        from py2neo import Graph, Node, Relationship
    except Exception:
        raise RuntimeError("py2neo 未安装，请在环境中安装 py2neo")

    graph = Graph(uri, auth=(user, password))
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    created_nodes = 0
    created_rels = 0

    # 写入节点
    for n in nodes:
        label = n.get("label")
        if not label:
            continue
        props = {"name": label, "count": n.get("count", 0)}
        node = Node(node_label, **props)
        graph.merge(node, node_label, "name")
        created_nodes += 1

    # 写入关系
    for e in edges:
        src_id = e.get("source")
        tgt_id = e.get("target")
        try:
            src_idx = int(src_id) - 1
            tgt_idx = int(tgt_id) - 1
            src_label = nodes[src_idx]["label"]
            tgt_label = nodes[tgt_idx]["label"]
        except Exception:
            continue

        src_node = graph.nodes.match(node_label, name=src_label).first()
        tgt_node = graph.nodes.match(node_label, name=tgt_label).first()
        if not src_node or not tgt_node:
            continue

        rel = Relationship(src_node, rel_type, tgt_node, 
                          weight=e.get("weight", 1), 
                          relation=e.get("relation", "cooccurrence"))
        graph.merge(rel)
        created_rels += 1

    return {"nodes_created": created_nodes, "rels_created": created_rels}


@YA_MCPServer_Tool(
    name="export_kg_visualization",
    title="Export KG Visualization",
    description="导出知识图谱为 GraphML 或 PNG 可视化文件",
)
def export_kg_visualization(kg: Dict, path: str = "kg.graphml", format: str = "graphml") -> Dict:
    """
    核心修复：解决pos为None导致的下标访问错误
    """
    # 空图谱直接返回
    if not kg or not kg.get("nodes") or not kg.get("edges"):
        logger.warning("空图谱，跳过可视化导出")
        return {
            "path": path, 
            "format": format, 
            "error": None, 
            "message": "空图谱，跳过导出"
        }
    
    try:
        import networkx as nx
    except Exception:
        raise RuntimeError("networkx 未安装，请安装 networkx")

    # 自动创建导出目录
    out_dir = os.path.dirname(path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        logger.info(f"创建导出目录：{out_dir}")

    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    G = nx.Graph()
    # 添加节点
    for n in nodes:
        label = n.get("label")
        if label is None:
            continue
        G.add_node(label, count=n.get("count", 1))

    # 添加边
    for e in edges:
        try:
            src = nodes[int(e.get("source")) - 1]["label"]
            tgt = nodes[int(e.get("target")) - 1]["label"]
        except Exception:
            src = e.get("source")
            tgt = e.get("target")
        if src is None or tgt is None:
            continue
        G.add_edge(src, tgt, 
                  weight=e.get("weight", 1), 
                  relation=e.get("relation", "cooccurrence"))

    # 导出逻辑
    fmt = format.lower()
    if fmt == "graphml":
        nx.write_graphml(G, path)
    elif fmt == "gexf":
        nx.write_gexf(G, path)
    elif fmt == "png":
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            # 支持中文显示
            plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
        except Exception:
            raise RuntimeError("matplotlib 未安装，无法导出 PNG")

        plt.figure(figsize=(10, 8))
        # 关键修复：确保pos永远不为None
        try:
            pos = nx.spring_layout(G, seed=42)  # seed固定布局，避免随机
        except Exception as e:
            logger.warning(f"spring布局失败：{e}，使用圆形布局")
            pos = nx.circular_layout(G)
        
        # 双重保险：如果pos还是None，手动构造简单布局
        if pos is None or len(pos) == 0:
            pos = {node: (i, 0) for i, node in enumerate(G.nodes())}

        # 节点大小（避免0值）
        sizes = [max(G.nodes[n].get("count", 1) * 100, 100) for n in G.nodes()]
        
        # 绘图（增加异常捕获）
        try:
            nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color="#4CAF50", alpha=0.8)
            nx.draw_networkx_edges(G, pos, alpha=0.5, edge_color="#666666")
            labels = {n: n for n in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels, font_size=8, font_family="sans-serif")
        except Exception as e:
            logger.warning(f"绘图失败：{e}，简化绘图")
            nx.draw(G, pos, with_labels=True, node_size=100, font_size=8)

        plt.axis("off")
        plt.tight_layout()
        plt.savefig(path, dpi=200, bbox_inches="tight")
        plt.close()
    else:
        raise ValueError(f"Unsupported export format: {format}")

    return {"path": path, "format": fmt}


@YA_MCPServer_Tool(
    name="process_and_publish_kg",
    title="Process and Publish KG",
    description="抽取知识图谱，并可选写入 Neo4j 与导出可视化（供 MCP 调用）",
)
def process_and_publish_kg(
    ppt_path: Optional[str] = None,
    text: Optional[str] = None,
    write_neo4j: bool = False,
    neo_uri: str = "bolt://localhost:7687",
    neo_user: str = "neo4j",
    neo_password: str = "neo4j",
    export_format: str = "graphml",
    export_path: str = "kg_output",
) -> Dict:
    logger.info(f"process_and_publish_kg called with ppt_path={ppt_path!r}, text_len={len(text) if text else 0}, write_neo4j={write_neo4j}, export_format={export_format}, export_path={export_path}")
    neo_result = None
    export_result = None
    try:
        # 抽取图谱（已确保返回字典）
        kg = extract_knowledge_graph(ppt_path=ppt_path, text=text)
        logger.info(f"KG extraction complete: nodes={len(kg.get('nodes',[]))} edges={len(kg.get('edges',[]))}")

        # 写入Neo4j（可选）
        if write_neo4j:
            logger.info("Writing KG to Neo4j")
            try:
                neo_result = write_kg_to_neo4j(kg, uri=neo_uri, user=neo_user, password=neo_password)
                logger.info(f"Neo4j write result: {neo_result}")
            except Exception as e:
                neo_result = {"error": str(e)}
                logger.exception("Failed to write KG to Neo4j")

        # 导出可视化
        logger.info("Exporting KG visualization")
        fmt = export_format.lower() if export_format else "graphml"
        if fmt == "png":
            out_file = f"{export_path}.png"
        elif fmt == "gexf":
            out_file = f"{export_path}.gexf"
        else:
            out_file = f"{export_path}.graphml"

        try:
            export_result = export_kg_visualization(kg, path=out_file, format=fmt)
            logger.info(f"Export result: {export_result}")
        except Exception as e:
            export_result = {"error": str(e)}
            logger.exception("Failed to export KG visualization")

        logger.info("process_and_publish_kg completed successfully")
        return {"kg": kg, "neo_result": neo_result, "export_result": export_result}
    except Exception as exc:
        logger.exception("Unhandled exception in process_and_publish_kg")
        return {"kg": {"nodes": [], "edges": [], "slides_summary": []}, "neo_result": None, "export_result": {"error": str(exc)}}


# 测试入口
if __name__ == "__main__":
    # 快速测试：抽取文本图谱并导出PNG
    test_kg = extract_knowledge_graph(text="张三是李四的同学，李四是北京大学的学生，北京大学位于北京市")
    print("测试图谱结果：")
    print(f"节点数：{len(test_kg['nodes'])}，边数：{len(test_kg['edges'])}")
    
    # 导出测试
    export_res = export_kg_visualization(test_kg, path="test_kg_output", format="png")
    print(f"导出结果：{export_res}")