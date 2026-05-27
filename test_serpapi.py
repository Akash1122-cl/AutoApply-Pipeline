import os
import sys
from dotenv import load_dotenv

# Set UTF-8 encoding for Windows terminals
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Load environment variables
load_dotenv()

from src.agent_1.adapters import SerpApiAdapter

def test_serpapi():
    print("=" * 60)
    print("TESTING SERPAPI ADAPTER")
    print("=" * 60)

    serpapi = SerpApiAdapter()
    if serpapi.api_key:
        print(f"✓ SerpAPI key found in environment ({serpapi.api_key[:8]}...)")
        try:
            # Let's override search queries to just do one query to be fast
            import unittest.mock
            search_queries = ["Associate Product Manager jobs India"]
            
            print(f"Fetching jobs using query: {search_queries[0]}")
            
            # Temporary patch list to run quickly
            import requests
            params = {
                "engine": "google_jobs",
                "q": search_queries[0],
                "api_key": serpapi.api_key,
                "num": 5
            }
            response = requests.get(serpapi.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            jobs = data.get("jobs_results", data.get("jobs", []))
            print(f"✓ Successfully fetched {len(jobs)} jobs from SerpAPI!")
            if not jobs:
                print("DEBUG full response keys:", list(data.keys()))
                print("DEBUG full response:", data)
            for i, job in enumerate(jobs[:3], 1):
                print(f"  {i}. {job.get('company_name')} - {job.get('title')}")
                print(f"     URL: {job.get('share_link', job.get('apply_link', job.get('sharing_link', job.get('job_id'))))}")
        except Exception as e:
            print(f"✗ Error during SerpAPI fetch: {e}")
    else:
        print("✗ SerpAPI key not found in .env")

if __name__ == "__main__":
    test_serpapi()
