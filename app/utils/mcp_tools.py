# app/utils/mcp_tools.py
import asyncio
import inspect
from typing import Optional, List

from mcp.client.session import ClientSession
from mcp.types import Tool
from langchain.tools import BaseTool


async def _maybe_initialize(session: ClientSession, reader, writer):
    """
    Call initialize() if present. Works across MCP client versions:
    - Some take no args: initialize()
    - Some take streams: initialize(reader, writer)
    - Some don't need initialize() at all
    """
    if not hasattr(session, "initialize"):
        return
    init = getattr(session, "initialize")
    try:
        sig = inspect.signature(init)
        if len(sig.parameters) == 0:
            maybe = init()  # type: ignore[misc]
        else:
            maybe = init(reader, writer)  # type: ignore[misc]
        if asyncio.iscoroutine(maybe):
            await maybe
    except (TypeError, NotImplementedError):
        # Safe fallback if already initialized or not supported
        pass


class MCPTool(BaseTool):
    """
    Wrap an MCP tool as a LangChain Tool.

    PROCESS TRANSPORT ONLY:
    Spawns an MCP server via a command (e.g., npx ...).
    Call the MCP tool by its 'tool_name'.
    """

    name: str
    description: str = "MCP tool"
    cmd: Optional[str] = None           # e.g., "npx"
    spawn_args: Optional[str] = None    # e.g., "@modelcontextprotocol/server-github"
    tool_name: str = ""

    def _run(self, *args, **kwargs):
        raise NotImplementedError("Use async")

    async def _arun(self, query: str) -> str:
        if not self.cmd:
            raise RuntimeError("MCPTool requires a process command (e.g., npx) in 'cmd'")

        # spawn MCP server process
        proc = await asyncio.create_subprocess_exec(
            self.cmd,
            *(self.spawn_args.split() if self.spawn_args else []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        reader, writer = proc.stdout, proc.stdin

        # Try stream-based or no-arg constructor depending on version
        try:
            session = ClientSession(reader, writer)  # type: ignore[call-arg]
        except TypeError:
            session = ClientSession()  # type: ignore[call-arg]

        try:
            await _maybe_initialize(session, reader, writer)
            result = await self._call_tool(session, query)
        finally:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                maybe_close = session.close()
                if asyncio.iscoroutine(maybe_close):
                    await maybe_close
            except Exception:
                pass

        return result

    async def _call_tool(self, session: ClientSession, query: str) -> str:
        tools = await session.list_tools()
        tool: Optional[Tool] = next((t for t in tools if t.name == self.tool_name), None)
        if tool is None:
            names = ", ".join(t.name for t in tools)
            raise RuntimeError(f"MCP tool '{self.tool_name}' not found. Available: {names}")
        # Convention: pass {"query": "..."}; adjust if your server wants different args
        result = await session.call_tool(tool.name, {"query": query})
        if isinstance(result, dict) and "content" in result:
            return str(result["content"])
        return str(result)


# -------- Debug helper to list available tools on a server --------
async def list_mcp_tools(cmd: Optional[str], args: Optional[str]) -> List[str]:
    if not cmd:
        raise RuntimeError("list_mcp_tools requires a command (e.g., npx)")
    proc = await asyncio.create_subprocess_exec(
        cmd,
        *(args.split() if args else []),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    reader, writer = proc.stdout, proc.stdin
    try:
        try:
            session = ClientSession(reader, writer)  # type: ignore[call-arg]
        except TypeError:
            session = ClientSession()  # type: ignore[call-arg]
        await _maybe_initialize(session, reader, writer)
        ts = await session.list_tools()
        return [t.name for t in ts]
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            maybe_close = session.close()
            if asyncio.iscoroutine(maybe_close):
                await maybe_close
        except Exception:
            pass
