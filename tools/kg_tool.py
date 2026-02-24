from typing import Optional, List, Dict
import os
import sys
import re
import math

# 确保项目根目录导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ========== 定制化停用词/黑名单（适配AI架构与系统PPT）==========
STOPWORDS = set(
    """
的 了 在 是 我 你 他 她 它 我们 你们 他们 这个 那个 这些 那些 和 与 或 及 而 但 也 
a an the and or but if is are was were be been being have has had do does did will would shall should may might must can could of in on at to for with by from as into through during before after above below up down out off over under again further then once here there when where why how all any both each few more most other some such no nor not only own same so than too very s t can will just don should now
的话 之类 等等 左右 上下 前后 多少 大小 高低 长短 强弱 好坏 与否 可以 能够 应该 必须 需要 想要 打算 准备 开始 结束 进行 完成 实现 达到 超过 不足 缺乏 拥有 具有 包含 包括 涉及 关于 对于 至于 由于 因为 所以 因此 从而 进而 于是 然后 接着 此外 另外 同时 同样 相反 否则 除非 只要 只有 如果 假如 假设 比如 例如 举例 比如 诸如 像 如 若 即 也就是 换句话说 总的来说 总而言之 综上所述
引论 计划 研究 成果 浙江大学 计算机学院 人工智能研究所 高等教育出版社 文档 内容 章节 部分 框架 体系 结构 方法 技术 过程 结果 问题 原因 影响 发展 应用 系统 开发 运行 设计 优化 计算 处理 训练 推理 加速 支持 提供 实现 构建 封装 分配 调度 管理 协同 工作 能力 性能 效率 能耗 带宽 延时 资源
John Hennessy David Patterson ACM Turing 作者 教授 院士 出版社 出版 年份 章节 页码
"""
)

# 无意义前缀/后缀（AI领域定制）
MEANINGLESS_SUFFIX = {"的时代", "的发展", "的应用", "的技术", "的方法", "的过程", "的结果", "的问题", "的架构", "的框架"}
MEANINGLESS_PREFIX = {"基于", "通过", "利用", "采用", "实现", "达到", "超过", "不足", "缺乏", "面向", "针对"}

# AI架构领域专业名词白名单（强制保留）
AI_WHITELIST = {
    "GPU", "CPU", "TPU", "XPU", "DSP", "FLOPs", "SmartNIC", "人工智能芯片", "异构计算",
    "并行计算", "分布式训练", "数据并行", "张量并行", "流水线并行", "参数服务器",
    "Ring AllReduce", "类脑芯片", "智能交换机", "存算分离", "冯诺依曼结构", "人工智能算法",
    "人工智能架构与系统", "芯片", "框架", "微计算模式", "神经网络训练任务",
    "人工智能基础软硬件", "人工智能系统"
}

# 核心实体黑名单（适配PPT，过滤冗余标题/通用词/人名/无意义短语）
ENTITY_BLACKLIST = {
    "介绍", "概述", "总结", "例子", "示例", "例如", "因此", "然后", "其中", "以及",
    "我们", "你们", "他们", "这个", "那个", "一种", "用于", "可以", "通过", "进行",
    "使用", "101计划", "人工智能引论", "君子性非异也", "善假于物", "延伸阅读", "咸与维新",
    "John", "Hennessy", "David", "Patterson", "ACM", "Turing", "作者", "教授", "院士",
    "数据是燃料", "模型是引擎", "算力是加速器", "和推理是数据密集", "年度图灵奖"
}

try:
    from tools import YA_MCPServer_Tool
except ImportError:
    def YA_MCPServer_Tool(**kwargs):
        def decorator(func):
            return func
        return decorator

try:
    from modules.YA_Common.utils.logger import get_logger
except ImportError:
    import logging
    def get_logger(name):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        return logging.getLogger(name)

logger = get_logger("YA_MCPServer_KG_Tool-AI架构")

# ========== 配置项（定向优化，适配AI PPT的节点/边密度）==========
def _load_kg_defaults() -> Dict:
    return {
        "top_k_entities": 40,          # 大幅减少实体数量，只保留核心
        "min_occur": 3,                # 提高最低出现次数到3次，过滤低频噪音
        "min_len": 2,                  # 恢复2字符（适配GPU/TPU/XPU等核心缩写）
        "max_len": 10,                 # 限制最大长度，避免长句/短语
        "entity_blacklist": sorted(ENTITY_BLACKLIST),
        "min_edge_weight": 4,          # 大幅提高边权重阈值到4，只保留核心关系
        "centrality_metric": "pagerank",
        "core_node_count": 6,          # 核心节点6个（适配PPT核心概念：GPU/TPU/芯片/并行等）
        "subcore_node_count": 12,      # 次核心节点12个，覆盖重要子概念
        "core_radius": 0.5,            # 核心半径更小，更紧凑聚焦
        "subcore_radius": 1.8,         # 次核心半径适中
        "periphery_radius": 3.2,       # 外围半径合理，避免节点拥挤
        "edge_alpha": 0.15,            # 边透明度更低，减少视觉干扰
        "core_node_size": 2800,        # 核心节点更大，突出重点
        "subcore_node_size": 1300,     # 次核心节点大小适中
        "periphery_node_size": 300,    # 外围节点更小，不抢焦点
        "edge_arc_rad": 0.03,          # 边弧形半径更小，避免边重叠
        "label_font_size": 11,         # 标签字体大小，适配节点密度
    }

# ========== 实体清洗与过滤（核心优化，解决关键字不准确/空节点）==========
def _clean_entity(entity: str) -> str:
    """AI领域定制实体清洗，移除无意义前缀/后缀，标准化缩写"""
    ent = entity.strip()
    # 移除无意义前缀
    for prefix in MEANINGLESS_PREFIX:
        if ent.startswith(prefix):
            ent = ent[len(prefix):].strip()
            break
    # 移除无意义后缀
    for suffix in MEANINGLESS_SUFFIX:
        if ent.endswith(suffix):
            ent = ent[:-len(suffix)].strip()
            break
    # AI领域缩写标准化（避免重复/错误）
    ent = ent.replace("GPU", "GPU").replace("TPU", "TPU").replace("XPU", "XPU")
    ent = ent.replace("AI芯片", "人工智能芯片").replace("异构计算", "异构计算")
    return ent

def _is_valid_entity(entity: str, min_len: int, max_len: int, blacklist: set) -> bool:
    """
    极致实体过滤规则（解决空节点/关键字不准确）
    1. 强制保留AI专业名词白名单
    2. 过滤人名、机构名、无意义短语（如“xx是xx”）
    3. 过滤包含过多虚词的碎片化文本
    """
    # 基础清洗
    ent = _clean_entity(entity)
    
    # 强制保留白名单中的专业名词
    if ent in AI_WHITELIST:
        return True
    
    # 空值/长度过滤
    if not ent or len(ent) < min_len or len(ent) > max_len:
        return False
    
    # 黑名单/停用词过滤（优先过滤无意义短语）
    if ent in STOPWORDS or ent in blacklist:
        return False
    
    # 过滤人名（包含英文大写开头的词）
    if re.match(r"^[A-Z][a-z]+$", ent):
        return False
    
    # 过滤“xx是xx”句式的无意义短语
    if re.search(r"是.+$", ent) and len(ent) > 8:
        return False
    
    # 纯符号/纯数字过滤（保留GPU/TPU等字母缩写）
    if re.fullmatch(r"[\W_]+", ent) or (re.fullmatch(r"\d+(\.\d+)?", ent) and not re.search(r"[A-Za-z]", ent)):
        return False
    
    # 过滤包含标点的碎片化文本
    if any(char in ent for char in "：；！？，。,.!?;:()（）[]【】"):
        return False
    
    # 过滤仅由虚词构成的短语
    function_words = {"的", "地", "得", "是", "了", "着", "过"}
    char_list = [c for c in ent if c in function_words]
    if len(char_list) >= len(ent) / 2:
        return False
    
    return True

# ========== 实体提取（定制化，适配AI PPT专业名词）==========
def _extract_seed_entities_from_titles(slides: List[str], top_k_each: int = 5) -> List[str]:
    """从PPT标题提取种子实体，优先锁定核心概念"""
    seeds = []
    for s in slides:
        lines = [ln.strip() for ln in (s or "").splitlines() if ln and ln.strip()]
        if not lines:
            continue
        title = lines[0]
        # 过滤PPT冗余标题，只提取有效内容
        if any(kw in title for kw in ["人工智能引论", "第九章", "一、", "二、", "三、"]):
            title = re.sub(r"人工智能引论|第九章|[\u4e00-\u96f9]、", "", title).strip()
        if title:
            title_ents = _simple_entity_extraction(title, top_k=top_k_each)
            seeds.extend(title_ents)
    return list(dict.fromkeys(seeds))

def _simple_entity_extraction(text: str, top_k: int = 50) -> List[str]:
    """
    AI领域定制实体提取（解决关键字不准确）
    1. 优先提取白名单中的专业名词
    2. 强化AI专业名词识别
    3. 过滤通用动词/形容词/人名/无意义短语
    """
    if not text.strip():
        return []
    
    # 第一步：手动提取AI领域核心专业名词（兜底，确保关键概念不丢失）
    ai_pro_nouns = re.findall(
        r"GPU|TPU|XPU|DSP|FLOPs|SmartNIC|MindSpore|PaddlePaddle|TensorFlow|PyTorch|异构计算|并行计算|分布式训练|数据并行|张量并行|流水线并行|参数服务器|Ring AllReduce|类脑芯片|智能交换机|存算分离|冯诺依曼结构|人工智能芯片|人工智能算法|人工智能架构与系统|芯片|框架|微计算模式|神经网络训练任务|人工智能基础软硬件|人工智能系统",
        text
    )
    
    # 第二步：jieba提取名词类实体，补充非缩写专业词
    try:
        import jieba
        import jieba.analyse as analyse
        # 只提取名词类，彻底过滤动词/形容词
        tags = analyse.extract_tags(
            text,
            topK=top_k + len(ai_pro_nouns),
            allowPOS=("n", "nr", "ns", "nt", "nz", "nw", "专名"),
            withWeight=False
        )
        # 合并手动提取的专业名词，去重
        all_ents = ai_pro_nouns + tags
        # 清洗和过滤
        all_ents = [_clean_entity(t) for t in all_ents]
        all_ents = [t for t in all_ents if t and t not in STOPWORDS and not re.match(r"^[A-Z][a-z]+$", t) and not re.search(r"是.+$", t)]
        # 去重并保留前top_k
        uniq_ents = list(dict.fromkeys(all_ents))
        return uniq_ents[:top_k]
    except Exception as e:
        logger.warning(f"Jieba提取失败，使用正则兜底: {e}")
        pass
    
    # 第三步：正则兜底，提取中文名词+AI缩写
    raw_tokens = re.findall(r"[A-Za-z0-9_-]{2,8}|[\u4e00-\u9fff]{2,8}", text)
    tokens = [_clean_entity(t) for t in raw_tokens if t not in STOPWORDS and not re.match(r"^[A-Z][a-z]+$", t) and not re.search(r"是.+$", t)]
    tokens = [t for t in tokens if _is_valid_entity(t, 2, 10, set())]
    from collections import Counter
    freq = Counter(tokens)
    return [w for w, _ in freq.most_common(top_k)]

# ========== 基础工具函数（保留，轻微优化）==========
def _compute_node_scores(graph, metric: str = "pagerank") -> Dict[str, float]:
    """计算节点重要性，优先PageRank，兜底度中心性"""
    try:
        import networkx as nx
    except Exception:
        return {n: 1.0 for n in graph.nodes()}
    if graph.number_of_nodes() == 0:
        return {}
    metric_l = (metric or "pagerank").lower()
    try:
        if metric_l == "degree":
            return {n: float(v) for n, v in graph.degree(weight="weight")}
        elif metric_l == "betweenness":
            return nx.betweenness_centrality(graph, normalized=True, weight="weight")
        else:
            return nx.pagerank(graph, alpha=0.85, weight="weight")
    except Exception:
        return {n: float(v) for n, v in graph.degree(weight="weight")}

def _extract_text_from_pptx(path: str) -> List[str]:
    """提取PPT文本，过滤空白幻灯片/冗余图片标注"""
    try:
        from pptx import Presentation
    except Exception:
        raise RuntimeError("python-pptx is required to parse PPTX files, 请安装：pip install python-pptx")
    if not os.path.exists(path):
        raise FileNotFoundError(f"PPT文件不存在：{path}")
    prs = Presentation(path)
    slides_text = []
    for slide in prs.slides:
        parts = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text = shape.text.strip()
                # 过滤PPT图片标注/冗余字符
                if text and not re.match(r"tmp/|img|图\d+\.\d+", text):
                    parts.append(text)
        slide_text = "\n".join(parts)
        if slide_text:
            slides_text.append(slide_text)
        else:
            logger.warning("跳过空白/仅图片幻灯片")
    return slides_text

def _split_sentences_chinese(text: str) -> List[str]:
    """中文分句，适配PPT文本格式"""
    if not text:
        return []
    text = text.strip()
    parts = re.split(r"(?<=[。！？；\n])\s*", text)
    return [p.strip() for p in parts if p and len(p.strip()) > 5]

def _extract_key_sentences(text: str, top_k: int = 3) -> List[str]:
    """提取关键句，保留PPT核心内容"""
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

# ========== 核心函数1：抽取知识图谱（无空节点/关键字精准）==========
@YA_MCPServer_Tool(
    name="extract_knowledge_graph",
    title="Extract Knowledge Graph",
    description="从AI架构与系统PPT中抽取精准知识图谱，无空节点、关键字准确"
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
    core_node_count: Optional[int] = None,
    subcore_node_count: Optional[int] = None,
    core_radius: Optional[float] = None,
    subcore_radius: Optional[float] = None,
    periphery_radius: Optional[float] = None,
    entity_blacklist: Optional[List[str]] = None,
) -> Dict:
    if not ppt_path and not text:
        raise ValueError("ppt_path 或 text 其中之一必须提供")
    # 加载配置
    defaults = _load_kg_defaults()
    top_k_entities = int(defaults.get("top_k_entities", top_k_entities))
    min_occur = int(defaults.get("min_occur", 3) if min_occur is None else min_occur)
    min_len = int(defaults.get("min_len", 2) if min_len is None else min_len)
    max_len = int(defaults.get("max_len", 10) if max_len is None else max_len)
    min_edge_weight = int(defaults.get("min_edge_weight", 4) if min_edge_weight is None else min_edge_weight)
    centrality_metric = str(defaults.get("centrality_metric", "pagerank") if centrality_metric is None else centrality_metric)
    # 构建黑名单（基础+定制）
    blacklist = set(ENTITY_BLACKLIST)
    entity_blacklist_cfg = defaults.get("entity_blacklist", []) if entity_blacklist is None else entity_blacklist
    if isinstance(entity_blacklist_cfg, list):
        blacklist.update([str(i).strip() for i in entity_blacklist_cfg if str(i).strip()])
    # 提取PPT/文本内容
    slides = []
    if ppt_path:
        slides = _extract_text_from_pptx(ppt_path)
    else:
        slides = [text] if text and text.strip() else []
    slides = [s for s in slides if s.strip()]
    if not slides:
        logger.warning("无有效文本可提取")
        return {"nodes": [], "edges": [], "slides_summary": []}
    # 提取实体+种子实体（从标题提取，确保核心概念不丢失）
    slide_entities: List[List[str]] = []
    slide_summaries: List[Dict] = []
    all_entities = {}
    seed_entities = set(_extract_seed_entities_from_titles(slides))
    seed_entities = {e for e in seed_entities if _is_valid_entity(e, min_len, max_len, blacklist)}
    logger.info(f"从标题提取种子核心实体：{seed_entities}")
    # 遍历幻灯片提取实体
    for s in slides:
        raw_ents = _simple_entity_extraction(s, top_k=top_k_entities)
        # 严格过滤实体，确保无空节点/无意义节点
        ents = [e for e in raw_ents if _is_valid_entity(e, min_len, max_len, blacklist)]
        ents = list(dict.fromkeys(ents))  # 去重
        # 强制加入种子实体和白名单实体，确保核心概念保留
        ents = list(set(ents + list(seed_entities) + list(AI_WHITELIST)))
        slide_entities.append(ents)
        slide_summaries.append({"text": s, "key_points": _extract_key_sentences(s)})
        # 统计实体出现次数
        for e in ents:
            all_entities[e] = all_entities.get(e, 0) + 1
    # 过滤低频实体
    filtered_entities = {e: cnt for e, cnt in all_entities.items() if cnt >= min_occur}
    if not filtered_entities:
        filtered_entities = dict(all_entities)
    ranked_entities = sorted(filtered_entities.items(), key=lambda x: x[1], reverse=True)
    ranked_entities = ranked_entities[: max(top_k_entities, 0)]
    candidate_set = {ent for ent, _ in ranked_entities}
    logger.info(f"过滤后候选实体（{len(candidate_set)}个）：{[e for e, _ in ranked_entities]}")
    # 构建边：确保**两两节点仅一条边**，按共现次数加权
    from collections import defaultdict
    edge_counts = defaultdict(lambda: defaultdict(int))
    for ents in slide_entities:
        uniq = [e for e in dict.fromkeys(ents) if e in candidate_set]
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                if a == b:
                    continue
                if a > b:  # 标准化边的key，避免(a,b)和(b,a)重复
                    a, b = b, a
                edge_counts[a][b] += 1
    # 过滤低权重边，精简杂乱边
    pruned_edge_counts = {}
    for a, others in edge_counts.items():
        for b, w in others.items():
            if w >= min_edge_weight:
                pruned_edge_counts[(a, b)] = w
    # 计算节点重要性
    try:
        import networkx as nx
        candidate_graph = nx.Graph()
        for ent, cnt in ranked_entities:
            candidate_graph.add_node(ent, count=cnt)
        for (a, b), w in pruned_edge_counts.items():
            if a in candidate_graph and b in candidate_graph:
                candidate_graph.add_edge(a, b, weight=w)
        scores = _compute_node_scores(candidate_graph, metric=centrality_metric)
    except Exception as e:
        logger.warning(f"计算节点分数失败，使用词频兜底: {e}")
        scores = {ent: float(cnt) for ent, cnt in ranked_entities}
    # 构建最终节点和边
    sorted_by_score = sorted(ranked_entities, key=lambda x: (scores.get(x[0], 0.0), x[1]), reverse=True)
    final_ranked = sorted_by_score
    nodes = []
    id_map = {}
    for idx, (ent, cnt) in enumerate(final_ranked):
        nid = str(idx + 1)
        id_map[ent] = nid
        nodes.append({
            "id": nid,
            "label": ent,
            "count": cnt,
            "score": round(float(scores.get(ent, 0.0)), 6),
        })
    edges = []
    for (a, b), w in pruned_edge_counts.items():
        if a in id_map and b in id_map:
            edges.append({
                "source": id_map[a],
                "target": id_map[b],
                "weight": w,
                "relation": "cooccurrence",
            })
    # 日志统计
    logger.info(
        f"图谱抽取完成：原始实体{len(all_entities)}个 → 过滤后有效节点{len(nodes)}个 | "
        f"原始边{sum(len(v) for v in edge_counts.values())}条 → 过滤后唯一边{len(edges)}条"
    )
    return {"nodes": nodes, "edges": edges, "slides_summary": slide_summaries}

# ========== 核心函数2：写入Neo4j（保留，兼容现有逻辑）==========
@YA_MCPServer_Tool(
    name="write_kg_to_neo4j",
    title="Write KG to Neo4j",
    description="将AI知识图谱写入Neo4j，merge节点与关系"
)
def write_kg_to_neo4j(
    kg: Dict,
    uri: str = "bolt://localhost:7687",
    user: str = "neo4j",
    password: str = "neo4j",
    node_label: str = "AI_Entity",
    rel_type: str = "RELATED_TO",
) -> Dict:
    if not kg or not kg.get("nodes") or not kg.get("edges"):
        logger.warning("空图谱，跳过写入Neo4j")
        return {"nodes_created": 0, "rels_created": 0}
    try:
        from py2neo import Graph, Node, Relationship
    except Exception:
        raise RuntimeError("py2neo 未安装，请安装：pip install py2neo")
    graph = Graph(uri, auth=(user, password))
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])
    created_nodes = 0
    created_rels = 0
    # 写入节点（AI领域专属标签AI_Entity）
    for n in nodes:
        label = n.get("label")
        if not label:
            continue
        props = {"name": label, "count": n.get("count", 0), "score": n.get("score", 0.0), "domain": "人工智能架构与系统"}
        node = Node(node_label, **props)
        graph.merge(node, node_label, "name")
        created_nodes += 1
    # 写入关系（保留权重）
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
        if src_node and tgt_node:
            rel = Relationship(
                src_node, rel_type, tgt_node,
                weight=e.get("weight", 1),
                relation=e.get("relation", "cooccurrence"),
                domain="人工智能架构与系统"
            )
            graph.merge(rel)
            created_rels += 1
    logger.info(f"Neo4j写入完成：节点{created_nodes}个，关系{created_rels}条")
    return {"nodes_created": created_nodes, "rels_created": created_rels}

@YA_MCPServer_Tool(
    name="export_kg_visualization",
    title="Export KG Visualization",
    description="导出AI知识图谱可视化，按重要性分层发散，无空节点、边不杂乱、节点清晰"
)
def export_kg_visualization(
    kg: Dict, path: str = "kg.graphml", format: str = "graphml"
) -> Dict:
    if not kg or not kg.get("nodes") or not kg.get("edges"):
        logger.warning("空图谱，跳过可视化导出")
        return {"path": path, "format": format, "error": None, "message": "空图谱，跳过导出"}
    try:
        import networkx as nx
    except Exception:
        raise RuntimeError("networkx 未安装，请安装：pip install networkx")
    # 创建输出目录
    out_dir = os.path.dirname(path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
        logger.info(f"创建导出目录：{out_dir}")

    # ========== 关键修改：先过滤所有无意义/空标签节点 ==========
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])

    # 1. 过滤节点：只保留有有效标签的实体
    valid_nodes = []
    valid_node_ids = set()
    node_label_map = {}  # id -> label
    label_to_id = {}     # label -> id
    for n in nodes:
        label = n.get("label")
        if label is None or not label.strip():
            continue
        # 额外过滤：纯符号/纯数字/图片标注/公式
        if re.fullmatch(r"[\W_]+", label) or re.fullmatch(r"\d+(\.\d+)?", label):
            continue
        if re.match(r"^图\d+.*$", label) or re.match(r"^(tmp|img).*$", label):
            continue
        if re.search(r"[∑∫√×÷±≠≈∞∂∇∈∉⊂⊃∪∩∅∀∃¬∧∨→↔⇒⇔∴∵∼≅≡≤≥]", label):
            continue
        valid_nodes.append(n)
        valid_node_ids.add(n["id"])
        node_label_map[n["id"]] = label
        label_to_id[label] = n["id"]
    if not valid_nodes:
        logger.error("过滤后无有效节点，无法生成可视化")
        return {"path": path, "format": format, "error": "无有效节点"}

    # 2. 过滤边：只保留两端都是有效节点的边
    valid_edges = []
    for e in edges:
        src_id = e.get("source")
        tgt_id = e.get("target")
        if src_id in valid_node_ids and tgt_id in valid_node_ids:
            valid_edges.append(e)

    # 3. 用过滤后的节点和边重建图
    G = nx.Graph()
    node_score_map = {}
    for n in valid_nodes:
        label = n["label"]
        score = float(n.get("score", 0.0))
        node_score_map[label] = score
        G.add_node(label, count=n.get("count", 1), score=score)
    for e in valid_edges:
        src_label = node_label_map[e["source"]]
        tgt_label = node_label_map[e["target"]]
        if src_label != tgt_label and src_label in node_score_map and tgt_label in node_score_map:
            G.add_edge(src_label, tgt_label, weight=e.get("weight", 1))

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
            # 配置中文显示（强制生效，适配各种环境）
            plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans", "Arial Unicode MS"]
            plt.rcParams["axes.unicode_minus"] = False
            plt.rcParams['figure.dpi'] = 300
            plt.rcParams['savefig.dpi'] = 300
            plt.rcParams['savefig.facecolor'] = 'white'  # 白底，避免黑边
            plt.rcParams['savefig.bbox'] = 'tight'       # 紧凑布局，裁剪空白
        except Exception as e:
            raise RuntimeError(f"matplotlib 未安装/配置失败：{e}，请安装：pip install matplotlib")
        # 加载布局配置
        defaults = _load_kg_defaults()
        core_node_count = int(defaults.get("core_node_count", 6))
        subcore_node_count = int(defaults.get("subcore_node_count", 12))
        core_radius = float(defaults.get("core_radius", 0.5))
        subcore_radius = float(defaults.get("subcore_radius", 1.8))
        edge_alpha = float(defaults.get("edge_alpha", 0.15))
        edge_arc_rad = float(defaults.get("edge_arc_rad", 0.03))
        core_node_size = int(defaults.get("core_node_size", 2800))
        subcore_node_size = int(defaults.get("subcore_node_size", 1300))
        label_font_size = int(defaults.get("label_font_size", 11))

        # ========== 关键修改：只对有效节点进行分层布局 ==========
        # 按重要性严格分层，核心向四周发散
        sorted_nodes = sorted(node_score_map.items(), key=lambda x: x[1], reverse=True)
        core_nodes = [n for n, _ in sorted_nodes[:core_node_count]]  # 核心层（最中心）
        subcore_nodes = [n for n, _ in sorted_nodes[core_node_count:core_node_count+subcore_node_count]]  # 次核心层
        # 不再生成外围层，所有有效节点都在核心和次核心层
        all_visible_nodes = core_nodes + subcore_nodes
        logger.info(f"图谱分层：核心节点{core_nodes} | 次核心节点{len(subcore_nodes)}个 | 无外围空节点")

        # 计算分层布局（圆形发散，无重叠）
        pos = {}
        # 1. 核心节点：正中心紧凑布局
        core_count = len(core_nodes)
        for i, node in enumerate(core_nodes):
            angle = 2 * math.pi * i / core_count
            x = core_radius * math.cos(angle)
            y = core_radius * math.sin(angle)
            pos[node] = (x, y)
        # 2. 次核心节点：中层圆形布局
        subcore_count = len(subcore_nodes)
        for i, node in enumerate(subcore_nodes):
            angle = 2 * math.pi * i / subcore_count
            x = subcore_radius * math.cos(angle)
            y = subcore_radius * math.sin(angle)
            pos[node] = (x, y)

        # 过滤图G中的边，只保留两端都在pos中的边
        edges_to_draw = []
        for u, v, data in G.edges(data=True):
            if u in pos and v in pos:
                edges_to_draw.append((u, v, data))
        # 重建一个只包含可见节点和边的子图
        G_visible = nx.Graph()
        for node in all_visible_nodes:
            if node in node_score_map:
                G_visible.add_node(node, score=node_score_map[node])
        for u, v, data in edges_to_draw:
            G_visible.add_edge(u, v, weight=data.get("weight", 1))

        # 节点样式：颜色+大小双重区分层次，无视觉混淆
        sizes = []
        node_colors = []
        node_edgecolors = []  # 节点边框，增强区分度
        for n in G_visible.nodes():
            if n in core_nodes:
                sizes.append(core_node_size)
                node_colors.append("#1f77b4")  # 深蓝色（核心）
                node_edgecolors.append("#ffffff")  # 白色粗边框
            elif n in subcore_nodes:
                sizes.append(subcore_node_size)
                node_colors.append("#ff7f0e")  # 橙色（次核心）
                node_edgecolors.append("#ffffff")  # 白色边框
            else:
                # 所有其他节点（如果有）都用次核心样式，不再生成外围空点
                sizes.append(subcore_node_size)
                node_colors.append("#ff7f0e")
                node_edgecolors.append("#ffffff")

        # 边样式：粗细按权重+弧形+低透明度，解决边杂乱
        edge_weights = [float(d.get("weight", 1)) for u, v, d in G_visible.edges(data=True)]
        max_w = max(edge_weights) if edge_weights else 1.0
        edge_widths = [0.8 + 2.2 * (w / max_w) for w in edge_weights]  # 权重越大，边越粗

        # 标签配置：仅显示核心+次核心，避免文字拥挤，标签带背景更清晰
        label_nodes = set(core_nodes + subcore_nodes)
        labels = {n: n for n in G_visible.nodes() if n in label_nodes}

        # 开始绘图（大画布，适配分层布局）
        plt.figure(figsize=(20, 16))
        # 绘制边：弧形+低透明度，彻底解决边重叠/杂乱
        nx.draw_networkx_edges(
            G_visible, pos,
            alpha=edge_alpha,
            edge_color="#888888",  # 灰色边，不抢节点焦点
            width=edge_widths,
            connectionstyle=f"arc3,rad={edge_arc_rad}"  # 弧形边，避免交叉重叠
        )
        # 绘制节点：带白色边框，层次更清晰
        nx.draw_networkx_nodes(
            G_visible, pos,
            node_size=sizes,
            node_color=node_colors,
            alpha=0.95,
            edgecolors=node_edgecolors,
            linewidths=2 if core_node_count > 0 else 1  # 核心节点边框更粗
        )
        # 绘制标签：带半透明黑色背景，文字清晰不被遮挡
        nx.draw_networkx_labels(
            G_visible, pos, labels,
            font_size=label_font_size,
            font_family="sans-serif",
            font_weight="bold",
            font_color="white",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.7)  # 标签背景
        )
        # 美化：隐藏坐标轴，紧凑布局
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.1)
        plt.close()
        logger.info(f"PNG可视化导出完成：{path}")
    else:
        raise ValueError(f"不支持的导出格式: {format}，仅支持graphml/gexf/png")
    return {"path": path, "format": fmt, "node_count": len(G.nodes()), "edge_count": len(G.edges())}


# ========== 核心函数4：一站式处理（抽取+导出+可选写入Neo4j）==========
@YA_MCPServer_Tool(
    name="process_and_publish_kg",
    title="Process and Publish KG",
    description="一站式处理AI架构PPT：抽取图谱+导出可视化+可选写入Neo4j"
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
    core_node_count: Optional[int] = None,
    subcore_node_count: Optional[int] = None,
    core_radius: Optional[float] = None,
    subcore_radius: Optional[float] = None,
    periphery_radius: Optional[float] = None,
    entity_blacklist: Optional[List[str]] = None,
    write_neo4j: bool = False,
    neo_uri: str = "bolt://localhost:7687",
    neo_user: str = "neo4j",
    neo_password: str = "neo4j",
    export_format: str = "graphml",
    export_path: str = "ai_kg_output",
) -> Dict:
    logger.info(f"开始一站式处理AI架构与系统图谱 | PPT路径：{ppt_path} | 导出格式：{export_format}")
    neo_result = None
    export_result = None
    try:
        # 1. 抽取图谱
        kg = extract_knowledge_graph(
            ppt_path=ppt_path,
            text=text,
            top_k_entities=top_k_entities,
            min_occur=min_occur,
            min_len=min_len,
            max_len=max_len,
            min_edge_weight=min_edge_weight,
            centrality_metric=centrality_metric,
            core_node_count=core_node_count,
            subcore_node_count=subcore_node_count,
            core_radius=core_radius,
            subcore_radius=subcore_radius,
            periphery_radius=periphery_radius,
            entity_blacklist=entity_blacklist,
        )
        # 2. 可选写入Neo4j
        if write_neo4j:
            logger.info("开始写入Neo4j图数据库")
            try:
                neo_result = write_kg_to_neo4j(kg, uri=neo_uri, user=neo_user, password=neo_password)
            except Exception as e:
                neo_result = {"error": str(e)}
                logger.error(f"Neo4j写入失败: {e}", exc_info=True)
        # 3. 导出可视化
        logger.info("开始导出图谱可视化")
        fmt = export_format.lower()
        # 拼接导出路径（自动加后缀）
        if fmt == "png":
            out_file = f"{export_path}.png"
        elif fmt == "gexf":
            out_file = f"{export_path}.gexf"
        else:
            out_file = f"{export_path}.graphml"
        try:
            export_result = export_kg_visualization(kg, path=out_file, format=fmt)
        except Exception as e:
            export_result = {"error": str(e)}
            logger.error(f"可视化导出失败: {e}", exc_info=True)
        # 处理完成
        logger.info("AI架构与系统图谱一站式处理完成！")
        return {
            "kg": kg,
            "neo_result": neo_result,
            "export_result": export_result,
            "status": "success" if not (neo_result and "error" in neo_result) and not (export_result and "error" in export_result) else "partial_success"
        }
    except Exception as exc:
        logger.error(f"一站式处理失败: {exc}", exc_info=True)
        return {
            "kg": {"nodes": [], "edges": [], "slides_summary": []},
            "neo_result": None,
            "export_result": {"error": str(exc)},
            "status": "failed"
        }

# ========== 测试入口（直接运行可测试AI PPT图谱提取）==========
if __name__ == "__main__":
    # 测试：替换为你的AI PPT路径
    TEST_PPT_PATH = "1.pptx"
    # 一站式处理：抽取+导出PNG可视化
    result = process_and_publish_kg(
        ppt_path=TEST_PPT_PATH,
        export_format="png",
        export_path="ai_architecture_kg",
        write_neo4j=False  # 无需Neo4j则设为False
    )
    # 打印结果统计
    print("="*50)
    print("AI架构与系统知识图谱提取结果")
    print("="*50)
    print(f"处理状态：{result['status']}")
    print(f"有效节点数：{len(result['kg']['nodes'])}")
    print(f"唯一边数：{len(result['kg']['edges'])}")
    print(f"可视化文件：{result['export_result'].get('path', '未导出')}")
    if result['kg']['nodes']:
        print(f"核心节点（按重要性）：{[n['label'] for n in result['kg']['nodes'][:6]]}")