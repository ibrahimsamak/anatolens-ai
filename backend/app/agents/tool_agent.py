from contextlib import AsyncExitStack
from types import SimpleNamespace
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.errors import GraphRecursionError
from app.obs.cost import CostCallback
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

async def _arun(structure_id: str, question: str, locale: str):
    async with AsyncExitStack() as stack:
        try:
            session = await stack.enter_async_context(_client().session("anatomy"))
            tools = await load_mcp_tools(session)
        except Exception as e:
            raise KnowledgeServiceUnavailable("anatomy MCP server unavailable") from e
        
        for t in tools:
            t.handle_tool_error = True
        model = route_model(question, structure_id)
        llm = init_chat_model(model, temperature=0, callbacks=[CostCallback(model)])
        agent = create_agent(llm, tools, system_prompt=SYSTEM.format(locale=locale))
        try:
            out = await agent.ainvoke(
                {"messages": [("user", f"Structure id: {structure_id}\nQuestion: {question}")]},
                {"recursion_limit": settings.agent_max_steps * 2 + 1})
        except GraphRecursionError:
            return "", []
        return out["messages"][-1].text, _chunks(out["messages"])
    
    
def run_agent(structure_id: str, question: str, locale: str) -> tuple[str, list]:
    return _run(_arun(structure_id, question, locale))