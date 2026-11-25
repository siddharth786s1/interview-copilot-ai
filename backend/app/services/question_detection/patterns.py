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
    # Common Devanagari technical terms
    "ऑथेंटिकेशन", "ऑथराइजेशन", "डेटाबेस", "माइक्रोसर्विसेज", "एसक्यूएल", "रेडिस", "सिक्योरिटी", "आर्किटेक्चर", "कैशिंग",
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

# Substantive conversational interview cues (scenarios, constraints, pushback, topic pivots)
# Used when conversation_mode=True so the AI replies to ongoing dialogue, not only formal questions.
CONVERSATION_CUE_PATTERNS = [
    re.compile(r"\b(imagine|suppose|assume|let'?s say|consider a scenario|for example we have|picture this)\b", re.I),
    re.compile(r"\b(in our (system|production|architecture|team|company|environment|setup|stack))\b", re.I),
    re.compile(r"\b(we (are seeing|had an outage|have a problem|don'?t use|cannot use|can'?t use|switched to|migrated to|need to|want to|use))\b", re.I),
    re.compile(r"\b(the (constraint|challenge|issue|problem|bottleneck|requirement|trade-?off) (here )?is)\b", re.I),
    re.compile(r"\b(actually[,\s]|however[,\s]|on the other hand|the catch is|keep in mind|one thing to note)\b", re.I),
    re.compile(r"\b(i'?m not sure (that|if|whether)|that might not|wouldn'?t that|doesn'?t that|my concern is)\b", re.I),
    re.compile(r"\b(let'?s (move on to|switch to|dive into|focus on|look at|design|build|debug|solve))\b", re.I),
    re.compile(r"\b(your thoughts on|i'?d love to hear|curious to hear|interesting[,\s]+we)\b", re.I),
]

# Bilingual (Hindi / Hinglish) Small Talk Patterns
HINDI_SMALL_TALK_PATTERNS = [
    re.compile(r"^(theek hai|thik hai|theek h|dhanyawad|shukriya|haan ji|hanji|achha|accha|sahi hai|bahut badhiya)[.!?\s,]*$", re.I),
    re.compile(r"\b(aap sun sakte ho|meri awaz aa rahi hai|sun pa rahe ho|kya aap sun sakte ho|audio clear hai|awaz aa rahi hai)\b", re.I),
    re.compile(r"^(ठीक है|धन्यवाद|शुक्रिया|हाँजी|हाँ जी|अच्छा|बहुत बढ़िया)[.!?\s,]*$", re.I),
    re.compile(r"\b(क्या आप सुन सकते हैं|मेरी आवाज़ आ रही है|आवाज़ साफ है|सुन पा रहे हैं)\b", re.I),
]

# Bilingual (Hindi / Hinglish) Direct Question Starters & Endings
HINGLISH_DIRECT_QUESTION_PATTERNS = [
    re.compile(r"^(so\s+|aur\s+|to\s+|accha\s+)?(kya (aap|tum|hum|ye)|kaise (karenge|hota|hoga|kare|handle|solve)|kyun (use|karna)|kab (kare|hota))\b", re.I),
    re.compile(r"\b(kya hai|kya hoga|kaise kaam karta hai|kaise kare|bata sakte ho|bata sakti ho)\??$", re.I),
]

HINDI_DIRECT_QUESTION_PATTERNS = [
    re.compile(r"^(तो\s+|और\s+)?(क्या|कैसे|क्यों|कब|कहाँ|किस|कौन)\b", re.I),
    re.compile(r"(क्या है|कैसे काम करता है|समझा सकते हैं|बता सकते हैं)\??$", re.I),
]

# Bilingual (Hindi / Hinglish) Indirect & Imperative Prompts
HINGLISH_INDIRECT_QUESTION_PATTERNS = [
    re.compile(r"\b(explain karo|elaborate karo|batao|bataiye|samjhao|describe karo|walkthrough do|share karo|discuss karo)\b", re.I),
    re.compile(r"\b(aapka (experience|approach|view|background|take|project)|apna (experience|project))\b", re.I),
    re.compile(r"\b(mujhe (janna hai|bataiye|samjhaiye)|humein (bataiye|samjhaiye))\b", re.I),
]

HINDI_INDIRECT_QUESTION_PATTERNS = [
    re.compile(r"\b(समझाओ|बताइए|बताओ|विवरण दें|का क्या मतलब है|अंतर क्या है|के बारे में बताइए)\b", re.I),
    re.compile(r"\b(आपका अनुभव|अपने प्रोजेक्ट के बारे में|हमें बताइए|मुझे जानना है)\b", re.I),
]

# Bilingual (Hindi / Hinglish) Conversational Scenarios & Constraints
HINGLISH_CONVERSATION_CUE_PATTERNS = [
    re.compile(r"\b(maan lijiye|suppose karo|assume karo|sochiye ki)\b", re.I),
    re.compile(r"\b(agar hamare (system|server|architecture|database|codebase|team) mein)\b", re.I),
    re.compile(r"\b(problem yeh hai ki|issue yeh aa raha hai|dikkatt yeh hai ki|catch yeh hai ki)\b", re.I),
    re.compile(r"\b(hum (use nahi kar sakte|cannot use|dekh rahe hain|chahte hain ki|facing an issue))\b", re.I),
    re.compile(r"\b(latency badh rahi hai|memory full ho rahi hai|deadlocks aa rahe hain|outage hua tha)\b", re.I),
]

HINDI_CONVERSATION_CUE_PATTERNS = [
    re.compile(r"\b(मान लीजिए|सोचिए कि|मान लें)\b", re.I),
    re.compile(r"\b(अगर हमारे (सिस्टम|सर्वर|डेटाबेस|आर्किटेक्चर) में)\b", re.I),
    re.compile(r"\b(समस्या यह है कि|दिक्कत यह है कि|चुनौती यह है कि)\b", re.I),
    re.compile(r"\b(हम उपयोग नहीं कर सकते|हम देख रहे हैं कि)\b", re.I),
]
