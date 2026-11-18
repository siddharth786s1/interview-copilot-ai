"""
Deterministic, zero-fabrication structured resume field extractor.
Parses skills, experience, projects, education, and certifications strictly
from the extracted resume text without inventing any information.
"""
import re
from typing import Dict, List

SECTION_HEADERS = {
    "skills": re.compile(r"^(technical\s+)?(skills|core\s+competencies|technologies|tech\s+stack)\s*:?$", re.I),
    "experience": re.compile(r"^(work\s+|professional\s+)?(experience|employment\s+history|career\s+history)\s*:?$", re.I),
    "projects": re.compile(r"^(key\s+|selected\s+|personal\s+|academic\s+)?projects\s*:?$", re.I),
    "education": re.compile(r"^(education|academic\s+background|qualifications)\s*:?$", re.I),
    "certifications": re.compile(r"^(certifications?|licenses?\s*&?\s*certifications?|credentials)\s*:?$", re.I),
    "summary": re.compile(r"^(summary|professional\s+summary|profile|objective|about\s+me)\s*:?$", re.I),
}

KNOWN_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "SQL", "PostgreSQL", "MySQL", "SQLite",
    "FastAPI", "Django", "Flask", "Spring Boot", "React", "Next.js", "Node.js", "Tailwind CSS",
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux", "Git", "REST", "GraphQL", "gRPC",
    "OAuth2", "JWT", "SAML", "SSO", "OWASP", "Application Security", "API Security",
    "Cybersecurity", "SAP Security", "PFCG", "SU53", "GRC", "Oracle Fusion HCM", "OTBI",
    "BI Publisher", "Redis", "Kafka", "Microservices", "System Design", "CI/CD", "Terraform",
]


def extract_resume_fields(extracted_text: str) -> Dict[str, List[str]]:
    """
    Parse structured resume fields from extracted plain text.
    Never fabricates items not grounded in the input text.
    """
    sections: Dict[str, List[str]] = {
        "skills": [],
        "experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
    }

    current_section: str | None = None
    lines = [line.strip() for line in extracted_text.splitlines()]

    for line in lines:
        if not line:
            continue

        # Check if this line is a section header (also handle inline "Skills: Python, SQL")
        matched_header = None
        inline_remainder = ""
        for sec_name, pat in SECTION_HEADERS.items():
            if pat.match(line):
                matched_header = sec_name
                break
            # Inline prefix like "Skills: Python, Java, SQL"
            prefix_match = re.match(rf"^{sec_name}\s*:\s*(.+)$", line, re.I)
            if prefix_match:
                matched_header = sec_name
                inline_remainder = prefix_match.group(1).strip()
                break

        if matched_header:
            current_section = matched_header if matched_header in sections else None
            if current_section and inline_remainder:
                _append_item(sections, current_section, inline_remainder)
            continue

        if current_section:
            _append_item(sections, current_section, line)

    # Supplement skills with explicitly mentioned known skills found in the text
    seen_lower = {s.lower() for s in sections["skills"]}
    for skill in KNOWN_SKILLS:
        if re.search(rf"\b{re.escape(skill)}\b", extracted_text, re.I):
            if skill.lower() not in seen_lower:
                sections["skills"].append(skill)
                seen_lower.add(skill.lower())

    # Deduplicate and cap item counts cleanly
    for key in sections:
        deduped: List[str] = []
        seen: set[str] = set()
        for item in sections[key]:
            norm = item.strip("•-* \t")
            if norm and norm.lower() not in seen:
                deduped.append(norm)
                seen.add(norm.lower())
        sections[key] = deduped[:40]

    return sections


def _append_item(sections: Dict[str, List[str]], section: str, line: str) -> None:
    cleaned = line.strip("•-* \t")
    if not cleaned:
        return
    if section == "skills":
        # Split comma/pipe/semicolon separated skill lists (and strip sub-labels like "Languages:")
        if ":" in cleaned:
            cleaned = cleaned.split(":", 1)[1].strip()
        for token in re.split(r"[,;|/]+", cleaned):
            t = token.strip()
            if 1 <= len(t) <= 60:
                sections["skills"].append(t)
    else:
        sections[section].append(cleaned[:300])
