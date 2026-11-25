"""
Multi-Paradigm Few-Shot Learning Library for Interview Copilot AI.

Provides diverse, production-tested training exemplars across 5 core interview paradigms:
1. System Design & Architectural Constraints
2. Incident Debugging & Performance Diagnostics
3. Behavioral STAR Framework (Quantified Results)
4. Interviewer Pushback & Technical Defense
5. Bilingual / Hinglish Real-World Technical Dialogue
"""
from typing import Dict, List, Optional

AVAILABLE_PARADIGMS = [
    "system_design",
    "incident_debugging",
    "behavioral_star",
    "pushback_handling",
    "bilingual_hinglish",
]

PARADIGM_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "system_design": {
        "title": "System Design & Architecture",
        "description": "High-scale trade-offs, caching, partitioning, and resilience patterns.",
        "question": "In our architecture, we are seeing high memory consumption in our Redis cluster under peak traffic and we cannot add more cluster nodes.",
        "ideal_answer": (
            "**Direct Answer**\n"
            "To resolve high memory pressure in a fixed-size Redis cluster, I would configure aggressive key eviction policies, tune memory-efficient internal data structures, and audit high-cardinality keys.\n\n"
            "**Key Points**\n"
            "- Set `maxmemory-policy` to `allkeys-lru` or `volatile-lru` to prevent out-of-memory crashes.\n"
            "- Audit memory distribution using `redis-cli --bigkeys` and enforce explicit TTLs on all cache writes.\n"
            "- Optimize data representation by leveraging Redis hashes with ziplist encoding (`hash-max-ziplist-entries`).\n"
            "- Offload cold session state to an auxiliary persistent document or relational store.\n\n"
            "**Practical Example**\n"
            "```bash\n"
            "redis-cli config set maxmemory-policy allkeys-lru\n"
            "redis-cli --bigkeys\n"
            "```\n\n"
            "**Quick Tip**\n"
            "Monitor CPU overhead when activating LRU eviction under 100k+ ops/sec throughput."
        ),
    },
    "incident_debugging": {
        "title": "Incident & Latency Debugging",
        "description": "Systematic root-cause analysis, I/O wait, connection pool exhaustion, and profiling.",
        "question": "Our payment gateway service suddenly experienced a p99 latency spike to 4 seconds, but CPU utilization is under 20%.",
        "ideal_answer": (
            "**Direct Answer**\n"
            "Low CPU paired with severe p99 latency indicates an external I/O bottleneck, connection pool exhaustion, or downstream lock contention rather than compute saturation.\n\n"
            "**Key Points**\n"
            "- Inspect client connection pool metrics (active vs idle pool connections, wait queue time).\n"
            "- Check downstream database wait events and thread dump states (looking for `WAITING` or `BLOCKED` states on socket read).\n"
            "- Verify network latency and TCP retransmits between the service and payment provider API.\n"
            "- Implement circuit breakers (e.g. Resilience4j / Polly) and strict timeouts to fail fast.\n\n"
            "**Practical Example**\n"
            "```bash\n"
            "# Check socket states and queue backlog\n"
            "ss -s\n"
            "netstat -s | grep -i retrans\n"
            "```\n\n"
            "**Quick Tip**\n"
            "Always set client-side read timeouts lower than upstream load balancer gateway timeouts."
        ),
    },
    "behavioral_star": {
        "title": "Behavioral STAR with Metrics",
        "description": "Situation, Task, Action, and Result with concrete quantified business impact.",
        "question": "Tell me about a time you had a technical disagreement with a colleague on an architectural choice.",
        "ideal_answer": (
            "**Direct Answer**\n"
            "On our microservices order platform, a senior teammate wanted synchronous REST calls while I advocated for an asynchronous event-driven transactional outbox.\n\n"
            "**Key Points**\n"
            "- **Situation**: Direct REST chains created cascading failures and 8% checkout timeout errors during flash promotions.\n"
            "- **Task**: Align the team on a reliable architecture without missing our release deadline.\n"
            "- **Action**: Built a benchmark POC comparing REST timeouts vs Kafka event publishing, demonstrating zero-loss durability during downstream outages.\n"
            "- **Result**: The team unanimously adopted the outbox pattern; checkout reliability reached 99.98% and checkout failure rates dropped from 8% to under 0.05%.\n\n"
            "**Quick Tip**\n"
            "Frame technical disagreements around empirical data and user impact rather than personal opinions."
        ),
    },
    "pushback_handling": {
        "title": "Handling Interviewer Pushback",
        "description": "Constructively defending engineering trade-offs while acknowledging valid concerns.",
        "question": "Wouldn't adopting an event-driven architecture introduce too much operational complexity and eventual consistency headaches?",
        "ideal_answer": (
            "**Direct Answer**\n"
            "That is a completely valid concern—event-driven architectures do introduce distributed tracing, schema evolution, and eventual consistency overhead that isn't justified for simple CRUD workloads.\n\n"
            "**Key Points**\n"
            "- We reserve event-driven patterns strictly for asynchronous boundaries where decoupling throughput and fault isolation outweigh consistency latency.\n"
            "- For mission-critical balance deductions or inventory reservation, we keep strong consistency in single-boundary ACID transactions.\n"
            "- We mitigate operational complexity by using standardized schema registries (Avro/Protobuf) and OpenTelemetry distributed tracing.\n\n"
            "**Quick Tip**\n"
            "Acknowledge the interviewer's pushback first before articulating where and why the trade-off is worth it."
        ),
    },
    "bilingual_hinglish": {
        "title": "Bilingual / Hinglish Technical Dialogue",
        "description": "Natural technical code-switching with core engineering terms in English.",
        "question": "Maan lijiye hamare system mein Redis cluster memory full ho rahi hai aur hum nodes nahi badha sakte, usko kaise handle karoge?",
        "ideal_answer": (
            "**Direct Answer**\n"
            "Iss scenario mein main aggressive key eviction policies configure karunga, data structures ki memory optimization karunga, aur cold data ko persistent storage pe offload karunga.\n\n"
            "**Key Points**\n"
            "- `maxmemory-policy` ko `allkeys-lru` ya `volatile-lru` pe set karenge taaki memory crash na ho aur inactive keys auto-prune ho sakein.\n"
            "- `redis-cli --bigkeys` run karke top memory consuming keys identify karenge aur sabhi cache entries par explicit TTL enforce karenge.\n"
            "- Redis hashes mein `hash-max-ziplist-entries` tuning use karenge for memory compression.\n"
            "- Unnecessary caching ko eliminate karenge aur client-side caching implement karenge.\n\n"
            "**Practical Example**\n"
            "```bash\n"
            "redis-cli config set maxmemory-policy allkeys-lru\n"
            "redis-cli --bigkeys\n"
            "```\n\n"
            "**Quick Tip**\n"
            "Eviction policy enable karte waqt CPU utilization track karein kyunki aggressive LRU scans high-throughput mein CPU spikes create kar sakte hain."
        ),
    },
}


def get_learning_exemplars(active_paradigms: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    Retrieve structured training exemplars for the specified or all active paradigms.
    """
    selected = active_paradigms if active_paradigms is not None else AVAILABLE_PARADIGMS
    exemplars: List[Dict[str, str]] = []
    for paradigm in selected:
        if paradigm in PARADIGM_DEFINITIONS:
            defn = PARADIGM_DEFINITIONS[paradigm]
            exemplars.append(
                {
                    "paradigm": paradigm,
                    "title": defn["title"],
                    "question": defn["question"],
                    "ideal_answer": defn["ideal_answer"],
                }
            )
    return exemplars
