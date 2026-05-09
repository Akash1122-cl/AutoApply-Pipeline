from typing import Dict, Any, List, Set, Tuple
import os

from src.agent_1.adapters import JobSourceAdapter, MockAdapter, AdzunaAdapter, SerpApiAdapter, NaukriAdapter, OttaAdapter, CutshortAdapter, BaytAdapter
from src.agent_1.classifier import classify_region_and_work_mode
from src.agent_1.dedup import deduplicate_jobs
from src.agent_1.scoring import score_jobs


class Agent1Pipeline:
    """Orchestrates the discovery and qualification phase."""

    def __init__(self, adapters: List[JobSourceAdapter] = None):
        # Check if mock jobs are explicitly configured (default to true for safety)
        use_mock = os.getenv("USE_MOCK_JOBS", "true").lower() in ["true", "1", "yes"]
        if adapters:
            self.adapters = adapters
        elif use_mock:
            self.adapters = [MockAdapter()]
        else:
            # Load real job scrapers for live data
            self.adapters = self._load_real_adapters()

    def _load_real_adapters(self) -> List[JobSourceAdapter]:
        """Load all available real job portal adapters."""
        adapters = []

        # Add Naukri scraper (RSS discovery + detail scraping)
        print("Adding Naukri adapter (RSS discovery + scraping)")
        adapters.append(NaukriAdapter())

        # Add Cutshort scraper (APM-specific for India)
        print("Adding Cutshort adapter (APM-specific for India)")
        adapters.append(CutshortAdapter())

        # Add Otta adapter (Europe - requires Playwright for JS rendering)
        print("Adding Otta adapter (Europe - Playwright for JS)")
        adapters.append(OttaAdapter())

        # Add Bayt adapter (MENA region - disabled by default)
        print("Adding Bayt adapter (MENA region)")
        adapters.append(BaytAdapter())

        # Add Adzuna adapter (requires API key)
        adzuna = AdzunaAdapter()
        if adzuna.app_id and adzuna.app_key:
            print("Adding Adzuna adapter (credentials found)")
            adapters.append(adzuna)
        else:
            print("Adzuna credentials not found, skipping Adzuna adapter")

        # Add SerpAPI adapter (requires API key)
        serpapi = SerpApiAdapter()
        if serpapi.api_key:
            print("Adding SerpAPI adapter (credentials found)")
            adapters.append(serpapi)
        else:
            print("SerpAPI key not found, skipping SerpAPI adapter")

        # If no real adapters are configured, fall back to mock
        if not adapters:
            print("Warning: No real job portal adapters configured. Falling back to MockAdapter.")
            adapters = [MockAdapter()]

        return adapters

    def run(self, existing_keys: Set[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
        """
        Executes the Agent 1 pipeline:
        Fetch -> Dedup -> Classify -> Score
        Returns only the newly discovered, scored jobs.
        """
        all_new_jobs = []
        for adapter in self.adapters:
            print(f"Fetching jobs from {adapter.__class__.__name__}...")
            jobs = adapter.fetch_jobs()
            print(f"Found {len(jobs)} jobs from {adapter.__class__.__name__}")
            all_new_jobs.extend(jobs)

        # 1. Deduplicate against existing tracker keys
        deduped_jobs = deduplicate_jobs(all_new_jobs, existing_keys)

        # 2. Classify region and work mode
        classified_jobs = [classify_region_and_work_mode(job) for job in deduped_jobs]

        # 3. Score jobs
        # Note: the status will be set to SCRAPED initially by adapters.
        # Orchestrator handles the transition to SCORED later.
        # But we can calculate the score here.
        scored_jobs = score_jobs(classified_jobs)

        return scored_jobs
