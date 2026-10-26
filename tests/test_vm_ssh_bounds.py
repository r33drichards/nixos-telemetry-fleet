import ast
from pathlib import Path
import textwrap
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).parents[1]

class SshBoundsTests(unittest.TestCase):
    def setUp(self):
        source = (ROOT/'tests/cloud-init-ssh6.nix').read_text().split("testScript = ''", 1)[1].rsplit("'';", 1)[0]
        tree = ast.parse(textwrap.dedent(source))
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'check_ssh')
        self.client, self.server = Mock(), Mock()
        self.client.succeed.return_value = self.server.succeed.return_value = 'fixture diagnostic'
        scope = {'client': self.client, 'server': self.server, 'print': Mock()}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), '<VM helper>', 'exec'), scope)
        self.check = scope['check_ssh']
    def test_positive_requires_zero_and_bounds_driver(self):
        self.client.execute.return_value = (0, '')
        self.check('fixture SSH', 0)
        self.client.execute.assert_called_once_with('fixture SSH', timeout=40)
    def test_denied_requires_ssh_exit_not_timeout(self):
        self.client.execute.return_value = (255, 'denied')
        self.check('fixture SSH', 255)
        for status in (0, 124, 137):
            self.client.execute.return_value = (status, 'fixture result')
            with self.assertRaises(AssertionError): self.check('fixture SSH', 255)
    def test_positive_failure_is_not_retried_or_accepted(self):
        self.client.execute.return_value = (124, 'timed out')
        with self.assertRaises(AssertionError): self.check('fixture SSH', 0)
        self.assertEqual(self.client.execute.call_count, 1)
        self.client.succeed.assert_called_once_with('tail -n 80 /tmp/fixture-ssh.log', timeout=10)
    def test_driver_timeout_propagates(self):
        self.client.execute.side_effect = TimeoutError('driver capture')
        with self.assertRaises(TimeoutError): self.check('fixture SSH', 0)
