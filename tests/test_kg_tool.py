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
    sys.modules.setdefault("modules.YA_Common.utils", types.ModuleType("modules.YA_Common.utils"))

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


if __name__ == "__main__":
    unittest.main()
