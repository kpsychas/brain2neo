#!/usr/bin/python

from unittest import TestCase, TestLoader, TestSuite

import brain2neo.brain2neo as b2n


class ExampleTestCase(TestCase):
    def setUp(self):
        xmlfile = "example.xml"
        cfg = b2n.get_cfg(xmlfile)
        root = b2n.get_root(xmlfile)

        self.graph = b2n.get_graph(cfg)

        # empty graph
        self.graph.run('MATCH (n) OPTIONAL MATCH (n)-[r]-() DELETE n,r')
        self.assertTrue(b2n.is_empty(self.graph))

        b2n.store2neo(root, cfg)

    def test_nonempty(self):
        self.assertFalse(b2n.is_empty(self.graph))

    def test_nodes(self):
        n_nodes = self.graph.run('MATCH (n) RETURN COUNT (n)').evaluate()
        self.assertEquals(n_nodes, 19)

    def test_examplenode(self):
        examplenode = self.graph.run(
            'MATCH (n{name:"Example"}) RETURN (n)').evaluate()
        self.assertIsNotNone(examplenode)

    def test_relationships(self):
        n_nodes = self.graph.run('MATCH (n)-[d]-() RETURN COUNT(d)/2') \
            .evaluate()
        self.assertEquals(n_nodes, 32)

    def test_examplerelationship(self):
        examplerelationship = self.graph.run(
            'MATCH (n)-[d:`based on`]-() RETURN (d)').evaluate()
        self.assertIsNotNone(examplerelationship)

    def test_tree_neoname(self):
        examplechildren = self.graph.run(
            'MATCH (n{name:"Example"})-[d:`CHILD`]->() RETURN COUNT(d)') \
                .evaluate()
        self.assertEquals(examplechildren, 6)
        notexamplechildren = self.graph.run(
            'MATCH (n{name:"Example"})<-[d:`CHILD`]-() RETURN COUNT(d)') \
                .evaluate()
        self.assertEquals(notexamplechildren, 0)


class ModExampleTestCase(TestCase):
    def modifyconfig(self, cfg):
        cfg['Convert']['ignore_attachments'] = True
        cfg['Convert']['ignore_private'] = False
        cfg['Convert']['sibl_mode'] = 'directed'
        cfg['Convert']['upper_linknames'] = True
        cfg['Convert']['tree_neoname'] = 'PARENT'
        cfg['Convert']['tree_neodir'] = 'child_to_parent'

    def setUp(self):
        xmlfile = "example.xml"
        cfg = b2n.get_cfg(xmlfile)
        root = b2n.get_root(xmlfile)

        self.modifyconfig(cfg)
        self.graph = b2n.get_graph(cfg)

        # empty graph
        self.graph.run('MATCH (n) OPTIONAL MATCH (n)-[r]-() DELETE n,r')
        self.assertTrue(b2n.is_empty(self.graph))

        b2n.store2neo(root, cfg)

    def test_nonempty(self):
        self.assertFalse(b2n.is_empty(self.graph))

    def test_nodes(self):
        n_nodes = self.graph.run('MATCH (n) RETURN COUNT (n)').evaluate()
        self.assertEquals(n_nodes, 20)

    def test_examplenode(self):
        examplenode = self.graph.run(
            'MATCH (n{name:"Example"}) RETURN (n)').evaluate()
        self.assertIsNotNone(examplenode)

    def test_relationships(self):
        n_nodes = self.graph.run('MATCH (n)-[d]-() RETURN COUNT(d)/2') \
            .evaluate()
        self.assertEquals(n_nodes, 31)

    def test_examplerelationship(self):
        examplerelationship = self.graph.run(
            'MATCH (n)-[d:`BASED ON`]-() RETURN (d)').evaluate()
        self.assertIsNotNone(examplerelationship)

    def test_tree_neoname(self):
        notexamplechildren = self.graph.run(
            'MATCH (n{name:"Example"})-[d:`PARENT`]->() RETURN COUNT(d)') \
                .evaluate()
        self.assertEquals(notexamplechildren, 0)
        examplechildren = self.graph.run(
            'MATCH (n{name:"Example"})<-[d:`PARENT`]-() RETURN COUNT(d)') \
                .evaluate()
        self.assertEquals(examplechildren, 6)


def suite():
    suite = TestSuite()
    for test_class in (ExampleTestCase, ModExampleTestCase):
        tests = TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    return suite

