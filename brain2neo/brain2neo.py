#!/usr/bin/env python

import os

from pkg_resources import resource_filename

import xml.etree.ElementTree as ET

from py2neo import Graph, Node, Relationship
from py2neo.packages.httpstream.http import SocketError
from configobj import ConfigObj, flatten_errors
from validate import Validator

import HTMLParser


def chunks(l, n):
    """ Yield successive n-sized chunks from l. """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def create_entities(graph, entities):
    entities_v = entities.values()

    for entities_batch in chunks(entities_v, 100):
        graph.create(*entities_batch)

def updateRelationship(id1, relType, id2, guid, nodes, types, relationships):
    if id1 in types and id2 in nodes:
        nodes[id2].labels.add(types[id1])
    else:
        try:
            relationships[guid] = Relationship(nodes[id1], relType, nodes[id2])
        except KeyError:
            pass

def ignore(forgotten, accessControlType, cfg):
    # ignore forgotten thoughts or private thoughts if configuration
    # requires it
    ignore_private = cfg['Brain']['ignore_private']
    ignore_forgotten = cfg['Brain']['ignore_forgotten']

    return (forgotten and ignore_forgotten) \
        or (accessControlType == '1' and ignore_private)

def store2neo(root, cfg):
    neo4j_uri = cfg['Neo4j']['neo4j_uri']

    # Creates a py2neo Graph object (does not connect)
    if neo4j_uri != '':
        graph = Graph(neo4j_uri)
    else:
        graph = Graph()

    try:
        cypher = graph.cypher
    except SocketError as e:
        print('SocketError, there is likely no active connection to database.')
        app_exit(1)

    print('Verifying provided database is empty.')
    results = cypher.execute("MATCH (n) RETURN n IS NULL AS isEmpty LIMIT 1;")
    if results.one is not None:
        print('Provided database graph is not empty. Choose another one.')
        app_exit(0)

    thoughts = root.find('Thoughts').findall('Thought')
    # use to convert HTML to text, used for support of non-ascii characters
    h = HTMLParser.HTMLParser()
    # nodes is a dictionary of Node values with keys guid values
    nodes = {}
    # types is a dictionary of thought type names with keys guid values
    types = {}

    for thought in thoughts:
        name = thought.find('name').text
        guid = thought.find('guid').text

        isType = thought.find('isType').text
        forgotten = thought.find('forgottenDateTime') is not None
        accessControlType = thought.find('accessControlType').text

        # ignore forgotten thoughts
        if not ignore(forgotten, accessControlType, cfg):
            try:
                name = h.unescape(name)
            except:
                print('Unsuccessful decoding of {} of type {} and length {}.'.
                    format(name, type(name), len(name)))
                raise

            if isType != '0':
                types[guid] = name
            else:
                nodes[guid] = Node(name=name)

    links = root.find('Links').findall('Link')
    # relationships is a dictionary of Relationship values with keys guid values
    relationships = {}
    # linktypes is a dictionary of link type names with keys guid values
    linktypes = {}

    for link in links:
        isType = link.find('isType').text
        guid = link.find('guid').text
        name = link.find('name').text

        if isType == '1':
            linktypes[guid] = h.unescape(name).upper()

    for link in links:
        isType = link.find('isType').text
        if isType == '1':
            continue

        guid = link.find('guid').text
        idA = link.find('idA').text
        idB = link.find('idB').text
        name = link.find('name').text
        dir = link.find('dir').text
        linkTypeID = link.find('linkTypeID').text

        if name is not None:
            relType = h.unescape(name).upper()
        elif linkTypeID is not None:
            relType = linktypes[linkTypeID]
        elif dir == '1' or dir == '2':
            relType = 'CHILD'
        elif dir == '3':
            relType = 'RELATED'

        if dir == '1':
            id1, id2 = idA, idB
        elif dir == '2':
            id1, id2 = idB, idA
        elif dir == '3':
            isBackward = link.find('isBackward').text
            if isBackward == '0':
                id1, id2 = idA, idB
            else:
                id1, id2 = idB, idA
        else:
            # dir=0 when isType is 1
            continue

        updateRelationship(id1, relType, id2, guid, nodes, types, relationships)

    create_entities(graph, nodes)
    create_entities(graph, relationships)

def get_cfgobj(cfgfile, cfgspecfile):
    if cfgfile == cfgspecfile:
        raise ValueError('Configuration file is the same as specification file:'
                         ' {}.'.format(cfgspecfile))

    config = ConfigObj(cfgfile, configspec=cfgspecfile,
                       file_error=True)

    validator = Validator()
    res = config.validate(validator, preserve_errors=True)

    # res is not boolean necessarily
    if res is True:
        return config
    else:
        self.print_validation_errors(config, res)
        raise ValueError('Failed to validate file {} using '
                         'specification {}'.format(cfgfile,
                                                   cfgspecfile))


def get_cfg(xmlfile):
    f, ext = os.path.splitext(xmlfile)
    cfgfile = f + '.cfg'
    cfgspecfile = resource_filename(__name__, os.path.join('spec', 'specification.cfg'))

    if not os.path.isfile(cfgfile):
        print('Warning configuration file {} does not exist'.format(cfgfile))
        print('Generating empty configuration file {} (=default behavior)'
            .format(cfgfile))

        # try to create file (can fail due to any kind of race condition)
        try:
            open(cfgfile, 'a').close()
        except IOError as e:
            print ("I/O error({0}) while generating {2}: {1}"
                .format(e.errno, e.strerror, cfgfile))
            raise

    return get_cfgobj(cfgfile, cfgspecfile)


def get_root(xmlfile):
    tree = ET.parse(xmlfile)
    return tree.getroot()


def app_exit(status):
    print('Exiting...')
    exit(status)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='Brain XML file to be parsed',
                        required=True)

    args = parser.parse_args()
    xmlfile = args.file

    try:
        print('Getting root element from XML {}.'.format(xmlfile))
        root = get_root(xmlfile)
    except ET.ParseError as e:
        print("Error while parsing {0}: {1}".format(xmlfile, e))
        app_exit(1)
    except IOError as e:
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        app_exit(1)

    try:
        print('Getting configuration of XML {}.'.format(xmlfile))
        cfg = get_cfg(xmlfile)
    except IOError as e:
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
        app_exit(1)

    store2neo(root, cfg)

if __name__ == '__main__':
    main()