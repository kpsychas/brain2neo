#!/usr/bin/env python

import unittest

import test_example


modules = [test_example]

suites = [m.suite() for m in modules]

alltests = unittest.TestSuite(suites)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(alltests)