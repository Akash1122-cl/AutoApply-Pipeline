from abc import ABC, abstractmethod
from typing import Dict, Any, List
import uuid
import os
import requests
import feedparser
from datetime import datetime

try:
    from .scrapers.naukri_scraper import NaukriScraper
    NAUKRI_AVAILABLE = True
except ImportError:
    NAUKRI_AVAILABLE = False
    NaukriScraper = None

try:
    from .scrapers.cutshort_scraper import CutshortScraper
    CUTSHORT_AVAILABLE = True
except ImportError:
    CUTSHORT_AVAILABLE = False
    CutshortScraper = None
try:
    from .scrapers.otta_scraper import OttaScraper
    OTTA_AVAILABLE = True
except ImportError:
    OTTA_AVAILABLE = False
    OttaScraper = None
try:
    from .scrapers.bayt_scraper import BaytScraper
    BAYT_AVAILABLE = True
except ImportError:
    BAYT_AVAILABLE = False
    BaytScraper = None

class JobSourceAdapter(ABC):
    @abstractmethod
    def fetch_jobs(self) -> List[Dict[str, Any]]:
        """Fetch jobs from the source and return them in a normalized format."""
        pass

class MockAdapter(JobSourceAdapter):
    """Generates dummy job listings for testing the pipeline."""

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return [
            {
                "job_id": str(uuid.uuid4()),
                "company": "TechNova",
                "role_title": "Associate Product Manager",
                "job_url": "https://technova.example.com/jobs/apm",
                "source_platform": "MockPlatform",
                "date_scraped": today,
                "region": "India",
                "work_mode": "Remote",
                "work_permit_required": False,
                "required_skills": ["agile", "sql", "jira", "user research"],
                "status": "SCRAPED"
            },
            {
                "job_id": str(uuid.uuid4()),
                "company": "DataCorp",
                "role_title": "APM",
                "job_url": "https://datacorp.example.com/careers/123",
                "source_platform": "MockPlatform",
                "date_scraped": today,
                "region": "Berlin, Germany",
                "work_mode": "Hybrid",
                "work_permit_required": True,
                "required_skills": ["python", "data analysis", "sql", "a/b testing"],
                "status": "SCRAPED"
            },
            {
                "job_id": str(uuid.uuid4()),
                "company": "DataCorp",
                "role_title": "APM",
                "job_url": "https://datacorp.example.com/careers/123",
                "source_platform": "MockPlatform",
                "date_scraped": today,
                "region": "Berlin, Germany",
                "work_mode": "Hybrid",
                "work_permit_required": True,
                "required_skills": ["python", "data analysis", "sql", "a/b testing"],
                "status": "SCRAPED"
            },
            {
                "job_id": str(uuid.uuid4()),
                "company": "LowFit Inc",
                "role_title": "Product Owner",
                "job_url": "https://lowfit.example.com/job",
                "source_platform": "MockPlatform",
                "date_scraped": today,
                "region": "USA",
                "work_mode": "Onsite",
                "work_permit_required": True,
                "required_skills": ["scrum", "hardware design", "c++"],
                "status": "SCRAPED"
            }
        ]


class AdzunaAdapter(JobSourceAdapter):
    """Fetches jobs from Adzuna API (free tier available)."""

    def __init__(self):
        self.app_id = os.environ.get("ADZUNA_APP_ID", "")
        self.app_key = os.environ.get("ADZUNA_APP_KEY", "")
        self.base_url = "https://api.adzuna.com/v1/api/jobs"

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        if not self.app_id or not self.app_key:
            print("Warning: Adzuna API credentials not configured. Skipping Adzuna.")
            return []

        jobs = []
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Search for APM roles in target regions
        search_queries = [
            {"what": "Associate Product Manager", "where": "India"},
            {"what": "Associate Product Manager", "where": "UK"},
            {"what": "Associate Product Manager", "where": "Germany"},
            {"what": "Associate Product Manager", "where": "Poland"},
            {"what": "APM", "where": "India"},
        ]

        for query in search_queries:
            try:
                params = {
                    "app_id": self.app_id,
                    "app_key": self.app_key,
                    "what": query["what"],
                    "where": query["where"],
                    "content-type": "application/json",
                    "max_days_old": 7,
                    "sort_by": "date",
                    "results_per_page": 20
                }

                response = requests.get(f"{self.base_url}/gb/search/", params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                for job in data.get("results", []):
                    jobs.append({
                        "job_id": str(uuid.uuid4()),
                        "company": job.get("company", {}).get("display_name", "Unknown"),
                        "role_title": job.get("title", ""),
                        "job_url": job.get("redirect_url", ""),
                        "source_platform": "Adzuna",
                        "date_scraped": today,
                        "region": query["where"],
                        "work_mode": self._extract_work_mode(job.get("description", "")),
                        "work_permit_required": query["where"] in ["UK", "Germany", "Poland"],
                        "required_skills": self._extract_skills(job.get("description", "")),
                        "status": "SCRAPED"
                    })

            except Exception as e:
                print(f"Error fetching from Adzuna for {query}: {e}")
                continue

        return jobs

    def _extract_work_mode(self, description: str) -> str:
        desc_lower = description.lower()
        if "remote" in desc_lower:
            return "remote"
        elif "hybrid" in desc_lower:
            return "hybrid"
        return "onsite"

    def _extract_skills(self, description: str) -> List[str]:
        common_skills = [
            "sql", "python", "agile", "scrum", "product management",
            "data analysis", "user research", "a/b testing", "roadmapping",
            "stakeholder management", "jira", "figma", "analytics"
        ]
        desc_lower = description.lower()
        found_skills = [skill for skill in common_skills if skill in desc_lower]
        return found_skills if found_skills else ["product management"]


class SerpApiAdapter(JobSourceAdapter):
    """Fetches jobs from Google Jobs via SerpAPI or SearchApi.io."""

    def __init__(self):
        self.api_key = os.environ.get("SERPAPI_KEY", "")
        # SearchApi.io keys are 24 characters; SerpAPI keys are 64 characters
        if self.api_key and len(self.api_key.strip()) == 24:
            self.base_url = "https://www.searchapi.io/api/v1/search"
            self.provider_name = "SearchApi"
        else:
            self.base_url = "https://serpapi.com/search"
            self.provider_name = "SerpAPI"

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            print(f"Warning: {self.provider_name} key not configured. Skipping.")
            return []

        jobs = []
        today = datetime.utcnow().strftime("%Y-%m-%d")

        search_queries = [
            "Associate Product Manager jobs India",
            "Associate Product Manager jobs UK",
            "Associate Product Manager jobs Germany",
            "APM jobs remote",
        ]

        for query in search_queries:
            try:
                params = {
                    "engine": "google_jobs",
                    "q": query,
                    "api_key": self.api_key,
                    "num": 20
                }

                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                for job in data.get("jobs_results", data.get("jobs", [])):
                    jobs.append({
                        "job_id": str(uuid.uuid4()),
                        "company": job.get("company_name", "Unknown"),
                        "role_title": job.get("title", ""),
                        "job_url": job.get("share_link", job.get("apply_link", job.get("sharing_link", job.get("job_id", "")))),
                        "source_platform": "GoogleJobs",
                        "date_scraped": today,
                        "region": self._extract_region(query),
                        "work_mode": self._extract_work_mode_from_location(job.get("location", "")),
                        "work_permit_required": "India" not in query and "remote" not in query.lower(),
                        "required_skills": self._extract_skills_from_description(job.get("description", "")),
                        "status": "SCRAPED"
                    })

            except Exception as e:
                print(f"Error fetching from {self.provider_name} for {query}: {e}")
                continue

        return jobs

    def _extract_region(self, query: str) -> str:
        if "India" in query:
            return "India"
        elif "UK" in query:
            return "UK"
        elif "Germany" in query:
            return "Germany"
        return "Remote"

    def _extract_work_mode_from_location(self, location: str) -> str:
        loc_lower = location.lower()
        if "remote" in loc_lower:
            return "remote"
        elif "hybrid" in loc_lower:
            return "hybrid"
        return "onsite"

    def _extract_skills_from_description(self, description: str) -> List[str]:
        if not description:
            return ["product management"]

        common_skills = [
            "sql", "python", "agile", "scrum", "product management",
            "data analysis", "user research", "a/b testing", "roadmapping",
            "stakeholder management", "jira", "figma", "analytics"
        ]
        desc_lower = description.lower()
        found_skills = [skill for skill in common_skills if skill in desc_lower]
        return found_skills if found_skills else ["product management"]


class NaukriAdapter(JobSourceAdapter):
    """Fetches jobs from Naukri using the scraper with anti-ban measures."""

    def __init__(self):
        self.available = NAUKRI_AVAILABLE
        if self.available:
            enable_scraping = os.getenv("ENABLE_NAUKRI_SCRAPING", "true").lower() in ["true", "1", "yes"]
            self.scraper = NaukriScraper()
            self.scraper.config.enable_scraping = enable_scraping

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        if not self.available:
            print("Naukri: Scraper not available (missing dependencies).")
            return []
        if not self.scraper.config.enable_scraping:
            print("Naukri scraping disabled via ENABLE_NAUKRI_SCRAPING")
            return []

        search_params = {}
        return self.scraper.fetch_jobs(search_params)


class CutshortAdapter(JobSourceAdapter):
    """Fetches jobs from Cutshort using the scraper with anti-ban measures."""

    def __init__(self):
        self.available = CUTSHORT_AVAILABLE
        if self.available:
            enable_scraping = os.getenv("ENABLE_CUTSHORT_SCRAPING", "true").lower() in ["true", "1", "yes"]
            self.scraper = CutshortScraper()
            self.scraper.config.enable_scraping = enable_scraping

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        if not self.available:
            print("Cutshort: Scraper not available (missing dependencies).")
            return []
        if not self.scraper.config.enable_scraping:
            print("Cutshort scraping disabled via ENABLE_CUTSHORT_SCRAPING")
            return []

        search_params = {}
        return self.scraper.fetch_jobs(search_params)


class OttaAdapter(JobSourceAdapter):
    """Fetches jobs from Otta using the scraper with Playwright for JS rendering."""

    def __init__(self):
        enable_scraping = os.getenv("ENABLE_OTTA_SCRAPING", "true").lower() in ["true", "1", "yes"]
        self.scraper = OttaScraper()
        self.scraper.config.enable_scraping = enable_scraping

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        if not self.scraper.config.enable_scraping:
            print("Otta scraping disabled via ENABLE_OTTA_SCRAPING")
            return []

        search_params = {}
        return self.scraper.fetch_jobs(search_params)


class BaytAdapter(JobSourceAdapter):
    """Fetches jobs from Bayt using the scraper with anti-ban measures."""

    def __init__(self):
        enable_scraping = os.getenv("ENABLE_BAYT_SCRAPING", "false").lower() in ["true", "1", "yes"]
        self.scraper = BaytScraper()
        self.scraper.config.enable_scraping = enable_scraping

    def fetch_jobs(self) -> List[Dict[str, Any]]:
        if not self.scraper.config.enable_scraping:
            print("Bayt scraping disabled via ENABLE_BAYT_SCRAPING")
            return []

        search_params = {}
        return self.scraper.fetch_jobs(search_params)
