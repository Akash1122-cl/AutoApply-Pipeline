from src.agent_3b.ats_constants import (
    REQUIRED_SECTIONS,
    MAX_PAGES_ABSOLUTE,
    DATE_PATTERNS
)

class StructuralChecker:
    """Runs rule-based formatting and structure checks for ATS compatibility."""
    
    def run_all_checks(self, cv_data: dict, row: dict) -> dict:
        checks = [
            ("single_column", self.check_single_column_layout(cv_data)),
            ("file_type_docx", self.check_file_type_docx(row.get("cv_doc_link", ""))),
            ("required_sections", self.check_required_sections(cv_data)),
            ("no_tables", self.check_no_tables(cv_data)),
            ("no_graphics", self.check_no_graphics(cv_data)),
            ("no_headers_footers", self.check_no_headers_footers(cv_data)),
            ("length", self.check_length(cv_data, row)),
            ("contact_block", self.check_contact_block_at_top(cv_data)),
            ("date_consistency", self.check_date_format_consistency(cv_data)),
        ]
        
        return {
            "results": {name: result for name, result in checks},
            "passed_count": sum(1 for _, (passed, _) in checks if passed),
            "total_count": len(checks),
            "failures": [(name, msg) for name, (passed, msg) in checks if not passed]
        }

    def check_single_column_layout(self, cv_data: dict) -> tuple[bool, str]:
        if not cv_data.get("is_single_column", True):
            return False, "Multi-column layout detected - ATS will misparse"
        return True, ""

    def check_file_type_docx(self, cv_doc_link: str) -> tuple[bool, str]:
        if not cv_doc_link:
            return False, "Missing CV link"
            
        is_docx = cv_doc_link.endswith(".docx") or "docs.google.com" in cv_doc_link
        if not is_docx:
            return False, "File should be .docx for best ATS compatibility"
        return True, ""

    def check_required_sections(self, cv_data: dict) -> tuple[bool, str]:
        found_sections = [s.lower() for s in cv_data.get("section_headers", [])]
        required_lower = [s.lower() for s in REQUIRED_SECTIONS]
        
        missing = []
        for req in required_lower:
            # Check if required section name exists in any of the found headers
            if not any(req in fs for fs in found_sections):
                missing.append(req)
                
        if missing:
            return False, f"Missing required sections: {', '.join(missing)}"
        return True, ""

    def check_no_tables(self, cv_data: dict) -> tuple[bool, str]:
        count = cv_data.get("table_count", 0)
        if count > 0:
            return False, f"Found {count} tables — remove for ATS compatibility"
        return True, ""

    def check_no_graphics(self, cv_data: dict) -> tuple[bool, str]:
        count = cv_data.get("image_count", 0)
        if count > 0:
            return False, f"Found {count} images — remove for ATS compatibility"
        return True, ""

    def check_no_headers_footers(self, cv_data: dict) -> tuple[bool, str]:
        hf_text = cv_data.get("header_footer_text", "").strip()
        if hf_text:
            return False, "Content found in headers/footers — move to body"
        return True, ""

    def check_length(self, cv_data: dict, row: dict) -> tuple[bool, str]:
        pages = cv_data.get("estimated_pages", 0.0)
        if pages > MAX_PAGES_ABSOLUTE:
            return False, f"CV is {pages:.1f} pages — max is {MAX_PAGES_ABSOLUTE}"
        return True, ""

    def check_contact_block_at_top(self, cv_data: dict) -> tuple[bool, str]:
        raw_text = cv_data.get("raw_text", "")
        first_100_words = " ".join(raw_text.split()[:100])
        
        has_email = "@" in first_100_words
        has_phone = any(c.isdigit() for c in first_100_words)
        
        if not (has_email and has_phone):
            return False, "Contact info (email + phone) must be at top of CV"
        return True, ""

    def check_date_format_consistency(self, cv_data: dict) -> tuple[bool, str]:
        import re
        text = cv_data.get("raw_text", "")
        pattern_matches = [len(re.findall(p, text)) for p in DATE_PATTERNS]
        
        # Count how many DIFFERENT date patterns are used
        patterns_used = sum(1 for count in pattern_matches if count > 0)
        
        if patterns_used > 1:
            return False, "Inconsistent date formats — use one format throughout"
        return True, ""
