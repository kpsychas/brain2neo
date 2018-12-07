#!/usr/bin/env python

import unittest

import test_example


modules = [test_example]

suites = [m.test_suite() for m in modules]

all_tests = unittest.TestSuite(suites)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(all_tests)
