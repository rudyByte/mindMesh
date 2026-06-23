import uuid
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from utils.neo4j_client import neo4j_client

router = APIRouter()
logger = logging.getLogger("citations_router")

class CitationCreate(BaseModel):
    paper_id: str
    style: str # "APA", "MLA", "IEEE"

def format_citation_template(title: str, authors: list, year: int, doi_url: str, style: str) -> str:
    paper_title = title.strip() if title else "Untitled Paper"
    
    # 1. Format authors list
    if not authors:
        authors_formatted = "Unknown Author"
    else:
        valid_authors = [a.strip() for a in authors if a and isinstance(a, str) and a.strip()]
        if not valid_authors:
            authors_formatted = "Unknown Author"
        elif len(valid_authors) == 1:
            authors_formatted = valid_authors[0]
        elif len(valid_authors) == 2:
            authors_formatted = f"{valid_authors[0]} & {valid_authors[1]}"
        else:
            authors_formatted = f"{valid_authors[0]}, et al."

    # Fallback year and URL
    year_str = str(year).strip() if year else "n.d."
    url_str = doi_url.strip() if doi_url else "https://doi.org/"

    # 2. Styles template formatting
    if style.upper() == "APA":
        return f"{authors_formatted}. ({year_str}). {paper_title}. {url_str}"
    elif style.upper() == "MLA":
        return f"{authors_formatted}. \"{paper_title}.\" {url_str}, {year_str}."
    elif style.upper() == "IEEE":
        return f"{authors_formatted}, \"{paper_title},\" {year_str}. Available: {url_str}"
    else:
        return f"{authors_formatted}. {paper_title} ({year_str})."

@router.post("/citations")
def create_citation(request: CitationCreate, session_id: str = Query(...)):
    # Fetch Paper details
    query = """
    MATCH (p:Paper {id: $paper_id})
    OPTIONAL MATCH (p)-[:AUTHORED_BY]->(a:Author)
    RETURN coalesce(p.title, p.name) as title, p.year as year, p.doi as doi, collect(a.name) as authors
    """
    res = neo4j_client.run_query(query, {"paper_id": request.paper_id})
    
    if not res:
        # In mock mode, check the mock node
        if neo4j_client.is_mock() and request.paper_id in neo4j_client.mock_nodes:
            paper = neo4j_client.mock_nodes[request.paper_id]
            title = paper.get("title") or paper.get("name") or "Sample Research Paper"
            authors = ["Rudy, B."]
            year = paper.get("year", 2026)
            doi = paper.get("doi", "10.1234/mock.doi")
        else:
            raise HTTPException(status_code=404, detail="Paper not found.")
    else:
        record = res[0]
        title = record["title"] or "Untitled Paper"
        authors = record["authors"]
        year = record["year"]
        doi = record["doi"] or ""

    # Generate formatted text
    formatted = format_citation_template(title, authors, year, doi, request.style)
    
    cit_id = str(uuid.uuid4())
    
    # Save Citation node
    save_query = """
    MERGE (c:Citation {id: $id, session_id: $session_id})
    ON CREATE SET c.style = $style, c.formatted_text = $formatted_text
    RETURN c
    """
    neo4j_client.run_query(save_query, {
        "id": cit_id,
        "style": request.style,
        "formatted_text": formatted,
        "session_id": session_id
    })
    
    # Link Citation to Paper
    link_query = """
    MATCH (c:Citation {id: $cit_id, session_id: $session_id})
    MATCH (p:Paper {id: $paper_id})
    MERGE (c)-[:FOR_PAPER]->(p)
    """
    neo4j_client.run_query(link_query, {"cit_id": cit_id, "paper_id": request.paper_id, "session_id": session_id})

    # Save to mock database
    if neo4j_client.is_mock():
        neo4j_client.mock_nodes[cit_id] = {
            "id": cit_id,
            "label": "Citation",
            "style": request.style,
            "formatted_text": formatted,
            "session_id": session_id
        }
        neo4j_client.mock_edges.append({"from": cit_id, "to": request.paper_id, "type": "FOR_PAPER"})

    return {
        "id": cit_id,
        "style": request.style,
        "formatted_text": formatted,
        "paper_title": title
    }

@router.get("/citations")
def get_citations(style: Optional[str] = Query(None), session_id: str = Query(...)):
    if neo4j_client.is_mock():
        results = []
        for nid, node in neo4j_client.mock_nodes.items():
            if node.get("label") == "Citation" and node.get("session_id") == session_id:
                if style and node.get("style", "").upper() != style.upper():
                    continue
                    
                # Find paper title
                paper_title = "Research Paper"
                for edge in neo4j_client.mock_edges:
                    if edge["from"] == nid and edge["type"] == "FOR_PAPER":
                        p_node = neo4j_client.mock_nodes.get(edge["to"])
                        if p_node:
                            paper_title = p_node.get("title") or p_node.get("name") or "Research Paper"
                            
                results.append({
                    "id": node["id"],
                    "style": node["style"],
                    "formatted_text": node["formatted_text"],
                    "paper_title": paper_title
                })
        return results

    if style:
        query = """
        MATCH (c:Citation {style: $style, session_id: $session_id})-[:FOR_PAPER]->(p:Paper)
        RETURN c.id as id, c.style as style, c.formatted_text as formatted_text, coalesce(p.title, p.name) as paper_title
        """
        res = neo4j_client.run_query(query, {"style": style, "session_id": session_id})
    else:
        query = """
        MATCH (c:Citation {session_id: $session_id})-[:FOR_PAPER]->(p:Paper)
        RETURN c.id as id, c.style as style, c.formatted_text as formatted_text, coalesce(p.title, p.name) as paper_title
        """
        res = neo4j_client.run_query(query, {"session_id": session_id})
        
    return [
        {
            "id": r["id"],
            "style": r["style"],
            "formatted_text": r["formatted_text"],
            "paper_title": r["paper_title"]
        }
        for r in res
    ]
