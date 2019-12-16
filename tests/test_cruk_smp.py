import unittest
from cruk_smp import *
from parse_variables_files import *





class TestCrukSmp2(unittest.TestCase):
    def setUp(self):
        self.cs = CrukSmp()

    def test_isupper(self):
        self.assertTrue('FOO'.isupper())
        self.assertFalse('Foo'.isupper())

    def test_find_samples(self):
        self.assertEqual(2, 2)


if __name__ == '__main__':
    unittest.main()
