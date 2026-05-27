"""Naukri scraper with RSS discovery and detail scraping."""

import feedparser
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from .base_scraper import BaseScraper, PortalConfig, ParsingError


class NaukriScraper(BaseScraper):
    """Naukri scraper using RSS feeds for discovery and scraping for details."""

    def __init__(self):
        config = PortalConfig(
            name="Naukri",
            base_url="https://www.naukri.com",
            requests_per_minute=10,
            base_delay_seconds=6.0,
            max_pages_per_day=500,
            robots_txt_check=True,
            enable_scraping=True
        )
        super().__init__(config, cache_hours=24)

        # RSS feeds for different locations (Phase 1: Discovery)
        self.rss_feeds = [
            "https://www.naukri.com/jobapi/rssSearch?k=Associate%20Product%20Manager&l=bangalore",
            "https://www.naukri.com/jobapi/rssSearch?k=Associate%20Product%20Manager&l=mumbai",
            "https://www.naukri.com/jobapi/rssSearch?k=Associate%20Product%20Manager&l=delhi",
            "https://www.naukri.com/jobapi/rssSearch?k=APM&l=bangalore",
        ]

    def discover_jobs(self, search_params: Dict[str, Any] = None) -> List[str]:
        """
        Phase 1: Discover job URLs from RSS feeds or a direct Search URL.
        """
        job_urls = []
        
        # Priority 1: Direct Search URL from search_params
        direct_url = (search_params or {}).get("direct_url")
        if direct_url:
            print(f"Scraping direct URL: {direct_url}")
            # We will use the browser/requests logic for this
            # For now, let's assume we can parse links from it
            # (I will implement the detail extractor in the next step)

        # Priority 2: RSS Feeds
        for feed_url in self.rss_feeds:
            try:
                # RSS feeds don't need rate limiting as much
                feed = feedparser.parse(feed_url)

                for entry in feed.entries[:20]:  # Limit to 20 per feed
                    if hasattr(entry, 'link'):
                        job_urls.append(self.normalize_url(entry.link))

            except Exception as e:
                print(f"Naukri: Error fetching RSS feed {feed_url}: {e}")
                continue

        # Deduplicate URLs
        return list(set(job_urls))

    def scrape_job_details(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Phase 2: Scrape full job details from job page.
        Only called for jobs passing initial filters.
        """
        try:
            job_url = self.normalize_url(job_url)
            html = self._fetch_page(job_url, use_cache=True)
            if not html:
                return None

            soup = self._parse_html(html)

            # Extract job details
            title_elem = soup.find('h1', class_='jd-header-title')
            company_elem = soup.find('a', class_='jd-header-comp-name')
            location_elem = soup.find('span', class_='loc')
            description_elem = soup.find('div', class_='dang-inner-html')
            skills_elem = soup.find('div', class_='key-skill')

            if not title_elem or not company_elem:
                raise ParsingError("Naukri: Missing required fields")

            # Extract skills from description or skills section
            skills = []
            if skills_elem:
                skills = [s.strip() for s in skills_elem.get_text().split(',') if s.strip()]
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

            return {
                "job_id": str(uuid.uuid4()),
                "company": company_elem.get_text(strip=True),
                "role_title": title_elem.get_text(strip=True),
                "job_url": job_url,
                "source_platform": "Naukri",
                "date_scraped": datetime.utcnow().strftime("%Y-%m-%d"),
                "region": region,
                "work_mode": work_mode,
                "work_permit_required": False,
                "required_skills": skills,
                "job_description": description_elem.get_text(strip=True) if description_elem else "",
                "status": "SCRAPED"
            }

        except ParsingError:
            raise
        except Exception as e:
            raise ParsingError(f"Naukri: Error scraping job details: {e}")
