import asyncio, json, os, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from langchain_mcp_adapters.client import MultiServerMCPClient

BACKEND = Path(__file__).resolve().parents[2]


class KnowledgeServiceUnavailable(RuntimeError):
    """The MCP anatomy server could not be started or reached. Never answer without it."""

class KnowledgeToolError(ValueError):
    """The server is up but rejected the call (unknown id, bad arguments)."""

def connections() -> dict:
    return {"anatomy": {
        "command": sys.executable, 
        "args": ["-m", "app.mcp_server.anatomy_server"],
        "transport": "stdio", 
        "cwd": str(BACKEND), 
        "env": dict(os.environ)}}

def _client():
    return MultiServerMCPClient(connections())

async def load_mcp_tools():
    try:
        return await _client().get_tools()
    except Exception as e:
        raise KnowledgeServiceUnavailable("anatomy MCP server unavailable") from e


async def call_tool(name: str, args: dict):
    try:
        async with _client().session("anatomy") as session:
            res = await session.call_tool(name, args)
    except Exception as e:
        raise KnowledgeServiceUnavailable(f"anatomy MCP server unavailable ({type(e).__name__})") from e
    if res.isError:
        raise KnowledgeToolError(" ".join(getattr(c, "text", "") for c in res.content) or name)
    if res.structuredContent is not None:
        return res.structuredContent.get("result", res.structuredContent)
    return json.loads(res.content[0].text) if res.content else None


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def search_knowledge_via_mcp(structure_ids: list[str], query: str, locale: str, db=None) -> list:
    """Same shape as rag.retriever.retrieve_chunks, but served by the MCP server."""
    rows = _run(call_tool("search_knowledge", {"query": query, "locale": locale, "structure_ids": list(structure_ids)}))
    return [SimpleNamespace(**r) for r in rows or []]
