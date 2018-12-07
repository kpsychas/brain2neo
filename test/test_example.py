#!/usr/bin/python

from unittest import TestCase, TestLoader, TestSuite

import brain2neo.brain2neo as b2n


class ExampleTestCase(TestCase):
    def setUp(self):
        xml_file = "example.xml"
        cfg = b2n.get_cfg(xml_file)
        root = b2n.get_root(xml_file)

        self.graph = b2n.get_graph(cfg)

        # empty graph
        self.graph.run('MATCH (n) DETACH DELETE n')
        self.assertTrue(b2n.is_empty(self.graph))

        b2n.store2neo(root, cfg)

    def test_nonempty(self):
        self.assertFalse(b2n.is_empty(self.graph))

    def test_nodes(self):
        n_nodes = self.graph.run('MATCH (n) RETURN COUNT (n)').evaluate()
        self.assertEquals(n_nodes, 19)

    def test_example_node(self):
        example_node = self.graph.run(
            'MATCH (n{name:"Example"}) RETURN (n)').evaluate()
        self.assertIsNotNone(example_node)

    def test_relationships(self):
        n_nodes = self.graph.run('MATCH (n)-[d]-() RETURN COUNT(d)/2') \
            .evaluate()
        self.assertEquals(n_nodes, 32)

    def test_example_relationship(self):
        example_relationship = self.graph.run(
            'MATCH (n)-[d:`BASED ON`]-() RETURN (d)').evaluate()
        self.assertIsNotNone(example_relationship)

    def test_tree_neoname(self):
        example_children = self.graph.run(
            'MATCH (n{name:"Example"})-[d:`CHILD`]->() RETURN COUNT(d)') \
                .evaluate()
        self.assertEquals(example_children, 6)
        notexample_children = self.graph.run(
            'MATCH (n{name:"Example"})<-[d:`CHILD`]-() RETURN COUNT(d)') \
                .evaluate()
        self.assertEquals(notexample_children, 0)


class ModExampleTestCase(TestCase):
    def modify_config(self, cfg):
        cfg['Convert']['ignore_attachments'] = True
        cfg['Convert']['ignore_private'] = False
        cfg['Convert']['sibl_mode'] = 'directed'
        cfg['Convert']['upper_link_names'] = True
        cfg['Convert']['tree_neoname'] = 'PARENT'
        cfg['Convert']['tree_neodir'] = 'child_to_parent'

    def setUp(self):
        xml_file = "example.xml"
        cfg = b2n.get_cfg(xml_file)
        root = b2n.get_root(xml_file)

        self.modify_config(cfg)
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

    def test_example_node(self):
        example_node = self.graph.run(
            'MATCH (n{name:"Example"}) RETURN (n)').evaluate()
        self.assertIsNotNone(example_node)

    def test_relationships(self):
        n_nodes = self.graph.run('MATCH (n)-[d]-() RETURN COUNT(d)/2') \
            .evaluate()
        self.assertEquals(n_nodes, 31)

    def test_example_relationship(self):
        example_relationship = self.graph.run(
            'MATCH (n)-[d:`BASED ON`]-() RETURN (d)').evaluate()
        self.assertIsNotNone(example_relationship)

    def test_tree_neoname(self):
        notexample_children = self.graph.run(
            'MATCH (n{name:"Example"})-[d:`PARENT`]->() RETURN COUNT(d)') \
                .evaluate()
        self.assertEquals(notexample_children, 0)
        example_children = self.graph.run(
            'MATCH (n{name:"Example"})<-[d:`PARENT`]-() RETURN COUNT(d)') \
                .evaluate()
        self.assertEquals(example_children, 6)


def test_suite():
    suite = TestSuite()
    for test_class in (ExampleTestCase, ModExampleTestCase):
        tests = TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    return suite

