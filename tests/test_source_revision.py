"""Kiểm tra vòng sửa nguồn bằng response giả lập, không đánh giá model thật."""
import unittest

from test_lab import FakeProvider, final, tool_call
from agent import run_agent
from status_tools import StatusTools


class SourceRevisionTests(unittest.TestCase):
    def test_unobserved_url_requires_revision_and_preserves_context(self):
        url = StatusTools().get_incident_details('github', 'xr3myzj7ms51')['url']
        draft = final('Nguồn: https://example.invalid/incident')
        provider = FakeProvider([
            tool_call('a', 'get_incident_details',
                      '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
            draft,
            final('Incident đã resolved. Nguồn: ' + url),
        ])
        result = run_agent('Kiểm tra incident', provider, StatusTools(), max_steps=3)
        self.assertEqual(result['status'], 'completed')
        self.assertIn(url, result['answer'])
        revision_context = provider.histories[2]
        self.assertEqual(revision_context[-2], draft['message'])
        self.assertEqual(revision_context[-1]['role'], 'user')
        self.assertIn(url, revision_context[-1]['content'])
        self.assertEqual(revision_context[-3]['tool_call_id'], 'a')
        self.assertEqual(len(result['usage']), 3)

    def test_repeated_missing_source_exhausts_shared_budget(self):
        provider = FakeProvider([
            tool_call('a', 'get_incident_details',
                      '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
            final('Vẫn thiếu nguồn.'), final('Vẫn thiếu nguồn.'),
        ])
        result = run_agent('Kiểm tra incident', provider, StatusTools(), max_steps=3)
        self.assertEqual(result['status'], 'max_steps')
        self.assertEqual(result['answer'], '')
        self.assertEqual(len(provider.histories), 3)
        self.assertEqual(sum(t['event'] == 'validation_missing_source'
                             for t in result['trace']), 2)


if __name__ == '__main__':
    unittest.main()
