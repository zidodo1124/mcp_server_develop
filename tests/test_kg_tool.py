import unittest
import importlib.util
from pathlib import Path


def _load_kg_tool():
    path = Path(__file__).resolve().parents[1] / "tools" / "kg_tool.py"
    spec = importlib.util.spec_from_file_location("kg_tool", str(path))
    module = importlib.util.module_from_spec(spec)

    # 插入临时的 `tools` 模块以避免导入项目的 tools 包（该包在导入时会引用缺失的外部依赖）
    import sys
    import types

    orig_tools = sys.modules.get("tools")
    fake_tools = types.ModuleType("tools")

    def YA_MCPServer_Tool(*args, **kwargs):
        def decorator(f):
            return f

        return decorator

    fake_tools.YA_MCPServer_Tool = YA_MCPServer_Tool
    sys.modules["tools"] = fake_tools

    # 注入简易的 modules.YA_Common.utils.logger.get_logger 避免外部依赖
    orig_modules_logger = sys.modules.get("modules.YA_Common.utils.logger")
    # 创建父包占位
    sys.modules.setdefault("modules", types.ModuleType("modules"))
    sys.modules.setdefault("modules.YA_Common", types.ModuleType("modules.YA_Common"))
    sys.modules.setdefault(
        "modules.YA_Common.utils", types.ModuleType("modules.YA_Common.utils")
    )

    fake_logger_mod = types.ModuleType("modules.YA_Common.utils.logger")

    def get_logger(name: str):
        import logging

        return logging.getLogger(name)

    fake_logger_mod.get_logger = get_logger
    sys.modules["modules.YA_Common.utils.logger"] = fake_logger_mod

    try:
        spec.loader.exec_module(module)
    finally:
        # 恢复原始 modules
        if orig_tools is not None:
            sys.modules["tools"] = orig_tools
        else:
            del sys.modules["tools"]

    return module


class TestKGTool(unittest.TestCase):
    def test_extract_from_text_structure(self):
        kg_tool = _load_kg_tool()
        extract_knowledge_graph = kg_tool.extract_knowledge_graph

        text = "人工智能（AI）是计算机科学的一个分支，研究智能代理的理论、方法和技术。"
        kg = extract_knowledge_graph(text=text)
        # 基本结构检查
        self.assertIsInstance(kg, dict)
        self.assertIn("nodes", kg)
        self.assertIn("edges", kg)
        self.assertIn("slides_summary", kg)

        # slides_summary 应包含原始文本
        slides = kg["slides_summary"]
        self.assertIsInstance(slides, list)
        self.assertGreaterEqual(len(slides), 1)
        self.assertEqual(slides[0]["text"], text)

    def test_entity_filtering_and_min_occur(self):
        kg_tool = _load_kg_tool()

        original_extract_text = kg_tool._extract_text_from_pptx
        original_entity_extractor = kg_tool._simple_entity_extraction
        try:
            kg_tool._extract_text_from_pptx = lambda _: [
                "标题一\n正文一",
                "标题二\n正文二",
            ]

            def fake_extract(text, top_k=50):
                if "正文一" in text:
                    return ["核心A", "核心B", "介绍", "A"]
                return ["核心A", "核心C", "因此", "1"]

            kg_tool._simple_entity_extraction = fake_extract

            kg = kg_tool.extract_knowledge_graph(
                ppt_path="dummy.pptx",
                min_occur=2,
                seed_from_title=False,
                keep_seed_entities=False,
                adaptive_top_n=False,
                top_n_core=10,
                min_edge_weight=1,
            )

            labels = {n["label"] for n in kg["nodes"]}
            self.assertIn("核心A", labels)
            self.assertNotIn("核心B", labels)
            self.assertNotIn("核心C", labels)
            self.assertNotIn("介绍", labels)
            self.assertNotIn("因此", labels)
            self.assertNotIn("A", labels)
        finally:
            kg_tool._extract_text_from_pptx = original_extract_text
            kg_tool._simple_entity_extraction = original_entity_extractor

    def test_edge_dedup_and_min_edge_weight(self):
        kg_tool = _load_kg_tool()

        original_extract_text = kg_tool._extract_text_from_pptx
        original_entity_extractor = kg_tool._simple_entity_extraction
        try:
            kg_tool._extract_text_from_pptx = lambda _: ["第一页", "第二页"]

            def fake_extract(text, top_k=50):
                if "第一页" in text:
                    return ["核心A", "核心A", "核心B", "概述"]
                return ["核心A", "核心B", "例子"]

            kg_tool._simple_entity_extraction = fake_extract

            kg = kg_tool.extract_knowledge_graph(
                ppt_path="dummy.pptx",
                min_occur=1,
                min_edge_weight=2,
                seed_from_title=False,
                keep_seed_entities=False,
                adaptive_top_n=False,
                top_n_core=10,
            )

            self.assertEqual(len(kg["nodes"]), 2)
            self.assertEqual(len(kg["edges"]), 1)
            self.assertEqual(kg["edges"][0]["weight"], 2)
            self.assertNotEqual(kg["edges"][0]["source"], kg["edges"][0]["target"])
        finally:
            kg_tool._extract_text_from_pptx = original_extract_text
            kg_tool._simple_entity_extraction = original_entity_extractor


if __name__ == "__main__":
    unittest.main()
