"""Otta scraper using Playwright for JavaScript rendering."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base_scraper import BaseScraper, PortalConfig, ParsingError


class OttaScraper(BaseScraper):
    """Otta scraper using Playwright for JavaScript rendering (key for Europe)."""

    def __init__(self):
        config = PortalConfig(
            name="Otta",
            base_url="https://otta.com",
            requests_per_minute=15,
            base_delay_seconds=4.0,
            max_pages_per_day=200,
            robots_txt_check=True,
            enable_scraping=True
        )
        super().__init__(config, cache_hours=24)

        self.search_urls = [
            "https://otta.com/jobs?q=product+manager&l=Poland",
            "https://otta.com/jobs?q=product+manager&l=Norway",
            "https://otta.com/jobs?q=product+manager&l=Germany",
            "https://otta.com/jobs?q=product+manager&l=United+Kingdom",
        ]

    def discover_jobs(self, search_params: Dict[str, Any]) -> List[str]:
        """
        Phase 1: Discover job URLs from search results using Playwright.
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("Otta: Playwright not installed. Install with: pip install playwright && playwright install")
            return []

        job_urls = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for search_url in self.search_urls:
                try:
                    # Rate limiting
                    if not self._wait_for_rate_limit():
                        continue

                    page.goto(search_url, timeout=15000)
                    page.wait_for_timeout(2000)  # Wait for JS to render

                    # Find job cards
                    job_links = page.query_selector_all('a[href*="/jobs/"]')

                    for link in job_links[:20]:  # Limit to 20 per search
                        href = link.get_attribute('href')
                        if href and not href.startswith('http'):
                            href = f"https://otta.com{href}"
                        if href:
                            job_urls.append(href)

                    self.metrics.requests_sent += 1
                    self.metrics.last_request_time = datetime.now().timestamp()
                    self._update_quota()

                except Exception as e:
                    print(f"Otta: Error discovering jobs from {search_url}: {e}")
                    self.metrics.failed_scrapes += 1
                    continue

            browser.close()

        return list(set(job_urls))

    def scrape_job_details(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Phase 2: Scrape full job details using Playwright.
        """
        if not PLAYWRIGHT_AVAILABLE:
            return None

        # Check cache first
        cache_key = self._get_cache_key(job_url)
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached.get('job_data')

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Rate limiting
                if not self._wait_for_rate_limit():
                    browser.close()
                    return None

                page.goto(job_url, timeout=15000)
                page.wait_for_timeout(2000)  # Wait for JS to render

                # Extract job details
                title_elem = page.query_selector('h1')
                company_elem = page.query_selector('[data-test="company-name"]')
                location_elem = page.query_selector('[data-test="location"]')
                description_elem = page.query_selector('[data-test="job-description"]')

                if not title_elem:
                    browser.close()
                    raise ParsingError("Otta: Missing job title")

                title = title_elem.inner_text().strip()
                company = company_elem.inner_text().strip() if company_elem else "Unknown"

                # Extract skills
                skills = ["product management"]  # Default
                if description_elem:
                    desc_text = description_elem.inner_text().lower()
                    common_skills = [
                        "sql", "python", "agile", "scrum", "product management",
                        "data analysis", "user research", "a/b testing", "roadmapping",
                        "stakeholder management", "jira", "figma", "analytics"
                    ]
                    skills = [skill for skill in common_skills if skill in desc_text]

                # Determine work mode
                work_mode = "remote"  # Otta has many remote roles
                if description_elem:
                    desc_text = description_elem.inner_text().lower()
                    if "hybrid" in desc_text:
                        work_mode = "hybrid"
                    elif "onsite" in desc_text or "office" in desc_text:
                        work_mode = "onsite"

                # Determine region
                region = "Europe"
                if location_elem:
                    loc_text = location_elem.inner_text().lower()
                    if "poland" in loc_text:
                        region = "Europe-Poland"
                    elif "norway" in loc_text:
                        region = "Europe-Norway"
                    elif "germany" in loc_text:
                        region = "Europe-Germany"
                    elif "united kingdom" in loc_text or "uk" in loc_text:
                        region = "Europe-UK"

                browser.close()

                job_data = {
                    "job_id": str(uuid.uuid4()),
                    "company": company,
                    "role_title": title,
                    "job_url": job_url,
                    "source_platform": "Otta",
                    "date_scraped": datetime.utcnow().strftime("%Y-%m-%d"),
                    "region": region,
                    "work_mode": work_mode,
                    "work_permit_required": True,  # EU roles typically require work permit
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
            raise ParsingError(f"Otta: Error scraping job details: {e}")
