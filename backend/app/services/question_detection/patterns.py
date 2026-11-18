"""
Linguistic patterns, domain vocabularies, and filters for interview Question Detection.
"""
import re

# Small talk, pleasantries, and meeting logistics that must NOT trigger LLM answers
SMALL_TALK_PATTERNS = [
    re.compile(r"^(ok(ay)?|alright|sure|great|awesome|cool|nice|got it|makes sense|fair enough|understood|right|yeah|yes|no|uh huh|mm hmm|sounds good|thank you|thanks|appreciate it)[.!?\s,]*$", re.I),
    re.compile(r"^(great|okay|alright|cool|awesome|good|fine)[,\s]+(let'?s move on|sounds good|thank you|thanks|moving on|next)[.!?\s]*$", re.I),
    re.compile(r"^(hello|hi|hey|good morning|good afternoon|good evening|nice to meet you|welcome)[,\s\w]*[.!?\s]*$", re.I),
    re.compile(r"\b(can you hear me|hear me okay|am i audible|can you see my screen|see my slides|is my screen visible|are you able to see|how are you doing|how'?s your day|how are you today|how have you been)\b", re.I),
    re.compile(r"\b(let me share my screen|sharing my screen|give me a second|one moment|hold on|sorry i was on mute|you'?re on mute|nice talking to you|have a great day)\b", re.I),
    re.compile(r"^(thanks for (joining|coming|your time|explaining|sharing)|thank you for (joining|that|sharing))", re.I),
]

# Direct interrogative starters
DIRECT_QUESTION_STARTERS = re.compile(
    r"^(so\s+|and\s+|well\s+|okay\s+|now\s+|alright\s+|next\s+)?"
    r"(what|how|why|when|where|who|which|whose|whom|"
    r"can you|could you|would you|will you|do you|did you|have you|has|had|"
    r"are you|is there|is it|are there|were you|should we|should you|does)\b",
    re.I,
)

# Indirect & imperative interview prompts (no '?' required)
INDIRECT_QUESTION_PATTERNS = [
    re.compile(r"\b(explain|describe|elaborate on|clarify|define|outline|summarize|discuss|compare|contrast)\b", re.I),
    re.compile(r"\b(tell me about|tell us about|walk me through|walk us through|talk me through|take me through)\b", re.I),
    re.compile(r"\b(give me an example|share an example|share a time|give us an example|provide an example)\b", re.I),
    re.compile(r"\b(i'?d like to (know|hear|understand|ask)|i want to (know|ask|understand)|i was wondering)\b", re.I),
    re.compile(r"\b(what'?s your (experience|approach|view|take|opinion|familiarity)|how familiar are you)\b", re.I),
    re.compile(r"\b(let'?s talk about|let'?s discuss|could you share|can you share)\b", re.I),
]

# Follow-up cues (anaphora / continuation referencing an earlier answer or topic)
FOLLOWUP_PATTERNS = [
    re.compile(r"\b(elaborate on that|expand on that|dive deeper into that|go deeper into that|more detail on that|tell me more about that)\b", re.I),
    re.compile(r"\b(how (did|do|would) you (handle|implement|fix|test|debug|solve|scale|secure|measure|optimize) (that|it|this|those))\b", re.I),
    re.compile(r"\b(why did you (choose|use|pick|go with) (that|it|this|those))\b", re.I),
    re.compile(r"\b(what about|how about|and what if|what if (that|it|the)|follow[\s-]?up)\b", re.I),
    re.compile(r"^(and\s+)?(can you|could you)\s+(explain\s+)?how\s+you\s+\w+\s+(that|it|this)\b", re.I),
    re.compile(r"\b(in that (project|case|scenario|situation)|from what you just (said|mentioned)|you mentioned)\b", re.I),
]

# Technical domain keywords to classify question_type="technical"
TECHNICAL_KEYWORDS = {
    "sql", "injection", "authentication", "authorization", "oauth", "jwt", "saml", "sso",
    "sap", "otbi", "bi publisher", "oracle", "fusion", "hcm", "owasp", "xss", "csrf",
    "api", "rest", "graphql", "grpc", "microservice", "microservices", "database",
    "index", "indexing", "transaction", "acid", "nosql", "redis", "cache", "caching",
    "python", "java", "javascript", "typescript", "react", "nextjs", "fastapi", "django",
    "docker", "kubernetes", "aws", "azure", "gcp", "ci/cd", "linux", "http", "https",
    "tls", "ssl", "encryption", "hashing", "security", "vulnerability", "troubleshoot",
    "troubleshooting", "debug", "debugging", "latency", "scalability", "concurrency",
    "async", "thread", "deadlock", "algorithm", "complexity", "data structure",
    "system design", "architecture", "load balancer", "kafka", "queue", "rbac", "abac",
    "t-code", "pfcg", "su53", "role", "roles", "profile", "segregation of duties", "sod",
}

# Incomplete fragment patterns (should be buffered and merged with next segment)
INCOMPLETE_ENDINGS = re.compile(
    r"(\.\.\.|…|\b(between|about|with|for|of|in|on|to|into|from|how|what|why|when|where|whether|if|and|or|but|that|which|your|the|a|an|you|can|could|would|should|explain|describe|difference))\s*$",
    re.I,
)

# Standalone very short fragment openers like "Could you...", "Can you...", "So uh..."
FRAGMENT_ONLY_PATTERNS = [
    re.compile(r"^(so|and|well|um|uh|can you|could you|would you|what is|what are|how do|how would|tell me|explain)[,.\s…]*$", re.I),
]
