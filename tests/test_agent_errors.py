"""Kiểm tra lỗi ở ranh giới model/tools mà không gọi API thật."""
import json
import unittest
from unittest.mock import Mock

from test_lab import FakeProvider, final, tool_call
from agent import run_agent
from status_tools import StatusTools


class AgentErrorTests(unittest.TestCase):
    def test_provider_failure_preserves_previous_trace_and_usage(self):
        first = tool_call('a', 'get_status', '{"provider":"github"}')
        first['usage'] = {'total_tokens': 12}
        provider = Mock()
        provider.complete.side_effect = [first, RuntimeError('secret-api-key')]
        result = run_agent('Kiểm tra', provider, StatusTools())
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['usage'], [{'total_tokens': 12}])
        self.assertEqual(result['trace'][-1]['error'], 'PROVIDER_ERROR')
        self.assertEqual(result['trace'][1]['name'], 'get_status')
        self.assertNotIn('secret-api-key', json.dumps(result))

    def test_thrown_tool_timeout_does_not_skip_other_calls(self):
        first = tool_call('a', 'get_status', '{"provider":"github"}')
        second = tool_call('b', 'get_status', '{"provider":"cloudflare"}')
        first['calls'] += second['calls']
        first['message']['tool_calls'] += second['message']['tool_calls']
        provider = FakeProvider([first, final('Không xác nhận được GitHub.')])
        tools = Mock()
        tools.execute.side_effect = [TimeoutError('private request'), {'provider': 'cloudflare'}]
        result = run_agent('Kiểm tra', provider, tools)
        self.assertEqual(result['status'], 'completed')
        observations = provider.histories[1][-2:]
        self.assertEqual([m['tool_call_id'] for m in observations], ['a', 'b'])
        self.assertEqual(json.loads(observations[0]['content'])['error'], 'TimeoutError')
        self.assertEqual(json.loads(observations[1]['content'])['provider'], 'cloudflare')
        self.assertNotIn('private request', json.dumps(result))

    def test_non_object_arguments_are_returned_without_executing_tool(self):
        for arguments in ('[]', 'null', '42', '"github"', None):
            with self.subTest(arguments=arguments):
                provider = FakeProvider([tool_call('a', 'get_status', arguments), final()])
                tools = Mock()
                result = run_agent('Kiểm tra', provider, tools)
                self.assertEqual(result['status'], 'completed')
                tools.execute.assert_not_called()
                self.assertEqual(json.loads(provider.histories[1][-1]['content'])['error'], 'INVALID_ARGUMENTS')

    def test_registry_errors_reach_model_and_trace(self):
        cases = [
            ('missing', '{}', StatusTools(), 'UNKNOWN_TOOL'),
            ('get_status', '{"provider":"invalid"}', StatusTools(), 'ValueError'),
            ('get_status', '{"provider":"github"}', StatusTools(fail=True), 'TimeoutError'),
        ]
        for name, args, tools, expected in cases:
            with self.subTest(error=expected):
                provider = FakeProvider([tool_call('a', name, args), final('Thiếu dữ liệu.')])
                result = run_agent('Kiểm tra', provider, tools)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['trace'][1]['result']['error'], expected)
                self.assertEqual(json.loads(provider.histories[1][-1]['content'])['error'], expected)

    def test_invalid_provider_response_returns_error(self):
        for response in (None, {}, {'message': {}, 'calls': None, 'finish': 'stop'}):
            with self.subTest(response=response):
                result = run_agent('Kiểm tra', FakeProvider([response]), StatusTools())
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['trace'][-1]['error'], 'INVALID_RESPONSE')

    def test_truncated_response_does_not_execute_calls(self):
        response = tool_call('a', 'get_status', '{"provider":"github"}')
        response['finish'] = 'length'
        tools = Mock()
        result = run_agent('Kiểm tra', FakeProvider([response]), tools)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['trace'][-1]['error'], 'MODEL_STOP_ERROR')
        tools.execute.assert_not_called()

    def test_step_budget_stops_repeated_tool_calls(self):
        provider = FakeProvider([tool_call(str(i), 'get_status', '{"provider":"github"}') for i in range(3)])
        result = run_agent('Kiểm tra', provider, StatusTools(), max_steps=2)
        self.assertEqual(result['status'], 'max_steps')
        self.assertEqual(len(provider.histories), 2)
        self.assertEqual(result['trace'][-1]['event'], 'max_steps')

    def test_invalid_budget_does_not_call_model(self):
        for budget in (0, -1, True, 1.5):
            with self.subTest(budget=budget):
                provider = Mock()
                result = run_agent('Kiểm tra', provider, StatusTools(), max_steps=budget)
                self.assertEqual(result['status'], 'error')
                provider.complete.assert_not_called()


if __name__ == '__main__':
    unittest.main()
