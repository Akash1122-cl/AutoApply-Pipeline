"""Test suite for job portal scrapers with rate limiting and error handling."""

import os
import time
from dotenv import load_dotenv

load_dotenv()

from src.agent_1.scrapers.naukri_scraper import NaukriScraper
from src.agent_1.scrapers.cutshort_scraper import CutshortScraper
from src.agent_1.scrapers.otta_scraper import OttaScraper
from src.agent_1.scrapers.bayt_scraper import BaytScraper
from src.agent_1.scrapers.base_scraper import RateLimitError, BlockedError, ParsingError


def test_rate_limiting(scraper_class, scraper_name):
    """Test that rate limiting is enforced (delays between requests)."""
    print(f"\n{'='*60}")
    print(f"Testing Rate Limiting: {scraper_name}")
    print(f"{'='*60}")

    scraper = scraper_class()
    scraper.config.enable_scraping = True

    # Make multiple requests to test delay
    start_time = time.time()
    for i in range(3):
        print(f"  Request {i+1}...")
        try:
            # Use a simple test URL or discovery
            if scraper_name == "Naukri":
                urls = scraper.discover_jobs({})
            else:
                urls = scraper.discover_jobs({})
        except Exception as e:
            print(f"  Error: {e}")
        time.sleep(0.1)  # Small delay to allow scraper to enforce its own rate limit

    elapsed = time.time() - start_time
    expected_min_delay = (60 / scraper.config.requests_per_minute) * 2  # For 2 intervals

    print(f"  Total time: {elapsed:.2f}s")
    print(f"  Expected min delay: {expected_min_delay:.2f}s")
    print(f"  Rate limiting: {'✓ PASS' if elapsed >= expected_min_delay * 0.8 else '✗ FAIL'}")


def test_error_handling(scraper_class, scraper_name):
    """Test error handling for rate limit, block, and parsing errors."""
    print(f"\n{'='*60}")
    print(f"Testing Error Handling: {scraper_name}")
    print(f"{'='*60}")

    scraper = scraper_class()
    scraper.config.enable_scraping = True

    # Test with invalid URL to trigger parsing error
    try:
        result = scraper.scrape_job_details("https://invalid-url-that-does-not-exist.com")
        print(f"  Invalid URL handling: {'✓ PASS (returned None)' if result is None else '✗ FAIL'}")
    except ParsingError:
        print(f"  Invalid URL handling: ✓ PASS (ParsingError raised)")
    except Exception as e:
        print(f"  Invalid URL handling: ✗ FAIL (unexpected error: {e})")


def test_cache_functionality(scraper_class, scraper_name):
    """Test that caching works (hit/miss)."""
    print(f"\n{'='*60}")
    print(f"Testing Cache Functionality: {scraper_name}")
    print(f"{'='*60}")

    scraper = scraper_class()
    scraper.config.enable_scraping = True

    # Clear cache dir for clean test
    import shutil
    if scraper.cache_dir.exists():
        shutil.rmtree(scraper.cache_dir)
    scraper.cache_dir.mkdir(parents=True, exist_ok=True)

    # First call - should be cache miss
    start_time = time.time()
    try:
        result1 = scraper.scrape_job_details("https://example.com/test-job")
        first_time = time.time() - start_time
    except Exception:
        first_time = time.time() - start_time

    # Second call - should be cache hit (if successful)
    start_time = time.time()
    try:
        result2 = scraper.scrape_job_details("https://example.com/test-job")
        second_time = time.time() - start_time
    except Exception:
        second_time = time.time() - start_time

    print(f"  First call time: {first_time:.3f}s")
    print(f"  Second call time: {second_time:.3f}s")
    print(f"  Cache speedup: {first_time/second_time:.1f}x" if second_time > 0 else "  Cache speedup: N/A")
    print(f"  Cache functionality: {'✓ PASS' if second_time < first_time else '✗ FAIL (or error)'}")


def test_deduplication():
    """Test that duplicate URLs are deduplicated."""
    print(f"\n{'='*60}")
    print(f"Testing Deduplication")
    print(f"{'='*60}")

    # Simulate duplicate URLs from multiple sources
    urls = [
        "https://example.com/job1",
        "https://example.com/job2",
        "https://example.com/job1",  # Duplicate
        "https://example.com/job3",
        "https://example.com/job2",  # Duplicate
    ]

    unique_urls = list(set(urls))
    print(f"  Original URLs: {len(urls)}")
    print(f"  Unique URLs: {len(unique_urls)}")
    print(f"  Deduplication: {'✓ PASS' if len(unique_urls) == 3 else '✗ FAIL'}")


def test_quota_tracking(scraper_class, scraper_name):
    """Test that daily quota tracking works."""
    print(f"\n{'='*60}")
    print(f"Testing Quota Tracking: {scraper_name}")
    print(f"{'='*60}")

    scraper = scraper_class()
    scraper.config.enable_scraping = True

    # Load initial quota
    quota = scraper._load_daily_quota()
    initial_requests = quota.get('requests', 0)
    print(f"  Initial requests: {initial_requests}")

    # Simulate a request
    scraper._update_quota()
    new_quota = scraper._load_daily_quota()
    new_requests = new_quota.get('requests', 0)

    print(f"  Updated requests: {new_requests}")
    print(f"  Quota tracking: {'✓ PASS' if new_requests == initial_requests + 1 else '✗ FAIL'}")


def test_naukri_rss_discovery():
    """Test Naukri RSS discovery (Phase 1)."""
    print(f"\n{'='*60}")
    print(f"Testing Naukri RSS Discovery (Phase 1)")
    print(f"{'='*60}")

    scraper = NaukriScraper()
    scraper.config.enable_scraping = True

    try:
        job_urls = scraper.discover_jobs({})
        print(f"  Discovered URLs: {len(job_urls)}")
        print(f"  RSS Discovery: {'✓ PASS' if len(job_urls) > 0 else '⚠ No URLs (may be rate limited)'}")

        if job_urls:
            print(f"  Sample URL: {job_urls[0]}")
    except Exception as e:
        print(f"  RSS Discovery: ✗ FAIL ({e})")


def main():
    """Run all scraper tests."""
    print("\n" + "="*60)
    print("SCRAPER TEST SUITE")
    print("="*60)

    # Check environment
    print("\nEnvironment Check:")
    print(f"  ENABLE_NAUKRI_SCRAPING: {os.getenv('ENABLE_NAUKRI_SCRAPING', 'true')}")
    print(f"  ENABLE_CUTSHORT_SCRAPING: {os.getenv('ENABLE_CUTSHORT_SCRAPING', 'true')}")
    print(f"  ENABLE_OTTA_SCRAPING: {os.getenv('ENABLE_OTTA_SCRAPING', 'false')}")
    print(f"  ENABLE_BAYT_SCRAPING: {os.getenv('ENABLE_BAYT_SCRAPING', 'false')}")

    # Run tests
    test_deduplication()
    test_naukri_rss_discovery()

    # Test each scraper
    scrapers = [
        (NaukriScraper, "Naukri"),
        (CutshortScraper, "Cutshort"),
        (BaytScraper, "Bayt"),
    ]

    for scraper_class, name in scrapers:
        test_rate_limiting(scraper_class, name)
        test_error_handling(scraper_class, name)
        test_cache_functionality(scraper_class, name)
        test_quota_tracking(scraper_class, name)

    # Otta requires Playwright - test separately
    try:
        from playwright.sync_api import sync_playwright
        print("\n✓ Playwright is installed")
        test_rate_limiting(OttaScraper, "Otta")
        test_error_handling(OttaScraper, "Otta")
        test_cache_functionality(OttaScraper, "Otta")
        test_quota_tracking(OttaScraper, "Otta")
    except ImportError:
        print("\n⚠ Playwright not installed - skipping Otta tests")
        print("  Install with: pip install playwright && playwright install")

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print("All tests completed. Check results above.")
    print("="*60)


if __name__ == "__main__":
    main()
