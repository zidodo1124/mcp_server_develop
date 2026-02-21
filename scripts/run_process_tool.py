import json
import sys
import os

# ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.kg_tool import process_and_publish_kg


if __name__ == '__main__':
    res = process_and_publish_kg(text="直接调用测试", export_format="graphml", export_path="kg_output_local")
    print(json.dumps(res, ensure_ascii=False, indent=2))
