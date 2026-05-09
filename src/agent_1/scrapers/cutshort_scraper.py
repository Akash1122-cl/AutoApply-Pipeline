"""Cutshort scraper for APM-specific roles in India."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from .base_scraper import BaseScraper, PortalConfig, ParsingError


class CutshortScraper(BaseScraper):
    """Cutshort scraper for APM-specific roles (India-focused)."""

    def __init__(self):
        config = PortalConfig(
            name="Cutshort",
            base_url="https://cutshort.io",
            requests_per_minute=20,
            base_delay_seconds=3.0,
            max_pages_per_day=300,
            robots_txt_check=True,
            enable_scraping=True
        )
        super().__init__(config, cache_hours=24)

        # Search URLs for APM roles (Phase 1: Discovery)
        self.search_urls = [
            "https://cutshort.io/jobs?q=Associate+Product+Manager",
            "https://cutshort.io/jobs?q=APM",
            "https://cutshort.io/jobs?q=Product+Manager+Associate",
        ]

    def discover_jobs(self, search_params: Dict[str, Any]) -> List[str]:
        """
        Phase 1: Discover job URLs from search results.
        """
        job_urls = []

        for search_url in self.search_urls:
            try:
                html = self._fetch_page(search_url, use_cache=False)  # Don't cache search pages
                if not html:
                    continue

                soup = self._parse_html(html)

                # Find job cards - Cutshort uses specific class names
                job_cards = soup.find_all('a', class_='job-card') or soup.find_all('a', href=lambda x: x and '/job/' in x)

                for card in job_cards[:20]:  # Limit to 20 per search
                    job_url = card.get('href', '')
                    if job_url:
                        if not job_url.startswith('http'):
                            job_url = f"https://cutshort.io{job_url}"
                        job_urls.append(job_url)

            except Exception as e:
                print(f"Cutshort: Error discovering jobs from {search_url}: {e}")
                continue

        return list(set(job_urls))

    def scrape_job_details(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Phase 2: Scrape full job details from job page.
        """
        try:
            html = self._fetch_page(job_url, use_cache=True)
            if not html:
                return None

            soup = self._parse_html(html)

            # Extract job details - Cutshort structure
            title_elem = soup.find('h1') or soup.find('div', class_='job-title')
            company_elem = soup.find('div', class_='company-name') or soup.find('a', class_='company-link')
            location_elem = soup.find('div', class_='location') or soup.find('span', class_='location-text')
            description_elem = soup.find('div', class_='job-description') or soup.find('div', class_='description')
            skills_elem = soup.find('div', class_='skills') or soup.find('div', class_='tags')

            if not title_elem:
                raise ParsingError("Cutshort: Missing job title")

            # Extract company name
            company = company_elem.get_text(strip=True) if company_elem else "Unknown"

            # Extract skills
            skills = []
            if skills_elem:
                skill_tags = skills_elem.find_all('span') or skills_elem.find_all('a')
                skills = [s.get_text(strip=True) for s in skill_tags if s.get_text(strip=True)]
            elif description_elem:
                desc_text = description_elem.get_text().lower()
                common_skills = [
                    "sql", "python", "agile", "scrum", "product management",
                    "data analysis", "user research", "a/b testing", "roadmapping",
                    "stakeholder management", "jira", "figma", "analytics"
                ]
                skills = [skill for skill in common_skills if skill in desc_text]

            if not skills:
                skills = ["product management"]

            # Determine work mode
            work_mode = "onsite"
            if description_elem:
                desc_text = description_elem.get_text().lower()
                if "remote" in desc_text:
                    work_mode = "remote"
                elif "hybrid" in desc_text:
                    work_mode = "hybrid"

            # Determine region
            region = "India"
            if location_elem:
                loc_text = location_elem.get_text().lower()
                if "bangalore" in loc_text or "bengaluru" in loc_text:
                    region = "India-Bangalore"
                elif "mumbai" in loc_text:
                    region = "India-Mumbai"
                elif "delhi" in loc_text or "ncr" in loc_text:
                    region = "India-Delhi"
                elif "remote" in loc_text:
                    region = "India-Remote"

            return {
                "job_id": str(uuid.uuid4()),
                "company": company,
                "role_title": title_elem.get_text(strip=True),
                "job_url": job_url,
                "source_platform": "Cutshort",
                "date_scraped": datetime.utcnow().strftime("%Y-%m-%d"),
                "region": region,
                "work_mode": work_mode,
                "work_permit_required": False,
                "required_skills": skills,
                "status": "SCRAPED"
            }

        except ParsingError:
            raise
        except Exception as e:
            raise ParsingError(f"Cutshort: Error scraping job details: {e}")
