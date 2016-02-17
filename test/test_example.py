#!/usr/bin/python

from unittest import TestCase, TestLoader, TestSuite

from brain2neo.brain2neo import get_cfg, get_root, store2neo


class ExampleTestCase(TestCase):
    def setUp(self):
        xmlfile = "example.xml"
        self.cfg = get_cfg(xmlfile)
        self.root = get_root(xmlfile)

    def test_example(self):
        store2neo(self.root, self.cfg)

def suite():
    suite = TestSuite()
    for test_class in (ExampleTestCase,):
        tests = TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    return suite

