"""Query understanding and intent classification engine for Sankalit Intelligence.
Classifies user queries into 9 distinct functional domains without LLM overhead.
"""

import re
from typing import Any, Dict, Optional

# Classification Categories
CLASS_COMPANY_SPECIFIC = "COMPANY_SPECIFIC"
CLASS_DEPARTMENT_SPECIFIC = "DEPARTMENT_SPECIFIC"
CLASS_PROJECT_SPECIFIC = "PROJECT_SPECIFIC"
CLASS_TECHNICAL = "TECHNICAL"
CLASS_HR_POLICY = "HR_POLICY"
CLASS_OPERATIONS = "OPERATIONS"
CLASS_GENERAL_PROFESSIONAL = "GENERAL_PROFESSIONAL"
CLASS_GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
CLASS_AMBIGUOUS = "AMBIGUOUS"

# Domain Keyword Maps
DOMAIN_PATTERNS = {
    "airport-systems": [
        r"\bairport\b", r"\bbhs\b", r"\baodb\b", r"\bfids\b", r"\bbaggage\b",
        r"\brunway\b", r"\bterminal\b", r"\bboarding\b", r"\baviation\b"
    ],
    "acoustic": [
        r"\bacoustic\b", r"\bacoustics\b", r"\bsound isolation\b", r"\breverberation\b",
        r"\brt60\b", r"\bnoise control\b", r"\bvibration\b", r"\bauditorium\b",
        r"\bstc rating\b", r"\bdecibel\b", r"\bdba\b", r"\baudio-visual\b", r"\baudio visual\b"
    ],
    "lighting": [
        r"\blighting\b", r"\blux\b", r"\blumen\b", r"\bdali\b", r"\bdmx\b",
        r"\bfixture\b", r"\bfaçade\b", r"\bfacade lighting\b", r"\barchitectural lighting\b"
    ],
    "mep": [
        r"\bmep\b", r"\bhvac\b", r"\bchiller\b", r"\bductwork\b", r"\bplumbing\b",
        r"\belectrical power\b", r"\bsubstation\b", r"\bfire protection\b",
        r"\bsprinkler\b", r"\bbim coordination\b", r"\bventilation\b"
    ],
    "it": [
        r"\bit\b", r"\bserver\b", r"\bnetwork\b", r"\bfirewall\b", r"\bcybersecurity\b",
        r"\bstructured cabling\b", r"\bhelpdesk\b", r"\bsoftware license\b", r"\bcloud\b",
        r"\bencryption\b", r"\bactive directory\b", r"\blan\b", r"\bwan\b", r"\bswitch\b"
    ],
    "hr": [
        r"\bleave\b", r"\bvacation\b", r"\bholiday\b", r"\battendance\b", r"\bonboarding\b",
        r"\bprobation\b", r"\bsalary\b", r"\bbonus\b", r"\bcompensation\b", r"\bappraisal\b",
        r"\bgrievance\b", r"\bposh\b", r"\bhandbook\b", r"\bnotice period\b", r"\bhiring\b"
    ],
    "projects": [
        r"\bproject\b", r"\bproposal\b", r"\bboq\b", r"\bbill of quantities\b",
        r"\btender\b", r"\brfp\b", r"\bdbr\b", r"\btechnical submission\b",
        r"\bclient\b", r"\bas-built\b", r"\bprogress report\b"
    ],
    "operations": [
        r"\bsop\b", r"\bprocurement\b", r"\bvendor\b", r"\bpurchase order\b",
        r"\binternal coordination\b", r"\bdocument control\b", r"\barchiving\b"
    ],
    "management": [
        r"\bmanagement\b", r"\bstrategic plan\b", r"\bexecutive\b", r"\bgovernance\b",
        r"\bboard\b", r"\biso certification\b", r"\brisk register\b", r"\bquality manual\b"
    ],
    "company-profile": [
        r"\bsankalit\b", r"\bwho are we\b", r"\bwhat does sankalit do\b",
        r"\bcompany overview\b", r"\bmission\b", r"\bvision\b",
        r"\bcompany background\b", r"\bfounded\b", r"\bcompany history\b"
    ]
}

GENERAL_KNOWLEDGE_PATTERNS = [
    r"\bcapital of\b", r"\bwho is president\b", r"\bweather in\b",
    r"\btell me a joke\b", r"\bhow many countries\b", r"\bmount everest\b",
    r"\bwho wrote\b", r"\bpopulation of\b"
]

PROFESSIONAL_PATTERNS = [
    r"\bdraft\b.*\bemail\b", r"\bwrite\b.*\bemail\b", r"\bformal letter\b",
    r"\bmeeting agenda\b", r"\bmeeting minutes\b", r"\bprofessional communication\b",
    r"\bcover letter\b", r"\bbusiness etiquette\b", r"\bemail template\b",
    r"\bprofessional email\b", r"\bhow to conduct a meeting\b"
]

TECHNICAL_PATTERNS = [
    r"\bsql\b", r"\bpython\b", r"\brest api\b", r"\bindexing\b",
    r"\bohm's law\b", r"\bfourier transform\b", r"\bnewton's law\b",
    r"\bpolymorphism\b", r"\btime complexity\b", r"\bformula\b", r"\bcalculation\b",
    r"\bdatabase storage\b"
]


def classify_query(query: str) -> Dict[str, Any]:
    """
    Classify incoming user query into one of the 9 categories.
    Determines likely domain slug, confidence, and company relevance.
    """
    clean = query.strip()
    if not clean:
        return {
            "classification": CLASS_AMBIGUOUS,
            "domain_slug": None,
            "confidence": 1.0,
            "is_company_relevant": False,
            "explanation": "Empty query received."
        }

    lower = clean.lower()

    # 1. Check for general knowledge trivia
    for pat in GENERAL_KNOWLEDGE_PATTERNS:
        if re.search(pat, lower):
            return {
                "classification": CLASS_GENERAL_KNOWLEDGE,
                "domain_slug": None,
                "confidence": 0.95,
                "is_company_relevant": False,
                "explanation": "Query matched general knowledge / trivia pattern."
            }

    # 2. Check for general technical / coding / science questions
    for pat in TECHNICAL_PATTERNS:
        if re.search(pat, lower):
            return {
                "classification": CLASS_TECHNICAL,
                "domain_slug": None,
                "confidence": 0.90,
                "is_company_relevant": False,
                "explanation": "Query matched general technical or software concept."
            }

    # 3. Check for general professional communication
    for pat in PROFESSIONAL_PATTERNS:
        if re.search(pat, lower):
            return {
                "classification": CLASS_GENERAL_PROFESSIONAL,
                "domain_slug": None,
                "confidence": 0.90,
                "is_company_relevant": False,
                "explanation": "Query matched general professional communication pattern."
            }

    # 4. Check for specific domains
    matched_domains = []
    for domain_slug, patterns in DOMAIN_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, lower):
                matched_domains.append(domain_slug)
                break

    # Prioritize specific functional and engineering domains over generic company-profile
    if "operations" in matched_domains:
        return {
            "classification": CLASS_OPERATIONS,
            "domain_slug": "operations",
            "confidence": 0.90,
            "is_company_relevant": True,
            "explanation": "Query relates to operations, SOPs, or procurement."
        }

    if "projects" in matched_domains:
        return {
            "classification": CLASS_PROJECT_SPECIFIC,
            "domain_slug": "projects",
            "confidence": 0.90,
            "is_company_relevant": True,
            "explanation": "Query relates to specific projects, proposals, or BOQs."
        }

    if "hr" in matched_domains:
        return {
            "classification": CLASS_HR_POLICY,
            "domain_slug": "hr",
            "confidence": 0.95,
            "is_company_relevant": True,
            "explanation": "Query relates to HR policies, leave, or benefits."
        }

    # Check engineering / technical departments
    for eng_domain in ["acoustic", "airport-systems", "lighting", "mep", "it"]:
        if eng_domain in matched_domains:
            return {
                "classification": CLASS_DEPARTMENT_SPECIFIC,
                "domain_slug": eng_domain,
                "confidence": 0.92,
                "is_company_relevant": True,
                "explanation": f"Query relates to departmental engineering domain '{eng_domain}'."
            }

    if "management" in matched_domains:
        return {
            "classification": CLASS_DEPARTMENT_SPECIFIC,
            "domain_slug": "management",
            "confidence": 0.90,
            "is_company_relevant": True,
            "explanation": "Query relates to management and executive governance."
        }

    if "company-profile" in matched_domains:
        return {
            "classification": CLASS_COMPANY_SPECIFIC,
            "domain_slug": "company-profile",
            "confidence": 0.95,
            "is_company_relevant": True,
            "explanation": "Query explicitly relates to Sankalit organization and profile."
        }

    # 4. Check length / ambiguity
    words = lower.split()
    if len(words) <= 2:
        return {
            "classification": CLASS_AMBIGUOUS,
            "domain_slug": None,
            "confidence": 0.70,
            "is_company_relevant": True,
            "explanation": "Short query without distinct domain keywords."
        }

    # Default fallback: General technical query
    return {
        "classification": CLASS_TECHNICAL,
        "domain_slug": None,
        "confidence": 0.65,
        "is_company_relevant": True,
        "explanation": "Query contains engineering or technical terminology."
    }
