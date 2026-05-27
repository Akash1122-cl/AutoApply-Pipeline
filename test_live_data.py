"""
Test script for live job portal data fetching.

This script tests the real job portal adapters (Adzuna, SerpAPI) to verify
live data can be fetched from job portals.

Usage:
1. Set your API keys in .env file:
   - ADZUNA_APP_ID
   - ADZUNA_APP_KEY
   - SERPAPI_KEY
2. Set USE_MOCK_JOBS=false in .env
3. Run: python test_live_data.py
"""

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

from src.agent_1.adapters import AdzunaAdapter, SerpApiAdapter, MockAdapter, NaukriAdapter, OttaAdapter
from src.agent_1.pipeline import Agent1Pipeline


def test_adapters():
    """Test each adapter individually."""
    print("=" * 60)
    print("TESTING LIVE JOB PORTAL ADAPTERS")
    print("=" * 60)

    # Test Naukri (no API key required)
    print("\n[1] Testing Naukri Adapter (India - no API key)...")
    naukri = NaukriAdapter()
    try:
        jobs = naukri.fetch_jobs()
        print(f"   ✓ Fetched {len(jobs)} jobs from Naukri")
        if jobs:
            print(f"   Sample job: {jobs[0]['company']} - {jobs[0]['role_title']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test Otta (no API key required)
    print("\n[2] Testing Otta Adapter (Europe - no API key)...")
    otta = OttaAdapter()
    try:
        jobs = otta.fetch_jobs()
        print(f"   ✓ Fetched {len(jobs)} jobs from Otta")
        if jobs:
            print(f"   Sample job: {jobs[0]['company']} - {jobs[0]['role_title']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test Adzuna (requires API key)
    print("\n[3] Testing Adzuna Adapter...")
    adzuna = AdzunaAdapter()
    if adzuna.app_id and adzuna.app_key:
        print(f"   ✓ Adzuna credentials found (APP_ID: {adzuna.app_id[:8]}...)")
        try:
            jobs = adzuna.fetch_jobs()
            print(f"   ✓ Fetched {len(jobs)} jobs from Adzuna")
            if jobs:
                print(f"   Sample job: {jobs[0]['company']} - {jobs[0]['role_title']}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    else:
        print("   ✗ Adzuna credentials not found in .env")
        print("   Add: ADZUNA_APP_ID and ADZUNA_APP_KEY to .env")

    # Test SerpAPI (requires API key)
    print("\n[4] Testing SerpAPI Adapter...")
    serpapi = SerpApiAdapter()
    if serpapi.api_key:
        print(f"   ✓ SerpAPI key found ({serpapi.api_key[:8]}...)")
        try:
            jobs = serpapi.fetch_jobs()
            print(f"   ✓ Fetched {len(jobs)} jobs from SerpAPI")
            if jobs:
                print(f"   Sample job: {jobs[0]['company']} - {jobs[0]['role_title']}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    else:
        print("   ✗ SerpAPI key not found in .env")
        print("   Add: SERPAPI_KEY to .env")

    # Test Mock (fallback)
    print("\n[5] Testing Mock Adapter (fallback)...")
    mock = MockAdapter()
    try:
        jobs = mock.fetch_jobs()
        print(f"   ✓ Fetched {len(jobs)} mock jobs")
    except Exception as e:
        print(f"   ✗ Error: {e}")


def test_pipeline():
    """Test the full Agent 1 pipeline with live data."""
    print("\n" + "=" * 60)
    print("TESTING AGENT 1 PIPELINE WITH LIVE DATA")
    print("=" * 60)

    use_mock = os.getenv("USE_MOCK_JOBS", "true").lower() in ["true", "1", "yes"]
    print(f"\nConfiguration: USE_MOCK_JOBS = {use_mock}")

    if use_mock:
        print("⚠ WARNING: Mock mode is enabled. Set USE_MOCK_JOBS=false in .env for live data.")
        print("The pipeline will use MockAdapter instead of real job portals.")
    else:
        print("✓ Live mode enabled. Pipeline will use real job portal adapters.")

    print("\nInitializing Agent 1 Pipeline...")
    pipeline = Agent1Pipeline()

    print(f"Loaded adapters: {[a.__class__.__name__ for a in pipeline.adapters]}")

    print("\nRunning pipeline (this may take 30-60 seconds)...")
    try:
        jobs = pipeline.run(existing_keys=set())
        print(f"\n✓ Pipeline completed successfully!")
        print(f"  Total jobs fetched: {len(jobs)}")

        if jobs:
            print("\nSample jobs:")
            for i, job in enumerate(jobs[:5], 1):
                print(f"  {i}. {job['company']} - {job['role_title']} ({job['source_platform']})")
                print(f"     Region: {job['region']}, Mode: {job['work_mode']}, Score: {job.get('fit_score', 'N/A')}")

        return jobs
    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return []
def main():
    """Main test function."""
    print("\n" + "=" * 60)
    print("LIVE DATA TEST SUITE")
    print("=" * 60)

    # Check environment setup
    print("\nEnvironment Check:")
    print(f"  ADZUNA_APP_ID: {'✓ Set' if os.getenv('ADZUNA_APP_ID') else '✗ Not set'}")
    print(f"  ADZUNA_APP_KEY: {'✓ Set' if os.getenv('ADZUNA_APP_KEY') else '✗ Not set'}")
    print(f"  SERPAPI_KEY: {'✓ Set' if os.getenv('SERPAPI_KEY') else '✗ Not set'}")
    print(f"  USE_MOCK_JOBS: {os.getenv('USE_MOCK_JOBS', 'true')}")

    # Run tests
    test_adapters()
    jobs = test_pipeline()
    print(f"  Naukri Adapter: ✓ Available (no API key needed)")
    print(f"  Otta Adapter: ✓ Available (no API key needed)")

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total jobs fetched: {len(jobs)}")
    print("\nNext Steps:")
    print("1. If jobs fetched from Naukri/Otta: System is ready for live data without API keys")
    print("2. For more coverage: Add ADZUNA_APP_ID, ADZUNA_APP_KEY, SERPAPI_KEY to .env")
    print("3. To push to Google Sheets: Configure GOOGLE_APPLICATION_CREDENTIALS")
    print("=" * 60)


if __name__ == "__main__":
    main()
