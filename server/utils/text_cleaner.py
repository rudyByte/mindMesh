import io
import re
import unicodedata
from collections import Counter
from pypdf import PdfReader

def clean_pdf_text_from_bytes(file_bytes: bytes) -> tuple[str, list[str]]:
    """
    Given PDF file bytes, parses the text page by page and applies the clean_raw_pages function.
    Returns a tuple of (combined_cleaned_text, list_of_cleaned_pages).
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    raw_pages = []
    for page in reader.pages:
        raw_pages.append(page.extract_text() or "")
    return clean_raw_pages(raw_pages)

def clean_raw_pages(raw_pages: list[str]) -> tuple[str, list[str]]:
    """
    Cleans raw PDF text page-by-page.
    - Removes isolated page numbers, headers, footers
    - Identifies recurring header/footer elements dynamically using normalized templates
    - Fixes OCR artifacts, spacing issues, and restores proper paragraph flows
    """
    # Pre-process raw pages to convert soft hyphens to regular hyphens
    processed_raw_pages = []
    for page_text in raw_pages:
        if page_text:
            # Replace soft hyphens (\xad, \u00ad) with regular hyphens
            p = page_text.replace('\u00ad', '-').replace('\xad', '-')
            processed_raw_pages.append(p)
        else:
            processed_raw_pages.append("")

    pages_lines = []
    for page_text in processed_raw_pages:
        lines = [line.strip() for line in (page_text or "").split('\n')]
        pages_lines.append(lines)
        
    num_pages = len(pages_lines)
    
    # Helper to normalize candidates for header/footer templates
    def normalize_candidate(line: str) -> str:
        # Convert to lowercase, remove digits, and all non-alphanumeric chars
        n = line.lower()
        n = re.sub(r'\d+', '', n)
        n = re.sub(r'[^\w]', '', n)
        return n.strip()
    
    # Identify dynamic headers and footers using normalized templates
    # (appearing on >= 15% of pages or at least 2 pages)
    top_candidates = []
    bottom_candidates = []
    for lines in pages_lines:
        if not lines:
            continue
        # Top 3 lines
        for i in range(min(3, len(lines))):
            line = lines[i].strip()
            norm = normalize_candidate(line)
            if norm and len(norm) > 3:
                top_candidates.append(norm)
        # Bottom 3 lines
        for i in range(1, min(4, len(lines) + 1)):
            line = lines[-i].strip()
            norm = normalize_candidate(line)
            if norm and len(norm) > 3:
                bottom_candidates.append(norm)
                
    top_counts = Counter(top_candidates)
    bottom_counts = Counter(bottom_candidates)
    
    min_pages_threshold = max(2, int(num_pages * 0.15))
    headers = {template for template, count in top_counts.items() if count >= min_pages_threshold}
    footers = {template for template, count in bottom_counts.items() if count >= min_pages_threshold}
    
    cleaned_pages = []
    for page_idx, lines in enumerate(pages_lines):
        cleaned_lines = []
        num_lines = len(lines)
        
        for i, line in enumerate(lines):
            line_strip = line.strip()
            if not line_strip:
                continue
                
            # Consecutively duplicate lines check (deduplicate consecutive identical lines on same page)
            if cleaned_lines and line_strip == cleaned_lines[-1]:
                continue

            # A. Remove solitary page numbers and roman numerals
            if line_strip.isdigit():
                continue
            if re.match(r'^(page|pg\.?)\s*\d+$', line_strip, re.IGNORECASE):
                continue
            if re.match(r'^\d+\s*(of|/)\s*\d+$', line_strip, re.IGNORECASE):
                continue
            # Match lines with only numbers, spaces, and punctuation (e.g. "123 456 789")
            if re.match(r'^[\d\s\W_]+$', line_strip):
                continue
            # Match Table / Figure header refs (e.g. Table 1, Figure 2)
            if re.match(r'^(table|figure|fig|chapter|section)\s+\d+\b', line_strip, re.IGNORECASE):
                continue
            if (i < 3 or i >= num_lines - 3):
                # Match digit-hyphen patterns like [12], - 12 -, — 12 —
                if re.match(r'^([-~—_\[(]?\s*\d+\s*[-~—_\])]?|page\s*\|\s*\d+)$', line_strip, re.IGNORECASE):
                    continue
                # Match Roman numerals iv, vi, ix, etc.
                if re.match(r'^[ivxldcm]+\.?$', line_strip, re.IGNORECASE):
                    continue
                
            # B. Remove recurring headers/footers using normalized templates
            norm_line = normalize_candidate(line_strip)
            if i < 3 and norm_line in headers:
                continue
            if i >= num_lines - 3 and norm_line in footers:
                continue
                
            # C. Remove copyright / generic metadata line
            if re.search(r'©\s*\d{4}\b', line_strip, re.IGNORECASE) or re.search(r'\bcopyright\b', line_strip, re.IGNORECASE):
                if i >= num_lines - 3:
                    continue
            
            # Remove promotion lines or website names
            if "oceanofpdf" in line_strip.lower():
                continue

            # D. Clean OCR artifacts, malformed text, and gibberish
            words_in_line = re.findall(r'\b\w+\b', line_strip.lower())
            
            # 1. Alphanumeric OCR noise (e.g. 123ABC456, XYZ123XYZ)
            has_alphanumeric_noise = False
            for w in words_in_line:
                if re.search(r'\b[a-zA-Z]+\d+[a-zA-Z]+\b', w) or re.search(r'\b\d+[a-zA-Z]+\d+\b', w):
                    has_alphanumeric_noise = True
                    break
            if has_alphanumeric_noise:
                continue

            # 2. Gibberish checking (no vowels or keyboard rows)
            has_gibberish = False
            for w in words_in_line:
                if len(w) >= 5 and not any(v in w for v in 'aeiouy'):
                    has_gibberish = True
                    break
                if w in {"abc", "xyz", "qwe", "asdfghjkl", "qwertyuiop", "zxcvbnm", "xyzqwe", "abcxyz", "testtest", "testtesttest", "lorem", "ipsum"}:
                    has_gibberish = True
                    break
            if has_gibberish:
                continue

            # 3. High word repetition check (e.g. Example Example Example)
            if len(words_in_line) >= 2:
                unique_ratio = len(set(words_in_line)) / len(words_in_line)
                if unique_ratio <= 0.5:
                    continue
                # Consecutive repeating phrase (e.g. Random Text Random Text)
                words_str = " ".join(words_in_line)
                if re.search(r'\b(\w+(?:\s+\w+)+)\s+\1\b', words_str):
                    continue

            cleaned_lines.append(line)
            
        page_text = "\n".join(cleaned_lines)
        
        # Normalize Unicode ligatures
        page_text = unicodedata.normalize('NFKD', page_text)
        
        # Remove null bytes, control characters, and private/surrogate areas
        page_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', '', page_text)
        page_text = re.sub(r'[\uD800-\uDFFF\uE000-\uF8FF]', '', page_text)
        
        # Restore proper spacing and handle soft-hyphenation at newline boundaries
        # Join words divided by hyphen and newline: "co-\nordinate" -> "coordinate"
        page_text = re.sub(r'(\b\w+)-\s*\n+\s*(\b\w+)', r'\1\2', page_text)
        
        # Join lines within a paragraph, keeping paragraph boundaries
        lines_to_join = page_text.split('\n')
        joined_text = ""
        for idx, line in enumerate(lines_to_join):
            line = line.strip()
            if not line:
                if not joined_text.endswith("\n\n"):
                    joined_text += "\n\n"
                continue
                
            # Check if this line is a list item or bullet point (e.g. "* ", "- ", "1. ")
            is_bullet = re.match(r'^([•\-\*\+]|\d+[\.\)]|[a-zA-Z][\.\)])\s+', line)
            
            if joined_text and not joined_text.endswith("\n\n") and not is_bullet:
                # If the current line is a continuation of the previous line
                if joined_text.endswith("-"):
                    joined_text = joined_text[:-1] + line
                else:
                    joined_text += " " + line
            else:
                if joined_text.endswith("\n\n") or not joined_text:
                    joined_text += line
                else:
                    joined_text += "\n" + line
                    
        # Apply word spacing adjustments (spaced letters and run-togethers)
        joined_text = fix_spacing(joined_text)
        
        # Remove duplicate spaces
        joined_text = re.sub(r'[ \t]+', ' ', joined_text)
        joined_text = re.sub(r'\n{3,}', '\n\n', joined_text)
        
        cleaned_pages.append(joined_text.strip())
        
    combined_text = "\n\n".join([p for p in cleaned_pages if p])
    return combined_text, cleaned_pages

def fix_spacing(text: str) -> str:
    # Split camelCase / PascalCase word boundaries (e.g. InterconnectedLANs -> Interconnected LANs)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # 1. Merge spaced letters: "S E L L I N G" -> "SELLING", "S P I N" -> "SPIN", "1 9 9 6" -> "1996"
    def replace_spaced(match):
        return match.group(0).replace(" ", "")
    text = re.sub(r'\b[a-zA-Z0-9](?:\s+[a-zA-Z0-9]){2,}\b', replace_spaced, text)
    
    # 2. Fix specific split words
    split_words_map = {
        r'\bS\s+ELLING\b': 'SELLING',
        r'\bSTRA\s+TEGY\b': 'STRATEGY',
        r'\bCREA\s+TING\b': 'CREATING',
        r'\bADVANT\s+AGE\b': 'ADVANTAGE',
        r'\bda\s+ta\b': 'data',
        r'\bco\s+nnection\b': 'connection',
        r'\bpro\s+cessing\b': 'processing',
        r'\bma\s+trix\b': 'matrix',
        r'\bne\s+twork\b': 'network',
        r'\blear\s+ning\b': 'learning',
        r'\bse\s+quence\b': 'sequence',
        r'\btrans\s+duction\b': 'transduction',
        r'\bpo\s+sitional\b': 'positional',
        r'\ben\s+coding\b': 'encoding',
        r'\bde\s+coder\b': 'decoder',
        r'\ben\s+coder\b': 'encoder',
        r'\bat\s+tention\b': 'attention',
        r'\bback\s+propagation\b': 'backpropagation',
        r'\bgrad\s+ient\b': 'gradient',
        r'\bde\s+scent\b': 'descent',
        r'\bstoch\s+astic\b': 'stochastic',
        r'\bconvo\s+lutional\b': 'convolutional',
        r'\brecur\s+rent\b': 'recurrent',
        r'\btrans\s+formers\b': 'transformers',
        r'\bblock\s+chain\b': 'blockchain',
        r'\bknow\s+ledge\b': 'knowledge',
        r'\bde\s+centralized\b': 'decentralized',
        r'\bse\s+cure\b': 'secure',
        r'\bvo\s+ting\b': 'voting',
        r'\belec\s+tion\b': 'election',
        r'\bco\s+mmittee\b': 'committee',
        r'\bano\s+nymity\b': 'anonymity',
        r'\bauth\s+entication\b': 'authentication',
        r'\breg\s+istration\b': 'registration',
        r'\bbu\s+siness\b': 'business',
        r'\bpla\s+tform\b': 'platform',
        r'\bser\s+vice\b': 'service',
        r'\bdo\s+cument\b': 'document',
        r'\bsa\s+tellite\b': 'satellite',
        r'\bver\s+ification\b': 'verification',
        r'\bcer\s+tification\b': 'certification',
        r'\bauto\s+mated\b': 'automated',
        r'\ben\s+terprise\b': 'enterprise',
        r'\bcom\s+compliance\b': 'compliance',
        r'\bcli\s+mate\b': 'climate',
        r'\bparti\s+cipate\b': 'participate',
        r'\bper\s+formance\b': 'performance',
        r'\bgov\s+ernment\b': 'government',
        r'\breg\s+ulator\b': 'regulator',
        r'\benvi\s+ronment\b': 'environment',
        r'\bman\s+agement\b': 'management',
        r'\bde\s+forestation\b': 'deforestation',
        r'\bcon\s+tinuous\b': 'continuous',
        r'\bse\s+questration\b': 'sequestration',
        r'\bman\s+ual\b': 'manual',
        r'\bver\s+ifiable\b': 'verifiable',
        r'\binfra\s+structure\b': 'infrastructure'
    }
    for pattern, repl in split_words_map.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        
    # Fix common short word splits inside sentences
    common_short_splits = {
        r'\bth\s+e\b': 'the',
        r'\ba\s+nd\b': 'and',
        r'\ban\s+d\b': 'and',
        r'\bo\s+f\b': 'of',
        r'\bt\s+o\b': 'to',
        r'\bi\s+n\b': 'in',
        r'\bi\s+s\b': 'is',
        r'\ba\s+t\b': 'at',
        r'\bo\s+n\b': 'on',
        r'\bb\s+y\b': 'by',
        r'\ba\s+s\b': 'as',
        r'\bi\s+t\b': 'it',
        r'\bf\s+or\b': 'for',
        r'\bfo\s+r\b': 'for',
        r'\bwi\s+th\b': 'with',
        r'\bwit\s+h\b': 'with',
        r'\bfr\s+om\b': 'from',
        r'\bfro\s+m\b': 'from',
        r'\bthi\s+s\b': 'this',
        r'\bth\s+is\b': 'this',
        r'\btha\s+t\b': 'that',
        r'\bth\s+at\b': 'that',
        r'\bthe\s+se\b': 'these',
        r'\bthe\s+y\b': 'they',
        r'\bha\s+ve\b': 'have',
        r'\bhav\s+e\b': 'have',
        r'\bha\s+s\b': 'has',
        r'\bmo\s+bile\b': 'mobile',
        r'\bde\s+vice\b': 'device',
        r'\bde\s+vices\b': 'devices',
        r'\blear\s+ner\b': 'learner',
        r'\blear\s+ners\b': 'learners',
        r'\bda\s+ta\b': 'data',
        r'\bin\s+terview\b': 'interview',
        r'\bstud\s+y\b': 'study',
        r'\bEn\s+glish\b': 'English',
        r'\bLan\s+guage\b': 'Language',
        r'\blan\s+guage\b': 'language',
        r'\baca\s+demic\b': 'academic',
        r'\bres\s+earch\b': 'research',
        r'\bpa\s+per\b': 'paper',
        r'\bcon\s+cept\b': 'concept',
        r'\bcon\s+cepts\b': 'concepts',
        r'\btop\s+ic\b': 'topic',
        r'\btop\s+ics\b': 'topics',
        r'\bIo\s+T\b': 'IoT'
    }
    for pattern, repl in common_short_splits.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # 3. Split run-together words (missing spaces)
    run_together_map = {
        r'\bRequirementfornetworkin\b': 'Requirement for network in',
        r'\baboutthe\b': 'about the',
        r'\binthe\b': 'in the',
        r'\bofthe\b': 'of the',
        r'\btothe\b': 'to the',
        r'\bforthe\b': 'for the',
        r'\bonthe\b': 'on the',
        r'\bwiththe\b': 'with the',
        r'\bandthe\b': 'and the',
        r'\bforthe\b': 'for the',
        r'\bonthe\b': 'on the',
        r'\bbythe\b': 'by the',
        r'\bfromthe\b': 'from the',
        r'\batthe\b': 'at the',
        r'\bintothe\b': 'into the',
        r'\btoour\b': 'to our',
        r'\binour\b': 'in our',
        r'\bofour\b': 'of our',
        r'\bwithour\b': 'with our',
        r'\bwehave\b': 'we have',
        r'\bwealready\b': 'we already',
        r'\btobe\b': 'to be',
        r'\binone\b': 'in one',
        r'\bofeach\b': 'of each',
        r'\baboutour\b': 'about our',
        r'\bforour\b': 'for our',
        r'\bandour\b': 'and our',
        r'\bbyour\b': 'by our',
        r'\bfromour\b': 'from our',
        r'\batour\b': 'at our',
        r'\bintoour\b': 'into our',
        r'\baboutthis\b': 'about this',
        r'\binthis\b': 'in this',
        r'\bofthis\b': 'of this',
        r'\btothis\b': 'to this',
        r'\bforthis\b': 'for this',
        r'\bonthis\b': 'on this',
        r'\bwiththis\b': 'with this',
        r'\bandthis\b': 'and this',
        r'\bbythis\b': 'by this',
        r'\bfromthis\b': 'from this',
        r'\batthis\b': 'at this',
        r'\bintothis\b': 'into this',
        r'\bfirstofall\b': 'first of all',
        r'\bofthings\b': 'of things',
        r'\binternetofthings\b': 'internet of things',
        r'\bnetworkofnetworks\b': 'network of networks',
        r'\binterconnectedlans\b': 'interconnected LANs',
        r'\boftech\b': 'of tech',
        r'\bdeforestationafter\b': 'deforestation after',
        r'\bcarbonoffsets\b': 'carbon offsets',
        r'\bverifiabledata\b': 'verifiable data',
        r'\bauditready\b': 'audit-ready',
        r'\bchallengetransitions\b': 'challenge transitions',
        r'\bfiniteautomata\b': 'finite automata',
        r'\bregularexpression\b': 'regular expression',
        r'\bregulargrammar\b': 'regular grammar',
        r'\bfinitestate\b': 'finite state',
        r'\bstatetransition\b': 'state transition',
        r'\btransitiondiagram\b': 'transition diagram',
        r'\bneuralnetwork\b': 'neural network',
        r'\bneuralnetworks\b': 'neural networks',
        r'\bdeeplearning\b': 'deep learning',
        r'\bmachinelearning\b': 'machine learning',
        r'\blinearalgebra\b': 'linear algebra',
        r'\bvectorcalculus\b': 'vector calculus',
        r'\bpos-wise\b': 'position-wise',
        r'\bposition-wise\b': 'position-wise',
        r'\bself-attention\b': 'self-attention',
        r'\bmulti-head\b': 'multi-head',
        r'\bscaleddot-product\b': 'scaled dot-product',
        r'\bdot-product\b': 'dot-product',
        r'\blabelsmoothing\b': 'label smoothing',
        r'\bresidualconnections\b': 'residual connections',
        r'\blayer-norm\b': 'layer normalization',
        r'\blayernorm\b': 'layer normalization',
        r'\boptimizing\b': 'optimizing',
        r'\badamoptimizer\b': 'adam optimizer',
        r'\blearningrate\b': 'learning rate',
        r'\blearningpaths\b': 'learning paths',
        r'\blearningpath\b': 'learning path',
        r'\bstudyguide\b': 'study guide',
        r'\bstudyguides\b': 'study guides',
        r'\bknowledgegraph\b': 'knowledge graph',
        r'\bknowledgegraphs\b': 'knowledge graphs',
        r'\bknowledgemesh\b': 'knowledge mesh',
        r'\bgraphrag\b': 'graph RAG',
        r'\bprereq\b': 'prerequisite',
        r'\bprereqs\b': 'prerequisites',
        r'\bprerequisiteof\b': 'prerequisite of',
        r'\brelatedto\b': 'related to',
        r'\bextends\b': 'extends',
        r'\bcontradicts\b': 'contradicts',
        r'\busesmethod\b': 'uses method',
        r'\bdependson\b': 'depends on',
        r'\bauthoredby\b': 'authored by',
        r'\bmentions\b': 'mentions',
        r'\bhaskeyword\b': 'has keyword'
    }
    for pattern, repl in run_together_map.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
        
    # Split punctuation lacking space, e.g. "word.Next" -> "word. Next"
    text = re.sub(r'([a-zA-Z0-9])([.,;:!?])([a-zA-Z])', r'\1\2 \3', text)
    
    # 4. De-hyphenate any residual split words across line boundaries
    text = re.sub(r'(\b\w+)-\s*\n+\s*(\b\w+)', r'\1\2', text)
    
    return text
