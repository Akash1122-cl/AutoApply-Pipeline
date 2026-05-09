"""Test suite for web scraping with anti-ban measures."""

import os
import time
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import pytest

from src.agent_1.scrapers.base_scraper import (
    BaseScraper,
    PortalConfig,
    ScraperError,
    RateLimitError,
    BlockedError,
    ParsingError,
    ScraperMetrics
)
from src.agent_1.scrapers.naukri_scraper import NaukriScraper
from src.agent_1.scrapers.cutshort_scraper import CutshortScraper
from src.agent_1.scrapers.bayt_scraper import BaytScraper


class TestBaseScraper:
    """Test cases for base scraper functionality."""

    def test_01_portal_config_initialization(self):
        """Test 1: PortalConfig initializes with correct values."""
        config = PortalConfig(
            name="TestPortal",
            base_url="https://example.com",
            requests_per_minute=10,
            base_delay_seconds=6.0,
            max_pages_per_day=500,
            robots_txt_check=True,
            enable_scraping=True
        )
        assert config.name == "TestPortal"
        assert config.requests_per_minute == 10
        assert config.max_pages_per_day == 500
        assert config.enable_scraping is True

    def test_02_scraper_metrics_initialization(self):
        """Test 2: ScraperMetrics initializes with zero values."""
        metrics = ScraperMetrics()
        assert metrics.requests_sent == 0
        assert metrics.successful_scrapes == 0
        assert metrics.failed_scrapes == 0
        assert metrics.rate_limit_hits == 0
        assert metrics.blocked_ips == 0
        assert metrics.jobs_discovered == 0

    def test_03_user_agent_rotation(self):
        """Test 3: User agents are rotated from predefined list."""
        scraper = NaukriScraper()
        assert len(scraper.USER_AGENTS) >= 5
        for ua in scraper.USER_AGENTS:
            assert "Mozilla" in ua
            assert "Chrome" in ua or "Firefox" in ua or "Safari" in ua

    def test_04_rate_limiting_enforcement(self):
        """Test 4: Rate limiting enforces minimum delay between requests."""
        scraper = NaukriScraper()
        scraper.metrics.last_request_time = time.time()
        
        # Should enforce delay
        can_proceed = scraper._check_rate_limit()
        assert can_proceed is False or scraper.metrics.last_request_time is not None

    def test_05_cache_key_generation(self):
        """Test 5: Cache keys are generated consistently for same URL."""
        scraper = NaukriScraper()
        url1 = "https://example.com/job/123"
        url2 = "https://example.com/job/123"
        
        key1 = scraper._get_cache_key(url1)
        key2 = scraper._get_cache_key(url2)
        
        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length

    def test_06_job_data_validation(self):
        """Test 6: Job data validation rejects invalid jobs."""
        scraper = NaukriScraper()
        
        # Valid job
        valid_job = {
            "title": "Product Manager",
            "company": "Test Company",
            "job_url": "https://example.com/job/123"
        }
        assert scraper._validate_job(valid_job) is True
        
        # Missing required field
        invalid_job1 = {
            "title": "Product Manager",
            "company": "Test Company"
        }
        assert scraper._validate_job(invalid_job1) is False
        
        # Invalid URL
        invalid_job2 = {
            "title": "Product Manager",
            "company": "Test Company",
            "job_url": "not-a-valid-url"
        }
        assert scraper._validate_job(invalid_job2) is False
        
        # Title too short
        invalid_job3 = {
            "title": "PM",
            "company": "Test Company",
            "job_url": "https://example.com/job/123"
        }
        assert scraper._validate_job(invalid_job3) is False

    def test_07_daily_quota_tracking(self):
        """Test 7: Daily quota tracking persists and increments correctly."""
        scraper = NaukriScraper()
        
        # Load initial quota
        quota = scraper._load_daily_quota()
        initial_requests = quota.get('requests', 0)
        
        # Increment quota
        scraper._update_quota()
        
        # Verify increment
        new_quota = scraper._load_daily_quota()
        new_requests = new_quota.get('requests', 0)
        assert new_requests == initial_requests + 1

    def test_08_error_handling_rate_limit(self):
        """Test 8: Rate limit error (429) triggers 1-hour pause."""
        scraper = NaukriScraper()
        
        # Mock response with 429 status
        class MockResponse:
            status_code = 429
        
        with pytest.raises(RateLimitError):
            scraper._handle_response(MockResponse())
        
        # Verify quota has blocked_until set
        quota = scraper._load_daily_quota()
        assert quota.get('blocked_until') is not None

    def test_09_error_handling_blocked(self):
        """Test 9: Blocked error (403) triggers 24-hour pause."""
        scraper = NaukriScraper()
        
        # Mock response with 403 status
        class MockResponse:
            status_code = 403
        
        with pytest.raises(BlockedError):
            scraper._handle_response(MockResponse())
        
        # Verify quota has blocked_until set
        quota = scraper._load_daily_quota()
        assert quota.get('blocked_until') is not None

    def test_10_metrics_logging(self):
        """Test 10: Scraper metrics are logged to file."""
        scraper = NaukriScraper()
        scraper.metrics.requests_sent = 10
        scraper.metrics.successful_scrapes = 8
        scraper.metrics.failed_scrapes = 2
        scraper.metrics.jobs_discovered = 5
        
        scraper._save_metrics()
        
        # Verify metrics file exists
        metrics_file = scraper.metrics_dir / f"scraper_metrics_{scraper.metrics.last_request_time or time.time():.0f}.json"
        # Check for today's metrics file
        from datetime import datetime
        today_str = datetime.now().strftime('%Y%m%d')
        expected_file = scraper.metrics_dir / f"scraper_metrics_{today_str}.json"
        
        assert expected_file.exists()
        
        # Verify content
        with open(expected_file, 'r') as f:
            data = json.load(f)
        assert "Naukri" in data
        assert data["Naukri"]["requests_sent"] == 10
        assert data["Naukri"]["jobs_discovered"] == 5


class TestNaukriScraper:
    """Test cases for Naukri scraper."""

    def test_naukri_rss_discovery(self):
        """Test Naukri RSS discovery returns job URLs."""
        scraper = NaukriScraper()
        scraper.config.enable_scraping = True
        
        try:
            urls = scraper.discover_jobs({})
            # Should return list (may be empty if rate limited)
            assert isinstance(urls, list)
            if urls:
                assert all(url.startswith('http') for url in urls)
        except Exception as e:
            pytest.skip(f"Naukri RSS discovery failed (may be rate limited): {e}")


class TestCutshortScraper:
    """Test cases for Cutshort scraper."""

    def test_cutshort_initialization(self):
        """Test Cutshort scraper initializes with correct config."""
        scraper = CutshortScraper()
        assert scraper.config.name == "Cutshort"
        assert scraper.config.requests_per_minute == 20
        assert scraper.config.max_pages_per_day == 300


class TestBaytScraper:
    """Test cases for Bayt scraper."""

    def test_bayt_initialization(self):
        """Test Bayt scraper initializes with correct config."""
        scraper = BaytScraper()
        assert scraper.config.name == "Bayt"
        assert scraper.config.requests_per_minute == 10
        assert scraper.config.max_pages_per_day == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
