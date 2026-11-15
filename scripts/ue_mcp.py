#!/usr/bin/env python3
"""
ue_mcp.py - tiny stdlib-only client for the Unreal Editor MCP server.

Use it when your agent can run shell commands on the machine with the editor
but doesn't have the Unreal MCP tools loaded natively.

    python ue_mcp.py probe
    python ue_mcp.py toolsets
    python ue_mcp.py describe-toolsets BlueprintToolsets.BlueprintDslToolset
    python ue_mcp.py describe-tools editor_toolset.toolsets.python_scripting.PythonScriptingTools.execute_python
    python ue_mcp.py call EditorToolset.EditorAppToolset IsPIERunning '{}'
    python ue_mcp.py py -c "unreal.SystemLibrary.get_engine_version()"
    python ue_mcp.py py my_script.py          # or '-' to read stdin
    python ue_mcp.py shot title_screen        # capture game viewport (PIE must be running)

Environment:
    UE_MCP_URL      endpoint (default http://127.0.0.1:8000/mcp)
    UE_MCP_TIMEOUT  seconds per request (default 300)

Every command does its own handshake, so it never depends on a stale session.
Output is JSON on stdout; exit code 1 on tool errors.
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("UE_MCP_URL", "http://127.0.0.1:8000/mcp")
TIMEOUT = float(os.environ.get("UE_MCP_TIMEOUT", "300"))
PROTOCOL = "2025-06-18"
PY_TOOLSET = "editor_toolset.toolsets.python_scripting.PythonScriptingTools"


class Session:
    def __init__(self, url=URL):
        self.url, self.sid, self.next_id = url, None, 1

    def _post(self, payload):
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": PROTOCOL}
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            self.sid = r.headers.get("Mcp-Session-Id") or self.sid
            body = r.read().decode("utf-8", errors="replace")
        return _parse(body)

    def request(self, method, params=None):
        self.next_id += 1
        msg = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            msg["params"] = params
        return self._post(msg)

    def open(self):
        init = self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": PROTOCOL, "capabilities": {},
                                      "clientInfo": {"name": "ue_mcp.py", "version": "1.0"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return init

    def tool(self, name, arguments=None):
        """Call a top-level MCP tool (list_toolsets, describe_tools, call_tool...)."""
        res = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        if res is None:
            return "", False
        if "error" in res:
            return json.dumps(res["error"]), True
        result = res.get("result", {})
        text = "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        return text, bool(result.get("isError"))

    def call(self, toolset, tool, arguments=None):
        """Call a tool inside a toolset through the call_tool dispatcher."""
        return self.tool("call_tool", {"toolset_name": toolset, "tool_name": tool, "arguments": arguments or {}})

    def py(self, code):
        text, err = self.call(PY_TOOLSET, "execute_python", {"script": {"content": code, "language": "Python"}})
        try:
            j = json.loads(text)
            if isinstance(j, dict) and "returnValue" in j and not err:
                return j["returnValue"], False
            return j, err
        except (json.JSONDecodeError, TypeError):
            return text, err


def _parse(body):
    """Accept a plain JSON body or an SSE stream; return the last JSON-RPC message."""
    body = body.strip()
    if not body:
        return None
    if body.startswith("{"):
        return json.loads(body)
    last = None
    for line in body.splitlines():
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if chunk:
                try:
                    last = json.loads(chunk)
                except json.JSONDecodeError:
                    pass
    return last


SHOT = r'''
import base64, os
res = await call_tool('SceneCaptureToolset.SceneCaptureToolset.CaptureGameViewport', world=None, maxResolution=%(res)d)
d = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + 'AgentShots/'
os.makedirs(d, exist_ok=True)
p = d + '%(name)s.png'
open(p, 'wb').write(base64.b64decode(res['image']['data']))
p
'''


def out(value, err=False):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    print(json.dumps(value, indent=2, ensure_ascii=False) if not isinstance(value, str) else value)
    sys.exit(1 if err else 0)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    s = Session()
    try:
        init = s.open()
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        out({"ok": False, "url": URL, "error": str(e),
             "hint": "Is the Unreal editor open with the MCP server started on this port?"}, True)

    if cmd == "probe":
        info = (init or {}).get("result", {})
        text, err = s.tool("list_toolsets")
        names = [l[2:].split(":")[0] for l in text.splitlines() if l.startswith("- ")]
        out({"ok": not err, "url": URL, "session": s.sid, "server": info.get("serverInfo"),
             "meta": info.get("_meta"), "toolsets": len(names) or None,
             "sample": names[:15] if names else text[:800]}, err)
    elif cmd == "toolsets":
        out(*s.tool("list_toolsets"))
    elif cmd == "describe-toolsets":
        out(*s.tool("describe_toolsets", {"toolset_names": args}))
    elif cmd == "describe-tools":
        out(*s.tool("describe_tools", {"tool_names": args}))
    elif cmd == "call":
        if len(args) < 2:
            sys.exit("usage: call TOOLSET TOOL [JSON_ARGS]")
        out(*s.call(args[0], args[1], json.loads(args[2]) if len(args) > 2 else {}))
    elif cmd == "py":
        if not args:
            sys.exit("usage: py -c CODE | py FILE | py -")
        code = args[1] if args[0] == "-c" else (sys.stdin.read() if args[0] == "-" else open(args[0], encoding="utf-8").read())
        out(*s.py(code))
    elif cmd == "shot":
        name = args[0] if args else "shot"
        res = int(args[1]) if len(args) > 1 else 1600
        out(*s.py(SHOT % {"name": name, "res": res}))
    else:
        sys.exit("unknown command: " + cmd)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except urllib.error.HTTPError as e:
        out({"ok": False, "http_status": e.code, "error": str(e),
             "hint": "400/404 after a restart usually means a stale session; just rerun."}, True)
    except (urllib.error.URLError, TimeoutError) as e:
        out({"ok": False, "error": str(e),
             "hint": "Timed out or lost the editor. It may be busy (shader compile, modal dialog, long script)."}, True)
