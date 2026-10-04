import unittest

from server.research import prepare_messages


class ResearchContextTests(unittest.TestCase):
    def test_recent_history_is_bounded_and_case_rules_retained(self):
        case = {"reference": "CONTEXT-ONLY", "title": "Example", "description": "Synthetic case", "details": {"jurisdiction": "MX"}, "documents": [{"original_name": "x" * 500} for _ in range(100)]}
        history = [{"status": "completed", "question": f"Turn {index}: " + "q" * 4000, "answer": "a" * 10000} for index in range(6)]
        messages = prepare_messages(case, history, "Current question", "en", "research")
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("CONTEXT-ONLY", messages[0]["content"])
        self.assertIn('"jurisdiction": "MX"', messages[0]["content"])
        self.assertIn("NO external sources", messages[0]["content"])
        self.assertEqual(messages[-1]["content"], "Current question")
        self.assertLessEqual(sum(len(message["content"]) for message in messages[1:-1]), 12000)
        self.assertIn("Turn 5", messages[-3]["content"])
        self.assertNotIn("Turn 0", str(messages))
        self.assertNotIn("x" * 161, messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
