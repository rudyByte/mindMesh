import asyncio
import logging
import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from anthropic import AsyncAnthropic

from utils.neo4j_client import neo4j_client
from utils.llm_client import llm_client
from config import config

router = APIRouter()
logger = logging.getLogger("copilot_router")

class ContextRequest(BaseModel):
    node_id: str

class ChatMessageSchema(BaseModel):
    role: str # 'user' or 'assistant'
    content: str

class ChatRequest(BaseModel):
    message: str
    node_id: Optional[str] = None
    conversation_history: List[ChatMessageSchema] = []
    user_role: Optional[str] = "student" # 'student' or 'researcher'

def get_node_graphrag_context(node_id: str) -> dict:
    if neo4j_client.is_mock():
        # Fallback context in mock mode
        node = neo4j_client.mock_nodes.get(node_id)
        if not node:
            return {"node": None, "prerequisites": [], "related": [], "papers": []}
            
        prereqs = []
        related = []
        papers = []
        
        for edge in neo4j_client.mock_edges:
            if edge["to"] == node_id and edge["type"] == "PREREQUISITE_OF":
                from_node = neo4j_client.mock_nodes.get(edge["from"])
                if from_node:
                    prereqs.append({"id": from_node["id"], "name": from_node.get("name", "Unknown")})
            elif edge["from"] == node_id or edge["to"] == node_id:
                other_id = edge["to"] if edge["from"] == node_id else edge["from"]
                other_node = neo4j_client.mock_nodes.get(other_id)
                if other_node:
                    item = {"id": other_node["id"], "name": other_node.get("name") or other_node.get("title") or "Unknown", "type": edge["type"]}
                    if other_node.get("label") == "Paper":
                        papers.append(item)
                    else:
                        related.append(item)
                        
        return {
            "node": {
                "id": node["id"],
                "label": node.get("label", "Concept"),
                "name": node.get("name") or node.get("title") or "Unknown",
                "description": node.get("description", ""),
                "difficulty_level": node.get("difficulty_level", "Beginner")
            },
            "prerequisites": prereqs[:10],
            "related": related[:10],
            "papers": papers[:10]
        }

    # Real Neo4j context builder
    query = """
    MATCH (n {id: $node_id})
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN labels(n)[0] as label, n.id as id, n.name as name, n.description as description, n.difficulty_level as difficulty,
           n.title as title, labels(m)[0] as m_label, m.id as m_id, m.name as m_name, m.title as m_title, type(r) as rel_type, startNode(r).id = n.id as is_outgoing
    """
    res = neo4j_client.run_query(query, {"node_id": node_id})
    
    if not res:
        return {"node": None, "prerequisites": [], "related": [], "papers": []}
        
    # Unpack records
    first = res[0]
    node_name = first.get("name") or first.get("title") or "Unknown"
    node_details = {
        "id": first.get("id"),
        "label": first.get("label"),
        "name": node_name,
        "description": first.get("description") or "",
        "difficulty_level": first.get("difficulty") or "Beginner"
    }
    
    prereqs = []
    related = []
    papers = []
    seen_ids = set()
    
    for r in res:
        m_id = r.get("m_id")
        if not m_id or m_id in seen_ids:
            continue
        seen_ids.add(m_id)
        
        m_label = r.get("m_label")
        m_name = r.get("m_name") or r.get("m_title") or "Unknown"
        rel_type = r.get("rel_type")
        is_outgoing = r.get("is_outgoing")
        
        item = {"id": m_id, "name": m_name, "type": rel_type}
        
        if m_label == "Paper":
            papers.append(item)
        elif rel_type == "PREREQUISITE_OF" and not is_outgoing:
            # incoming prerequisite -> it is a prereq of the current node
            prereqs.append(item)
        else:
            related.append(item)
            
    return {
        "node": node_details,
        "prerequisites": prereqs[:10],
        "related": related[:10],
        "papers": papers[:10]
    }

@router.post("/copilot/context")
def get_copilot_context(request: ContextRequest):
    context = get_node_graphrag_context(request.node_id)
    if not context.get("node"):
        raise HTTPException(status_code=404, detail="Node not found.")
    return context

async def generate_mock_stream(message: str, context: dict):
    node = context.get("node")
    node_name = node["name"] if node else "no active selection"
    
    response = (
        f"Hi! I am your MindMesh AI tutor/assistant. You asked about **{message}** while focusing on the concept **{node_name}**.\n\n"
    )
    
    if node:
        response += (
            f"Here is how this node links to other elements in the database:\n"
            f"- **Focus Node**: {node_name} ({node['difficulty_level']} level). Description: {node['description']}\n"
        )
        
        if context.get("prerequisites"):
            prereq_names = ", ".join([p["name"] for p in context["prerequisites"]])
            response += f"- **Prerequisite Chain**: It depends on covering **{prereq_names}** first.\n"
        else:
            response += "- **Prerequisite Chain**: No immediate prerequisite dependencies mapped. It is a great place to start!\n"
            
        if context.get("related"):
            related_names = ", ".join([r["name"] for r in context["related"][:3]])
            response += f"- **Adjacent Paths**: Related expansions include **{related_names}**.\n"
            
        if context.get("papers"):
            paper_titles = ", ".join([p["name"] for p in context["papers"][:2]])
            response += f"- **Grounding Literature**: Key papers using or extending this method include: *{paper_titles}*.\n"
            
        response += (
            f"\nIn relation to your query, we can observe that {node_name} acts as a key conceptual step. "
            f"Would you like me to map out a step-by-step learning path from its prerequisites to advanced implementations?"
        )
    else:
        response += (
            "I see that you haven't selected a node on the canvas. Based on general knowledge, "
            "this concept represents a key building block. To see how it connects in your uploaded documents, "
            "try clicking an element on the graph!"
        )

    # Yield words one by one to simulate live streaming
    for chunk in re.findall(r'\S+|\s+', response):
        yield chunk
        await asyncio.sleep(0.015)

async def generate_live_stream(message: str, context: dict, history: list, user_role: str):
    node = context.get("node")
    node_context_str = ""
    
    if node:
        node_context_str = (
            f"Focus Node: {node['name']}\n"
            f"Description: {node['description']}\n"
            f"Difficulty: {node['difficulty_level']}\n"
        )
        if context.get("prerequisites"):
            node_context_str += "Prerequisites: " + ", ".join([p["name"] for p in context["prerequisites"]]) + "\n"
        if context.get("related"):
            node_context_str += "Related concepts: " + ", ".join([r["name"] for r in context["related"]]) + "\n"
        if context.get("papers"):
            node_context_str += "Grounding Papers: " + ", ".join([p["name"] for p in context["papers"]]) + "\n"

    system_prompt = (
        f"You are KnowledgeWeb's AI Copilot, acting as a "
        f"{'friendly academic tutor' if user_role == 'student' else 'professional research assistant'} for a {user_role}. "
        f"You have access to the following graph-grounded context about the user's focus node:\n"
        f"==== GRAPH CONTEXT ====\n{node_context_str or 'No focus node currently selected.'}\n========================\n"
        f"Respond to the user's message. When making a claim, cite which graph relationship supports it (e.g. 'Linear Algebra is a prerequisite of Gradient Descent'). "
        f"If the context doesn't contain enough information, state so clearly instead of hallucinating. Keep your explanation structured and concise.\n\n"
        f"CRITICAL FORMATTING RULES:\n"
        f"1. Generate clean, natural, and friendly responses. Avoid raw markdown artifacts, technical delimiters, or JSON dumps.\n"
        f"2. DO NOT mention internal filenames (such as 'test.pdf', 'MachineLearningTextbook.pdf', or any text matching '*.pdf') in your answers unless intentionally cited. Refer to them as 'the document' or by the formal paper title/author.\n"
        f"3. Make the tone conversational, clean, and directly helpful without robotic structural prefixes."
    )

    try:
        # Anthropic async client stream
        aclient = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        messages_payload = []
        for h in history:
            messages_payload.append({"role": h.role, "content": h.content})
        messages_payload.append({"role": "user", "content": message})
        
        async with aclient.messages.stream(
            model=config.ANTHROPIC_MODEL,
            max_tokens=2000,
            temperature=0.2,
            system=system_prompt,
            messages=messages_payload
        ) as stream:
            async for event in stream.text_stream:
                yield event
    except Exception as e:
        logger.error(f"Error during live Copilot stream: {e}")
        # Fallback to simulated message if API fails
        yield f"\n*(Notice: Live API call failed due to: {str(e)}. Falling back to mock assistant explanation)*\n\n"
        async for chunk in generate_mock_stream(message, context):
            yield chunk

@router.post("/copilot/chat")
async def chat_copilot(request: ChatRequest):
    # Fetch focus node context
    context = {}
    if request.node_id:
        context = get_node_graphrag_context(request.node_id)
        
    is_mock = not config.ANTHROPIC_API_KEY or "mock-api-key" in config.ANTHROPIC_API_KEY
    
    if is_mock:
        return StreamingResponse(
            generate_mock_stream(request.message, context),
            media_type="text/plain"
        )
    else:
        return StreamingResponse(
            generate_live_stream(request.message, context, request.conversation_history, request.user_role),
            media_type="text/plain"
        )
