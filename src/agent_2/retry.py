import asyncio
import random
from typing import Callable, Any

from src.shared.run_logger import RunLogger


class RetryPolicy:
    """Exponential backoff retry policy for external API calls."""
    
    def __init__(self, logger: RunLogger, max_attempts: int = 3, base_delay: float = 1.0):
        self.logger = logger
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        # Do NOT retry on these client errors
        self.non_retryable_status_codes = {400, 401, 403, 404}
        # Retry on rate limit and server errors
        self.retryable_status_codes = {429, 500, 502, 503, 504}

    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        import httpx
        
        attempt = 0
        while attempt < self.max_attempts:
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                
                if status_code in self.non_retryable_status_codes:
                    self.logger.record_error("retry_policy", "execute", f"Non-retryable HTTP {status_code}: {exc}")
                    raise  # Re-raise immediately
                    
                if status_code not in self.retryable_status_codes:
                    # Unknown status code, re-raise just in case
                    self.logger.record_error("retry_policy", "execute", f"Unexpected HTTP {status_code}: {exc}")
                    raise
                    
                # Calculate backoff
                delay = (self.base_delay * (2 ** attempt)) + random.uniform(0, 1)
                self.logger.record_error(
                    "retry_policy", 
                    "execute", 
                    f"HTTP {status_code}. Retrying {attempt + 1}/{self.max_attempts} in {delay:.2f}s"
                )
                await asyncio.sleep(delay)
                attempt += 1
            except httpx.RequestError as exc:
                # Network errors (timeout, connection error, etc.)
                delay = (self.base_delay * (2 ** attempt)) + random.uniform(0, 1)
                self.logger.record_error(
                    "retry_policy", 
                    "execute", 
                    f"Request error: {exc}. Retrying {attempt + 1}/{self.max_attempts} in {delay:.2f}s"
                )
                await asyncio.sleep(delay)
                attempt += 1
                
        # If we exit the loop, max attempts exceeded
        self.logger.record_error("retry_policy", "execute", f"Max retries ({self.max_attempts}) exceeded.")
        raise Exception("Max retries exceeded for external API call")
