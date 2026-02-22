from typing import Optional, List, Dict
import os
import sys
import re

# 确保模块能被正确导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 简易停用词表（可自行扩充）
STOPWORDS = set(
    """
的 了 在 是 我 你 他 她 它 我们 你们 他们 这个 那个 这些 那些 和 与 或 及 而 但 也 
a an the and or but if is are was were be been being have has had do does did will would shall should may might must can could of in on at to for with by from as into through during before after above below up down out off over under again further then once here there when where why how all any both each few more most other some such no nor not only own same so than too very s t can will just don should now
""".split()
)

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


ENTITY_BLACKLIST = {
    "介绍",
    "概述",
    "总洁",
    "总结",
    "例子",
    "示例",
    "例如",
    "因此",
    "然后",
    "其中",
    "以及",
    "我们",
    "你们",
    "他们",
}


def _load_kg_defaults() -> Dict:
    defaults = {
        "top_k_entities": 80,
        "min_occur": 2,
        "min_len": 2,
        "max_len": 10,
        "entity_blacklist": sorted(ENTITY_BLACKLIST),
        "min_edge_weight": 2,
        "centrality_metric": "pagerank",
        "top_n_core": None,
        "adaptive_top_n": True,
        "keep_seed_entities": True,
        "seed_from_title": True,
    }
    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
    )
    if not os.path.exists(cfg_path):
        return defaults

    try:
        import yaml

        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        kg_cfg = cfg.get("kg", {}) if isinstance(cfg, dict) else {}
        if isinstance(kg_cfg, dict):
            for key in defaults:
                if key in kg_cfg and kg_cfg[key] is not None:
                    defaults[key] = kg_cfg[key]
    except Exception as exc:
        logger.warning(f"加载kg默认配置失败，使用内置默认值: {exc}")

    return defaults


def _is_valid_entity(entity: str, min_len: int, max_len: int, blacklist: set) -> bool:
    ent = (entity or "").strip()
    if not ent:
        return False
    if ent in STOPWORDS:
        return False
    if ent in blacklist:
        return False
    if len(ent) < min_len or len(ent) > max_len:
        return False
    if re.fullmatch(r"[\W_]+", ent):
        return False
    if re.fullmatch(r"\d+(\.\d+)?", ent):
        return False
    return True


def _extract_seed_entities_from_titles(
    slides: List[str], top_k_each: int = 5
) -> List[str]:
    seeds = []
    for s in slides:
        lines = [ln.strip() for ln in (s or "").splitlines() if ln and ln.strip()]
        if not lines:
            continue
        title = lines[0]
        title_ents = _simple_entity_extraction(title, top_k=top_k_each)
        seeds.extend(title_ents)
    return list(dict.fromkeys(seeds))


def _resolve_adaptive_top_n(total_nodes: int) -> int:
    if total_nodes <= 0:
        return 0
    if total_nodes <= 30:
        return total_nodes
    if total_nodes <= 80:
        return max(25, int(total_nodes * 0.8))
    if total_nodes <= 200:
        return 80
    if total_nodes <= 500:
        return 100
    return 120


def _compute_node_scores(graph, metric: str = "pagerank") -> Dict[str, float]:
    try:
        import networkx as nx
    except Exception:
        return {n: 1.0 for n in graph.nodes()}

    if graph.number_of_nodes() == 0:
        return {}

    metric_l = (metric or "pagerank").lower()
    if metric_l == "degree":
        return {n: float(v) for n, v in graph.degree(weight="weight")}
    if metric_l == "betweenness":
        return nx.betweenness_centrality(graph, normalized=True, weight="weight")
    try:
        return nx.pagerank(graph, alpha=0.85, weight="weight")
    except Exception:
        return {n: float(v) for n, v in graph.degree(weight="weight")}


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
    """
    改进版：优先使用spaCy NER（过滤类型），否则使用jieba关键词/词性+停用词
    """
    if not text.strip():
        return []

    # ---------- 1. 尝试spaCy NER（如果可用且有模型）----------
    try:
        import spacy

        try:
            nlp = spacy.load("en_core_web_sm")  # 英文模型
        except:
            # 若无英文模型，尝试中文模型
            try:
                nlp = spacy.load("zh_core_web_sm")
            except:
                nlp = spacy.blank("en")  # 空白模型无NER能力

        doc = nlp(text)

        # 定义希望保留的实体类型（根据语言调整）
        if doc.lang_ == "zh":
            keep_types = {
                "PERSON",
                "ORG",
                "GPE",
                "LOC",
                "PRODUCT",
                "EVENT",
                "WORK_OF_ART",
                "LAW",
            }
        else:
            keep_types = {
                "PERSON",
                "ORG",
                "GPE",
                "LOC",
                "PRODUCT",
                "EVENT",
                "WORK_OF_ART",
                "LAW",
                "LANGUAGE",
            }

        ents = []
        for ent in doc.ents:
            if ent.label_ in keep_types:
                # 去除停用词（实体文本可能包含停用词，可以进一步处理）
                clean = ent.text.strip()
                if clean and clean not in STOPWORDS:
                    ents.append(clean)

        # 去重后返回
        if ents:
            seen = set()
            uniq = []
            for e in ents:
                if e not in seen:
                    seen.add(e)
                    uniq.append(e)
            return uniq[:top_k]
    except Exception as e:
        # 静默失败，继续尝试其他方法
        pass

    # ---------- 2. 尝试jieba关键词提取（TF-IDF）----------
    try:
        import jieba.analyse as analyse

        # 设置停用词（analyse.extract_tags 可以接受停用词列表）
        tags = analyse.extract_tags(
            text, topK=top_k, allowPOS=("n", "nr", "ns", "nt", "nz", "vn")
        )
        # 进一步过滤停用词
        tags = [t for t in tags if t not in STOPWORDS]
        return tags[:top_k]
    except Exception:
        pass

    # ---------- 3. 回退：jieba分词 + 词性过滤 + 停用词----------
    try:
        import jieba.posseg as pseg

        words = []
        for word, flag in pseg.cut(text):
            # 保留名词、专名、动词（可调整）
            if flag.startswith(("n", "nr", "ns", "nt", "nz", "v")):
                if len(word) > 1 and word not in STOPWORDS:
                    words.append(word)
        # 统计词频并排序
        from collections import Counter

        freq = Counter(words)
        sorted_words = [w for w, _ in freq.most_common(top_k)]
        return sorted_words
    except Exception:
        pass

    # ---------- 4. 最后防线：中英文正则分词 + 停用词----------
    import re

    raw_tokens = re.findall(r"[\u4e00-\u9fff]{2,6}|[A-Za-z][A-Za-z0-9_-]{2,}", text)
    tokens = [
        t for t in raw_tokens if t not in STOPWORDS and t.lower() not in STOPWORDS
    ]
    from collections import Counter

    freq = Counter(tokens)
    return [w for w, _ in freq.most_common(top_k)]


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
def extract_knowledge_graph(
    ppt_path: Optional[str] = None,
    text: Optional[str] = None,
    top_k_entities: int = 50,
    min_occur: Optional[int] = None,
    min_len: Optional[int] = None,
    max_len: Optional[int] = None,
    min_edge_weight: Optional[int] = None,
    centrality_metric: Optional[str] = None,
    top_n_core: Optional[int] = None,
    adaptive_top_n: Optional[bool] = None,
    keep_seed_entities: Optional[bool] = None,
    seed_from_title: Optional[bool] = None,
    entity_blacklist: Optional[List[str]] = None,
) -> Dict:
    """
    传入 `ppt_path`（.pptx 文件路径）或直接传入 `text`，返回知识图谱数据结构。
    核心修复：强制返回字典，永不返回 None
    """
    if not ppt_path and not text:
        raise ValueError("ppt_path 或 text 其中之一必须提供")

    defaults = _load_kg_defaults()
    top_k_entities = (
        int(defaults.get("top_k_entities", top_k_entities))
        if top_k_entities == 50
        else int(top_k_entities)
    )
    min_occur = int(defaults.get("min_occur", 2) if min_occur is None else min_occur)
    min_len = int(defaults.get("min_len", 2) if min_len is None else min_len)
    max_len = int(defaults.get("max_len", 10) if max_len is None else max_len)
    min_edge_weight = int(
        defaults.get("min_edge_weight", 2)
        if min_edge_weight is None
        else min_edge_weight
    )
    centrality_metric = str(
        defaults.get("centrality_metric", "pagerank")
        if centrality_metric is None
        else centrality_metric
    )
    if top_n_core is None:
        top_n_core = defaults.get("top_n_core", None)
    if adaptive_top_n is None:
        adaptive_top_n = bool(defaults.get("adaptive_top_n", True))
    if keep_seed_entities is None:
        keep_seed_entities = bool(defaults.get("keep_seed_entities", True))
    if seed_from_title is None:
        seed_from_title = bool(defaults.get("seed_from_title", True))
    entity_blacklist_cfg = (
        defaults.get("entity_blacklist", [])
        if entity_blacklist is None
        else entity_blacklist
    )

    blacklist = set(ENTITY_BLACKLIST)
    if isinstance(entity_blacklist_cfg, list):
        blacklist.update(
            [str(i).strip() for i in entity_blacklist_cfg if str(i).strip()]
        )

    slides = []
    if ppt_path:
        slides = _extract_text_from_pptx(ppt_path)
    else:
        slides = [text] if text and text.strip() else []

    slides = [s for s in slides if s.strip()]

    slide_entities: List[List[str]] = []
    slide_summaries: List[Dict] = []
    all_entities = {}
    seed_entities = set()
    if seed_from_title:
        for seed in _extract_seed_entities_from_titles(slides):
            if _is_valid_entity(
                seed, min_len=min_len, max_len=max_len, blacklist=blacklist
            ):
                seed_entities.add(seed)

    for s in slides:
        raw_ents = _simple_entity_extraction(s, top_k=top_k_entities)
        ents = []
        for e in raw_ents:
            ent = (e or "").strip()
            if _is_valid_entity(
                ent, min_len=min_len, max_len=max_len, blacklist=blacklist
            ):
                ents.append(ent)
        ents = list(dict.fromkeys(ents))
        key_sentences = _extract_key_sentences(s, top_k=3)
        slide_entities.append(ents)
        slide_summaries.append({"text": s, "key_points": key_sentences})
        for e in ents:
            all_entities[e] = all_entities.get(e, 0) + 1

    original_node_count = len(all_entities)
    filtered_entities = {e: cnt for e, cnt in all_entities.items() if cnt >= min_occur}
    if not filtered_entities:
        filtered_entities = dict(all_entities)

    ranked_entities = sorted(
        filtered_entities.items(), key=lambda x: x[1], reverse=True
    )
    ranked_entities = ranked_entities[: max(top_k_entities, 0)]
    candidate_set = {ent for ent, _ in ranked_entities}

    from collections import defaultdict

    edge_counts = defaultdict(int)
    for ents in slide_entities:
        uniq = [e for e in dict.fromkeys(ents) if e in candidate_set]
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                if a == b:
                    continue
                key = tuple(sorted((a, b)))
                edge_counts[key] += 1

    pruned_edge_counts = {
        (a, b): w for (a, b), w in edge_counts.items() if w >= min_edge_weight
    }

    try:
        import networkx as nx

        candidate_graph = nx.Graph()
        for ent, cnt in ranked_entities:
            candidate_graph.add_node(ent, count=cnt)
        for (a, b), w in pruned_edge_counts.items():
            if a in candidate_graph and b in candidate_graph:
                candidate_graph.add_edge(a, b, weight=w, relation="cooccurrence")

        scores = _compute_node_scores(candidate_graph, metric=centrality_metric)
    except Exception:
        scores = {ent: float(cnt) for ent, cnt in ranked_entities}

    total_candidates = len(ranked_entities)
    if adaptive_top_n:
        keep_n = _resolve_adaptive_top_n(total_candidates)
    else:
        keep_n = total_candidates
    if top_n_core is not None:
        keep_n = min(int(top_n_core), total_candidates)
    keep_n = min(max(keep_n, 1), total_candidates) if total_candidates > 0 else 0

    sorted_by_score = sorted(
        ranked_entities,
        key=lambda x: (scores.get(x[0], 0.0), x[1]),
        reverse=True,
    )
    selected_entities = {ent for ent, _ in sorted_by_score[:keep_n]}
    if keep_seed_entities and seed_entities:
        selected_entities.update([e for e in seed_entities if e in candidate_set])

    final_ranked = [item for item in sorted_by_score if item[0] in selected_entities]

    nodes = []
    id_map = {}
    for idx, (ent, cnt) in enumerate(final_ranked):
        nid = str(idx + 1)
        id_map[ent] = nid
        nodes.append(
            {
                "id": nid,
                "label": ent,
                "count": cnt,
                "score": round(float(scores.get(ent, 0.0)), 6),
            }
        )

    edges = []
    for (a, b), w in pruned_edge_counts.items():
        if a in id_map and b in id_map:
            edges.append(
                {
                    "source": id_map[a],
                    "target": id_map[b],
                    "weight": w,
                    "relation": "cooccurrence",
                }
            )

    result = {"nodes": nodes, "edges": edges, "slides_summary": slide_summaries}

    logger.info(
        f"Extracted KG: raw_nodes={original_node_count}, filtered_nodes={len(nodes)}, "
        f"raw_edges={len(edge_counts)}, filtered_edges={len(edges)}, "
        f"min_occur={min_occur}, min_edge_weight={min_edge_weight}, centrality={centrality_metric}, keep_n={keep_n}"
    )
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

        rel = Relationship(
            src_node,
            rel_type,
            tgt_node,
            weight=e.get("weight", 1),
            relation=e.get("relation", "cooccurrence"),
        )
        graph.merge(rel)
        created_rels += 1

    return {"nodes_created": created_nodes, "rels_created": created_rels}


@YA_MCPServer_Tool(
    name="export_kg_visualization",
    title="Export KG Visualization",
    description="导出知识图谱为 GraphML 或 PNG 可视化文件",
)
def export_kg_visualization(
    kg: Dict, path: str = "kg.graphml", format: str = "graphml"
) -> Dict:
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
            "message": "空图谱，跳过导出",
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
    node_by_id = {}

    # 添加节点
    for n in nodes:
        label = n.get("label")
        if label is None:
            continue
        node_id = str(n.get("id")) if n.get("id") is not None else None
        if node_id:
            node_by_id[node_id] = label
        G.add_node(label, count=n.get("count", 1), score=n.get("score", 0.0))

    # 添加边
    for e in edges:
        src = node_by_id.get(str(e.get("source")), e.get("source"))
        tgt = node_by_id.get(str(e.get("target")), e.get("target"))
        if src is None or tgt is None:
            continue
        if src == tgt:
            continue
        G.add_edge(
            src,
            tgt,
            weight=e.get("weight", 1),
            relation=e.get("relation", "cooccurrence"),
        )

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
            plt.rcParams["font.sans-serif"] = [
                "SimHei",
                "Microsoft YaHei",
                "DejaVu Sans",
            ]
            plt.rcParams["axes.unicode_minus"] = False
        except Exception:
            raise RuntimeError("matplotlib 未安装，无法导出 PNG")

        plt.figure(figsize=(14, 10))
        # 关键修复：确保pos永远不为None
        try:
            pos = nx.spring_layout(
                G, seed=42, k=0.8 / (max(G.number_of_nodes(), 1) ** 0.5), iterations=100
            )
        except Exception as e:
            logger.warning(f"spring布局失败：{e}，使用圆形布局")
            pos = nx.circular_layout(G)

        # 双重保险：如果pos还是None，手动构造简单布局
        if pos is None or len(pos) == 0:
            pos = {node: (i, 0) for i, node in enumerate(G.nodes())}

        node_scores = _compute_node_scores(G, metric="pagerank")
        if not node_scores:
            node_scores = {n: float(G.nodes[n].get("count", 1)) for n in G.nodes()}

        max_score = max(node_scores.values()) if node_scores else 1.0
        min_score = min(node_scores.values()) if node_scores else 0.0
        span = max(max_score - min_score, 1e-9)

        def _norm_size(v: float) -> float:
            ratio = (v - min_score) / span
            return 300 + ratio * 2200

        sizes = [_norm_size(node_scores.get(n, 0.0)) for n in G.nodes()]
        colors = [node_scores.get(n, 0.0) for n in G.nodes()]

        edge_weights = [float(G[u][v].get("weight", 1)) for u, v in G.edges()]
        max_w = max(edge_weights) if edge_weights else 1.0
        edge_widths = (
            [0.8 + 3.0 * (w / max_w) for w in edge_weights] if edge_weights else 0.8
        )

        rank_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)
        label_topn = 35 if len(rank_nodes) > 35 else len(rank_nodes)
        label_nodes = {name for name, _ in rank_nodes[:label_topn]}
        labels = {n: n for n in G.nodes() if n in label_nodes}

        # 绘图（增加异常捕获）
        try:
            nx.draw_networkx_nodes(
                G, pos, node_size=sizes, node_color=colors, cmap=plt.cm.Blues, alpha=0.9
            )
            nx.draw_networkx_edges(
                G, pos, alpha=0.35, edge_color="#666666", width=edge_widths
            )
            nx.draw_networkx_labels(
                G, pos, labels, font_size=9, font_family="sans-serif"
            )
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
    top_k_entities: int = 50,
    min_occur: Optional[int] = None,
    min_len: Optional[int] = None,
    max_len: Optional[int] = None,
    min_edge_weight: Optional[int] = None,
    centrality_metric: Optional[str] = None,
    top_n_core: Optional[int] = None,
    adaptive_top_n: Optional[bool] = None,
    keep_seed_entities: Optional[bool] = None,
    seed_from_title: Optional[bool] = None,
    entity_blacklist: Optional[List[str]] = None,
    write_neo4j: bool = False,
    neo_uri: str = "bolt://localhost:7687",
    neo_user: str = "neo4j",
    neo_password: str = "neo4j",
    export_format: str = "graphml",
    export_path: str = "kg_output",
) -> Dict:
    logger.info(
        f"process_and_publish_kg called with ppt_path={ppt_path!r}, text_len={len(text) if text else 0}, write_neo4j={write_neo4j}, export_format={export_format}, export_path={export_path}"
    )
    neo_result = None
    export_result = None
    try:
        # 抽取图谱（已确保返回字典）
        kg = extract_knowledge_graph(
            ppt_path=ppt_path,
            text=text,
            top_k_entities=top_k_entities,
            min_occur=min_occur,
            min_len=min_len,
            max_len=max_len,
            min_edge_weight=min_edge_weight,
            centrality_metric=centrality_metric,
            top_n_core=top_n_core,
            adaptive_top_n=adaptive_top_n,
            keep_seed_entities=keep_seed_entities,
            seed_from_title=seed_from_title,
            entity_blacklist=entity_blacklist,
        )
        logger.info(
            f"KG extraction complete: nodes={len(kg.get('nodes', []))} edges={len(kg.get('edges', []))}"
        )

        # 写入Neo4j（可选）
        if write_neo4j:
            logger.info("Writing KG to Neo4j")
            try:
                neo_result = write_kg_to_neo4j(
                    kg, uri=neo_uri, user=neo_user, password=neo_password
                )
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
        return {
            "kg": {"nodes": [], "edges": [], "slides_summary": []},
            "neo_result": None,
            "export_result": {"error": str(exc)},
        }


# 测试入口
if __name__ == "__main__":
    # 快速测试：抽取文本图谱并导出PNG
    test_kg = extract_knowledge_graph(
        text="张三是李四的同学，李四是北京大学的学生，北京大学位于北京市"
    )
    print("测试图谱结果：")
    print(f"节点数：{len(test_kg['nodes'])}，边数：{len(test_kg['edges'])}")

    # 导出测试
    export_res = export_kg_visualization(test_kg, path="test_kg_output", format="png")
    print(f"导出结果：{export_res}")
