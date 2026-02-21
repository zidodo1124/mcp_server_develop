from typing import Optional, List, Dict
from tools import YA_MCPServer_Tool
from modules.YA_Common.utils.logger import get_logger

logger = get_logger("YA_MCPServer_KG_Tool")


def _extract_text_from_pptx(path: str) -> List[str]:
    try:
        from pptx import Presentation
    except Exception:
        raise RuntimeError("python-pptx is required to parse PPTX files")

    prs = Presentation(path)
    slides_text = []
    for slide in prs.slides:
        parts = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text = shape.text.strip()
                if text:
                    parts.append(text)
        slides_text.append("\n".join(parts))
    return slides_text


def _simple_entity_extraction(text: str, top_k: int = 50) -> List[str]:
    # Try spaCy first for better entity extraction
    try:
        import spacy

        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception:
            # fallback to blank English model
            nlp = spacy.blank("en")

        doc = nlp(text)
        ents = [ent.text.strip() for ent in doc.ents if ent.text.strip()]
        if ents:
            # return unique preserving order
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
        # frequency
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words][:top_k]
    except Exception:
        # naive split by non-word
        import re

        tokens = [t for t in re.split(r"\W+", text) if len(t) > 2]
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        sorted_tokens = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [t for t, _ in sorted_tokens][:top_k]


def _split_sentences_chinese(text: str) -> List[str]:
    # 简单中文分句，保留常见的句末标点
    import re

    if not text:
        return []
    text = text.strip()
    # 切分规则：。！？；及换行
    parts = re.split(r"(?<=[。！？；\n])\s*", text)
    sentences = [p.strip() for p in parts if p and len(p.strip()) > 2]
    return sentences


def _extract_key_sentences(text: str, top_k: int = 3) -> List[str]:
    """基于 jieba.analyse 提取关键词，再对句子打分，返回 top_k 要点句子。"""
    try:
        import jieba.analyse as analyse
    except Exception:
        return []

    # 获取关键词（带权重）
    try:
        tags = analyse.extract_tags(text, topK=20, withWeight=True)
    except Exception:
        tags = []

    kw_weights = {w[0]: w[1] for w in tags}

    sentences = _split_sentences_chinese(text)
    if not sentences:
        # fallback: split by newline
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
    # 如果没匹配到关键词则降级返回前几句
    if not selected:
        return sentences[:top_k]
    return selected


@YA_MCPServer_Tool(
    name="extract_knowledge_graph",
    title="Extract Knowledge Graph",
    description="从 PPT 或文本中抽取实体并基于共现构建简单知识图谱",
)
def extract_knowledge_graph(ppt_path: Optional[str] = None, text: Optional[str] = None, top_k_entities: int = 50) -> Dict:
    """
    传入 `ppt_path`（.pptx 文件路径）或直接传入 `text`，返回知识图谱数据结构。

    返回格式：{"nodes": [{"id": str, "label": str, "count": int}], "edges": [{"source": str, "target": str, "weight": int, "relation": str}]}
    """
    if not ppt_path and not text:
        raise ValueError("ppt_path 或 text 其中之一必须提供")

    slides = []
    if ppt_path:
        slides = _extract_text_from_pptx(ppt_path)
    else:
        slides = [text]

    # collect entities per slide and extract key points per slide
    slide_entities: List[List[str]] = []
    slide_summaries: List[Dict] = []
    all_entities = {}
    for s in slides:
        ents = _simple_entity_extraction(s, top_k=top_k_entities)
        # 要点句子（中文/英文均可）
        key_sentences = _extract_key_sentences(s, top_k=3)
        slide_entities.append(ents)
        slide_summaries.append({"text": s, "key_points": key_sentences})
        for e in ents:
            all_entities[e] = all_entities.get(e, 0) + 1

    # build nodes
    nodes = []
    id_map = {}
    for idx, (ent, cnt) in enumerate(sorted(all_entities.items(), key=lambda x: x[1], reverse=True)):
        nid = str(idx + 1)
        id_map[ent] = nid
        nodes.append({"id": nid, "label": ent, "count": cnt})

    # build co-occurrence edges
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
        edges.append({"source": id_map[a], "target": id_map[b], "weight": w, "relation": "cooccurrence"})

    result = {"nodes": nodes, "edges": edges}
    # include slide summaries for extraction/展示
    result["slides_summary"] = slide_summaries
    logger.info(f"Extracted KG: {len(nodes)} nodes, {len(edges)} edges")
    return result


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
    """
    将 `extract_knowledge_graph` 返回的结构写入 Neo4j。

    参数:
      - kg: 知识图谱字典（含 `nodes` 和 `edges`）
      - uri,user,password: 连接 Neo4j 的凭据
      - node_label: 在 Neo4j 中使用的节点标签
      - rel_type: 关系类型

    返回: {"nodes_created": int, "rels_created": int}
    """
    try:
        from py2neo import Graph, Node, Relationship
    except Exception:
        raise RuntimeError("py2neo 未安装，请在环境中安装 py2neo")

    graph = Graph(uri, auth=(user, password))

    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    created_nodes = 0
    created_rels = 0

    # 使用 merge 保证幂等
    for n in nodes:
        label = n.get("label")
        if not label:
            continue
        props = {"name": label, "count": n.get("count", 0)}
        node = Node(node_label, **props)
        graph.merge(node, node_label, "name")
        created_nodes += 1

    for e in edges:
        src_id = e.get("source")
        tgt_id = e.get("target")
        # source/target in our structure are ids mapping to nodes list; map back by index
        try:
            src_idx = int(src_id) - 1
            tgt_idx = int(tgt_id) - 1
            src_label = nodes[src_idx]["label"]
            tgt_label = nodes[tgt_idx]["label"]
        except Exception:
            continue

        matcher = {"name": src_label}
        src_node = graph.nodes.match(node_label, **matcher).first()
        tgt_node = graph.nodes.match(node_label, name=tgt_label).first()
        if not src_node or not tgt_node:
            continue

        rel = Relationship(src_node, rel_type, tgt_node, weight=e.get("weight", 1), relation=e.get("relation", "cooccurrence"))
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
    将知识图谱导出为可视化格式。

    format 支持："graphml"（GraphML 文件），"gexf"，"png"（静态 PNG 图片）。
    返回：{"path": str, "format": str}
    """
    try:
        import networkx as nx
    except Exception:
        raise RuntimeError("networkx 未安装，请安装 networkx")

    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    G = nx.Graph()
    # 使用标签作为节点标识
    for n in nodes:
        label = n.get("label")
        if label is None:
            continue
        G.add_node(label, count=n.get("count", 1))

    for e in edges:
        try:
            src = nodes[int(e.get("source")) - 1]["label"]
            tgt = nodes[int(e.get("target")) - 1]["label"]
        except Exception:
            # 若无法映射 id，则尝试直接用 source/target 字段
            src = e.get("source")
            tgt = e.get("target")
        if src is None or tgt is None:
            continue
        G.add_edge(src, tgt, weight=e.get("weight", 1), relation=e.get("relation", "cooccurrence"))

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
        except Exception:
            raise RuntimeError("matplotlib 未安装，无法导出 PNG")

        plt.figure(figsize=(10, 8))
        try:
            pos = nx.spring_layout(G)
        except Exception:
            pos = None
        sizes = [G.nodes[n].get("count", 1) * 100 for n in G.nodes()]
        nx.draw_networkx_nodes(G, pos, node_size=sizes)
        nx.draw_networkx_edges(G, pos, alpha=0.5)
        labels = {n: n for n in G.nodes()}
        nx.draw_networkx_labels(G, pos, labels, font_size=8)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(path, dpi=200)
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
    """
    综合流程：抽取 KG；可选将 KG 写入 Neo4j；可选导出可视化文件。

    返回包含：kg, neo_result (若写入), export_result (若导出)
    """
    logger.info(f"process_and_publish_kg called with ppt_path={ppt_path!r}, text_len={len(text) if text else 0}, write_neo4j={write_neo4j}, export_format={export_format}, export_path={export_path}")
    neo_result = None
    export_result = None
    try:
        # 1) 抽取
        logger.info("Starting KG extraction")
        kg = extract_knowledge_graph(ppt_path=ppt_path, text=text)
        logger.info(f"KG extraction complete: nodes={len(kg.get('nodes',[]))} edges={len(kg.get('edges',[]))}")

        # 2) 写入 Neo4j（可选）
        if write_neo4j:
            logger.info("Writing KG to Neo4j")
            try:
                neo_result = write_kg_to_neo4j(kg, uri=neo_uri, user=neo_user, password=neo_password)
                logger.info(f"Neo4j write result: {neo_result}")
            except Exception as e:
                neo_result = {"error": str(e)}
                logger.exception("Failed to write KG to Neo4j")

        # 3) 导出可视化
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
        return {"kg": None, "neo_result": None, "export_result": {"error": str(exc)}}
