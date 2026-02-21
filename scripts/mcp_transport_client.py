"""
MCP Transport 客户端（SSE 模式）

此脚本通过 HTTP 与运行中的 MCP server 的 SSE endpoint 交互：
- 使用 GET / to 建立 SSE 长连接接收服务器消息
- 使用 POST /messages/ 发送消息到服务器

注意：MCP 的消息格式可能依实现而不同；此脚本使用通用的 JSON 包装：
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tool.invoke",
  "params": {"name": "process_and_publish_kg", "arguments": {...}}
}

根据你的 MCP 服务实现，你可能需要调整 `build_request` 的内容以匹配真实协议。
"""
import argparse
import httpx
import json
import os
from datetime import datetime
import threading
import time
import queue


def build_request(tool_name: str, arguments: dict, req_id: int = 1):
    # 通用 JSON-RPC 风格请求（如需不同协议请修改）
    return {"jsonrpc": "2.0", "id": req_id, "method": "tool.invoke", "params": {"name": tool_name, "arguments": arguments}}


def sse_listen(url: str, stop_event: threading.Event, result_queue: queue.Queue | None = None):
    """建立到 server root 的 SSE 连接，并打印接收到的 data 字段（假定为 JSON）。"""
    headers = {"Accept": "text/event-stream"}
    with httpx.Client(timeout=None) as client:
        with client.stream("GET", url, headers=headers) as resp:
            if resp.status_code != 200:
                print(f"SSE 连接失败: {resp.status_code} {resp.text}")
                return

            buffer = ""
            for chunk in resp.iter_bytes():
                if stop_event.is_set():
                    break
                try:
                    text = chunk.decode("utf-8")
                except Exception:
                    continue
                buffer += text
                while "\n\n" in buffer:
                    part, buffer = buffer.split("\n\n", 1)
                    # 解析 event block（支持 event: 和 data: 行）
                    lines = [l for l in part.splitlines()]
                    event_lines = [l[len("event:"):].strip() for l in lines if l.startswith("event:")]
                    data_lines = [l[len("data:"):].strip() for l in lines if l.startswith("data:")]
                    event_name = event_lines[-1] if event_lines else "message"
                    data = "\n".join(data_lines)
                    # 尝试把 data 解析为 JSON，否则保留原始字符串
                    parsed = None
                    try:
                        parsed = json.loads(data)
                    except Exception:
                        parsed = data

                    obj = {"event": event_name, "data": parsed}
                    if result_queue is not None:
                        try:
                            result_queue.put(obj, block=False)
                        except Exception:
                            pass

                    if event_name == "message" and isinstance(parsed, dict):
                        print("[SSE RECEIVED]", json.dumps(parsed, ensure_ascii=False, indent=2))
                    else:
                        print("[SSE RECEIVED RAW]", obj)


def post_message(post_url: str, payload: dict):
    # write request to local log for debugging
    try:
        os.makedirs("logs", exist_ok=True)
        fname = os.path.join("logs", "requests.log")
        with open(fname, "a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()}Z POST {post_url} payload:\n")
            json.dump(payload, f, ensure_ascii=False)
            f.write("\n---\n")
    except Exception:
        pass

    with httpx.Client() as client:
        r = client.post(post_url, json=payload)
        try:
            print("[POST RESPONSE]", r.status_code, r.text)
        except Exception:
            print("[POST RESPONSE] status", r.status_code)
        return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://127.0.0.1:12345", help="MCP SSE server base URL (e.g. http://host:port)")
    p.add_argument("--post-only", dest="post_only", action="store_true", help="只执行 POST 请求，不建立 SSE 长连接")
    p.add_argument("--wait", dest="wait", action="store_true", help="在发送后等待来自 SSE 的响应（启用后会建立 SSE 连接）")
    p.add_argument("--wait-timeout", dest="wait_timeout", type=int, default=30, help="等待 SSE 响应的超时时间（秒）")
    p.add_argument("--poll-results", dest="poll_results", action="store_true", help="在 POST 后轮询 /results/{id} 获取执行结果")
    p.add_argument("--poll-timeout", dest="poll_timeout", type=int, default=30, help="轮询 /results/ 的超时时间（秒）")
    p.add_argument("--ppt", dest="ppt_path", help="pptx path")
    p.add_argument("--text", dest="text", help="text input")
    p.add_argument("--export-format", dest="export_format", default="graphml")
    p.add_argument("--export-path", dest="export_path", default="kg_output")
    args = p.parse_args()

    base = args.host.rstrip("/")
    sse_url = f"{base}/"
    post_url = f"{base}/messages/"

    # 构造 arguments
    arguments = {"export_format": args.export_format, "export_path": args.export_path}
    if args.ppt_path:
        arguments["ppt_path"] = args.ppt_path
    if args.text:
        arguments["text"] = args.text

    req = build_request("process_and_publish_kg", arguments, req_id=int(time.time()))

    # 如果用户要求等待 SSE 响应，则强制不开启 post-only
    if args.wait:
        args.post_only = False

    if args.post_only:
        print("Post-only mode: not establishing SSE, sending single POST")
        # 如果处于 wait 模式，尝试从 SSE 的初始 endpoint 事件获得带 session_id 的 POST 路径
        if args.wait and result_q is not None:
            try:
                # 等待最多 5 秒获得 endpoint 事件
                endpoint_obj = None
                deadline_e = time.time() + 5
                while time.time() < deadline_e:
                    try:
                        ev = result_q.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if isinstance(ev, dict) and ev.get("event") == "endpoint":
                        endpoint_obj = ev
                        break
                if endpoint_obj is not None:
                    ep = endpoint_obj.get("data")
                    if isinstance(ep, str):
                        # ep is a path+query like "/messages/?session_id=..."
                        post_url = base.rstrip("/") + ep
                        print(f"Using sessioned POST URL: {post_url}")
            except Exception:
                pass

        print("Sending request:", json.dumps(req, ensure_ascii=False))
        post_message(post_url, req)
        # 如果用户要求轮询 /results/{id}
        if args.poll_results:
            poll_url = f"{base}/results/{req.get('id')}"
            deadline = time.time() + args.poll_timeout
            got = None
            with httpx.Client() as client:
                while time.time() < deadline:
                    try:
                        r = client.get(poll_url, timeout=5)
                        if r.status_code == 200:
                            try:
                                got = r.json()
                                print("[POLL RESULT]", json.dumps(got, ensure_ascii=False, indent=2))
                                break
                            except Exception:
                                pass
                        else:
                            # not found or pending
                            pass
                    except Exception:
                        pass
                    time.sleep(1)
            if got is None:
                print(f"[POLL RESULT] timed out after {args.poll_timeout}s")
    else:
        stop_event = threading.Event()
        result_q = queue.Queue() if args.wait else None
        t = threading.Thread(target=sse_listen, args=(sse_url, stop_event, result_q), daemon=True)
        t.start()

        # 给 SSE 连接一点时间
        time.sleep(0.5)

        print("Sending request:", json.dumps(req, ensure_ascii=False))
        post_message(post_url, req)

        if args.wait and result_q is not None:
            # 等待来自 SSE 的响应，尝试匹配请求 id 或直到超时
            deadline = time.time() + args.wait_timeout
            matched = None
            while time.time() < deadline:
                try:
                    item = result_q.get(timeout=1)
                except queue.Empty:
                    continue
                # 尝试匹配 JSON-RPC id 或包含工具名的结果
                try:
                    if isinstance(item, dict):
                        if item.get("id") == req.get("id"):
                            matched = item
                            break
                        # 有些实现会把结果放在 params/result 中
                        if item.get("params") and isinstance(item.get("params"), dict):
                            p = item.get("params")
                            if p.get("name") == req.get("params", {}).get("name"):
                                matched = item
                                break
                except Exception:
                    pass

            if matched is not None:
                print("[WAITED RESPONSE]", json.dumps(matched, ensure_ascii=False, indent=2))
            else:
                print(f"[WAITED RESPONSE] timed out after {args.wait_timeout}s without matching SSE event")

        # 等待若干秒以接收其它回复（短延迟）
        try:
            time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        stop_event.set()
        t.join(timeout=1)


if __name__ == "__main__":
    main()
