"""Base scraper with anti-ban measures, rate limiting, caching, and error handling."""

import os
import json
import time
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import hashlib

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from bs4 import BeautifulSoup


class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass


class RateLimitError(ScraperError):
    """Raised when rate limit is hit (HTTP 429)."""
    pass


class BlockedError(ScraperError):
    """Raised when IP is blocked (HTTP 403, 406, or CAPTCHA)."""
    pass


class ParsingError(ScraperError):
    """Raised when HTML parsing fails."""
    pass


@dataclass
class ScraperMetrics:
    """Track scraper performance metrics."""
    requests_sent: int = 0
    successful_scrapes: int = 0
    failed_scrapes: int = 0
    rate_limit_hits: int = 0
    blocked_ips: int = 0
    parsing_errors: int = 0
    jobs_discovered: int = 0
    cache_hits: int = 0
    last_request_time: Optional[float] = None
    blocked_until: Optional[float] = None


@dataclass
class PortalConfig:
    """Configuration for a job portal."""
    name: str
    base_url: str
    requests_per_minute: int
    base_delay_seconds: float
    max_pages_per_day: int
    robots_txt_check: bool = True
    enable_scraping: bool = True


class BaseScraper(ABC):
    """Abstract base scraper with anti-ban measures and rate limiting."""

    # Realistic user agents from modern browsers
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ]

    def __init__(self, config: PortalConfig, cache_hours: int = 24):
        self.config = config
        self.cache_hours = cache_hours
        self.metrics = ScraperMetrics()
        self.session = self._create_session()
        self.cache_dir = Path("logs/scraper_cache")
        self.metrics_dir = Path("logs")
        self._init_directories()
        self._load_daily_quota()

    def _create_session(self) -> requests.Session:
        """Create a persistent session with proper headers."""
        session = requests.Session()
        session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.google.com/',
        })
        return session

    def _init_directories(self):
        """Initialize cache and metrics directories."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / f"{cache_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache is still valid."""
        if not cache_path.exists():
            return False
        cache_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - cache_time < timedelta(hours=self.cache_hours)

    def _get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache if valid."""
        cache_path = self._get_cache_path(cache_key)
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.metrics.cache_hits += 1
                return data
            except Exception:
                return None
        return None

    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]):
        """Save data to cache."""
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass  # Cache save failure is not critical

    def _load_daily_quota(self) -> Dict[str, Any]:
        """Load daily quota from persistent storage."""
        quota_file = self.metrics_dir / f"{self.config.name}_quota.json"
        if quota_file.exists():
            try:
                with open(quota_file, 'r', encoding='utf-8') as f:
                    quota = json.load(f)
                # Reset if new day
                if quota.get('date') != datetime.now().strftime('%Y-%m-%d'):
                    return {'date': datetime.now().strftime('%Y-%m-%d'), 'requests': 0, 'blocked_until': None}
                return quota
            except Exception:
                pass
        return {'date': datetime.now().strftime('%Y-%m-%d'), 'requests': 0, 'blocked_until': None}

    def _save_daily_quota(self, quota: Dict[str, Any]):
        """Save daily quota to persistent storage."""
        quota_file = self.metrics_dir / f"{self.config.name}_quota.json"
        try:
            with open(quota_file, 'w', encoding='utf-8') as f:
                json.dump(quota, f)
        except Exception:
            pass

    def _check_rate_limit(self) -> bool:
        """Check if we can make a request (rate limiting and quota)."""
        quota = self._load_daily_quota()

        # Check if blocked
        if quota.get('blocked_until'):
            blocked_until = datetime.fromisoformat(quota['blocked_until'])
            if datetime.now() < blocked_until:
                return False
            else:
                # Unblock
                quota['blocked_until'] = None
                self._save_daily_quota(quota)

        # Check daily quota
        if quota['requests'] >= self.config.max_pages_per_day:
            return False

        # Check rate limiting (requests per minute)
        if self.metrics.last_request_time:
            time_since_last = time.time() - self.metrics.last_request_time
            min_interval = 60 / self.config.requests_per_minute
            if time_since_last < min_interval:
                return False

        return True

    def _wait_for_rate_limit(self):
        """Wait for rate limit before making request."""
        quota = self._load_daily_quota()

        # Check if blocked
        if quota.get('blocked_until'):
            blocked_until = datetime.fromisoformat(quota['blocked_until'])
            wait_time = (blocked_until - datetime.now()).total_seconds()
            if wait_time > 0:
                print(f"{self.config.name}: Blocked until {blocked_until}. Waiting {wait_time/60:.1f} minutes.")
                time.sleep(min(wait_time, 3600))  # Max wait 1 hour
                return wait_time <= 3600  # Return True if we've waited through the block

        # Calculate delay with jitter (±30%)
        base_delay = 60 / self.config.requests_per_minute
        jitter = base_delay * 0.3
        delay = base_delay + random.uniform(-jitter, jitter)
        delay = max(delay, self.config.base_delay_seconds)

        # Respect last request time
        if self.metrics.last_request_time:
            time_since_last = time.time() - self.metrics.last_request_time
            if time_since_last < delay:
                time.sleep(delay - time_since_last)

        return True

    def _update_quota(self):
        """Update daily quota after successful request."""
        quota = self._load_daily_quota()
        quota['requests'] += 1
        self._save_daily_quota(quota)

    def _handle_response(self, response: requests.Response):
        """Handle HTTP response and raise appropriate errors."""
        self.metrics.requests_sent += 1

        if response.status_code == 429:
            self.metrics.rate_limit_hits += 1
            # Block for 1 hour
            quota = self._load_daily_quota()
            quota['blocked_until'] = (datetime.now() + timedelta(hours=1)).isoformat()
            self._save_daily_quota(quota)
            raise RateLimitError(f"{self.config.name}: Rate limit hit (429)")

        elif response.status_code in [403, 406]:
            self.metrics.blocked_ips += 1
            # Block for 24 hours
            quota = self._load_daily_quota()
            quota['blocked_until'] = (datetime.now() + timedelta(days=1)).isoformat()
            self._save_daily_quota(quota)
            raise BlockedError(f"{self.config.name}: Blocked ({response.status_code})")

        elif response.status_code >= 500:
            self.metrics.failed_scrapes += 1
            raise ScraperError(f"{self.config.name}: Server error {response.status_code}")

        elif response.status_code != 200:
            self.metrics.failed_scrapes += 1
            raise ScraperError(f"{self.config.name}: Unexpected status {response.status_code}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ScraperError)),
        reraise=True
    )
    def _fetch_page(self, url: str, use_cache: bool = True) -> Optional[str]:
        """Fetch a page with caching and rate limiting."""
        if not self.config.enable_scraping:
            return None

        # Check cache
        cache_key = self._get_cache_key(url)
        if use_cache:
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached.get('content')

        # Rate limiting
        if not self._wait_for_rate_limit():
            return None

        # Update user agent randomly
        self.session.headers['User-Agent'] = random.choice(self.USER_AGENTS)

        try:
            response = self.session.get(url, timeout=15)
            self._handle_response(response)
            self.metrics.successful_scrapes += 1
            self.metrics.last_request_time = time.time()
            self._update_quota()

            content = response.text

            # Cache the result
            if use_cache:
                self._save_to_cache(cache_key, {
                    'content': content,
                    'cached_at': datetime.now().isoformat()
                })

            return content

        except requests.Timeout:
            self.metrics.failed_scrapes += 1
            raise ScraperError(f"{self.config.name}: Request timeout")
        except requests.RequestException as e:
            self.metrics.failed_scrapes += 1
            raise ScraperError(f"{self.config.name}: Request failed: {e}")

    def _parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML with error handling."""
        try:
            return BeautifulSoup(html, 'html.parser')
        except Exception as e:
            self.metrics.parsing_errors += 1
            raise ParsingError(f"{self.config.name}: HTML parsing failed: {e}")

    def _validate_job(self, job: Dict[str, Any]) -> bool:
        """Validate scraped job data."""
        required_fields = ['title', 'company', 'job_url']
        for field in required_fields:
            if not job.get(field):
                return False

        # URL validation
        job_url = job['job_url']
        if not job_url.startswith(('http://', 'https://')):
            return False

        # Title length validation (spam filter)
        title = job['title']
        if len(title) < 5 or len(title) > 200:
            return False

        return True

    def _save_metrics(self):
        """Save metrics to file for monitoring."""
        metrics_file = self.metrics_dir / f"scraper_metrics_{datetime.now().strftime('%Y%m%d')}.json"
        
        # Load existing metrics
        all_metrics = {}
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    all_metrics = json.load(f)
            except Exception:
                pass

        # Update current portal metrics
        all_metrics[self.config.name] = {
            'requests_sent': self.metrics.requests_sent,
            'successful_scrapes': self.metrics.successful_scrapes,
            'failed_scrapes': self.metrics.failed_scrapes,
            'rate_limit_hits': self.metrics.rate_limit_hits,
            'blocked_ips': self.metrics.blocked_ips,
            'parsing_errors': self.metrics.parsing_errors,
            'jobs_discovered': self.metrics.jobs_discovered,
            'cache_hits': self.metrics.cache_hits,
            'success_rate': self.metrics.successful_scrapes / max(self.metrics.requests_sent, 1),
            'timestamp': datetime.now().isoformat()
        }

        try:
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(all_metrics, f, indent=2)
        except Exception:
            pass

    def _check_robots_txt(self) -> bool:
        """Check robots.txt before scraping."""
        if not self.config.robots_txt_check:
            return True

        try:
            robots_url = f"{self.config.base_url}/robots.txt"
            response = self.session.get(robots_url, timeout=10)
            if response.status_code == 200:
                # Simple check - disallow if * is disallowed
                if 'Disallow: /' in response.text or 'Disallow: *' in response.text:
                    print(f"{self.config.name}: robots.txt disallows scraping")
                    return False
        except Exception:
            pass  # If robots.txt check fails, proceed with caution

        return True

    @abstractmethod
    def discover_jobs(self, search_params: Dict[str, Any]) -> List[str]:
        """
        Phase 1: Discover job URLs from search results.
        Returns list of job URLs only (cheap operation).
        """
        pass

    @abstractmethod
    def scrape_job_details(self, job_url: str) -> Optional[Dict[str, Any]]:
        """
        Phase 2: Scrape full job details.
        Only called for jobs passing initial filters.
        """
        pass

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main method: Two-phase scraping (discovery + details).
        """
        jobs = []

        if not self.config.enable_scraping:
            return jobs

        if not self._check_robots_txt():
            return jobs

        try:
            # Phase 1: Discover job URLs
            print(f"{self.config.name}: Phase 1 - Discovering job URLs...")
            job_urls = self.discover_jobs(search_params)
            print(f"{self.config.name}: Discovered {len(job_urls)} job URLs")

            # Phase 2: Scrape details for each URL
            print(f"{self.config.name}: Phase 2 - Scraping job details...")
            for job_url in job_urls[:50]:  # Limit to 50 per run
                try:
                    job_data = self.scrape_job_details(job_url)
                    if job_data and self._validate_job(job_data):
                        jobs.append(job_data)
                        self.metrics.jobs_discovered += 1
                except Exception as e:
                    print(f"{self.config.name}: Error scraping {job_url}: {e}")
                    continue

            # Save metrics
            self._save_metrics()

            # Check for alerts
            if self.metrics.requests_sent > 0:
                success_rate = self.metrics.successful_scrapes / self.metrics.requests_sent
                if success_rate < 0.7:
                    print(f"WARNING: {self.config.name} success rate {success_rate:.1%} < 70%")
                if self.metrics.blocked_ips > 0:
                    print(f"WARNING: {self.config.name} has {self.metrics.blocked_ips} IP blocks")
                if self.metrics.jobs_discovered == 0:
                    print(f"WARNING: {self.config.name} discovered zero jobs")

            return jobs

        except (RateLimitError, BlockedError) as e:
            print(f"{self.config.name}: {e}. Portal paused.")
            return jobs
        except Exception as e:
            print(f"{self.config.name}: Unexpected error: {e}")
            self.metrics.failed_scrapes += 1
            self._save_metrics()
            return jobs
