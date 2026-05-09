import dns.resolver
from src.shared.run_logger import RunLogger
from src.agent_2.retry import RetryPolicy

class EmailVerifier:
    """Verifies email deliverability via MX record checks."""
    
    def __init__(self, logger: RunLogger, retry_policy: RetryPolicy):
        self.logger = logger
        self.retry_policy = retry_policy
        self._cache = {} # Cache results for the run

    async def verify(self, email: str) -> bool:
        if not email or "@" not in email:
            return False
            
        domain = email.split("@")[1]
        
        if domain in self._cache:
            return self._cache[domain]
            
        def _check_mx():
            try:
                # dns.resolver.resolve is synchronous, but we can wrap it or just call it 
                # since dns resolution is fast, but better to use execute_with_retry for safety.
                answers = dns.resolver.resolve(domain, 'MX')
                return len(answers) > 0
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
                return False
            except Exception as e:
                self.logger.record_error("verification", "mx_check", f"DNS error for {domain}: {e}")
                return False

        # execute_with_retry expects an async function, we can just make a wrapper
        async def _async_check():
            return _check_mx()
            
        try:
            result = await self.retry_policy.execute_with_retry(_async_check)
            self._cache[domain] = result
            return result
        except Exception as e:
            self.logger.record_error("verification", "verify", f"Verification failed for {email}: {e}")
            return False
