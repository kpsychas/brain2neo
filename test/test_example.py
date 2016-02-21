#!/usr/bin/python

from unittest import TestCase, TestLoader, TestSuite

import brain2neo.brain2neo as b2n


class ExampleTestCase(TestCase):
    def setUp(self):
        xmlfile = "example.xml"
        cfg = b2n.get_cfg(xmlfile)
        root = b2n.get_root(xmlfile)

        graph = b2n.get_graph(cfg)
        self.cypher = b2n.get_cypher(graph)

        # empty graph
        self.cypher.execute('MATCH (n) OPTIONAL MATCH (n)-[r]-() DELETE n,r')
        self.assertTrue(b2n.is_empty(self.cypher))

        b2n.store2neo(root, cfg)

    def test_nonempty(self):
        self.assertFalse(b2n.is_empty(self.cypher))


def suite():
    suite = TestSuite()
    for test_class in (ExampleTestCase,):
        tests = TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    return suite

