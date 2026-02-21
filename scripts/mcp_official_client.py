"""
尝试使用 mcp 官方 client API 的客户端脚本。

行为：
- 若能导入 `mcp.client`，脚本会自动探测可用 Client 类并尝试调用 `process_and_publish_kg` 工具。
- 若导入失败或探测无法成功，会回退到 SSE transport 客户端 `mcp_transport_client.py`。

注意：本脚本以探索为主，实际库中类名或方法名可能不同；脚本会打印诊断信息以便调整。
"""
import argparse
import importlib
import inspect
import json
import sys
from typing import Any


def try_official_client(host: str, ppt_path: str | None, text: str | None, export_format: str, export_path: str):
    try:
        cli_mod = importlib.import_module("mcp.client")
    except Exception as e:
        print("无法导入 mcp.client:", e)
        return False

    print("mcp.client 模块可用，正在探测 Client 类...")

    candidates = []
    for name in dir(cli_mod):
        if name.lower().endswith("client"):
            obj = getattr(cli_mod, name)
            candidates.append((name, obj))

    if not candidates:
        print("未在 mcp.client 中找到以 Client 结尾的符号，列出模块成员供排查：")
        print([n for n in dir(cli_mod) if not n.startswith("_")][:200])
        return False

    print("候选 Client:", [name for name, _ in candidates])

    for name, cls in candidates:
        try:
            if inspect.isclass(cls):
                sig = inspect.signature(cls)
                kwargs: dict[str, Any] = {}
                # 如果构造函数接受 host/url 参数，尝试传入
                for param in sig.parameters.values():
                    if param.name in ("host", "url", "base_url"):
                        kwargs[param.name] = host
                print(f"尝试实例化 {name} with {kwargs}...")
                inst = cls(**kwargs) if kwargs else cls()
            elif inspect.isfunction(cls) or inspect.ismethod(cls):
                # skip
                continue
            else:
                inst = cls

            # 探测可能的调用方法
            method_names = [
                "invoke_tool",
                "invoke",
                "call",
                "request",
                "send",
                "run",
                "tool",
            ]
            found = None
            for m in method_names:
                if hasattr(inst, m):
                    found = m
                    break

            # 若没有常见方法，列出实例成员并继续下一个候选
            if not found:
                print(f"{name} 没有常见的调用方法，实例成员示例：", [n for n in dir(inst) if not n.startswith("_")][:200])
                continue

            print(f"使用 {name}.{found} 调用 process_and_publish_kg 工具")
            call = getattr(inst, found)

            arguments = {"export_format": export_format, "export_path": export_path}
            if ppt_path:
                arguments["ppt_path"] = ppt_path
            if text:
                arguments["text"] = text

            # 记录准备发送的请求到本地日志，便于与服务器端日志比对
            try:
                import os
                from datetime import datetime
                os.makedirs("logs", exist_ok=True)
                fname = os.path.join("logs", "requests.log")
                with open(fname, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.utcnow().isoformat()}Z OFFICIAL_CLIENT candidate={name} call={found} host={host} payload:\n")
                    json.dump({"tool_name": "process_and_publish_kg", "arguments": arguments}, f, ensure_ascii=False)
                    f.write("\n---\n")
            except Exception:
                pass

            # 尝试调用（根据方法签名选择调用样式）
            m_sig = inspect.signature(call)
            if "name" in m_sig.parameters and "arguments" in m_sig.parameters:
                # 假定 API: call(name=str, arguments=dict)
                resp = call(name="process_and_publish_kg", arguments=arguments)
            elif len(m_sig.parameters) == 1:
                # 可能接受一个 dict
                resp = call({"name": "process_and_publish_kg", "arguments": arguments})
            else:
                # 最后手段：尝试关键字调用
                try:
                    resp = call(tool_name="process_and_publish_kg", arguments=arguments)
                except Exception as e:
                    print("尝试不同调用方式失败:", e)
                    continue

            print("调用返回：", json.dumps(resp, ensure_ascii=False, indent=2) if not isinstance(resp, str) else resp)
            return True
        except Exception as e:
            print(f"尝试使用 {name} 失败:", e)
            continue

    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://127.0.0.1:12345", help="MCP server base URL")
    p.add_argument("--ppt", dest="ppt_path", help="pptx path")
    p.add_argument("--text", dest="text", help="text input")
    p.add_argument("--export-format", dest="export_format", default="graphml")
    p.add_argument("--export-path", dest="export_path", default="kg_output")
    args = p.parse_args()

    ok = try_official_client(args.host, args.ppt_path, args.text, args.export_format, args.export_path)
    if not ok:
        # streamablehttp_client 在当前环境中会产生内部 AttributeError（非致命），
        # 为避免噪音日志，直接退回到我们已实现的 SSE+POST 客户端实现。
        import subprocess

        subprocess.run([sys.executable, "scripts/mcp_transport_client.py", "--host", args.host, "--ppt", args.ppt_path or "", "--export-format", args.export_format, "--export-path", args.export_path])


if __name__ == "__main__":
    main()
