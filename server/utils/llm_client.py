import json
import logging
import re
import urllib.request
import urllib.error
from types import SimpleNamespace
from server.config import config

try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover - optional provider
    Anthropic = None

logger = logging.getLogger("llm_client")


class _OpenAICompatClient:
    """Tiny OpenAI-compatible chat client for Groq/OpenAI-style endpoints."""
    def __init__(self, api_key: str, base_url: str, timeout: float = 30):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.groq.com/openai/v1").rstrip("/")
        self.timeout = timeout
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat_create))

    def _chat_create(self, model: str, messages: list[dict], max_tokens: int, temperature: float = 0, **_: dict):
        payload = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

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
    "learning", "learning document",
    "chapter 1", "chapter 2", "chapter 3", "chapter 4", "chapter 5", "chapter 6",
    "section 1", "section 2", "section 3", "section 4", "section 5", "section 6",
    "table 1", "table 2", "table 3", "figure 1", "figure 2", "figure 3",
    # Procedure/layout/date noise commonly produced by textbook and lab PDFs
    "january", "february", "march", "april", "june", "july", "august", "september", "october", "november", "december",
    "using", "similar", "adding", "building", "whether", "where", "include", "standard", "unplug", "construct",
    "determine", "consider", "compare", "start", "starting", "according", "identify", "never", "adjust", "choose",
    "remember", "attach", "turn", "plug", "prof", "objectiv", "background", "reqis", "reqand", "rfrom",
}

TECHNICAL_SINGLE_WORD_HINTS: set[str] = set()

BAD_ENTITY_TOKENS = {
    "you", "your", "we", "our", "if", "use", "using", "used", "unlike", "example", "suppose",
    "provide", "providing", "given", "same", "very", "huge", "small", "large", "low", "high",
    "material", "materials", "assembly", "operation", "procedure", "objective", "background",
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
        "involves", "focuses", "suggests", "indicates", "supports", "uses", "occurs", "occur"
    }
    if any(w in sentence_triggers for w in words_lower):
        return 0.0

    if any(w in BAD_ENTITY_TOKENS for w in words_lower):
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

    if len(words) == 1:
        if n_lower.endswith(("ing", "ed", "ly")):
            return 0.0
        # Single-word lowercase/common Title Case candidates are often sentence-start noise.
        # Keep technical terms/acronyms, but reject generic extracted verbs/months/procedure words.
        alpha = re.sub(r"[^a-zA-Z]", "", n_clean)
        is_acronym = alpha.isupper() and len(alpha) >= 2
        if not is_acronym and n_lower not in TECHNICAL_SINGLE_WORD_HINTS and label == "Keyword":
            if n_clean.istitle():
                return 0.45
        
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
    if re.fullmatch(r'[IVXLCDM]{1,6}', n_clean):
        return 0.0
    if n_clean.isupper() and len(words) <= 4 and label in {"Keyword", "Concept", "Topic"}:
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
        if re.search(r'(ses|xes|zes|ches|shes)$', n_lower):
            return n[:-2]
        return n[:-1]
    elif n_lower.endswith('s') and not n_lower.endswith('ss') and not n_lower.endswith('us') and not n_lower.endswith('is'):
        return n[:-1]
    return n

class LLMClient:
    def __init__(self):
        self._client = None
        self._anthropic_client = None
        self._anthropic_http = False
        self._is_mock = False

        if config.ANTHROPIC_API_KEY and "mock" not in config.ANTHROPIC_API_KEY.lower() and Anthropic:
            try:
                self._anthropic_client = Anthropic(
                    api_key=config.ANTHROPIC_API_KEY,
                    timeout=config.LLM_TIMEOUT_SECONDS,
                )
                self._is_mock = False
                logger.info("Successfully connected to Anthropic API.")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}.")
        elif config.ANTHROPIC_API_KEY and "mock" not in config.ANTHROPIC_API_KEY.lower():
            self._anthropic_http = True
            self._is_mock = False
            logger.info("Anthropic SDK unavailable; using lightweight Anthropic HTTP client.")

        if config.GROQ_API_KEY and "mock-api-key" not in config.GROQ_API_KEY:
            try:
                self._client = _OpenAICompatClient(
                    api_key=config.GROQ_API_KEY,
                    base_url=config.GROQ_BASE_URL,
                    timeout=config.LLM_TIMEOUT_SECONDS,
                )
                self._is_mock = False
                logger.info("Successfully connected to Groq API.")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}.")

        if not self._anthropic_client and not self._anthropic_http and not self._client:
            logger.warning("No valid LLM API key detected. Starting LLM client in mock mode.")
            self._is_mock = True

    def _anthropic_complete(self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float = 0) -> str:
        payload = json.dumps({
            "model": config.ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT_SECONDS) as res:
                data = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic HTTP {e.code}: {detail[:500]}") from e
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ).strip()

    def _complete_text(self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float = 0, prefer_anthropic: bool = False) -> str:
        if prefer_anthropic and self._anthropic_client:
            response = self._anthropic_client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return "".join(
                block.text for block in response.content
                if getattr(block, "type", None) == "text" and getattr(block, "text", None)
            ).strip()
        if prefer_anthropic and self._anthropic_http:
            return self._anthropic_complete(system_prompt, user_prompt, max_tokens, temperature)

        if self._client:
            response = self._client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content.strip()

        if self._anthropic_client:
            response = self._anthropic_client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return "".join(
                block.text for block in response.content
                if getattr(block, "type", None) == "text" and getattr(block, "text", None)
            ).strip()
        if self._anthropic_http:
            return self._anthropic_complete(system_prompt, user_prompt, max_tokens, temperature)

        raise RuntimeError("No LLM provider available.")

    def complete_text(self, system_prompt: str, user_prompt: str, max_tokens: int = 1000, temperature: float = 0, prefer_anthropic: bool = True) -> str:
        """Public provider-neutral completion helper for routers.

        Uses Anthropic first when configured, then Groq/OpenAI-compatible fallback.
        """
        return self._complete_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            prefer_anthropic=prefer_anthropic,
        )

    @staticmethod
    def _strip_json_fences(content: str) -> str:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

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
            content = self._strip_json_fences(self._complete_text(
                system_prompt,
                f"Filename: {filename}\n\nText sample:\n\n{sample_text[:8000]}",
                max_tokens=1000,
                temperature=0,
                prefer_anthropic=False,
            ))
            
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
        

        # Fallback
        clean_name = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').strip().title()
        if not clean_name:
            clean_name = "Document Analysis"
        return {
            "name": clean_name,
            "description": f"Unified knowledge map and conceptual analysis of the document {filename}."
        }
    def extract_graph_from_chunk(self, text_chunk: str, include_prerequisites: bool = True) -> dict:
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
            "- PART_OF: For concepts that are a component or part of a larger concept (e.g., Engine PART_OF Car).\n"
            "- PREREQUISITE: For foundational concepts required before learning another concept (Concept A must be understood before Concept B).\n"
            "- DEPENDS_ON: For direct dependencies (e.g., Framework A depends on Technology B).\n"
            "- EXTENDS: For inheritance, specialization, or subclassing (e.g., Subtopic B extends Topic A, or Method B extends Method A).\n"
            "- USES: For utilization/application (e.g., Method A uses Dataset B, or Framework A uses Concept B, or Method A uses Concept B).\n"
            "- USED_BY: The inverse of USES (e.g., Concept B USED_BY Method A).\n"
            "- CAUSES: When one concept or phenomenon causes another (e.g., Heat CAUSES Evaporation).\n"
            "- USED_FOR: For indicating a method is used for a specific task or a dataset is used for evaluation.\n"
            "- EVALUATED_ON: Specifically for linking a method or model to a dataset/benchmark it was tested on.\n"
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
            content = self._strip_json_fences(self._complete_text(
                system_prompt,
                f"Extract graph elements from this text chunk:\n\n{text_chunk}",
                max_tokens=4000,
                temperature=0,
                prefer_anthropic=True,
            ))
            
            data = json.loads(content)
            if "nodes" in data and "relationships" in data:
                nodes = data["nodes"]
                relationships = data["relationships"]
                
                concept_names = [n.get("name") for n in nodes if n.get("name")]
                if include_prerequisites and concept_names:
                    prereq_prompt = (
                        "You are building a learning roadmap.\n\n"
                        "Below is a text chunk and the concepts extracted from it.\n\n"
                        "Concepts:\n"
                        f"{json.dumps(concept_names)}\n\n"
                        "Return ONLY prerequisite relationships that are logically necessary for understanding another concept.\n\n"
                        "Rules:\n"
                        "- Use ONLY concepts already present in the list.\n"
                        "- Never invent new concepts.\n"
                        "- Return only JSON.\n"
                        "- Return relationships when educational dependency is clear even if the PDF never literally says 'prerequisite'.\n"
                        "- Use educational reasoning.\n"
                        "- Ignore RELATED_TO unless it represents a learning dependency."
                    )
                    
                    try:
                        prereq_content = self._strip_json_fences(self._complete_text(
                            prereq_prompt,
                            f"Text Chunk:\n{text_chunk}\n\nReturn the JSON with prerequisite relationships.",
                            max_tokens=1500,
                            temperature=0.0,
                            prefer_anthropic=True,
                        ))
                        
                        prereq_data = json.loads(prereq_content)
                        if "relationships" in prereq_data:
                            new_rels = prereq_data["relationships"]
                            valid_names = set(concept_names)
                            for r in new_rels:
                                r_from = r.get("from")
                                r_to = r.get("to")
                                r_type = r.get("type", "PREREQUISITE_OF")
                                if r_from in valid_names and r_to in valid_names:
                                    exists = any(
                                        e.get("from") == r_from and e.get("to") == r_to and e.get("type") == r_type
                                        for e in relationships
                                    )
                                    if not exists:
                                        relationships.append({
                                            "from": r_from,
                                            "to": r_to,
                                            "type": r_type
                                        })
                    except Exception as e:
                        logger.error(f"Error during prerequisite generation: {e}")

                data["relationships"] = relationships
                return data
            raise ValueError("LLM returned JSON missing 'nodes' or 'relationships' keys.")
        except Exception as e:
            logger.error(f"Error during real LLM extraction: {e}")
            raise e

    def extract_citations(self, text_block: str) -> list[dict]:
        if self._is_mock:
            logger.info("[MOCK] Running mock citations extraction.")
            # Mock behavior: return a static list if bibliography is provided
            if not text_block.strip():
                return []
            return [
                {
                    "title": "Attention Is All You Need",
                    "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit", "Llion Jones", "Aidan N. Gomez", "Lukasz Kaiser", "Illia Polosukhin"],
                    "year": 2017,
                    "venue": "NIPS",
                    "doi": "10.48550/arXiv.1706.03762"
                },
                {
                    "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                    "authors": ["Jacob Devlin", "Ming-Wei Chang", "Kenton Lee", "Kristina Toutanova"],
                    "year": 2018,
                    "venue": "NAACL-HLT",
                    "doi": "10.48550/arXiv.1810.04805"
                }
            ]
            
        system_prompt = (
            "You are a strict citation extraction engine. Your task is to parse a references or bibliography section from a research paper and extract each individual citation into structured JSON. "
            "For each citation, extract the title, list of authors, year of publication, venue (e.g. conference, journal, or publisher), and DOI or URL if available. "
            "If a field is missing, return null for that field.\n\n"
            "Return ONLY a valid JSON array of objects matching this schema, no prose, no markdown fences:\n"
            "[\n"
            "  {\n"
            "    \"title\": \"Attention Is All You Need\",\n"
            "    \"authors\": [\"Ashish Vaswani\", \"Noam Shazeer\", \"Niki Parmar\", \"Jakob Uszkoreit\", \"Llion Jones\", \"Aidan N. Gomez\", \"Lukasz Kaiser\", \"Illia Polosukhin\"],\n"
            "    \"year\": 2017,\n"
            "    \"venue\": \"NIPS\",\n"
            "    \"doi\": \"10.48550/arXiv.1706.03762\"\n"
            "  }\n"
            "]"
        )
        
        try:
            response = self._client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=4000,
                temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract citations from this references block:\n\n{text_block}"}
                ]
            )
            content = response.choices[0].message.content.strip()
            
            # Clean markdown JSON fences if LLM generated them
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            if isinstance(data, list):
                return data
            raise ValueError("LLM returned JSON that is not a list.")
        except Exception as e:
            logger.error(f"Error during citations LLM extraction: {e}")
            raise e

    def extract_hierarchical_graph_from_document(self, sample_text: str, filename: str, main_topic_info: dict) -> dict:
        """One-call, document-local learning hierarchy for serverless PDF extraction."""
        if self._is_mock:
            return self._run_mock_extraction(sample_text)

        system_prompt = (
            "You are a document-grounded educational knowledge-graph builder.\n"
            "Build a hierarchical learning graph for ONE uploaded PDF only. Do not use memory from prior documents.\n"
            "The graph must adapt to the document subject. No fixed templates.\n\n"
            "Learning hierarchy rules:\n"
            "- foundation nodes: concepts a student should learn before the main topic.\n"
            "- core nodes: main concepts directly taught by the PDF.\n"
            "- advanced nodes: extensions, applications, methods, instruments, edge cases, or next topics.\n"
            "- Use PREREQUISITE from foundation concept -> concept that depends on it.\n"
            "- Use CONTAINS from broader topic -> included concept.\n"
            "- Use EXTENDS from core concept -> advanced concept.\n"
            "- Use USES, USED_FOR, PART_OF, DEPENDS_ON, CAUSES, RELATED_TO only when clearly meaningful.\n\n"
            "Grounding rules:\n"
            "- Prefer concepts explicitly present in the text sample.\n"
            "- You may add a small number of universally necessary prerequisite concepts if needed for learning, "
            "but mark them with level='foundation' and explain why they help the document's main topic.\n"
            "- Never include content from other PDFs, old sessions, or famous examples unless this PDF mentions them.\n"
            "- Node names must be concise academic/technical terms, max 4 words, max 40 chars.\n"
            "- Labels must be one of: Topic, Subtopic, Concept, Technology, Framework, Application, Method, Dataset, Keyword.\n"
            "- level must be one of: foundation, core, advanced.\n\n"
            "Return ONLY valid JSON, no markdown:\n"
            "{\n"
            "  \"nodes\": [\n"
            "    {\"label\":\"Topic\",\"name\":\"Main Topic\",\"description\":\"...\",\"difficulty_level\":\"Beginner\",\"level\":\"core\"}\n"
            "  ],\n"
            "  \"relationships\": [\n"
            "    {\"from\":\"Prerequisite Concept\",\"to\":\"Dependent Concept\",\"type\":\"PREREQUISITE\"}\n"
            "  ]\n"
            "}"
        )
        user_prompt = (
            f"Filename: {filename}\n"
            f"Detected main topic: {json.dumps(main_topic_info, ensure_ascii=False)}\n\n"
            f"PDF text sample:\n{sample_text[:9000]}"
        )

        try:
            response = self._client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=3500,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            data = json.loads(content.strip())
            if not isinstance(data, dict) or "nodes" not in data or "relationships" not in data:
                raise ValueError("hierarchical graph JSON missing nodes or relationships")
            return data
        except Exception as e:
            logger.error(f"Hierarchical document extraction failed: {e}")
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

        # 1.1 Extract text-driven noun phrases around generic academic head nouns.
        # No subject-specific vocabulary belongs in fallback extraction.
        domain_keywords = [
            "system", "architecture", "method", "algorithm", "model", "approach", 
            "framework", "network", "function", "mechanism", "protocol", "identity", 
            "infrastructure", "verification", "technology", "principle", "law", "theory",
            "concept", "property", "quantity", "unit", "device", "instrument", "component",
            "structure", "reaction", "cycle", "pathway", "equation", "relationship",
            "difference", "measurement", "technique", "application", "dataset", "benchmark",
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

        # 1.2 Extract repeated single-word terms from this text only.
        token_counts = Counter(
            t.lower()
            for t in re.findall(r"\b[A-Za-z][A-Za-z-]{4,}\b", text_chunk)
            if t.lower() not in STOP_WORDS and t.lower() not in GENERIC_BLACKLIST
        )
        for term, count in token_counts.most_common(30):
            if count < 2:
                continue
            normalized_name = " ".join(word.capitalize() for word in singularize_concept_name(term).split())
            normalized_low = normalized_name.lower()
            if normalized_low not in concepts_map and calculate_entity_quality(normalized_name, "Concept") > 0.7:
                concepts_map[normalized_low] = {
                    "label": "Concept",
                    "name": normalized_name,
                    "description": f"{normalized_name} is discussed in this document section."
                }

        # Cap dynamic concept count to 15 per chunk to avoid rendering messy graphs.
        # Filter before capping so sentence-start/layout words do not crowd out real terms.
        filtered_concepts = [
            node for node in concepts_map.values()
            if calculate_entity_quality(node.get("name", ""), node.get("label", "Concept")) > 0.7
        ]
        sorted_concepts = filtered_concepts[:15]
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
                                relationships.append({"from": c2, "to": c1, "type": "DEPENDS_ON"})
                            else:
                                relationships.append({"from": c1, "to": c2, "type": "DEPENDS_ON"})
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
                            
        # Post-process to infer missing dependencies based on descriptions
        name_to_node = {n["name"].lower(): n["name"] for n in nodes if "name" in n}
        for node in nodes:
            desc = node.get("description", "").lower()
            node_name_lower = node.get("name", "").lower()
            for other_name_lower, other_name in name_to_node.items():
                if other_name_lower != node_name_lower and len(other_name_lower) > 3:
                    if f" {other_name_lower} " in f" {desc} " or f"requires {other_name_lower}" in desc:
                        edge_exists = any(
                            e["from"] == other_name and e["to"] == node["name"] and e["type"] in ["PREREQUISITE", "DEPENDS_ON"]
                            for e in relationships
                        )
                        if not edge_exists:
                            relationships.append({
                                "from": other_name,
                                "to": node["name"],
                                "type": "PREREQUISITE"
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
            response = self._client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=1000,
                temperature=0.5,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Please narrate this learning path: {concepts_str}"}
                ]
            )
            return response.choices[0].message.content.strip()
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

    def generate_prerequisites(self, concept: str) -> list:
        if self._is_mock:
            return []
            
        system_prompt = (
            "You are an educational prerequisite generator. Given a concept, return ONLY the real academic concepts "
            "someone must understand beforehand in learning order as a JSON array of objects, "
            "each containing 'name' and 'description' keys. "
            "Never generate placeholder concepts such as 'Basic <Concept>', 'Core Math for <Concept>', or 'Fundamentals of <Concept>' "
            "unless those are genuine academic concepts. Do not return any other text."
        )
        try:
            response = self._client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=500,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Return the JSON array of prerequisite concepts."}
                ]
            )
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"Failed to generate prerequisites from LLM: {str(e)}")
            return []

    def generate_explanation(self, concept: str) -> str:
        if self._is_mock:
            return f"{concept} is a foundational concept. Understanding it allows you to grasp more complex methodologies in this domain."
            
        system_prompt = (
            "You are an expert tutor. Provide a very concise, 1-2 paragraph explanation of the concept "
            f"'{concept}'. Focus on what it is and why it's important. Do not use formatting or markdown headers."
        )
        try:
            response = self._client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=300,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Explain the concept concisely."}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to generate explanation from LLM: {str(e)}")
            return "Explanation could not be generated."

    def extract_document_prerequisites(self, concepts: list[str]) -> list[dict]:
        """
        Takes a list of extracted concepts from a single document and returns PREREQUISITE relationships.
        Enforces strict usage of only the provided concept names.
        """
        if not concepts or len(concepts) < 2:
            return []
            
        if self._is_mock:
            # Generate deterministic mock prerequisites
            mock_rels = []
            for i in range(len(concepts) - 1):
                mock_rels.append({"from": concepts[i], "to": concepts[i+1]})
            return mock_rels
            
        system_prompt = (
            "You are an expert curriculum designer and educational graph builder.\n"
            "You will be given a list of concepts extracted from a single document.\n"
            "Your task is to determine the optimal learning order (prerequisite relationships) among ONLY THESE concepts.\n\n"
            "RULES:\n"
            "1. You MUST ONLY use the exact concept names provided in the input list. Do NOT modify the strings. Do NOT invent new concepts.\n"
            "2. Determine which concepts are foundational and must be understood BEFORE learning another concept in the list.\n"
            "3. Return the result as a JSON object containing a 'relationships' array.\n"
            "4. Each relationship must have a 'from' (the prerequisite) and a 'to' (the advanced concept).\n"
            "5. If there are no clear prerequisite relationships, return an empty array.\n\n"
            "Example Input: ['Voltage', 'Ohm\\'s Law', 'Current']\n"
            "Example Output:\n"
            "{\n"
            "  \"relationships\": [\n"
            "    { \"from\": \"Voltage\", \"to\": \"Ohm\\'s Law\" },\n"
            "    { \"from\": \"Current\", \"to\": \"Ohm\\'s Law\" }\n"
            "  ]\n"
            "}\n"
        )
        
        try:
            response_text = self._strip_json_fences(
                self._complete_text(
                    system_prompt,
                    f"Concepts list: {json.dumps(concepts[:80])}\nReturn ONLY valid JSON.",
                    max_tokens=1500,
                    temperature=0.0,
                    prefer_anthropic=True,
                )
            )
            parsed = json.loads(response_text)
            rels = parsed.get("relationships", [])
            
            # Strict validation to ensure no hallucinations
            valid_concepts = set(concepts)
            validated_rels = []
            for rel in rels:
                f = rel.get("from")
                t = rel.get("to")
                if f in valid_concepts and t in valid_concepts and f != t:
                    validated_rels.append(rel)
                    
            return validated_rels
            
        except Exception as e:
            logger.error(f"Failed to extract document prerequisites: {e}")
            return []

    def determine_node_prerequisites(self, target_concept: str, available_concepts: list[str]) -> list[dict]:
        """
        Takes a target concept and a list of available valid concepts.
        Determines which of the available concepts must be understood BEFORE learning the target concept.
        Returns a list of dictionaries with 'name' and 'reason'.
        """
        if not available_concepts:
            return []
            
        if self._is_mock:
            return []
            
        system_prompt = (
            "You are an expert curriculum designer and strict graph dependency analyzer.\n"
            "Your task is to determine the optimal learning prerequisites for a specific target concept.\n\n"
            "RULES:\n"
            "1. You MUST ONLY choose from the provided list of available concepts. Do NOT modify the strings. Do NOT invent new concepts.\n"
            "2. Determine which concepts are physically or fundamentally foundational and must be understood BEFORE learning the target concept.\n"
            "3. DO NOT select related links, semantic synonyms, tags, or metadata (e.g., 'Scientific', 'Similar', 'Like', 'Circuit' if it's just a tag). You are building a learning dependency tree, NOT a semantic similarity list.\n"
            "4. The output must answer ONLY this question: 'What must a learner know before they can understand this target concept?'\n"
            "5. For each chosen concept, provide a short educational reason explaining WHY it is a prerequisite.\n"
            "6. Return the result as a JSON object containing a 'prerequisites' array of objects, each with 'name' and 'reason'.\n"
            "7. If there are no true prerequisite concepts in the list, return an empty array.\n\n"
            "Example:\n"
            "Target: 'Target Concept'\n"
            "Available: ['Foundational Concept', 'Metadata Tag', 'Supporting Mechanism', 'Application']\n"
            "Output:\n"
            "{\n"
            "  \"prerequisites\": [\n"
            "    {\"name\": \"Foundational Concept\", \"reason\": \"It explains the base idea required before the target.\"},\n"
            "    {\"name\": \"Supporting Mechanism\", \"reason\": \"It describes how the target operates.\"}\n"
            "  ]\n"
            "}\n"
        )
        
        try:
            response = self._client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=800,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Target Concept: '{target_concept}'\nAvailable Concepts: {json.dumps(available_concepts)}\nReturn ONLY valid JSON."}
                ]
            )
            
            response_text = response.choices[0].message.content.strip()
            if response_text.startswith("```"):
                response_text = re.sub(r"^```(?:json)?", "", response_text)
                response_text = re.sub(r"```$", "", response_text).strip()
                
            parsed = json.loads(response_text)
            prereqs = parsed.get("prerequisites", [])
            
            # Strict validation to ensure no hallucinations
            valid_concepts = set(available_concepts)
            validated_prereqs = []
            for p in prereqs:
                pname = p.get("name")
                if pname in valid_concepts and pname != target_concept:
                    validated_prereqs.append({
                        "name": pname,
                        "reason": p.get("reason", "")
                    })
                    
            return validated_prereqs
            
        except Exception as e:
            logger.error(f"Failed to determine node prerequisites: {e}")
            return []

    def generate_dynamic_roadmap(self, target_concept: str) -> list[dict]:
        """
        Dynamically generates a strict chronological sequence of prerequisite concepts
        using the LLM, bypassing database relationships.
        """
        if self._is_mock:
            return [
                {
                    "name": target_concept,
                    "description": "Target concept from the uploaded document. Select connected graph nodes to expand real prerequisites.",
                    "difficulty": "Medium",
                    "duration": "20 min",
                }
            ]

        system_prompt = (
            "You are an expert curriculum builder. When given a target topic, research and output a strict "
            "chronological sequence of concepts the user MUST master BEFORE they can understand the target. "
            "For example, if target is 'Multithreading', it must generate a step-by-step path like: Basic Programming Syntax -> Java Core -> Object-Oriented Programming (OOP) -> Process vs Thread Concept -> Java Multithreading. "
            "For each step in the path, provide:\n"
            "- 'name': Concept Name\n"
            "- 'description': Detailed explanation of what this is and why it's a prerequisite.\n"
            "- 'difficulty': Easy, Medium, or Advanced\n"
            "- 'duration': Estimated study time (e.g., '10 min').\n\n"
            "RULES:\n"
            "1. Output ONLY a valid JSON object with a 'roadmap' array.\n"
            "2. The selected target concept MUST always be appended as the very LAST item in that array.\n"
            "3. The array must be sorted chronologically from the most fundamental topic up to the target.\n"
            "4. Do not wrap the JSON in Markdown formatting."
        )

        try:
            response = self._client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=1500,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Target topic: {target_concept}\nReturn ONLY valid JSON."}
                ]
            )

            response_text = response.choices[0].message.content.strip()
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r"^```(?:json)?", "", response_text)
                response_text = re.sub(r"```$", "", response_text).strip()

            parsed = json.loads(response_text)
            return parsed.get("roadmap", [])
        except Exception as e:
            logger.error(f"Failed to generate dynamic roadmap: {e}")
            return []

    def generate_concept_details(self, concept_name: str) -> dict:
        """
        Dynamically synthesize a comprehensive object for the requested concept name.
        """
        system_prompt = (
            f"You are an expert interactive textbook engine like Gemini. Given a concept name '{concept_name}', dynamically generate a rigorous, rich explanation for a student.\n\n"
            "Your response must be a valid JSON object with these exact keys:\n"
            "- `definition`: A comprehensive, beautifully detailed explanation of what this concept is.\n"
            "- `how_it_works`: A deep dive into its operational mechanics, physics, or internal logic.\n"
            "- `formula_syntax`: The standard formula or code structure (e.g., 'R = V / I' for Resistance, with full markdown formatting).\n"
            "- `properties`: A markdown bulleted list of key technical attributes or parameters.\n"
            "- `image_url`: Optional. Only populate with an actual schematic or diagram URL if the topic is a hardware component (like 'PIR Sensor'). Otherwise, return null."
        )
        try:
            # Bypass mock mode check to force real LLM generation
            client = self._client if self._client else _OpenAICompatClient(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL, timeout=config.LLM_TIMEOUT_SECONDS)
            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=800,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Concept: {concept_name}\nReturn ONLY valid JSON."}
                ]
            )
            response_text = response.choices[0].message.content.strip()
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r"^```(?:json)?", "", response_text)
                response_text = re.sub(r"```$", "", response_text).strip()
            
            data = json.loads(response_text)
            # Ensure backwards compatibility if the model returned embedded_image_url
            if "embedded_image_url" in data:
                data["image_url"] = data.pop("embedded_image_url")
            return data
        except Exception as e:
            logger.error(f"Failed to generate concept details (Auth Error or API Failure): {e}")
            return {
                "definition": f"{concept_name} is a concept extracted from the uploaded document. The graph shows its document-local learning relationships.",
                "how_it_works": "Use Path View to inspect prerequisite nodes above it and extension/application nodes below it. Add a live LLM key for richer generated explanations.",
                "formula_syntax": "No formula or syntax was grounded for this concept yet.",
                "properties": "• Document-local concept\n• Dynamic graph node\n• Explanation grounded by extracted context",
                "image_url": None,
            }
            
            c_name = concept_name.lower()
            
            if "syntax" in c_name or "basic" in c_name:
                return {
                    "definition": "Basic Programming Syntax defines the rules and structure for writing readable and compilable code statements.",
                    "how_it_works": "Compilers read these strict code lines sequentially. If a token or semi-colon is out of place, the parse layer fails immediately.",
                    "formula_syntax": "Example: public static void main(String[] args) { ... }",
                    "properties": "• Foundational layer\n• Language-specific constructs\n• Enforces code structure",
                    "image_url": None
                }
            elif "java core" in c_name or "core java" in c_name:
                return {
                    "definition": "Java Core covers the fundamental architecture of the Java language including the JVM, bytecode execution, and memory management structures.",
                    "how_it_works": "Java source code is compiled into platform-independent .class bytecode, which is then interpreted and executed line-by-line by the Java Virtual Machine (JVM).",
                    "formula_syntax": "Compile: javac Main.java \nExecute: java Main",
                    "properties": "• Platform Independent (WORA)\n• Garbage Collection automated\n• Multithreading built-in",
                    "image_url": None
                }
            elif "array" in c_name:
                return {
                    "definition": "An Array is a linear data structure containing a collection of elements stored in contiguous memory locations.",
                    "how_it_works": "Elements are accessed instantly via a base pointer index calculation: Address = Base + Index * Size. This provides rapid O(1) random lookup.",
                    "formula_syntax": "int[] numbers = new int[5]; \nnumbers[0] = 10;",
                    "properties": "• Continuous Memory blocks\n• Fixed capacity allocation\n• Homogeneous data types",
                    "image_url": None
                }
            elif "voltage" in c_name or "potential" in c_name:
                return {
                    "definition": "Voltage is the potential difference in electric charge between two distinct points in a circuit field.",
                    "how_it_works": "It acts like water pressure in a pipe, creating an electromotive driving force that pushes electrons across a conductive loop.",
                    "formula_syntax": "V = I × R",
                    "properties": "• SI Unit: Volts (V)\n• Measured by: Voltmeter",
                    "image_url": None
                }
            else:
                return {
                    "definition": f"Comprehensive core guide detailing the operational mechanics of {concept_name}.",
                    "how_it_works": f"Think of it as the foundational mechanism driving the system. Just as water pressure pushes more water through a pipe, {concept_name} drives the operational logic, allowing entities or resources to flow, compute, or function effectively.",
                    "formula_syntax": f"Standard domain equation or syntax applied for {concept_name}.",
                    "properties": "• Core operational parameter\n• Essential for domain mastery\n• Fundamental systemic variable",
                    "image_url": None
                }

llm_client = LLMClient()
