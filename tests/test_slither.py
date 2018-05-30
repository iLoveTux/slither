import unittest
import subprocess
import slither

class TestHelpOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = subprocess.check_output("slither --help")

    def test_version_in_help_output(self):
        self.assertIn(slither.__version__.encode(), self.output)
