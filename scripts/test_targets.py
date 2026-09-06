import unittest
from unittest.mock import patch
from targets import TARGETS, probe


class TargetTests(unittest.TestCase):
    def test_complete_matrix(self):
        self.assertEqual(len(TARGETS), 156)
        self.assertEqual(len({(t['pg'], t['arch']) for t in TARGETS}), 156)

    def test_archive_outcomes(self):
        cases = [
            ('first revision', [200], 'available', '-1-'),
            ('revised archive', [403, 200], 'available', '-2-'),
            ('missing', [404, 410, 404], 'missing', None),
            ('denied is not missing', [403, 403, 403], 'error', None),
            ('network is not missing', OSError('timeout'), 'error', None),
        ]
        for name, responses, expected, revision in cases:
            with self.subTest(name=name), patch('targets.head', side_effect=responses):
                result = probe({'pg': '9.5.21', 'arch': 'x86'})
                self.assertEqual(result['status'], expected)
                if revision:
                    self.assertIn(revision, result['url'])


if __name__ == '__main__':
    unittest.main()
