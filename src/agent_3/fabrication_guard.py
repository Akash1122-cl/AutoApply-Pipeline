class FabricationError(Exception):
    pass

class FabricationGuard:
    """Validates that no fabricated claims exist in generated CVs."""
    
    @staticmethod
    def validate_cv(generated_cv: dict, source_evidence: dict, master_cv: dict) -> dict:
        """
        Validates the generated CV against the master CV and accomplishments bank.
        source_evidence here is the mapped_skills from SkillMapper, 
        or we can just check against the master_cv and raw accomplishments.
        For simplicity and robustness, we check against the raw Master CV and Accomplishments Bank.
        """
        violations = []
        
        # We need all valid facts
        valid_companies = [exp.get("company", "").lower() for exp in master_cv.get("experience", [])]
        valid_roles = [exp.get("role", "").lower() for exp in master_cv.get("experience", [])]
        
        valid_bullets = []
        for exp in master_cv.get("experience", []):
            valid_bullets.extend([b.lower() for b in exp.get("bullets", [])])
            
        valid_skills = [s.lower() for s in master_cv.get("skills", [])]
        
        # We also need accomplishments to extract valid metrics/bullets
        # Since we don't have raw accomplishments passed in directly by the caller based on the prompt,
        # we assume source_evidence contains the matched accomplishments.
        # Let's extract all text from source_evidence.
        evidence_text = ""
        for skill, accs in source_evidence.items():
            for acc in accs:
                evidence_text += acc.get("accomplishment", "").lower() + " "
                evidence_text += acc.get("metrics_impact", "").lower() + " "
                for s in acc.get("skills_used", []):
                    valid_skills.append(s.lower())
        
        # 1. Check generated experience roles/companies
        for exp in generated_cv.get("experience", []):
            comp = exp.get("company", "").lower()
            role = exp.get("role", "").lower()
            
            if comp and comp not in valid_companies:
                violations.append({"section": "experience", "claim": comp, "reason": "Fabricated company"})
            if role and role not in valid_roles:
                violations.append({"section": "experience", "claim": role, "reason": "Fabricated role"})
                
            # 2. Check metrics in bullets
            for bullet in exp.get("bullets", []):
                import re
                # Find all numbers/metrics
                metrics = re.findall(r'\b\d+(?:\.\d+)?%?|\$\d+(?:[KkMmBb])?\b', bullet)
                for metric in metrics:
                    metric_lower = metric.lower()
                    # Check if metric exists in valid bullets or evidence
                    metric_found = False
                    for vb in valid_bullets:
                        if metric_lower in vb:
                            metric_found = True
                            break
                    if not metric_found and metric_lower in evidence_text:
                        metric_found = True
                        
                    if not metric_found:
                        violations.append({"section": "bullets", "claim": metric, "reason": "Fabricated metric"})
                        
        # 3. Check skills
        for skill in generated_cv.get("skills", []):
            skill_lower = skill.lower()
            # fuzzy check
            if skill_lower not in valid_skills and not any(skill_lower in vs for vs in valid_skills):
                violations.append({"section": "skills", "claim": skill, "reason": "Fabricated skill"})
                
        # 4. Check education
        master_edus = [e.get("degree", "").lower() for e in master_cv.get("education", [])]
        for edu in generated_cv.get("education", []):
            deg = edu.get("degree", "").lower()
            if deg and deg not in master_edus:
                violations.append({"section": "education", "claim": deg, "reason": "Fabricated degree"})
                
        is_valid = len(violations) == 0
        return {
            "is_valid": is_valid,
            "violations": violations
        }
