from contextlib import AsyncExitStack
from types import SimpleNamespace
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.tools import load_mcp_tools
from app.agents.mcp_tools import _client, _run, KnowledgeServiceUnavailable
from app.core.config import settings
from app.llm.router import route_model


SYSTEM = ("You are an anatomy tutor for students. Answer in {locale}.\n"
          "Use ONLY facts returned by search_knowledge. Never use your own memory.\n"
          "Steps: get_structure for the student's part, graph_neighbors if related parts help, "
          "then search_knowledge with those structure_ids. Cite sources inline as [n].\n"
          "If search_knowledge returns nothing, say you have no verified information.")

def _chunks(messages) -> list:
    """The knowledge the agent actually received: this becomes the judge's context."""
    seen, out = set(), []
    for m in messages:
        if m.type == "tool" and m.name == "search_knowledge" and m.status != "error":
            for r in ((m.artifact or {}).get("structured_content") or {}).get("result") or []:
                if r["text"] not in seen:
                    seen.add(r["text"]); 
                    out.append(SimpleNamespace(**r))
    return out