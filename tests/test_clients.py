import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class ClientTests(unittest.TestCase):
    def setUp(self):
        requests = ModuleType("requests")
        requests.Session = Mock()
        requests.exceptions = SimpleNamespace(Timeout=TimeoutError, ConnectionError=ConnectionError)
        path = Path(__file__).resolve().parents[1] / "src/collection/clients.py"
        spec = importlib.util.spec_from_file_location("clients_under_test", path)
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", {"requests": requests}):
            spec.loader.exec_module(self.module)
        self.policy = Mock()
        self.module.source_policy = Mock(return_value=self.policy)

    def test_search_and_details_use_the_same_policy(self):
        client = self.module.JobsGovtClient("https://jobs.govt.nz", {}, {})
        client.get_listing_page("20")
        client.get_job_page("jncustomsearch.viewFullSingle?in_jnCounter=1")
        calls = self.policy.request.call_args_list
        self.assertEqual([call.args[1] for call in calls], ["POST", "GET"])
        self.assertEqual(calls[0].kwargs["data"]["in_pg"], "20")
        self.assertEqual(calls[1].args[2], "https://jobs.govt.nz/jobtools/jncustomsearch.viewFullSingle?in_jnCounter=1")

    def test_trademe_passes_region_as_query_parameter(self):
        client = self.module.TradeMeClient("https://api.trademe.co.nz/jobs", {}, {"canonical_path": "/jobs/auckland"})
        client.get_listings(1, "wellington")
        self.assertEqual(self.policy.request.call_args.kwargs["params"]["canonical_path"], "/jobs/wellington")
