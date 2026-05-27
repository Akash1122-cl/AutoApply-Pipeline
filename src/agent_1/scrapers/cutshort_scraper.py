"""Cutshort scraper for APM-specific roles in India."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base_scraper import BaseScraper, PortalConfig, ParsingError


class CutshortScraper(BaseScraper):
    """Cutshort scraper for APM-specific roles (India-focused) using Playwright."""

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
        if not PLAYWRIGHT_AVAILABLE:
            print("Cutshort: Playwright not installed. Install with: pip install playwright && playwright install")
            return []

        job_urls = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page()

            for search_url in self.search_urls:
                try:
                    if not self._wait_for_rate_limit():
                        continue

                    page.goto(search_url, timeout=15000)
                    page.wait_for_timeout(3000)  # Wait for JS and jobs to render

                    # Find job cards - Cutshort uses specific class names or links containing '/job/'
                    job_links = page.query_selector_all('a.job-card, a[href*="/job/"]')

                    for link in job_links[:20]:  # Limit to 20 per search
                        href = link.get_attribute('href')
                        if href:
                            if not href.startswith('http'):
                                href = f"https://cutshort.io{href}"
                            job_urls.append(self.normalize_url(href))

                    self.metrics.requests_sent += 1
                    self.metrics.last_request_time = datetime.now().timestamp()
                    self._update_quota()

                except Exception as e:
                    print(f"Cutshort: Error discovering jobs from {search_url}: {e}")
                    self.metrics.failed_scrapes += 1
                    continue

            browser.close()

        return list(set(job_urls))

    def scrape_job_details(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Phase 2: Scrape full job details from job page using Playwright.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return None

        job_url = self.normalize_url(job_url)
        # Check cache first
        cache_key = self._get_cache_key(job_url)
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached.get('job_data')

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                page = browser.new_page()

                if not self._wait_for_rate_limit():
                    browser.close()
                    return None

                page.goto(job_url, timeout=15000)
                page.wait_for_timeout(3000)  # Wait for JS to render

                # Extract job details - Cutshort structure
                title_elem = page.query_selector('h1, .job-title')
                company_elem = page.query_selector('.company-name, .company-link')
                location_elem = page.query_selector('.location, .location-text')
                description_elem = page.query_selector('.job-description, .description')
                skills_elem = page.query_selector_all('.skills span, .tags span, .skills a, .tags a')

                if not title_elem:
                    browser.close()
                    raise ParsingError("Cutshort: Missing job title")

                title = title_elem.inner_text().strip()
                company = company_elem.inner_text().strip() if company_elem else "Unknown"

                # Extract skills
                skills = []
                if skills_elem:
                    skills = [s.inner_text().strip() for s in skills_elem if s.inner_text().strip()]
                elif description_elem:
                    desc_text = description_elem.inner_text().lower()
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
                    desc_text = description_elem.inner_text().lower()
                    if "remote" in desc_text:
                        work_mode = "remote"
                    elif "hybrid" in desc_text:
                        work_mode = "hybrid"

                # Determine region
                region = "India"
                if location_elem:
                    loc_text = location_elem.inner_text().lower()
                    if "bangalore" in loc_text or "bengaluru" in loc_text:
                        region = "India-Bangalore"
                    elif "mumbai" in loc_text:
                        region = "India-Mumbai"
                    elif "delhi" in loc_text or "ncr" in loc_text:
                        region = "India-Delhi"
                    elif "remote" in loc_text:
                        region = "India-Remote"

                browser.close()

                job_data = {
                    "job_id": str(uuid.uuid4()),
                    "company": company,
                    "role_title": title,
                    "job_url": job_url,
                    "source_platform": "Cutshort",
                    "date_scraped": datetime.utcnow().strftime("%Y-%m-%d"),
                    "region": region,
                    "work_mode": work_mode,
                    "work_permit_required": False,
                    "required_skills": skills,
                    "status": "SCRAPED"
                }

                # Cache the result
                self._save_to_cache(cache_key, {'job_data': job_data, 'cached_at': datetime.now().isoformat()})

                self.metrics.successful_scrapes += 1
                self.metrics.last_request_time = datetime.now().timestamp()
                self._update_quota()

                return job_data

        except ParsingError:
            raise
        except Exception as e:
            self.metrics.failed_scrapes += 1
            raise ParsingError(f"Cutshort: Error scraping job details: {e}")
