from datetime import date
from pathlib import Path
import sys
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from transformation.quality import normalize_date, validate_record


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.data = dict(raw_id=str(uuid4()), source="jobs_govt_nz", external_reference_id="123",
                         job_title=" Data   Engineer ", employer="Example", job_url="/jobs/123",
                         date_listed="05/08/2026", closing_date="2026-09-01")
        self.salary_parser = lambda value: (None, None, None)

    def validate(self):
        return validate_record(self.data, self.salary_parser, today=date(2026, 8, 6))

    def test_valid_record_normalizes_dates_text_and_relative_urls(self):
        result, issues = self.validate()
        self.assertEqual(issues, [])
        self.assertEqual(result["date_listed"], date(2026, 8, 5))
        self.assertEqual(result["job_title"], "Data Engineer")
        self.assertEqual(result["job_url"], "https://jobs.govt.nz/jobs/123")

    def test_blank_employer_and_oversized_title_are_rejected(self):
        self.data.update(employer="  ", job_title="x" * 256)
        self.assertEqual(self.validate()[1], ["employer:required", "job_title:too_long"])

    def test_bad_urls_and_dates_are_rejected(self):
        self.data.update(job_url="javascript:alert(1)", date_listed="not a date")
        self.assertIn("job_url:invalid_url", self.validate()[1])
        self.assertIn("date_listed:invalid_date", self.validate()[1])

    def test_reversed_dates_and_salaries_are_rejected(self):
        self.data.update(closing_date="2026-08-01")
        self.salary_parser = lambda value: (100000, 50000, "year")
        self.assertEqual(self.validate()[1], ["closing_date:before_listing", "salary_range:invalid_bounds"])

    def test_future_listing_is_rejected(self):
        self.data.update(date_listed="2030-01-01", closing_date=None)
        self.assertIn("date_listed:future_date", self.validate()[1])

    def test_iso_dates_are_not_day_month_swapped(self):
        self.assertEqual(normalize_date("2026-08-05"), date(2026, 8, 5))
