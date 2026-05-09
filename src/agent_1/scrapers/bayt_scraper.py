"""Bayt scraper for Middle East and North Africa region."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from .base_scraper import BaseScraper, PortalConfig, ParsingError


class BaytScraper(BaseScraper):
    """Bayt scraper for MENA region jobs."""

    def __init__(self):
        config = PortalConfig(
            name="Bayt",
            base_url="https://www.bayt.com",
            requests_per_minute=10,
            base_delay_seconds=6.0,
            max_pages_per_day=200,
            robots_txt_check=True,
            enable_scraping=True
        )
        super().__init__(config, cache_hours=24)

        # Search URLs for different MENA countries
        self.search_urls = [
            "https://www.bayt.com/en/uae/jobs/associate-product-manager/",
            "https://www.bayt.com/en/saudi-arabia/jobs/associate-product-manager/",
            "https://www.bayt.com/en/egypt/jobs/associate-product-manager/",
        ]

    def discover_jobs(self, search_params: Dict[str, Any]) -> List[str]:
        """
        Phase 1: Discover job URLs from search results.
        """
        job_urls = []

        for search_url in self.search_urls:
            try:
                html = self._fetch_page(search_url, use_cache=False)
                if not html:
                    continue

                soup = self._parse_html(html)

                # Find job cards - Bayt uses specific class names
                job_cards = soup.find_all('div', class_='job-card') or soup.find_all('a', href=lambda x: x and '/job/' in x)

                for card in job_cards[:20]:  # Limit to 20 per search
                    if card.name == 'a':
                        job_url = card.get('href', '')
                    else:
                        link = card.find('a', href=lambda x: x and '/job/' in x)
                        job_url = link.get('href', '') if link else ''

                    if job_url:
                        if not job_url.startswith('http'):
                            job_url = f"https://www.bayt.com{job_url}"
                        job_urls.append(job_url)

            except Exception as e:
                print(f"Bayt: Error discovering jobs from {search_url}: {e}")
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

            # Extract job details - Bayt structure
            title_elem = soup.find('h1', class_='job-title') or soup.find('h1')
            company_elem = soup.find('div', class_='company-name') or soup.find('a', class_='company-link')
            location_elem = soup.find('div', class_='location') or soup.find('span', class_='location-text')
            description_elem = soup.find('div', class_='job-description') or soup.find('div', class_='description')
            skills_elem = soup.find('div', class_='skills') or soup.find('div', class_='tags')

            if not title_elem:
                raise ParsingError("Bayt: Missing job title")

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
            region = "MENA"
            if location_elem:
                loc_text = location_elem.get_text().lower()
                if "uae" in loc_text or "dubai" in loc_text or "abu dhabi" in loc_text:
                    region = "MENA-UAE"
                elif "saudi" in loc_text or "riyadh" in loc_text:
                    region = "MENA-Saudi"
                elif "egypt" in loc_text or "cairo" in loc_text:
                    region = "MENA-Egypt"

            return {
                "job_id": str(uuid.uuid4()),
                "company": company,
                "role_title": title_elem.get_text(strip=True),
                "job_url": job_url,
                "source_platform": "Bayt",
                "date_scraped": datetime.utcnow().strftime("%Y-%m-%d"),
                "region": region,
                "work_mode": work_mode,
                "work_permit_required": True,  # MENA roles typically require work permit
                "required_skills": skills,
                "status": "SCRAPED"
            }

        except ParsingError:
            raise
        except Exception as e:
            raise ParsingError(f"Bayt: Error scraping job details: {e}")
