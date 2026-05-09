import unittest
import uuid
import tempfile
from pathlib import Path

from src.orchestrator.state_engine import StateTransitionError, validate_transition, TransitionContext
from src.orchestrator.run_lock_manager import run_lock
from src.orchestrator.main import Orchestrator
from src.shared.sheets_gateway import SheetsGateway
from src.shared.run_logger import RunLogger

from src.agent_1.dedup import deduplicate_jobs
from src.agent_1.classifier import classify_region_and_work_mode
from src.checkpoints.cp1_action_sync import sync_cp1_actions

class TestPhase1EdgeCases(unittest.IsolatedAsyncioTestCase):
    def test_terminal_state_transition(self):
        """Validates that terminal states cannot be transitioned from."""
        with self.assertRaises(StateTransitionError) as context:
            validate_transition("APPLIED", "SCORED")
        self.assertIn("Terminal status", str(context.exception))

    def test_missing_context_transition(self):
        """Validates that transitions requiring context fail if missing."""
        with self.assertRaises(StateTransitionError) as context:
            validate_transition("AWAITING_HUMAN_REVIEW", "CONTACT_DISCOVERY")
        self.assertIn("requires human_action", str(context.exception))

    def test_duplicate_run_lock(self):
        """Validates that single-run lock prevents overlapping runs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / ".test.lock"
            
            # Acquire lock first time
            with run_lock(lock_path):
                # Try to acquire again
                with self.assertRaises(RuntimeError):
                    with run_lock(lock_path):
                        pass # Should raise exception

    async def test_malformed_row_fault_isolation(self):
        """Validates that one failing row doesn't crash the orchestrator."""
        sheets = SheetsGateway.from_seed_rows([
            {
                "job_id": "job-ok",
                "status": "SCRAPED"
            },
            {
                "job_id": "job-bad",
                "status": "SCRAPED",
                "updated_at": "fail" # This will cause a conflict error on update
            }
        ])
        logger = RunLogger()
        orchestrator = Orchestrator(sheets, logger)
        
        # Override sheets.update_row to force a crash on job-bad
        original_update = sheets.update_row
        def mock_update(job_id, patch, expected_updated_at=None):
            if job_id == "job-bad":
                raise ValueError("Malformed row exception")
            return original_update(job_id, patch, expected_updated_at=expected_updated_at)
        sheets.update_row = mock_update

        await orchestrator._process_scoring_phase()
        
        ok_row = sheets.get_row("job-ok")
        bad_row = sheets.get_row("job-bad")
        
        self.assertEqual(ok_row["status"], "SCORED")
        self.assertEqual(bad_row["status"], "FAILED")
        self.assertIn("Malformed row exception", bad_row["notes"])


class TestPhase2EdgeCases(unittest.TestCase):
    def test_deduplication_tracking_parameters(self):
        """Validates query parameters are stripped during deduplication."""
        existing_keys = {
            ("acme corp", "product manager", "https://acme.com/jobs/1")
        }
        
        jobs = [
            {
                "company": "Acme Corp",
                "role_title": "Product Manager",
                "job_url": "https://acme.com/jobs/1?utm_source=linkedin&ref=123"
            },
            {
                "company": "Acme Corp",
                "role_title": "Product Manager",
                "job_url": "https://acme.com/jobs/2"
            }
        ]
        
        deduped = deduplicate_jobs(jobs, existing_keys)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["job_url"], "https://acme.com/jobs/2")

    def test_deduplication_company_naming(self):
        """Validates casing and whitespace are ignored in dedup."""
        existing_keys = {
            ("startup inc", "apm", "https://startup.com/job")
        }
        
        jobs = [
            {
                "company": "  Startup INC  ",
                "role_title": "APM",
                "job_url": "https://startup.com/job"
            }
        ]
        
        deduped = deduplicate_jobs(jobs, existing_keys)
        self.assertEqual(len(deduped), 0)

    def test_region_detection_edge_cases(self):
        """Validates region heuristic fallback rules."""
        job = classify_region_and_work_mode({"region": "Remote (EMEA)"})
        self.assertEqual(job["region"], "Europe")
        self.assertTrue(job["work_permit_required"])
        
        job2 = classify_region_and_work_mode({"region": "Bangalore / Remote"})
        self.assertEqual(job2["region"], "India")
        self.assertFalse(job2["work_permit_required"])


class TestPhase3EdgeCases(unittest.TestCase):
    def test_cp1_action_sync_blocking(self):
        """Validates that rows without valid human_action are ignored."""
        sheets = SheetsGateway.from_seed_rows([
            {
                "job_id": "job-1",
                "status": "AWAITING_HUMAN_REVIEW",
                "human_action": None
            },
            {
                "job_id": "job-2",
                "status": "AWAITING_HUMAN_REVIEW",
                "human_action": "Think About It" # Invalid
            }
        ])
        logger = RunLogger()
        
        # We capture transitions instead of orchestrator to test isolation
        transitions = []
        def mock_transition(row, nxt, ctx):
            transitions.append(row["job_id"])
            
        sync_cp1_actions(sheets, logger, mock_transition)
        self.assertEqual(len(transitions), 0)

    def test_cp1_routing(self):
        """Validates that Skip and Apply route correctly."""
        sheets = SheetsGateway.from_seed_rows([
            {
                "job_id": "job-skip",
                "status": "AWAITING_HUMAN_REVIEW",
                "human_action": "Skip"
            },
            {
                "job_id": "job-apply",
                "status": "AWAITING_HUMAN_REVIEW",
                "human_action": "Apply"
            }
        ])
        logger = RunLogger()
        
        transitions = {}
        def mock_transition(row, nxt, ctx):
            transitions[row["job_id"]] = nxt
            
        sync_cp1_actions(sheets, logger, mock_transition)
        self.assertEqual(transitions["job-skip"], "SKIPPED")
        self.assertEqual(transitions["job-apply"], "CONTACT_DISCOVERY")


class TestPhase4EdgeCases(unittest.IsolatedAsyncioTestCase):
    async def test_retry_policy_429(self):
        """Validates HTTP 429 retries with backoff."""
        from src.shared.run_logger import RunLogger
        from src.agent_2.retry import RetryPolicy
        import httpx
        
        logger = RunLogger()
        policy = RetryPolicy(logger, max_attempts=3, base_delay=0.01) # fast test
        
        calls = 0
        async def mock_func():
            nonlocal calls
            calls += 1
            if calls < 3:
                # Mock httpx error
                response = httpx.Response(429, request=httpx.Request("GET", "http://test"))
                raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
            return "success"
            
        result = await policy.execute_with_retry(mock_func)
        self.assertEqual(result, "success")
        self.assertEqual(calls, 3)

    async def test_retry_policy_401(self):
        """Validates HTTP 401 does NOT retry."""
        from src.shared.run_logger import RunLogger
        from src.agent_2.retry import RetryPolicy
        import httpx
        
        logger = RunLogger()
        policy = RetryPolicy(logger)
        
        calls = 0
        async def mock_func():
            nonlocal calls
            calls += 1
            response = httpx.Response(401, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("Unauthorized", request=response.request, response=response)
            
        with self.assertRaises(httpx.HTTPStatusError):
            await policy.execute_with_retry(mock_func)
        self.assertEqual(calls, 1) # Only called once

    async def test_orchestrator_quota_exhausted(self):
        """Validates quota exhaustion pauses remaining rows."""
        import httpx
        from src.shared.run_logger import RunLogger
        from src.shared.sheets_gateway import SheetsGateway
        from src.orchestrator.main import Orchestrator
        
        sheets = SheetsGateway.from_seed_rows([
            {"job_id": "job-1", "status": "CONTACT_DISCOVERY", "company": "test1"},
            {"job_id": "job-2", "status": "CONTACT_DISCOVERY", "company": "test2"}
        ])
        logger = RunLogger()
        orchestrator = Orchestrator(sheets, logger)
        
        # We patch discover_contact instead of Hunter to avoid complex mocking of the agent pipeline
        # just for this test
        original_process = orchestrator._process_contact_discovery
        
        # Quick and dirty patch: inside _process_contact_discovery, it creates an agent.
        # We will override _process_contact_discovery to use a mocked agent.
        import src.orchestrator.main
        class MockAgent:
            def __init__(self, *args): pass
            async def discover_contact(self, row):
                if row["job_id"] == "job-1":
                    raise ValueError("Quota exhausted 429")
                return row
                
        original_agent = src.orchestrator.main.ContactDiscoveryAgent
        src.orchestrator.main.ContactDiscoveryAgent = MockAgent
        
        try:
            await orchestrator._process_contact_discovery()
            
            row1 = sheets.get_row("job-1")
            row2 = sheets.get_row("job-2")
            
            # Both should be paused and remain in CONTACT_DISCOVERY
            self.assertTrue(row1.get("contact_discovery_paused"))
            self.assertEqual(row1["status"], "CONTACT_DISCOVERY")
            
            self.assertTrue(row2.get("contact_discovery_paused"))
            self.assertEqual(row2["status"], "CONTACT_DISCOVERY")
        finally:
            src.orchestrator.main.ContactDiscoveryAgent = original_agent

    async def test_rerun_paused_rows(self):
        """Validates paused rows are processed first."""
        from src.shared.run_logger import RunLogger
        from src.shared.sheets_gateway import SheetsGateway
        from src.orchestrator.main import Orchestrator
        import src.agent_2.pipeline
        
        sheets = SheetsGateway.from_seed_rows([
            {"job_id": "job-new", "status": "CONTACT_DISCOVERY", "company": "test_new"},
            {"job_id": "job-paused", "status": "CONTACT_DISCOVERY", "company": "test_paused", "contact_discovery_paused": True}
        ])
        logger = RunLogger()
        orchestrator = Orchestrator(sheets, logger)
        
        order = []
        import src.orchestrator.main
        class MockAgent:
            def __init__(self, *args): pass
            async def discover_contact(self, row):
                order.append(row["job_id"])
                row["status"] = "CONTENT_GENERATION"
                return row
                
        original_agent = src.orchestrator.main.ContactDiscoveryAgent
        src.orchestrator.main.ContactDiscoveryAgent = MockAgent
        
        try:
            await orchestrator._process_contact_discovery()
            
            # The paused job should have been processed first
            self.assertEqual(order, ["job-paused", "job-new"])
            
            # The paused flag should be cleared
            self.assertFalse(sheets.get_row("job-paused").get("contact_discovery_paused", False))
            self.assertEqual(sheets.get_row("job-paused")["status"], "CONTENT_GENERATION")
        finally:
            src.agent_2.pipeline.ContactDiscoveryAgent = original_agent

class TestPhase5EdgeCases(unittest.IsolatedAsyncioTestCase):
    async def test_fabrication_guard(self):
        """Validates FabricationGuard catches invented metrics and companies."""
        from src.agent_3.fabrication_guard import FabricationGuard
        from src.agent_3.source_reader import SourceReader
        
        master_cv = await SourceReader.load_master_cv()
        accomplishments = await SourceReader.load_accomplishments_bank()
        
        # Build source_evidence mimicking SkillMapper output
        source_evidence = {"SQL": [accomplishments[1]]}
        
        # 1. Valid CV
        valid_cv = {
            "experience": [
                {
                    "company": "XYZ Corp",
                    "role": "Product Intern",
                    "duration": "Jun 2023 - Aug 2023",
                    "bullets": ["Led redesign of onboarding flow using Figma and user research."]
                }
            ]
        }
        res1 = FabricationGuard.validate_cv(valid_cv, source_evidence, master_cv)
        self.assertTrue(res1["is_valid"])
        
        # 2. Fabricated Company
        invalid_cv1 = {
            "experience": [
                {
                    "company": "Invented Google",
                    "role": "Product Intern",
                    "duration": "Jun 2023 - Aug 2023",
                    "bullets": ["Led redesign of onboarding flow using Figma and user research."]
                }
            ]
        }
        res2 = FabricationGuard.validate_cv(invalid_cv1, source_evidence, master_cv)
        self.assertFalse(res2["is_valid"])
        self.assertEqual(res2["violations"][0]["reason"], "Fabricated company")
        
        # 3. Fabricated Metric
        invalid_cv2 = {
            "experience": [
                {
                    "company": "XYZ Corp",
                    "role": "Product Intern",
                    "duration": "Jun 2023 - Aug 2023",
                    "bullets": ["Increased revenue by $1M using Figma."]
                }
            ]
        }
        res3 = FabricationGuard.validate_cv(invalid_cv2, source_evidence, master_cv)
        self.assertFalse(res3["is_valid"])
        self.assertEqual(res3["violations"][0]["reason"], "Fabricated metric")

    async def test_skill_mapper_gaps(self):
        """Validates SkillMapper correctly identifies gaps and matches."""
        from src.agent_3.skill_mapper import SkillMapper
        from src.agent_3.source_reader import SourceReader
        
        master_cv = await SourceReader.load_master_cv()
        accomplishments = await SourceReader.load_accomplishments_bank()
        mapper = SkillMapper()
        
        # Figma is in XYZ Corp accomplishment, Performance is in TechStart, Rust is nowhere
        res = mapper.map_required_skills(["Figma", "Performance", "Rust"], accomplishments, master_cv)
        
        self.assertIn("Figma", res["matched_skills"])
        self.assertEqual(len(res["matched_skills"]["Figma"]), 1)
        self.assertEqual(res["matched_skills"]["Figma"][0]["company"], "XYZ Corp")
        
        self.assertIn("Rust", res["skill_gaps"])
        self.assertNotIn("Rust", res["matched_skills"])

if __name__ == '__main__':
    unittest.main()
