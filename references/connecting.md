# Connecting to the Unreal MCP server

## Contents
- Where the server lives
- Native client configs (Claude Code, Codex, others)
- The raw handshake (any language)
- Cloud agents: reaching the editor through a browser on the user's machine
- Troubleshooting

## Where the server lives

The server runs inside the Unreal editor process. Epic documents it as **Unreal MCP** (plugin `ModelContextProtocol`, marked Experimental), with tools coming from the **All Toolsets** plugin or individual toolset plugins; it reports itself as `unreal-mcp`. Official page: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-mcp-in-unreal-editor. Consequences:

- The editor must be open with the project loaded. Closing the editor stops the server.
- **Editor Preferences → Agentic Workflows → Model Context Protocol** has the port, **Auto Start Server** (on by default), and **Generate Client Config** (Claude Code, Codex, Cursor, Gemini, VS Code, All). Console equivalents: `ModelContextProtocol.StartServer [port]`, `ModelContextProtocol.StopServer`, `ModelContextProtocol.GenerateClientConfig <ClaudeCode|Codex|Cursor|VSCode|Gemini|All>`.
- Default endpoint: `http://127.0.0.1:8000/mcp`. Transports: Streamable HTTP and SSE only (no stdio). It binds to `127.0.0.1`, so use that rather than `localhost` (which may resolve to `::1`), and an agent on another machine can't reach it directly.
- There is **no authentication**: any local process can call it. Don't change the bind address to expose it on a network.
- **Tool calls run one at a time on the editor's game thread.** Don't fire parallel calls; batch work into one Python script instead.
- Some clients time out long calls (Claude Code after about 120 s). Keep each call short and run long jobs as background processes you poll.
- A `GET` returns 405. That's normal; MCP uses `POST`.

## Native client configs

Start the agent from the project folder so it picks up a project-level config.

Claude Code, `.mcp.json` in the project root:
```json
{
  "mcpServers": {
    "unreal-mcp": { "type": "http", "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

With a source-built engine, Generate Client Config writes `.mcp.json` to the engine root; copy the entry into the project.

Codex, `.codex/config.toml` in the project or `~/.codex/config.toml` (Streamable HTTP servers use `url`; check your Codex version's MCP docs if it doesn't load):
```toml
[mcp_servers.unreal-mcp]
url = "http://127.0.0.1:8000/mcp"
```
The editor writes the Codex file only once: if it already exists, changing the port later doesn't update it, so a stale port there is a common reason the tools "don't show up". Edit the entry by hand and restart Codex. Codex only reads a project-level `.codex/config.toml` for trusted projects.

Cursor, Gemini CLI and others take the same URL in their own MCP config. If the tools still don't appear, fall back to `scripts/ue_mcp.py`; it needs nothing but Python and a shell on the same machine.

The server exposes a small set of top-level tools and dispatches everything else:

| Tool | Arguments | Use |
|---|---|---|
| `list_toolsets` | none | names + one-line descriptions |
| `describe_toolsets` | `toolset_names: [...]`, optional `include_schemas: true` | tools in each toolset |
| `describe_tools` | `tool_names: ["Toolset.Name.Tool", ...]` | exact parameters |
| `call_tool` | `toolset_name`, `tool_name`, `arguments` | run any tool |

## The raw handshake

Useful when writing your own client or debugging. Each request is a JSON-RPC POST with
`Content-Type: application/json` and `Accept: application/json, text/event-stream`. Responses may be plain JSON or an SSE stream (`data: {...}` lines); take the last `data:` message.

1. `initialize` with `protocolVersion` (e.g. `2025-06-18`), empty `capabilities`, a `clientInfo`. Read the `Mcp-Session-Id` response header.
2. Send the `notifications/initialized` notification (no `id`) with the session header.
3. Send requests (`tools/list`, `tools/call`) with the session header and incrementing ids.

`scripts/ue_mcp.py` implements exactly this; read it rather than re-deriving it.

## Cloud agents: going through a browser

If the agent runs in the cloud but can drive a browser on the user's machine (e.g. a desktop app's built-in browser pane), the browser can reach `127.0.0.1`. Open `http://127.0.0.1:8000/mcp` in a tab (same origin avoids CORS problems), then run JavaScript in that page:

```js
window.__mcp = { sid: null, id: 10 };
window.mcpRaw = async (method, params) => {
  const h = { 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream' };
  if (!__mcp.sid) {
    const r = await fetch('/mcp', { method: 'POST', headers: h, body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize',
      params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'agent', version: '1' } } }) });
    __mcp.sid = r.headers.get('mcp-session-id'); await r.text();
    await fetch('/mcp', { method: 'POST', headers: { ...h, 'mcp-session-id': __mcp.sid },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) });
  }
  const r = await fetch('/mcp', { method: 'POST', headers: { ...h, 'mcp-session-id': __mcp.sid },
    body: JSON.stringify({ jsonrpc: '2.0', id: ++__mcp.id, method, params }) });
  const t = await r.text(); try { return JSON.parse(t) } catch (e) { return t }
};
window.mcp = async (tool, args = {}, toolset) => {
  const a = { tool_name: tool, arguments: args }; if (toolset) a.toolset_name = toolset;
  const j = await mcpRaw('tools/call', { name: 'call_tool', arguments: a });
  if (j.error) return 'ERROR ' + JSON.stringify(j.error);
  return (j.result?.content || []).map(c => c.text).join('\n') + (j.result?.isError ? '\n[isError]' : '');
};
window.py = async (code) => {
  const t = await mcp('execute_python', { script: { content: code, language: 'Python' } },
    'editor_toolset.toolsets.python_scripting.PythonScriptingTools');
  try { const j = JSON.parse(t); return j.returnValue !== undefined ? j.returnValue : j } catch (e) { return t }
};
```

Notes from real use:
- **Page state is lost** when the tab reloads or the browser session resets between turns. Re-run the setup snippet at the start of each turn rather than assuming `window.py` still exists.
- **Browser script calls time out** (tens of seconds). For long work, start it without awaiting (`window._job = py(...).then(r => window._res = r)`) and poll `window._res` in later calls.
- **Files**: write screenshots and logs under the project's `Saved/` folder from Python, then move them to the agent through whatever file bridge the agent has. Base64 image data through the browser is slow and gets truncated.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Connection refused / instant failure | Editor closed, server not started, or wrong port. Check Editor Preferences → MCP. |
| 405 on GET | Normal. |
| 400/404 after it worked | Session expired (editor restarted). Redo the handshake. |
| Tools missing from the client | Agent not started in the project folder, config not reloaded, or client lacks HTTP MCP support. Use `ue_mcp.py`. |
| Calls hang | Editor busy (compiling shaders, importing, a modal dialog open, a long Python script). Wait, then check the editor; ask the user to dismiss dialogs. |
| Two editors open | Each binds a port; confirm the project path from `unreal.Paths.get_project_file_path()` before editing. |
