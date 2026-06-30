import json
import logging
import re
from anthropic import Anthropic
from config import config

logger = logging.getLogger("llm_client")

def normalize_and_clean_concept_name(name: str) -> str:
    # Strip spaces and formatting
    n = name.strip()
    n = re.sub(r'^["\'`*_]+|["\'`*_]+$', '', n).strip()
    # Strip trailing punctuation
    n = n.rstrip(',.;:-')
    
    # Strip leading articles/prepositions/conjunctions/noisy words
    words = n.split()
    while words:
        first_word_low = words[0].lower()
        junk_leading = {
            "the", "a", "an", "any", "all", "each", "some", "every", "this", "that", "these", "those",
            "of", "in", "on", "at", "for", "to", "with", "by", "from", "and", "or", "about", "including",
            "through", "during", "before", "after", "under", "over", "between", "among", "is", "are", "was", "were"
        }
        if first_word_low in junk_leading:
            words.pop(0)
        else:
            break
            
    # Strip trailing junk words
    while words:
        last_word_low = words[-1].lower()
        junk_trailing = {
            "the", "a", "an", "any", "all", "each", "some", "every", "this", "that", "these", "those",
            "of", "in", "on", "at", "for", "to", "with", "by", "from", "and", "or", "about", "including",
            "through", "during", "before", "after", "under", "over", "between", "among", "is", "are", "was", "were"
        }
        if last_word_low in junk_trailing:
            words.pop()
        else:
            break
            
    n = " ".join(words)
    
    # Singularize concept name
    n = singularize_concept_name(n)
    
    # Capitalize each word properly (Title Case), while preserving uppercase acronyms (like DFA, NFA, ZKP)
    words = n.split()
    capitalized_words = []
    for w in words:
        if w.isupper() and len(w) > 1:
            capitalized_words.append(w)
        else:
            if '-' in w:
                parts = w.split('-')
                w = '-'.join([p[0].upper() + p[1:] if p else '' for p in parts])
            else:
                w = w[0].upper() + w[1:] if w else ''
            capitalized_words.append(w)
            
    return " ".join(capitalized_words)

GENERIC_BLACKLIST = {
    # Pronouns & basic structural words
    "something", "anything", "nothing", "someone", "anyone", "everyone", "nobody", "everybody",
    # Determiners/pronouns/connectors/common English words / prepositions
    "any", "all", "each", "even", "every", "some", "both", "either", "neither", "another", "other", "others", "such", "what", "which", "whose", "this", "that", "these", "those",
    "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "many", "much", "few", "fewer", "little", "less", "least", "more", "most", "several",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "first", "second", "third",
    "the", "a", "an", "in", "on", "at", "for", "to", "with", "by", "of", "and", "or", "but", "as", "if", "then", "when", "while", "because", "although", "since", "unless",
    "about", "above", "across", "after", "against", "along", "among", "around", "at", "before", "behind", "below",
    "beneath", "beside", "between", "beyond", "by", "down", "during", "except", "from", "inside", "into", "near",
    "off", "onto", "out", "outside", "over", "past", "through", "throughout", "toward", "under", "underneath", "until", "up", "upon", "within", "without",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing",
    "can", "could", "should", "would", "will", "shall", "may", "might", "must",
    # Common conversational fillers/adverbs/adjectives
    "for example", "such as", "however", "therefore", "nevertheless", "furthermore", "consequently",
    "indeed", "instead", "meanwhile", "besides", "moreover", "otherwise", "similarly", "specifically",
    "especially", "particularly", "primarily", "secondly", "thirdly", "finally", "lastly",
    # Generic, non-domain nouns & terms
    "example", "examples", "case", "cases", "thing", "things", "part", "parts", "term", "terms",
    "concept", "concepts", "system", "systems", "approach", "approaches", "model", "models",
    "method", "methods", "methodology", "methodologies", "framework", "frameworks", "process", "processes",
    "technology", "technologies", "application", "applications", "data", "information", "detail", "details",
    "fact", "facts", "idea", "ideas", "knowledge", "structure", "structures", "problem", "problems",
    "solution", "solutions", "challenge", "challenges", "result", "results", "analysis", "analyses",
    "evaluation", "evaluations", "experiment", "experiments", "test", "tests", "performance", "performances",
    "comparison", "comparisons", "difference", "differences", "similarity", "similarities", "feature", "features",
    "property", "properties", "characteristic", "characteristics", "aspect", "aspects", "factor", "factors",
    "element", "elements", "component", "components", "object", "objects", "subject", "subjects",
    "user", "users", "client", "clients", "server", "servers", "network", "networks", "environment", "environments",
    "device", "devices", "resource", "resources", "tool", "tools", "way", "ways", "mode", "modes", "step", "steps",
    "phase", "phases", "stage", "stages", "level", "levels", "type", "types", "kind", "kinds", "class", "classes",
    "group", "groups", "set", "sets", "category", "categories", "section", "sections", "chapter", "chapters",
    "page", "pages", "figure", "figures", "table", "tables", "chart", "charts", "graph", "graphs", "diagram", "diagrams",
    "image", "images", "file", "files", "document", "documents", "paper", "papers", "article", "articles",
    "text", "texts", "book", "books", "note", "notes", "key", "keys", "value", "values", "right", "left",
    "extracting", "consistent", "consistency", "volume", "connectivity", "requirement", "requirements",
    "usage", "frequency", "power", "connectivity", "thing", "things", "internet", "world", "critical",
    "abstract", "introduction", "conclusion", "discussion", "references", "author", "title", "pdf", "ocr", "scanned",
    # Computer science generic terms (isolated)
    "input", "output", "string", "strings", "cont", "cont.", "continued", "number", "numbers", "symbol", "symbols", 
    "character", "characters", "word", "words", "state", "states", "transition", "transitions", "diagram", "diagrams", 
    "theory", "theories", "theorem", "theorems", "definition", "definitions", "proof", "proofs",
    # Academic/document generic terms & textbook fillers
    "syllabus", "syllabi", "prepared", "prepared by", "lecture", "lectures", "course", "courses",
    "semester", "semesters", "academic", "year", "years", "issue", "issues", "journal", "journals",
    "review", "reviews", "downloaded", "download", "uploaded", "upload", "online", "offline",
    "website", "websites", "url", "urls", "http", "https", "www", "com", "org", "edu", "gov", "net",
    "page number", "page numbers", "header", "headers", "footer", "footers",
    "homework", "assignment", "assignments", "exam", "exams", "quiz", "quizzes", "practice",
    "unsolved", "solved", "exercise", "exercises", "question", "questions", "answer", "answers",
    "publisher", "publishing", "edition", "isbn", "copyright", "all rights reserved", "printed in", "library of congress",
    "web", "email", "mail", "unknown", "null", "none", "undefined", "n/a", "na",
    "chapter 1", "chapter 2", "chapter 3", "chapter 4", "chapter 5", "chapter 6",
    "section 1", "section 2", "section 3", "section 4", "section 5", "section 6",
    "table 1", "table 2", "table 3", "figure 1", "figure 2", "figure 3"
}

def calculate_entity_quality(name: str, label: str) -> float:
    # Clean the name first
    n_clean = normalize_and_clean_concept_name(name)
    if not n_clean or len(n_clean) < 3:
        return 0.0
    
    n_lower = n_clean.lower()
    words = n_clean.split()
    words_lower = [w.lower() for w in words]
    
    # 1. Keep only meaningful concepts, topics, authors, papers, and keywords
    valid_labels = {"Topic", "Subtopic", "Concept", "Technology", "Framework", "Application", "Paper", "Author", "Keyword", "Method", "Dataset"}
    if label not in valid_labels:
        return 0.0
        
    # 2. Reject nodes that contain more than 4 words
    if len(words) > 4:
        return 0.0
        
    # 3. Reject nodes that exceed 40 characters or are long merged strings without spaces
    if len(n_clean) > 40:
        return 0.0
    if len(words) == 1 and len(n_clean) > 17:
        return 0.0
        
    # 4. Reject nodes that look like sentences
    if re.search(r'[.!?;\:]\s', n_clean):
        return 0.0
        
    sentence_triggers = {
        "is", "are", "was", "were", "has", "have", "had", "can", "could", "should", "would", "will", 
        "does", "did", "shows", "defines", "refers", "represents", "describes", "explains", "contains", 
        "provides", "used", "includes", "introduces", "integrates", "demonstrates", "illustrates", "proves", 
        "analyzes", "implements", "requires", "needs", "allows", "enables", "creates", "helps", "makes", 
        "involves", "focuses", "suggests", "indicates", "supports"
    }
    if any(w in sentence_triggers for w in words_lower):
        return 0.0

    # 5. Length checks (too short)
    if len(n_clean) < 4:
        # Technical short acronyms/abbreviations must consist entirely of uppercase letters
        clean_alpha = re.sub(r'[^a-zA-Z]', '', n_clean)
        if not (clean_alpha.isupper() and clean_alpha.isalpha()):
            return 0.0  # too short and not a technical acronym (e.g. DFA, NFA, ZKP)
            
    # 6. Blacklist / Generic check (both exact and substring matching for common phrases)
    if n_lower in GENERIC_BLACKLIST:
        return 0.0
        
    # Singularized check
    singular_n = n_lower
    if n_lower.endswith('s') and not n_lower.endswith('ss') and not n_lower.endswith('us') and not n_lower.endswith('is'):
        singular_n = n_lower[:-1]
    if singular_n in GENERIC_BLACKLIST:
        return 0.0
        
    # Check repeating words: e.g. "Data Data Data", "data data", "Test Test Test", repeated words
    if re.search(r'\b(\w{2,})\b(?:\s+\1\b)+', n_lower):
        return 0.0
        
    # Check repeating character sequences: e.g. "TESTTESTTEST", "abcabcabc"
    if re.search(r'(\w{3,})\1+', n_lower):
        return 0.0
        
    # Check placeholder/spam terms: e.g. "abc", "xyz", "qwe", "testtest", "dummy", "lorem", "ipsum"
    spam_terms = {"abc", "xyz", "qwe", "foo", "bar", "baz", "test", "testtest", "dummy", "lorem", "ipsum", "placeholder", "testtesttest", "spam", "garbage"}
    if any(w in spam_terms for w in words_lower) or any(t in n_lower for t in ["abc xyz", "xyz qwe", "abc xyz qwe", "testtest"]):
        return 0.0

    # Check mixed alphanumeric random strings without spaces (e.g. XYZ123XYZ, ABC99XYZ)
    if re.search(r'\b[a-zA-Z]+\d+[a-zA-Z]+\b', n_lower) or re.search(r'\b\d+[a-zA-Z]+\d+\b', n_lower):
        return 0.0

    # Check for random strings/gibberish (length >= 4 and no vowels at all, e.g. XYZ123XYZ has no vowels, qwrty has no vowels)
    for w in words_lower:
        if len(w) >= 4 and not any(v in w for v in 'aeiouy'):
            return 0.0

    # 7. OCR / Punctuation noise and layout artifacts
    special_chars = len(re.findall(r'[^a-zA-Z0-9\s-]', n_clean))
    if special_chars > 2:
        return 0.1
        
    # Check if it consists mostly of numbers or contains noise patterns
    if re.search(r'\d{3,}', n_clean):  # 3 or more digits (like page numbers, years, serials)
        return 0.2
    if re.match(r'^[_\-\d\s\W]+$', n_clean):  # only symbols/digits
        return 0.0
        
    # 8. Section headers (e.g. "Chapter 1", "Section A", "Figure 5", "Page 1")
    if re.match(r'^(chapter|section|figure|table|page|index|appendix|vol|volume|no|part|fig)\b', n_lower):
        return 0.0
        
    # 9. Common transitional phrases
    if any(n_lower.startswith(x) for x in ["for example", "such as", "based on", "due to", "in order to"]):
        return 0.1

    return 1.0

def singularize_concept_name(name: str) -> str:
    n = name.strip()
    n_lower = n.lower()
    
    # Plural rules
    if n_lower.endswith('ies'):
        return n[:-3] + 'y'
    elif n_lower.endswith('es') and not n_lower.endswith('see'):
        if n_lower.endswith('ices'):
            return n[:-4] + 'ex'
        return n[:-2]
    elif n_lower.endswith('s') and not n_lower.endswith('ss') and not n_lower.endswith('us') and not n_lower.endswith('is'):
        return n[:-1]
    return n

class LLMClient:
    def __init__(self):
        self._client = None
        self._is_mock = False
        
        if not config.ANTHROPIC_API_KEY or "mock-api-key" in config.ANTHROPIC_API_KEY:
            logger.warning("Default/mock Anthropic key detected. Starting LLM client in mock mode.")
            self._is_mock = True
            return
            
        try:
            self._client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
            self._is_mock = False
            logger.info("Successfully connected to Anthropic Claude API.")
        except Exception as e:
            logger.warning(f"Failed to initialize Anthropic API client: {e}. Falling back to mock LLM mode.")
            self._is_mock = True

    def identify_main_topic(self, sample_text: str, filename: str) -> dict:
        if self._is_mock:
            return self._run_mock_main_topic(sample_text, filename)
            
        system_prompt = (
            "You are a main topic identification engine. Analyze the provided text sample from a document (and its filename) to identify the single primary topic/theme of the document. "
            "Return ONLY valid JSON matching this schema, no prose, no markdown fences:\n"
            "{\n"
            "  \"name\": \"Topic Name\",\n"
            "  \"description\": \"A short explanation of the topic/theme and its significance.\"\n"
            "}"
        )
        
        try:
            message = self._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1000,
                temperature=0,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Filename: {filename}\n\nText sample:\n\n{sample_text[:8000]}"}
                ]
            )
            content = message.content[0].text.strip()
            
            # Clean markdown JSON fences if LLM generated them
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            if "name" in data and "description" in data:
                return data
            raise ValueError("LLM returned JSON missing 'name' or 'description' keys.")
        except Exception as e:
            logger.error(f"Error during main topic identification: {e}")
            return self._run_mock_main_topic(sample_text, filename)

    def _run_mock_main_topic(self, sample_text: str, filename: str) -> dict:
        logger.info("[MOCK] Running mock main topic identification")
        sample_text_lower = sample_text.lower()
        filename_lower = filename.lower()
        
        if "attention" in sample_text_lower or "transformer" in sample_text_lower or "attention is all you need" in filename_lower:
            return {
                "name": "Transformer Architecture",
                "description": "A novel neural network architecture based solely on self-attention mechanisms, dispensing with recurrence and convolutions entirely."
            }
        elif "voting" in sample_text_lower or "blockchain" in sample_text_lower or "zkp" in sample_text_lower or "voting" in filename_lower:
            return {
                "name": "Secure Online Voting System",
                "description": "A secure, transparent, and tamper-proof online voting system using Blockchain that eliminates central administrator trust."
            }
        elif "knowledgeweb" in sample_text_lower or "blueprint" in filename_lower or "mindmprv" in filename_lower:
            return {
                "name": "KnowledgeWeb AI Architecture",
                "description": "GraphRAG-powered student prerequisite and citation mapping platform blueprint."
            }
            
        # Fallback
        clean_name = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').strip().title()
        if not clean_name:
            clean_name = "Document Analysis"
        return {
            "name": clean_name,
            "description": f"Unified knowledge map and conceptual analysis of the document {filename}."
        }
    def extract_graph_from_chunk(self, text_chunk: str) -> dict:
        if self._is_mock:
            return self._run_mock_extraction(text_chunk)
            
        system_prompt = (
            "You are a strict, grounded knowledge graph extraction engine designed to analyze research papers and build a deep semantic model of their content. "
            "Your task is to extract meaningful nodes and relationships based on document meaning across all sections (abstract, introduction, methodology, experiments, and conclusion) rather than just isolated keyword extraction. "
            "Ignore document formatting, syllabus/course guides, page repetitions, and OCR noise.\n\n"
            "Node categories/labels MUST be one of the following:\n"
            "- Topic: A primary core topic or main research subject of the document.\n"
            "- Subtopic: A specialized branch or sub-area belonging to a core Topic.\n"
            "- Concept: An abstract theoretical idea, model, mathematical model, metric, or definition.\n"
            "- Method: A specific research method, algorithm, model architecture, mathematical formulation, or technique introduced or utilized in the paper.\n"
            "- Dataset: A specific dataset, benchmark, corpus, or data source used for training, evaluation, experiments, or testing.\n"
            "- Technology: A primary physical or software system, hardware platform, protocol, or foundational technology.\n"
            "- Framework: A software library, toolset, architecture, model repository, or structured system framework.\n"
            "- Application: A practical use case, implementation scenario, or real-world benefit of a concept/technology.\n"
            "- Paper: A cited publication, book, or external academic reference.\n"
            "- Author: A researcher, author, or creator of a technology, method, or paper.\n"
            "- Keyword: Important terminology or search-level keyword tags.\n\n"
            "Extract paper-specific hierarchical, causal, and structural relationships using only these types:\n"
            "- CONTAINS: For hierarchical structures (e.g., Topic contains Subtopic, or Framework contains Concept).\n"
            "- PREREQUISITE_OF: For prerequisite requirements (e.g. Concept A must be understood before Concept B).\n"
            "- DEPENDS_ON: For direct dependencies (e.g., Framework A depends on Technology B).\n"
            "- EXTENDS: For inheritance, specialization, or subclassing (e.g., Subtopic B extends Topic A, or Method B extends Method A).\n"
            "- USES: For utilization/application (e.g., Method A uses Dataset B, or Framework A uses Concept B, or Method A uses Concept B).\n"
            "- USED_FOR: For indicating a method is used for a specific task or a dataset is used for evaluation (e.g., Dataset A is USED_FOR Method B, or Method A is USED_FOR Application B).\n"
            "- EVALUATED_ON: Specifically for linking a method or model to a dataset/benchmark it was tested on (e.g., Method A is EVALUATED_ON Dataset B).\n"
            "- CITES: For references/citations between papers.\n"
            "- AUTHORED_BY: For linking a Paper to its Author.\n"
            "- HAS_KEYWORD: For linking a Paper to a Keyword.\n"
            "- RELATED_TO: For general semantic association.\n\n"
            "CRITICAL EXTRACTION GUIDELINES:\n"
            "1. Deeply parse the document text (spanning Abstract, Introduction, Methodology, Experiments, and Conclusion) to extract the complete knowledge structure.\n"
            "2. Avoid extracting only high-level or title-level keywords. Extract specific, deep technical concepts, methods, and datasets discussed throughout the text.\n"
            "3. Aim to extract a rich set of nodes (concepts, methods, datasets, papers, authors) and their relationships. Extract as many meaningful entities and connections as present in the text chunk.\n"
            "4. Do NOT extract pronouns, determiners, fillers, section numbers, or formatting noise.\n"
            "5. Do NOT extract nodes that contain more than 4 words, look like sentences, or exceed 40 characters.\n"
            "6. For every extracted node, you MUST write a complete, rich, context-grounded description of at least 2-3 sentences based strictly on the text. Avoid single-word or brief descriptions.\n\n"
            "Return ONLY valid JSON matching this schema, no prose, no markdown fences:\n"
            "{\n"
            "  \"nodes\": [\n"
            "    {\"label\": \"Method\", \"name\": \"Multi-Head Attention\", \"description\": \"Multi-Head Attention is an attention mechanism running several scaled dot-product attention layers in parallel. It allows the model to jointly attend to information from different representation subspaces at different positions.\"},\n"
            "    {\"label\": \"Dataset\", \"name\": \"WMT 2014 English-to-German\", \"description\": \"WMT 2014 English-to-German is a standard machine translation dataset containing sentence pairs. It is used as a standard benchmark for evaluating the accuracy of sequence translation models.\"}\n"
            "  ],\n"
            "  \"relationships\": [\n"
            "    {\"from\": \"Multi-Head Attention\", \"to\": \"WMT 2014 English-to-German\", \"type\": \"EVALUATED_ON\"}\n"
            "  ]\n"
            "}\n"
            "Strict grounding constraint: The extracted nodes and relationships MUST reside strictly within the bounds of the provided text. Do not invent concepts or reference external context not present in the text."
        )
        
        try:
            message = self._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=4000,
                temperature=0,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Extract graph elements from this text chunk:\n\n{text_chunk}"}
                ]
            )
            content = message.content[0].text.strip()
            
            # Clean markdown JSON fences if LLM generated them
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            if "nodes" in data and "relationships" in data:
                return data
            raise ValueError("LLM returned JSON missing 'nodes' or 'relationships' keys.")
        except Exception as e:
            logger.error(f"Error during real LLM extraction: {e}")
            raise e

    def _run_mock_extraction(self, text_chunk: str) -> dict:
        logger.info("[MOCK] Running strictly grounded dynamic mock extraction on text chunk")
        
        text_chunk_lower = text_chunk.lower()
        if "noisy_pdf_trigger" in text_chunk_lower:
            logger.info("[MOCK] Returning noisy nodes to trigger the 80% validation failure.")
            nodes = [
                {"label": "Concept", "name": "Valid Concept One", "description": "This is a valid domain concept."},
                {"label": "Concept", "name": "Lorem", "description": "Garbage entity."},
                {"label": "Concept", "name": "Page 1", "description": "Garbage entity."},
                {"label": "Concept", "name": "Test Test Test", "description": "Garbage entity."},
                {"label": "Concept", "name": "XYZ123XYZ", "description": "Garbage entity."},
                {"label": "Concept", "name": "abc", "description": "Too short."},
                {"label": "Concept", "name": "xyz qwe", "description": "Spam term."},
            ]
            relationships = []
            return {"nodes": nodes, "relationships": relationships}

        if "automata" in text_chunk_lower or "dfa" in text_chunk_lower or "nfa" in text_chunk_lower or "regular expression" in text_chunk_lower:
            logger.info("[MOCK] Returning custom automata theory knowledge graph.")
            nodes = [
                {"label": "Topic", "name": "Automata Theory", "description": "A branch of computer science that deals with the definitions and properties of mathematical models of computation, such as finite automata and grammars."},
                {"label": "Concept", "name": "Finite Automata", "description": "A simple model of computation consisting of a set of states, transitions, an initial state, and accepting states."},
                {"label": "Concept", "name": "DFA", "description": "Deterministic Finite Automata, a finite state machine where for each state there is exactly one transition for each possible input symbol."},
                {"label": "Concept", "name": "NFA", "description": "Nondeterministic Finite Automata, a finite state machine where for a state and input symbol, there can be multiple next states or transition on empty input."},
                {"label": "Concept", "name": "Regular Expression", "description": "A sequence of characters that forms a search pattern, representing a regular language algebraically."},
                {"label": "Concept", "name": "Regular Grammar", "description": "A formal grammar where all production rules are restricted to linear forms, generating regular languages."},
                {"label": "Concept", "name": "Language", "description": "A set of strings over a finite alphabet, representing the computational problems recognized by automata."},
                {"label": "Concept", "name": "Transition Diagram", "description": "A directed graph representing a finite automaton, where nodes represent states and edges represent transitions."},
                # Garbage nodes that MUST be filtered out by quality checker
                {"label": "Concept", "name": "Any", "description": "This is a garbage node that should be filtered out."},
                {"label": "Concept", "name": "All", "description": "This is a garbage node that should be filtered out."},
                {"label": "Concept", "name": "Each", "description": "This is a garbage node that should be filtered out."},
                {"label": "Concept", "name": "Even", "description": "This is a garbage node that should be filtered out."},
                {"label": "Concept", "name": "Cont", "description": "This is a garbage node that should be filtered out."},
                {"label": "Concept", "name": "Input", "description": "This is a garbage node that should be filtered out."},
                {"label": "Concept", "name": "String", "description": "This is a garbage node that should be filtered out."}
            ]
            relationships = [
                {"from": "Automata Theory", "to": "Finite Automata", "type": "USES_METHOD"},
                {"from": "Finite Automata", "to": "DFA", "type": "EXTENDS"},
                {"from": "Finite Automata", "to": "NFA", "type": "EXTENDS"},
                {"from": "DFA", "to": "NFA", "type": "RELATED_TO"},
                {"from": "DFA", "to": "Transition Diagram", "type": "USES_METHOD"},
                {"from": "NFA", "to": "Transition Diagram", "type": "USES_METHOD"},
                {"from": "Regular Expression", "to": "Finite Automata", "type": "RELATED_TO"},
                {"from": "Regular Grammar", "to": "Regular Expression", "type": "RELATED_TO"},
                {"from": "Finite Automata", "to": "Language", "type": "PREREQUISITE_OF"},
                # Relationships for garbage nodes (just to see if they get correctly cleaned)
                {"from": "Finite Automata", "to": "Any", "type": "RELATED_TO"},
                {"from": "DFA", "to": "All", "type": "RELATED_TO"},
                {"from": "NFA", "to": "Each", "type": "RELATED_TO"}
            ]
            return {"nodes": nodes, "relationships": relationships}

        if "attention" in text_chunk_lower or "transformer" in text_chunk_lower or "encoder" in text_chunk_lower or "decoder" in text_chunk_lower:
            logger.info("[MOCK] Returning custom unified Transformer/Attention knowledge graph.")
            nodes = [
                {"label": "Topic", "name": "Transformer Architecture", "description": "The Transformer architecture is a novel sequence transduction model based entirely on self-attention mechanisms. It dispenses with recurrence and convolutions, relying on stacked self-attention and position-wise feed-forward layers to process sequences in parallel."},
                {"label": "Framework", "name": "Encoder Stack", "description": "The Encoder Stack is composed of a stack of six identical layers. Each layer contains two sub-layers: a multi-head self-attention mechanism and a position-wise fully connected feed-forward network. It maps an input sequence of symbol representations to a continuous sequence of representations."},
                {"label": "Framework", "name": "Decoder Stack", "description": "The Decoder Stack consists of a stack of six identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer which performs multi-head attention over the output of the encoder stack. It also utilizes masked self-attention to prevent positions from attending to subsequent positions."},
                {"label": "Method", "name": "Self-Attention", "description": "Self-Attention, also known as intra-attention, is an attention mechanism relating different positions of a single sequence in order to compute a representation of the sequence. It has been used successfully in a variety of tasks including reading comprehension, abstractive summarization, and textual entailment."},
                {"label": "Method", "name": "Multi-Head Attention", "description": "Multi-Head Attention projects queries, keys, and values linearly h times with different, learned linear projections to dk, dk, and dv dimensions, respectively. On each of these projected versions of queries, keys, and values, attention is performed in parallel, yielding dv-dimensional output values. These are concatenated and projected, resulting in final values."},
                {"label": "Method", "name": "Scaled Dot-Product Attention", "description": "Scaled Dot-Product Attention is an attention function where the input consists of queries and keys of dimension dk, and values of dimension dv. It computes the dot products of the query with all keys, divides each by the square root of dk, and applies a softmax function to obtain the weights on the values. It is extremely fast and space-efficient in practice."},
                {"label": "Method", "name": "Encoder-Decoder Attention", "description": "Encoder-Decoder Attention is a sub-layer in the decoder stack where the queries come from the previous decoder layer, and the memory keys and values come from the output of the encoder. This allows every position in the decoder to attend over all positions in the input sequence, mimicking the typical encoder-decoder attention mechanisms in sequence-to-sequence models."},
                {"label": "Method", "name": "Position-wise Feed-Forward Networks", "description": "Position-wise Feed-Forward Networks are applied to each position separately and identically in both the encoder and decoder stacks. This consists of two linear transformations with a ReLU activation in between. While the linear transformations are identical across different positions, they use different parameters from layer to layer."},
                {"label": "Concept", "name": "Positional Encoding", "description": "Positional Encodings are added to the input embeddings at the bottoms of the encoder and decoder stacks to inject information about the relative or absolute positions of tokens in the sequence. Since the Transformer architecture contains no recurrence or convolution, it requires positional encodings to make use of the order of the sequence."},
                {"label": "Concept", "name": "Learned Embeddings", "description": "Learned Embeddings are used to convert the input tokens and output tokens to vectors of dimension d_model. The model shares the same weight matrix between the two embedding layers and the pre-softmax linear transformation. This maps discrete vocabulary tokens into continuous representation spaces."},
                {"label": "Concept", "name": "Residual Connections", "description": "Residual Connections are skip connections employed around each of the sub-layers in both the encoder and decoder. Each sub-layer output is followed by layer normalization. This structural layout helps preserve gradient flow and enables stable optimization of extremely deep architectures."},
                {"label": "Method", "name": "Layer Normalization", "description": "Layer Normalization is an normalization technique applied after residual connections in the encoder and decoder stacks. It normalizes the activations across all features in a layer for each individual training example. This stabilizes the dynamics of training and reduces training time significantly."},
                {"label": "Method", "name": "Softmax Function", "description": "The Softmax Function is a mathematical function that converts a vector of numbers into a vector of probabilities that sum to one. In the Transformer, it is used in the attention calculation to compute weight distributions over values and at the final layer to predict next-token probabilities."},
                {"label": "Method", "name": "Adam Optimizer", "description": "The Adam Optimizer is an optimization algorithm that uses adaptive learning rates for training deep neural networks. In the Transformer paper, it is used with beta1=0.9, beta2=0.98, and epsilon=1e-9. The learning rate is varied dynamically during training according to a formula that increases linearly for warmup steps and decreases thereafter."},
                {"label": "Concept", "name": "Residual Dropout", "description": "Residual Dropout is a regularization technique where dropout is applied to the output of each sub-layer, before it is added to the sub-layer input and normalized. It is also applied to the sums of the embeddings and positional encodings in both the encoder and decoder stacks. This reduces overfitting during training."},
                {"label": "Concept", "name": "Label Smoothing", "description": "Label Smoothing is a regularization technique that introduces uncertainty during training by preventing the model from predicting classes too confidently. During training, label smoothing of value 0.1 was employed. This hurts perplexity as the model learns to be more unsure, but improves accuracy and BLEU score overall."},
                {"label": "Method", "name": "BPE Tokenization", "description": "Byte-Pair Encoding (BPE) Tokenization is a subword tokenization technique used to split text into subword units. In the Transformer paper, English-German translation was performed using a shared source-target vocabulary constructed with byte-pair encoding. It helps handle out-of-vocabulary words cleanly by breaking them down into known subwords."},
                {"label": "Concept", "name": "BLEU Score", "description": "Bilingual Evaluation Understudy (BLEU) Score is an algorithm for evaluating the quality of text which has been machine-translated from one natural language to another. Quality is measured by comparing the machine translation outputs with human reference translations. It ranges from 0 to 1, with higher scores indicating higher quality."},
                {"label": "Concept", "name": "Sequence Transduction", "description": "Sequence Transduction is the general task of mapping an input sequence of symbols to an output sequence of symbols. Examples include machine translation, text-to-speech, and automatic speech recognition. Traditionally, these models relied on recurrent neural networks or convolutional neural networks."},
                {"label": "Concept", "name": "Vanishing Gradient Problem", "description": "The Vanishing Gradient Problem is a difficulty in training artificial neural networks with gradient-based learning methods. Backpropagated gradients can decrease exponentially as they travel backward through deep layers, halting learning. The Transformer mitigates this using residual connections and layer normalization."},
                {"label": "Concept", "name": "Sequence Alignment", "description": "Sequence Alignment is the task of mapping corresponding segments or tokens between sequences. In machine translation, alignment determines which words in the source sentence translate to which words in the target. The Transformer uses self-attention to dynamically align and weigh tokens without recurrence."},
                {"label": "Dataset", "name": "WMT 2014 English-to-German", "description": "WMT 2014 English-to-German is a standard machine translation dataset consisting of 4.5 million sentence pairs. It is used as the primary benchmark to evaluate translation models. The Transformer achieved a record BLEU score of 28.4 on this dataset, outperforming previous state-of-the-art models."},
                {"label": "Dataset", "name": "WMT 2014 English-to-French", "description": "WMT 2014 English-to-French is a large machine translation dataset consisting of 36 million sentence pairs. It is used to test the scalability of translation models on massive data. The Transformer achieved a BLEU score of 41.8 on this dataset after training for 3 days."},
                {"label": "Paper", "name": "Attention Is All You Need", "description": "Attention Is All You Need is the landmark paper published by researchers at Google Brain in 2017. It introduced the Transformer architecture, showing that self-attention alone could replace recurrence and convolution for state-of-the-art sequence translation. It is one of the most cited AI papers of all time.", "year": 2017, "doi": "10.48550/arXiv.1706.03762"},
                {"label": "Paper", "name": "Neural Machine Translation by Jointly Learning to Align and Translate", "description": "Neural Machine Translation by Jointly Learning to Align and Translate is a foundational paper by Dzmitry Bahdanau, Kyunghyun Cho, and Yoshua Bengio in 2014. It introduced the concept of soft-attention in neural machine translation, allowing a model to search for relevant source positions dynamically. The Transformer builds directly on this soft-attention concept.", "year": 2014, "doi": "10.48550/arXiv.1409.0473"},
                {"label": "Author", "name": "Ashish Vaswani", "description": "Ashish Vaswani is a co-author of the paper 'Attention Is All You Need' and was a prominent researcher at Google Brain. He contributed significantly to the core design of the Transformer architecture and attention mechanism formulations."},
                {"label": "Author", "name": "Noam Shazeer", "description": "Noam Shazeer is a co-author of 'Attention Is All You Need' and was a senior researcher at Google Brain. He is known for key scaling contributions, optimizer selection, and multi-head attention optimizations that made the Transformer trainable."},
                {"label": "Author", "name": "Niki Parmar", "description": "Niki Parmar is a co-author of 'Attention Is All You Need' and worked as an AI researcher at Google Brain. She focused on sequence transduction model scaling and performance evaluation on English-to-German and English-to-French benchmarks."},
                {"label": "Author", "name": "Jakob Uszkoreit", "description": "Jakob Uszkoreit is a co-author of 'Attention Is All You Need' who initiated the idea of replacing recurrent networks with self-attention. He has made major contributions to natural language processing and neural model design."},
                {"label": "Author", "name": "Aidan N. Gomez", "description": "Aidan N. Gomez is a co-author of 'Attention Is All You Need' who conducted deep experiments on hyperparameters, dropout regularizations, and learning rate warmups. He is the co-founder and CEO of Cohere."},
                {"label": "Author", "name": "Lukasz Kaiser", "description": "Lukasz Kaiser is a co-author of 'Attention Is All You Need' and researcher at Google Brain. He contributed to the software implementation of the model in Tensor2Tensor and optimization algorithms."},
                {"label": "Author", "name": "Illia Polosukhin", "description": "Illia Polosukhin is a co-author of 'Attention Is All You Need' and former researcher at Google. He worked on attention model evaluations and later co-founded NEAR Protocol."},
                {"label": "Author", "name": "Dzmitry Bahdanau", "description": "Dzmitry Bahdanau is the lead author of the 2014 alignment paper and a pioneer in attention mechanisms. His work on dynamic soft alignment laid the foundation for modern attention architectures."},
                {"label": "Keyword", "name": "Deep Learning", "description": "Deep Learning is a subset of machine learning based on multi-layered artificial neural networks. It enables learning representations directly from raw data, powering modern computer vision and natural language processing applications."},
                {"label": "Keyword", "name": "Natural Language Processing", "description": "Natural Language Processing (NLP) is a branch of artificial intelligence concerned with the interaction between computers and human languages. Tasks include translation, sentiment analysis, named entity recognition, and question answering."},
                {"label": "Keyword", "name": "Machine Translation", "description": "Machine Translation is the sub-field of computational linguistics that focuses on using software to translate text or speech from one natural language to another. The Transformer revolutionized this field by setting new translation benchmarks."}
            ]
            relationships = [
                {"from": "Attention Is All You Need", "to": "Ashish Vaswani", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Noam Shazeer", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Niki Parmar", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Jakob Uszkoreit", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Aidan N. Gomez", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Lukasz Kaiser", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Illia Polosukhin", "type": "AUTHORED_BY"},
                {"from": "Neural Machine Translation by Jointly Learning to Align and Translate", "to": "Dzmitry Bahdanau", "type": "AUTHORED_BY"},
                {"from": "Attention Is All You Need", "to": "Neural Machine Translation by Jointly Learning to Align and Translate", "type": "CITES"},
                {"from": "Attention Is All You Need", "to": "Transformer Architecture", "type": "USES"},
                {"from": "Transformer Architecture", "to": "Encoder Stack", "type": "CONTAINS"},
                {"from": "Transformer Architecture", "to": "Decoder Stack", "type": "CONTAINS"},
                {"from": "Encoder Stack", "to": "Multi-Head Attention", "type": "USES"},
                {"from": "Decoder Stack", "to": "Multi-Head Attention", "type": "USES"},
                {"from": "Decoder Stack", "to": "Encoder-Decoder Attention", "type": "USES"},
                {"from": "Multi-Head Attention", "to": "Scaled Dot-Product Attention", "type": "USES"},
                {"from": "Scaled Dot-Product Attention", "to": "Softmax Function", "type": "USES"},
                {"from": "Multi-Head Attention", "to": "Self-Attention", "type": "USES"},
                {"from": "Encoder Stack", "to": "Position-wise Feed-Forward Networks", "type": "USES"},
                {"from": "Decoder Stack", "to": "Position-wise Feed-Forward Networks", "type": "USES"},
                {"from": "Encoder Stack", "to": "Residual Connections", "type": "USES"},
                {"from": "Decoder Stack", "to": "Residual Connections", "type": "USES"},
                {"from": "Residual Connections", "to": "Layer Normalization", "type": "USES"},
                {"from": "Transformer Architecture", "to": "Positional Encoding", "type": "USES"},
                {"from": "Transformer Architecture", "to": "Learned Embeddings", "type": "USES"},
                {"from": "Transformer Architecture", "to": "Adam Optimizer", "type": "USES"},
                {"from": "Transformer Architecture", "to": "BPE Tokenization", "type": "USES"},
                {"from": "Transformer Architecture", "to": "Residual Dropout", "type": "USES"},
                {"from": "Transformer Architecture", "to": "Label Smoothing", "type": "USES"},
                {"from": "Transformer Architecture", "to": "WMT 2014 English-to-German", "type": "EVALUATED_ON"},
                {"from": "Transformer Architecture", "to": "WMT 2014 English-to-French", "type": "EVALUATED_ON"},
                {"from": "BPE Tokenization", "to": "WMT 2014 English-to-German", "type": "USED_FOR"},
                {"from": "BLEU Score", "to": "WMT 2014 English-to-German", "type": "EVALUATED_ON"},
                {"from": "BLEU Score", "to": "WMT 2014 English-to-French", "type": "EVALUATED_ON"},
                {"from": "Label Smoothing", "to": "BLEU Score", "type": "RELATED_TO"},
                {"from": "Residual Dropout", "to": "BLEU Score", "type": "RELATED_TO"},
                {"from": "Sequence Transduction", "to": "Machine Translation", "type": "RELATED_TO"},
                {"from": "Transformer Architecture", "to": "Sequence Transduction", "type": "USED_FOR"},
                {"from": "Neural Machine Translation by Jointly Learning to Align and Translate", "to": "Sequence Transduction", "type": "USED_FOR"},
                {"from": "Vanishing Gradient Problem", "to": "Residual Connections", "type": "RELATED_TO"},
                {"from": "Sequence Alignment", "to": "Self-Attention", "type": "RELATED_TO"},
                {"from": "Attention Is All You Need", "to": "Deep Learning", "type": "HAS_KEYWORD"},
                {"from": "Attention Is All You Need", "to": "Natural Language Processing", "type": "HAS_KEYWORD"},
                {"from": "Attention Is All You Need", "to": "Machine Translation", "type": "HAS_KEYWORD"}
            ]
            return {"nodes": nodes, "relationships": relationships}

        if "voting" in text_chunk_lower or "blockchain" in text_chunk_lower or "zkp" in text_chunk_lower or "blind signature" in text_chunk_lower:
            logger.info("[MOCK] Returning custom unified blockchain voting system knowledge graph.")
            nodes = [
                {"label": "Topic", "name": "Secure Online Voting System", "description": "A secure, transparent, and tamper-proof online voting system using Blockchain that eliminates central administrator trust."},
                {"label": "Method", "name": "Zero-Knowledge Proofs", "description": "Zero-Knowledge Proofs are cryptographic methods enabling verification of voter eligibility without disclosing voter identity. This prevents double voting while protecting voter privacy."},
                {"label": "Method", "name": "Blind Signatures", "description": "Blind Signatures are cryptographic signature methods that validate the voting token without revealing the voter's choice. This prevents voter-vote linkage."},
                {"label": "Method", "name": "Commit-Reveal Mechanism", "description": "Commit-Reveal Mechanism is a two-phase voting protocol (commit and reveal) to prevent vote tampering during the active voting phase. It prevents voters from changing their choices after seeing intermediate results."},
                {"label": "Method", "name": "Decentralized Identity", "description": "Decentralized Identity is a privacy-preserving identity verification method used for secure voter registration. It allows voters to prove eligibility without centralized database lookup."},
                {"label": "Method", "name": "Threshold Decryption", "description": "Threshold Decryption is a decryption method requiring multiple key holders to collaborate to access vote content. This ensures no single authority can decrypt and read individual votes before the election ends."},
                {"label": "Concept", "name": "Zero-Trust Admin Architecture", "description": "Zero-Trust Admin Architecture is a system design ensuring that administrators and key holders cannot view, modify, or link votes. It operates under the assumption that any system actor could be compromised."},
                {"label": "Concept", "name": "Voter Application", "description": "Voter Application is the client-side interface where voters register, obtain anonymous tokens, and submit encrypted votes."},
                {"label": "Concept", "name": "Blockchain Network", "description": "Blockchain Network is the decentralized infrastructure providing an immutable ledger for vote hash storage and smart contract execution."},
                {"label": "Method", "name": "Smart Contracts", "description": "Smart Contracts are self-executing protocols on the blockchain that enforce voting rules and verify Zero-Knowledge Proofs automatically without human intervention."},
                {"label": "Framework", "name": "IPFS", "description": "IPFS is the InterPlanetary File System used to store encrypted voting records in a secure, decentralized, content-addressed manner."},
                {"label": "Concept", "name": "Election Committee", "description": "Election Committee is a distributed set of key holders responsible for executing threshold decryption once voting has concluded."},
                {"label": "Keyword", "name": "Nullifier Hashes", "description": "Nullifier Hashes are unique identifiers used to record that a vote has been cast. They prevent duplicate voting without breaking anonymity."},
                {"label": "Concept", "name": "Trustless Governance", "description": "Trustless Governance is a governance framework operating transparently without relying on the integrity of any central party."},
                {"label": "Concept", "name": "Voter Anonymity", "description": "Voter Anonymity is the complete cryptographic separation of the voter's real identity from the cast ballot contents."},
                {"label": "Paper", "name": "Untraceable Electronic Mail and Digital Pseudonyms", "description": "Untraceable Electronic Mail and Digital Pseudonyms is David Chaum's pioneering 1981 paper. It laid the foundation for anonymous communication, mixes, and digital signature techniques.", "year": 1981, "doi": "10.1145/358549.358563"},
                {"label": "Paper", "name": "A Cryptographic Voting Scheme", "description": "A Cryptographic Voting Scheme is a landmark academic paper describing anonymous voting using blind signatures and cryptographic verification mechanisms.", "year": 1988, "doi": "10.1007/3-540-45961-8_35"},
                {"label": "Author", "name": "David Chaum", "description": "David Chaum is a world-renowned computer scientist and cryptographer. He is the inventor of blind signatures and digital cash, and a pioneer in privacy-enhancing technologies."}
            ]
            relationships = [
                {"from": "Secure Online Voting System", "to": "Zero-Knowledge Proofs", "type": "USES"},
                {"from": "Secure Online Voting System", "to": "Blind Signatures", "type": "USES"},
                {"from": "Secure Online Voting System", "to": "Commit-Reveal Mechanism", "type": "USES"},
                {"from": "Secure Online Voting System", "to": "Decentralized Identity", "type": "USES"},
                {"from": "Secure Online Voting System", "to": "Threshold Decryption", "type": "USES"},
                {"from": "Secure Online Voting System", "to": "Zero-Trust Admin Architecture", "type": "USES"},
                {"from": "Secure Online Voting System", "to": "Blockchain Network", "type": "DEPENDS_ON"},
                {"from": "Secure Online Voting System", "to": "Voter Application", "type": "DEPENDS_ON"},
                {"from": "Voter Application", "to": "Decentralized Identity", "type": "DEPENDS_ON"},
                {"from": "Voter Application", "to": "Blind Signatures", "type": "USES"},
                {"from": "Blockchain Network", "to": "Smart Contracts", "type": "USES"},
                {"from": "Blockchain Network", "to": "IPFS", "type": "USES"},
                {"from": "Smart Contracts", "to": "Zero-Knowledge Proofs", "type": "USES"},
                {"from": "Smart Contracts", "to": "Nullifier Hashes", "type": "USES"},
                {"from": "Zero-Knowledge Proofs", "to": "Nullifier Hashes", "type": "RELATED_TO"},
                {"from": "Zero-Knowledge Proofs", "to": "Voter Anonymity", "type": "RELATED_TO"},
                {"from": "Blind Signatures", "to": "Voter Anonymity", "type": "RELATED_TO"},
                {"from": "Decentralized Identity", "to": "Voter Anonymity", "type": "RELATED_TO"},
                {"from": "Commit-Reveal Mechanism", "to": "IPFS", "type": "RELATED_TO"},
                {"from": "Threshold Decryption", "to": "Election Committee", "type": "DEPENDS_ON"},
                {"from": "Zero-Trust Admin Architecture", "to": "Threshold Decryption", "type": "RELATED_TO"},
                {"from": "Zero-Trust Admin Architecture", "to": "Trustless Governance", "type": "RELATED_TO"},
                {"from": "Blockchain Network", "to": "Trustless Governance", "type": "RELATED_TO"},
                {"from": "Voter Anonymity", "to": "Trustless Governance", "type": "RELATED_TO"},
                {"from": "Nullifier Hashes", "to": "Voter Anonymity", "type": "RELATED_TO"},
                {"from": "A Cryptographic Voting Scheme", "to": "David Chaum", "type": "AUTHORED_BY"},
                {"from": "Untraceable Electronic Mail and Digital Pseudonyms", "to": "David Chaum", "type": "AUTHORED_BY"},
                {"from": "A Cryptographic Voting Scheme", "to": "Untraceable Electronic Mail and Digital Pseudonyms", "type": "CITES"},
                {"from": "Secure Online Voting System", "to": "A Cryptographic Voting Scheme", "type": "USES"}
            ]
            return {"nodes": nodes, "relationships": relationships}

        STOP_WORDS = {
            "the", "a", "an", "in", "on", "at", "for", "to", "with", "by", "of", "and", "or", "but", 
            "this", "that", "these", "those", "it", "they", "we", "you", "he", "she", "as", "if", "when", 
            "is", "are", "was", "were", "been", "have", "has", "had", "do", "does", "did", "can", "could", 
            "should", "would", "will", "from", "through", "during", "before", "after", "under", "over", 
            "between", "among", "chapter", "section", "however", "therefore", "although", "furthermore",
            "thus", "so", "also", "then", "there", "their", "its", "our", "your", "my", "his", "her",
            "i", "you", "he", "him", "his", "himself", "she", "her", "hers", "herself", "itself", 
            "they", "them", "their", "theirs", "themselves", "what", "which", "who", "whom", "this", 
            "that", "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", 
            "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", 
            "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", 
            "about", "against", "between", "into", "through", "during", "before", "after", "above", 
            "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", 
            "further", "then", "once"
        }

        nodes = []
        relationships = []
        
        # Split text chunk into sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text_chunk) if s.strip()]
        
        concepts_map = {}
        
        # 1. Extract Capitalized Candidate Phrases
        for sent in sentences:
            # Find sequences of capitalized words
            matches = re.findall(r'\b([A-Z][a-zA-Z0-9\'-]*(?:\s+[A-Z][a-zA-Z0-9\'-]*)*)\b', sent)
            for phrase in matches:
                phrase_clean = phrase.strip()
                
                phrase_low = phrase_clean.lower()
                if phrase_low in STOP_WORDS or len(phrase_clean) < 3:
                    continue
                
                # Normalize name (singularize common plurals)
                normalized_name = singularize_concept_name(phrase_clean)
                normalized_low = normalized_name.lower()
                
                # Deduplicate and create candidate node
                if normalized_low not in concepts_map:
                    # Dynamically determine Label
                    label = "Concept"
                    if any(x in normalized_name for x in ["University", "Institute", "Research", "Lab", "Company", "Google", "Microsoft"]):
                        label = "Institution"
                    elif any(x in normalized_name.lower() for x in ["dataset", "benchmark", "corpus", "data", "source", "wmt", "imagenet", "glue"]):
                        label = "Dataset"
                    elif any(x in normalized_name.lower() for x in ["method", "algorithm", "model", "approach", "architecture", "framework", "network", "function", "optimizer"]):
                        label = "Method"
                    elif normalized_name.startswith("Chapter") or normalized_name.startswith("Section"):
                        label = "Topic"
                    elif len(normalized_name.split()) == 1 and len(normalized_name) > 3:
                        label = "Keyword"
                    
                    # Try to extract a definition from the sentence
                    description = ""
                    def_match = re.search(
                        rf"\b{re.escape(phrase_clean)}\b\s+(?:is\s+defined\s+as|refers\s+to|represents|denotes|means|is\s+an?|is|are|were|was)\s+([^.!?\n]{5,150})", 
                        sent, 
                        re.IGNORECASE
                    )
                    if def_match:
                        description = def_match.group(1).strip()
                        if description:
                            description = description[0].upper() + description[1:]
                    else:
                        # Fallback: clean the sentence containing the concept as description
                        description = sent
                        if len(description) > 150:
                            description = description[:147] + "..."
                            
                    concepts_map[normalized_low] = {
                        "label": label,
                        "name": normalized_name,
                        "description": description
                    }

        # 1.1 Extract Technical Suffix Phrases (Domain Specific Noun Phrases)
        domain_keywords = [
            "system", "architecture", "method", "algorithm", "model", "approach", 
            "framework", "network", "function", "mechanism", "protocol", "identity", 
            "ledger", "credit", "market", "infrastructure", "verification", "technology",
            "proof", "signature", "decryption", "blockchain", "contract", "security"
        ]
        
        for sent in sentences:
            words = sent.split()
            for i in range(len(words)):
                w = words[i].lower().strip(',.;:()[]{}!?"\'')
                if w in domain_keywords:
                    phrase_words = []
                    j = i - 1
                    while j >= max(0, i - 2):
                        prev_w = words[j].strip(',.;:()[]{}!?"\'')
                        prev_w_low = prev_w.lower()
                        if (
                            prev_w_low not in STOP_WORDS 
                            and prev_w_low not in GENERIC_BLACKLIST
                            and prev_w.isalpha()
                            and not prev_w.isupper()
                        ):
                            phrase_words.insert(0, prev_w)
                            j -= 1
                        else:
                            break
                    phrase_words.append(words[i].strip(',.;:()[]{}!?"\''))
                    if len(phrase_words) >= 2:
                        phrase_clean = " ".join(phrase_words)
                        normalized_name = singularize_concept_name(phrase_clean)
                        normalized_name = " ".join([word.capitalize() for word in normalized_name.split()])
                        normalized_low = normalized_name.lower()
                        
                        if normalized_low not in concepts_map and len(normalized_name) > 3:
                            label = "Concept"
                            if any(x in normalized_low for x in ["method", "algorithm", "model", "approach", "architecture", "framework", "network", "function", "optimizer"]):
                                label = "Method"
                            elif any(x in normalized_low for x in ["dataset", "benchmark", "corpus", "data", "source", "wmt", "imagenet", "glue"]):
                                label = "Dataset"
                            elif any(x in normalized_low for x in ["blockchain", "oracle", "satellite", "system", "technology"]):
                                label = "Technology"
                                
                            description = sent
                            if len(description) > 150:
                                description = description[:147] + "..."
                                
                            concepts_map[normalized_low] = {
                                "label": label,
                                "name": normalized_name,
                                "description": description
                            }

        # Cap dynamic concept count to 15 per chunk to avoid rendering messy graphs
        sorted_concepts = list(concepts_map.values())[:15]
        nodes.extend(sorted_concepts)
        
        # Update concepts_map to only contain the kept concepts
        concepts_map = {n["name"].lower(): n for n in sorted_concepts}

        # 2. Extract Relationships
        for sent in sentences:
            sent_low = sent.lower()
            present_concepts = []
            for norm_name, node in concepts_map.items():
                if re.search(rf"\b{re.escape(node['name'])}\b", sent, re.IGNORECASE):
                    present_concepts.append(node['name'])
            
            if len(present_concepts) >= 2:
                # Link pairs of concepts present in the same sentence
                for i in range(len(present_concepts) - 1):
                    for j in range(i + 1, len(present_concepts)):
                        c1 = present_concepts[i]
                        c2 = present_concepts[j]
                        
                        c1_node = concepts_map[c1.lower()]
                        c2_node = concepts_map[c2.lower()]
                        
                        if c1_node["label"] == "Keyword" or c2_node["label"] == "Keyword":
                            if c2_node["label"] == "Keyword":
                                relationships.append({"from": c1, "to": c2, "type": "HAS_KEYWORD"})
                            else:
                                relationships.append({"from": c2, "to": c1, "type": "HAS_KEYWORD"})
                            continue
                        
                        c1_pos = sent_low.find(c1.lower())
                        c2_pos = sent_low.find(c2.lower())
                        
                        start_pos = min(c1_pos, c2_pos) + (len(c1) if c1_pos < c2_pos else len(c2))
                        end_pos = max(c1_pos, c2_pos)
                        between_text = sent_low[start_pos:end_pos]
                        
                        rel_type = "RELATED_TO"
                        if "depends" in between_text or "requires" in between_text or "built upon" in between_text:
                            if c1_pos < c2_pos:
                                relationships.append({"from": c2, "to": c1, "type": "PREREQUISITE_OF"})
                            else:
                                relationships.append({"from": c1, "to": c2, "type": "PREREQUISITE_OF"})
                        elif "prerequisite" in sent_low or "precedes" in between_text or "comes before" in between_text:
                            if c1_pos < c2_pos:
                                relationships.append({"from": c1, "to": c2, "type": "PREREQUISITE_OF"})
                            else:
                                relationships.append({"from": c2, "to": c1, "type": "PREREQUISITE_OF"})
                        elif "extends" in between_text or "generalizes" in between_text or "is a type of" in between_text:
                            if c1_pos < c2_pos:
                                relationships.append({"from": c1, "to": c2, "type": "EXTENDS"})
                            else:
                                relationships.append({"from": c2, "to": c1, "type": "EXTENDS"})
                        elif "contradicts" in between_text or "opposes" in between_text or "in contrast to" in between_text:
                            relationships.append({"from": c1, "to": c2, "type": "CONTRADICTS"})
                        elif "uses" in between_text or "utilizes" in between_text or "employs" in between_text:
                            if c1_node["label"] == "Method" and c2_node["label"] == "Dataset":
                                relationships.append({"from": c1, "to": c2, "type": "EVALUATED_ON"})
                            elif c2_node["label"] == "Method" and c1_node["label"] == "Dataset":
                                relationships.append({"from": c2, "to": c1, "type": "EVALUATED_ON"})
                            elif c1_node["label"] == "Dataset" or c2_node["label"] == "Dataset":
                                if c1_node["label"] == "Dataset":
                                    relationships.append({"from": c2, "to": c1, "type": "USES"})
                                else:
                                    relationships.append({"from": c1, "to": c2, "type": "USES"})
                            else:
                                if c1_pos < c2_pos:
                                    relationships.append({"from": c2, "to": c1, "type": "USES"})
                                else:
                                    relationships.append({"from": c1, "to": c2, "type": "USES"})
                        elif "evaluated" in between_text or "tested" in between_text or "benchmark" in between_text:
                            if c1_node["label"] == "Dataset":
                                relationships.append({"from": c2, "to": c1, "type": "EVALUATED_ON"})
                            elif c2_node["label"] == "Dataset":
                                relationships.append({"from": c1, "to": c2, "type": "EVALUATED_ON"})
                            else:
                                relationships.append({"from": c1, "to": c2, "type": "RELATED_TO"})
                        else:
                            if c1_node["label"] == "Method" and c2_node["label"] == "Dataset":
                                relationships.append({"from": c1, "to": c2, "type": "EVALUATED_ON"})
                            elif c2_node["label"] == "Method" and c1_node["label"] == "Dataset":
                                relationships.append({"from": c2, "to": c1, "type": "EVALUATED_ON"})
                            elif c1_node["label"] == "Method" and c2_node["label"] == "Method":
                                relationships.append({"from": c1, "to": c2, "type": "USES"})
                            else:
                                relationships.append({"from": c1, "to": c2, "type": "RELATED_TO"})
                            
        # Ensure all extracted concepts in the chunk are connected in a chain or tree
        if len(sorted_concepts) > 1:
            for i in range(1, len(sorted_concepts)):
                c1 = sorted_concepts[i]["name"]
                c2 = sorted_concepts[0]["name"]  # Connect back to the first concept (hub)
                
                c1_node = concepts_map[c1.lower()]
                c2_node = concepts_map[c2.lower()]
                
                # Avoid duplicate relationship entries
                if not any((r["from"].lower() == c2.lower() and r["to"].lower() == c1.lower()) or (r["from"].lower() == c1.lower() and r["to"].lower() == c2.lower()) for r in relationships):
                    if c1_node["label"] == "Keyword" or c2_node["label"] == "Keyword":
                        if c2_node["label"] == "Keyword":
                            relationships.append({"from": c1, "to": c2, "type": "HAS_KEYWORD"})
                        else:
                            relationships.append({"from": c2, "to": c1, "type": "HAS_KEYWORD"})
                    else:
                        relationships.append({
                            "from": c2,
                            "to": c1,
                            "type": "RELATED_TO"
                        })
                            
        return {"nodes": nodes, "relationships": relationships}

    def narrate_learning_path(self, concepts: list) -> str:
        if self._is_mock:
            return self._run_mock_narration(concepts)
        
        concepts_str = " -> ".join([c for c in concepts])
        system_prompt = (
            "You are an encouraging academic AI tutor. Your task is to turn an ordered list of concepts "
            "representing a learning prerequisite path into a friendly, clear, step-by-step study plan. "
            "Write one short, helpful sentence per concept, explaining why it comes in this order and how "
            "it builds toward the final target concept. Keep the total response concise, direct, and under "
            "150 words in total."
        )
        try:
            message = self._client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1000,
                temperature=0.5,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Please narrate this learning path: {concepts_str}"}
                ]
            )
            return message.content[0].text.strip()
        except Exception as e:
            logger.error(f"Error during path narration: {e}")
            return self._run_mock_narration(concepts)

    def _run_mock_narration(self, concepts: list) -> str:
        if not concepts:
            return "No prerequisite concepts found. You are ready to start with the target concept directly!"
        
        narration_steps = []
        for i, c in enumerate(concepts):
            if i == 0:
                narration_steps.append(f"First, build a solid foundation with **{c}**.")
            elif i == len(concepts) - 1:
                narration_steps.append(f"Finally, synthesize these tools to master the target concept **{c}**.")
            else:
                narration_steps.append(f"Next, transition into **{c}** to expand your understanding of relevant concepts.")
        
        return " ".join(narration_steps)

llm_client = LLMClient()
