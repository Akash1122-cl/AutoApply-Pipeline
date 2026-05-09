import os
import json
import asyncio
import random
from groq import AsyncGroq
from groq import InternalServerError, APIConnectionError, RateLimitError

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from src.shared.run_logger import RunLogger

class LLMClient:
    """Wrapper for LLM providers (Groq/Gemini) with retry and concurrency cap."""
    
    def __init__(self, logger: RunLogger):
        self.logger = logger
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        self.model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        
        # Groq Setup
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "dummy-key-for-tests")
        self.groq_client = AsyncGroq(api_key=self.groq_api_key)
        
        # Gemini Setup
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if GEMINI_AVAILABLE and self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
        
        # Max concurrent requests
        self.semaphore = asyncio.Semaphore(3)
        self.max_retries = 3
        
    async def _execute_with_retry(self, func, *args, **kwargs):
        attempt = 0
        base_delay = 1.0
        
        while attempt < self.max_retries:
            try:
                async with self.semaphore:
                    return await func(*args, **kwargs)
            except Exception as e:
                # Handle provider-specific errors
                error_msg = str(e)
                if "429" in error_msg or "rate_limit" in error_msg.lower():
                    # 429
                    print(f"DEBUG: LLM Rate Limit (429): {e}")
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    self.logger.record_error("llm_client", "execute", f"Rate limit (429). Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    attempt += 1
                elif "500" in error_msg or "503" in error_msg or "connection" in error_msg.lower():
                    # 5xx or connection issues
                    print(f"DEBUG: LLM Server Error (5xx): {e}")
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    self.logger.record_error("llm_client", "execute", f"Server/Connection error. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                    attempt += 1
                else:
                    print(f"DEBUG: LLM call failed (non-retryable): {e}")
                    self.logger.record_error("llm_client", "execute", f"Non-retryable error: {e}")
                    raise
                
        raise Exception("Max retries exceeded for LLM API call")

    async def generate(self, prompt: str, max_tokens: int = 1500, temperature: float = 0.3) -> str:
        """Generates text from the configured LLM provider."""
        
        if self.provider == "gemini":
            return await self._generate_gemini(prompt, max_tokens, temperature)
        else:
            return await self._generate_groq(prompt, max_tokens, temperature)

    async def _generate_groq(self, prompt: str, max_tokens: int, temperature: float) -> str:
        if self.groq_api_key == "dummy-key-for-tests":
            return f"MOCK_GROQ_RESPONSE_FOR:\n{prompt[:50]}..."
            
        async def _call():
            response = await self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )
            usage = response.usage
            if usage:
                self.logger.increment("llm_prompt_tokens", usage.prompt_tokens)
                self.logger.increment("llm_completion_tokens", usage.completion_tokens)
            return response.choices[0].message.content

        return await self._execute_with_retry(_call)

    async def _generate_gemini(self, prompt: str, max_tokens: int, temperature: float) -> str:
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai package not installed")
            
        async def _call():
            model = genai.GenerativeModel(self.model)
            # Gemini generation is synchronous in the library, wrap in thread
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature
                    )
                )
            )
            return response.text

        return await self._execute_with_retry(_call)

    async def generate_json(self, prompt: str, schema: dict) -> dict:
        """Generates JSON from the LLM, validating against schema."""
        if self.provider == "gemini":
            # For Gemini, we use a simple text prompt and manual parse for now
            # as its native JSON mode requires different configuration
            full_prompt = prompt + f"\n\nOutput ONLY valid JSON matching this schema: {json.dumps(schema)}. No markdown."
            content = await self.generate(full_prompt)
            try:
                # Strip markdown code blocks if present
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                return json.loads(content)
            except Exception as e:
                self.logger.record_error("llm_client", "generate_json", f"Gemini JSON parse failed: {e}")
                raise
        else:
            # Groq Native JSON mode
            system_prompt = f"You are a strict JSON builder. Output ONLY valid JSON matching this schema: {json.dumps(schema)}. Do not include markdown formatting or extra text."
            
            async def _call():
                response = await self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    model=self.model,
                    response_format={"type": "json_object"},
                    max_completion_tokens=2000,
                    temperature=0.1,
                )
                content = response.choices[0].message.content
                return json.loads(content)

            return await self._execute_with_retry(_call)
