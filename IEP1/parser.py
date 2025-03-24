import re
import nltk
import json
import spacy
from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import List, Dict, Tuple
from gensim import corpora, models
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Download required NLTK resources
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('stopwords')

# Pre-defined categories with associated keywords
CATEGORY_KEYWORDS = {
    "Shopping": ["buy", "purchase", "shop", "order", "get", "groceries", "store"],
    "Cleaning": ["clean", "tidy", "wash", "sweep", "scrub", "organize"],
    "Communication": ["send", "email", "call", "talk", "discuss", "schedule", "contact"],
    "Review": ["review", "check", "verify", "inspect", "study", "read"],
    "Work": ["complete", "finish", "prepare", "submit", "work", "do", "make"],
    "Errand": ["pick", "drop", "collect", "deliver", "grab", "get"]
}

class TaskParser:
    def __init__(self):
        """
        Initialize TaskParser with regex patterns and keywords.
        """
        # Regex for detecting course codes (e.g., MATH201)
        self.course_code_pattern = re.compile(r'\b[A-Z]{2,}\d+\b')
        # Regex for detecting times (e.g., "10:00 AM", "14:30")
        self.time_pattern = re.compile(r'\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?(?:\s?(?:am|pm))?\b', re.IGNORECASE)
        # Priority keywords
        self.priority_keywords = {"urgent", "priority", "asap", "important", "critical", "super urgent", "super important"}
        # Map special time phrases to normalized outputs
        self.special_time_phrases = {
            "eod": "By 11:59PM",
            "end of day": "By 11:59PM",
            "by eod": "By 11:59PM",
            "by end of day": "By 11:59PM",
            "sometime today": "Today",
            "today": "Today",
            "tomorrow": "Tomorrow",
            "tonight": "Tonight"
        }
        # Meeting keywords (for meeting classification)
        self.meeting_keywords = {"meeting", "webinar", "session", "sync"}
        self.meeting_verbs = {"discuss", "meet", "sync"}
        # Connectors for splitting compound sentences
        self.compound_connectors = re.compile(r'\b(after that|then|and then|also|and)\b', re.IGNORECASE)
        # List markers for splitting tasks
        self.list_markers = re.compile(r'[,;]|\band\b|\balso\b|\bthen\b|\bor\b|\bplus\b', re.IGNORECASE)
        # New patterns for task extraction
        self.task_indicators = [
            "has to", "should", "must", "needs to", "ought to", "need to", "have to",
            "submit", "prepare", "review", "do", "make", "finish", "complete",
            "buy", "get", "pick", "clean", "send", "call", "email"
        ]
        self.deadline_pattern = r'\b(?:by|before|at|around|about)\s+((?:(?:\d{1,2}\s*(?:am|pm))|noon|midday|midnight)(?:\s+\w+)?|tomorrow|today|tonight|next\s+\w+day|\w+day|end of day|early morning|late night)(?=\b|[\s\.,]|$)'
        # Priority patterns including parentheses
        self.priority_pattern = re.compile(r'(?:^|\(|\s)(urgent|priority|asap|important|critical|super urgent|super important)[\!\.\)]*', re.IGNORECASE)
        # Load spaCy model locally for any additional text processing
        self.nlp = spacy.load("en_core_web_sm")

    def clean_text(self, text: str) -> str:
        """
        Lowercase, remove HTML tags, unwanted punctuation (but preserve .?!, - and :),
        and collapse multiple spaces.
        """
        text = text.lower()
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'[^a-z0-9\s\.\?!\-:,;\(\)]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def split_into_fragments(self, text: str) -> List[str]:
        """
        Split text into fragments using multiple delimiters and patterns.
        """
        # First split by obvious delimiters
        fragments = []
        current = text
        
        # Split by list markers first
        parts = self.list_markers.split(current)
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Further split by compound connectors if the part is long enough
            if len(part.split()) > 5:
                subparts = self.compound_connectors.split(part)
                fragments.extend(sp.strip() for sp in subparts if sp.strip())
            else:
                fragments.append(part)
        
        return [f for f in fragments if f and not f.isspace()]

    def extract_course_codes(self, text: str) -> List[str]:
        """Extract course codes from text."""
        codes = self.course_code_pattern.findall(text)
        return list(set(codes))

    def extract_time(self, sentence: str) -> str:
        """
        Extract time from the sentence.
        Check special phrases first, then search with regex.
        """
        # Check for special time phrases
        lower_sentence = sentence.lower()
        for phrase, mapped in self.special_time_phrases.items():
            if phrase in lower_sentence:
                return mapped
                
        # Look for specific time patterns
        match = self.time_pattern.search(sentence)
        if match:
            time = match.group().upper()
            if 'pm' in time.lower() or 'am' in time.lower():
                return time.replace(' ', '')
            # If no AM/PM specified and hour is 1-11, assume PM for task times
            try:
                hour = int(time.split(':')[0] if ':' in time else time)
                if 1 <= hour <= 11:
                    return f"{time}PM"
            except ValueError:
                pass
            return time
            
        return "not specified"

    def extract_priority(self, sentence: str) -> str:
        """
        Extract priority from the sentence, including from parentheses.
        """
        match = self.priority_pattern.search(sentence)
        if match:
            priority = match.group(1)
            return priority.title()
        return "not specified"

    def classify_fragment(self, fragment: str) -> str:
        """
        Classify the fragment as 'meeting' or 'task' using keyword matching.
        More precise meeting detection to avoid false positives.
        """
        fragment_lower = fragment.lower()
        words = set(word_tokenize(fragment_lower))
        
        # Check if this is explicitly about a meeting
        if any(keyword in fragment_lower for keyword in self.meeting_keywords):
            # Verify it's not just mentioning a meeting as context
            if not any(phrase in fragment_lower for phrase in [
                "before the meeting", "after the meeting", "for the meeting",
                "prepare for meeting", "ready for meeting"
            ]):
                return "meeting"
        
        # Check for meeting verbs with subjects
        if any(verb in words for verb in self.meeting_verbs):
            doc = self.nlp(fragment_lower)
            for token in doc:
                if (token.dep_ == "nsubj" and 
                    token.head.text in self.meeting_verbs and
                    not any(w in fragment_lower for w in ["need to", "have to", "should"])):
                    return "meeting"
        
        return "task"

    def extract_relevant_meeting(self, fragment: str, course_codes: List[str]) -> str:
        """
        Extract meeting description from a fragment.
        """
        fragment = fragment.strip()
        
        # If it's a course-related meeting
        for code in course_codes:
            if code.lower() in fragment.lower():
                # Try to extract more context
                parts = fragment.lower().split(code.lower())
                context = parts[1] if len(parts) > 1 else ""
                context = context.strip(" ,.:")
                return f"{code} Meeting" + (f": {context}" if context else "")
        
        # If it's about discussing something
        if "to discuss" in fragment.lower():
            parts = fragment.split("to discuss", 1)
            subject = parts[1].strip(" ,.:")
            if subject:
                return f"Discussion: {subject}"
        
        # Extract the subject after meeting keywords
        for keyword in self.meeting_keywords:
            if keyword in fragment.lower():
                parts = fragment.lower().split(keyword, 1)
                if len(parts) > 1:
                    subject = parts[1].strip(" ,.:")
                    if subject:
                        return f"Meeting: {subject}"
        
        # If we can't extract a good description, use the whole fragment
        return fragment.strip(" ,.:")

    def extract_relevant_task(self, fragment: str) -> str:
        """
        Extract task description from a fragment.
        Removes filler phrases and normalizes the text.
        """
        # Remove common filler phrases
        task = re.sub(r'^(i\s+)?(have|need|must|should|want)\s+(to\s+)?', '', fragment, flags=re.IGNORECASE)
        task = re.sub(r'^(lets|let\'s|going\s+to|gonna|gotta)\s+', '', task, flags=re.IGNORECASE)
        task = re.sub(r'^\s*(and|also|then)\s+', '', task, flags=re.IGNORECASE)
        
        # Remove trailing filler words
        task = re.sub(r'\s+(?:right now|soon|at some point|when possible|if possible)$', '', task, flags=re.IGNORECASE)
        
        # Clean up any remaining artifacts
        task = task.strip(' ,.!?:;')
        
        return task if task else fragment

    def is_imperative(self, sentence: str) -> bool:
        """Check if a sentence is likely an imperative sentence."""
        tokens = word_tokenize(sentence)
        if not tokens:
            return False
        tokens[0] = tokens[0].lower()
        tagged = nltk.pos_tag(tokens)
        return tagged[0][1] == 'VB'

    def extract_deadline(self, sentence: str) -> str:
        """Extract deadline information from the sentence."""
        match = re.search(self.deadline_pattern, sentence, re.IGNORECASE)
        return match.group(1) if match else None

    def contains_task_indicators(self, sentence: str) -> bool:
        """Check if the sentence contains task indicator phrases."""
        sentence_lower = sentence.lower()
        return any(indicator in sentence_lower for indicator in self.task_indicators)

    def keyword_categorization(self, task_sentence: str) -> str:
        """Categorize a task using keyword matching."""
        tokens = [word.lower() for word in word_tokenize(task_sentence)]
        category_counts = {}
        for category, keywords in CATEGORY_KEYWORDS.items():
            count = sum(token in keywords for token in tokens)
            if count > 0:
                category_counts[category] = count
        return max(category_counts, key=category_counts.get) if category_counts else "General"

    def lda_categorization(self, task_sentences: List[str], num_topics: int = 2) -> List[Dict[str, any]]:
        """Apply LDA topic modeling to task sentences."""
        if len(task_sentences) < 2:  # Reduced minimum tasks for topic modeling
            return []
            
        # Process and clean the tasks
        stop_words = set(stopwords.words('english'))
        processed_tasks = []
        for sentence in task_sentences:
            # Keep only content words, remove stopwords
            tokens = [word.lower() for word in word_tokenize(sentence) 
                     if word.isalpha() and word.lower() not in stop_words]
            if tokens:  # Only add if we have tokens after cleaning
                processed_tasks.append(tokens)
        
        if not processed_tasks:
            return []
            
        dictionary = corpora.Dictionary(processed_tasks)
        corpus = [dictionary.doc2bow(text) for text in processed_tasks]
        
        # Only proceed if we have enough unique terms
        if len(dictionary) < 4:  # Reduced minimum unique terms
            return []
        
        lda_model = models.LdaModel(
            corpus, 
            num_topics=min(num_topics, len(processed_tasks)), 
            id2word=dictionary,
            passes=15,
            random_state=42
        )
        
        # Convert topics to a more useful format
        topics = []
        for topic_id in range(lda_model.num_topics):
            topic_terms = dict(lda_model.show_topic(topic_id, topn=5))
            # Convert numpy float32 to regular Python float
            topic_terms = {k: float(v) for k, v in topic_terms.items()}
            # Only include topics with reasonable term weights
            if max(topic_terms.values()) > 0.1:
                topics.append({
                    "id": topic_id,
                    "terms": topic_terms,
                    "label": self._generate_topic_label(topic_terms)
                })
        
        return topics
    
    def _generate_topic_label(self, topic_terms: Dict[str, float]) -> str:
        """Generate a descriptive label for a topic based on its terms."""
        # Sort terms by weight
        sorted_terms = sorted(topic_terms.items(), key=lambda x: x[1], reverse=True)
        main_terms = [term for term, _ in sorted_terms[:3]]
        
        # Try to match with predefined categories
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(term in keywords for term in main_terms):
                return f"{category}-related tasks"
        
        # Default to a generic label using the top terms
        return f"Tasks involving {', '.join(main_terms)}"

    def parse(self, text: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Parse text into structured meeting and task information with enhanced task extraction.
        """
        course_codes = self.extract_course_codes(text)
        cleaned_text = self.clean_text(text)
        fragments = self.split_into_fragments(cleaned_text)
        
        tasks = []
        meetings = []
        task_sentences = []
        
        for fragment in fragments:
            # Skip empty or very short fragments
            if not fragment or len(fragment.split()) < 2:
                continue
            
            time_value = self.extract_time(fragment)
            priority_value = self.extract_priority(fragment)
            label = self.classify_fragment(fragment)
            
            if label == "meeting":
                meeting_desc = self.extract_relevant_meeting(fragment, course_codes)
                if meeting_desc and not meeting_desc.isspace():
                    meetings.append({
                        "description": meeting_desc,
                        "priority": priority_value,
                        "time": time_value
                    })
            else:
                # Enhanced task extraction
                if (self.is_imperative(fragment) or 
                    self.contains_task_indicators(fragment) or 
                    self.extract_deadline(fragment) or
                    priority_value != "not specified"):
                    
                    task_desc = self.extract_relevant_task(fragment)
                    if task_desc and not task_desc.isspace():
                        deadline = self.extract_deadline(fragment)
                        category = self.keyword_categorization(fragment)
                        
                        task_info = {
                            "description": task_desc,
                            "priority": priority_value,
                            "time": time_value or deadline or "not specified",
                            "category": category
                        }
                        tasks.append(task_info)
                        task_sentences.append(fragment)
        
        # Apply LDA topic modeling to tasks
        topics = self.lda_categorization(task_sentences)
        
        return {
            "meetings": meetings,
            "tasks": tasks,
            "course_codes": course_codes,
            "topics": topics
        }

# Flask app setup
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/parse-tasks', methods=['POST'])
def parse_tasks_endpoint():
    data = request.get_json()
    text = data.get('text', '')
    parser = TaskParser()
    result = parser.parse(text)
    return jsonify(result), 200, {'Content-Type': 'application/json; charset=utf-8'}

@app.route('/health', methods=['GET'])
def health_endpoint():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
