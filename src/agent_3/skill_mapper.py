import re

class SkillMapper:
    """Maps required skills to source evidence (Master CV & Accomplishments Bank)."""

    def map_required_skills(self, required_skills: list[str], accomplishments: list[dict], master_cv: dict) -> dict:
        """
        Maps JD skills to accomplishments and master CV to check for fabrication risks.
        Returns matched accomplishments per skill, and a list of unmapped skill gaps.
        """
        matched_skills = {}
        skill_gaps = []

        for skill in required_skills:
            skill_lower = skill.lower()
            matches_for_skill = []
            
            # 1. Search Accomplishments Bank
            for acc in accomplishments:
                # Direct match in skills_used
                skills_used_lower = [s.lower() for s in acc.get("skills_used", [])]
                if skill_lower in skills_used_lower:
                    matches_for_skill.append(acc)
                    continue
                    
                # Tag match
                tags_lower = [t.lower() for t in acc.get("tags", [])]
                if skill_lower in tags_lower:
                    matches_for_skill.append(acc)
                    continue
                    
                # Fuzzy match in accomplishment text (very basic for now)
                acc_text = acc.get("accomplishment", "").lower()
                # Use word boundaries to avoid partial matches (e.g., 'c' in 'cat')
                escaped_skill = re.escape(skill_lower)
                if re.search(rf'\b{escaped_skill}\b', acc_text):
                    matches_for_skill.append(acc)
                    continue

            # 2. Search Master CV if no accomplishments matched
            # We treat Master CV mention as an implicit match, but we prefer accomplishments
            # because we need metrics/impact for the CV bullets.
            # If we don't find it in accomplishments but find it in Master CV skills,
            # we consider it "matched" so it's not a gap, but we don't have a specific
            # accomplishment for it.
            if not matches_for_skill:
                master_skills_lower = [s.lower() for s in master_cv.get("skills", [])]
                if skill_lower in master_skills_lower:
                    # It's a match in Master CV, not an accomplishment.
                    # We can represent this with a dummy accomplishment or just keep it empty 
                    # but omit from skill_gaps. Let's just track it in matched_skills as empty,
                    # which means "found in CV skills, but no specific bullet".
                    matched_skills[skill] = []
                    continue
                
                # Check experience bullets
                found_in_bullets = False
                for exp in master_cv.get("experience", []):
                    for bullet in exp.get("bullets", []):
                        if re.search(rf'\b{escaped_skill}\b', bullet.lower()):
                            found_in_bullets = True
                            # Create a pseudo-accomplishment from the CV bullet
                            matches_for_skill.append({
                                "role": exp.get("role"),
                                "company": exp.get("company"),
                                "accomplishment": bullet,
                                "skills_used": [skill],
                                "metrics_impact": "",
                                "tags": []
                            })
                            break
                if found_in_bullets:
                    matched_skills[skill] = matches_for_skill
                    continue

                # If we get here, it's nowhere in the source evidence
                skill_gaps.append(skill)
            else:
                matched_skills[skill] = matches_for_skill

        return {
            "matched_skills": matched_skills,
            "skill_gaps": skill_gaps
        }
