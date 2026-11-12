"""Budget retry và pagination của agent, không gọi API thật."""
import json
import unittest
from unittest.mock import patch

from test_agent import ScriptedProvider, call, final
from agent import run_agent
from bonus.tools import BonusTools


class BonusResilienceTests(unittest.TestCase):
    def test_persistent_rate_limit_stops_actual_execution_after_three_attempts(self):
        tools = BonusTools(scenario='rate_limit_always')
        provider = ScriptedProvider([
            *(call(str(i), 'get_vercel_status', {}) for i in range(5)),
            call('github', 'get_github_status', {}),
            final('Vercel không xác nhận được; GitHub đã kiểm tra.'),
        ])
        result = run_agent('Kiểm tra', provider, tools, max_steps=8)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 3)
        self.assertEqual(tools.calls[('get_github_status', 'github')], 1)
        self.assertFalse(json.loads(provider.histories[3][-1]['content'])['retriable'])

    def test_retry_after_stops_instead_of_retrying_before_deadline(self):
        for retry_after in ('2', 'Wed, 21 Oct 2037 07:28:00 GMT'):
            with self.subTest(retry_after=retry_after):
                tools = BonusTools()
                response = {'ok': False, 'error': 'RATE_LIMITED', 'http_status': 429,
                            'retry_after': retry_after, 'retriable': True}
                provider = ScriptedProvider([
                    call('a', 'get_npm_status', {}), call('b', 'get_npm_status', {}),
                    final('Chưa xác nhận npm vì rate limit.'),
                ])
                with patch.object(tools, 'execute', return_value=response) as execute:
                    result = run_agent('Kiểm tra', provider, tools)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(execute.call_count, 1)
                observation = json.loads(provider.histories[1][-1]['content'])
                self.assertFalse(observation['retriable'])
                self.assertEqual(observation['retry_after'], retry_after)

    def test_next_page_reaches_model_with_earlier_page_preserved(self):
        tools = BonusTools()
        args = {'provider': 'vercel', 'incident_id': 'sps6n39gm4sg'}
        url = tools.get_incident_details(**args)['url']
        provider = ScriptedProvider([
            call('page1', 'get_incident_details', args),
            call('page2', 'get_incident_details', {**args, 'offset': 2}),
            final('Incident lịch sử đã resolved. ' + url),
        ])
        result = run_agent('Tìm update về upstream GitHub', provider, tools)
        self.assertEqual(result['status'], 'completed')
        pages = [json.loads(m['content']) for m in provider.histories[2] if m['role'] == 'tool']
        self.assertEqual(pages[0]['next_offset'], 2)
        self.assertEqual(pages[1]['offset'], 2)
        self.assertTrue(any('93njd414rpbx' in u['body'] for u in pages[1]['updates']))


if __name__ == '__main__':
    unittest.main()
