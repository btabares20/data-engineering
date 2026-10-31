from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from enrichment.descriptions import description_text, trademe_description
from enrichment.skills import extract_skills


class DescriptionTests(unittest.TestCase):
    def test_html_preserves_sections_without_script_content(self):
        text = description_text("<h2>Required skills</h2><ul><li>Python &amp; SQL</li></ul><script>Java</script>")
        self.assertEqual(text, "Required skills\nPython & SQL")
        self.assertEqual(extract_skills(text)["skills_required"], ["Python", "SQL"])

    def test_missing_and_summary_descriptions_are_explicit(self):
        self.assertEqual(trademe_description({}), (None, "missing"))
        self.assertEqual(trademe_description({"ShortDescription": "Use SQL"}), ("Use SQL", "summary"))
        self.assertEqual(trademe_description({"Body": "<p>Use SQL</p>"}), ("Use SQL", "full"))


class SkillTests(unittest.TestCase):
    def test_required_preferred_and_incidental_mentions(self):
        result = extract_skills("Python is required. SQL is preferred. Our platform uses Kafka.")
        self.assertEqual(result["skills_required"], ["Python"])
        self.assertEqual(result["skills_mentioned"], ["Apache Kafka", "Python", "SQL"])
        self.assertEqual(result["skills_evidence"][1]["classification"], "preferred")

    def test_negative_requirement_is_not_required(self):
        result = extract_skills("Python is not required. No SQL experience required.")
        self.assertEqual(result["skills_required"], [])
        self.assertEqual(result["skills_mentioned"], ["Python", "SQL"])

    def test_word_boundaries_and_punctuation_skills(self):
        result = extract_skills("Use JavaScript, C++, C#, .NET and PostgreSQL. Go to our website.")
        self.assertEqual(result["skills_mentioned"], [".NET", "C#", "C++", "JavaScript", "PostgreSQL"])

    def test_aliases_are_deduplicated_and_evidence_is_retained(self):
        result = extract_skills("AWS and Amazon Web Services are required.")
        self.assertEqual(result["skills_required"], ["AWS"])
        self.assertIn("AWS", result["skills_evidence"][0]["text"])

    def test_heading_context_resets(self):
        result = extract_skills("Essential skills:\nPython\nNice to have:\nSQL\nAbout us:\nWe use Docker")
        self.assertEqual(result["skills_required"], ["Python"])
        self.assertEqual(result["skills_mentioned"], ["Docker", "Python", "SQL"])
