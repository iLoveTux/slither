import sys
import unittest
import subprocess
import slither

class TestHelpOutput(unittest.TestCase):
    def test_version_in_help_output(self):
        self.assertIn(slither.__version__.encode(), self.output)
