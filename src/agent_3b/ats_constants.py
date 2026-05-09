# Pass threshold (per spec)
ATS_PASS_THRESHOLD = 80

# Maximum revisions (per spec)
MAX_ATS_REVISIONS = 2

# Total number of checks
TOTAL_CHECKS = 11

# Keyword coverage minimum (per spec)
KEYWORD_COVERAGE_MIN = 0.60  # 60%

# Length limits (per spec)
MAX_PAGES_UNDER_3YRS = 1
MAX_PAGES_ABSOLUTE = 2
WORDS_PER_PAGE = 500  # rough estimate for length validation

# Required CV sections
REQUIRED_SECTIONS = ["Summary", "Experience", "Education", "Skills"]

# Acceptable date format patterns
DATE_PATTERNS = [
    r"\b(0[1-9]|1[0-2])/\d{4}\b",          # MM/YYYY
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s\d{4}\b", # Month YYYY
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{4}\b",         # Mon YYYY
]
