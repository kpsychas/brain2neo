#!/usr/bin/env python

import os
import logging as log

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

    s = 1
    batch_size = 100
    log.debug('Batch size: {}'.format(batch_size))
    for entities_batch in chunks(entities_v, batch_size):
        log.debug('Batch: {}-{}'.format(s, s + len(entities_batch) - 1))
        s += batch_size
        graph.create(*entities_batch)

def updateRelationship(id1, relType, id2, guid, nodes, types, relationships):
    if id1 in types and id2 in nodes:
        nodes[id2].labels.add(types[id1])
    if id2 in types and id1 in nodes:
        nodes[id1].labels.add(types[id2])
    else:
        try:
            relationships[guid] = Relationship(nodes[id1], relType, nodes[id2])
        except KeyError:
            # might occur for ignored thoughts or connections between types
            pass

def ignore(forgotten, accessControlType, cfg):
    # ignore forgotten thoughts or private thoughts if configuration
    # requires it
    ignore_private = cfg['Convert']['ignore_private']
    ignore_forgotten = cfg['Convert']['ignore_forgotten']

    return (forgotten and ignore_forgotten) \
        or (accessControlType == '1' and ignore_private)

def tree_braindir(dir):
    if dir == '1':
        return 'parent_to_child'
    elif dir == '2':
        return 'child_to_parent'
    else:
        return 'sibling'

def linkname(h, name, upper_linknames):
    if upper_linknames:
        return h.unescape(name).upper()
    else:
        return h.unescape(name)


def is_treelink(dir):
    return dir == '1' or dir == '2'

def is_siblinglink(dir):
    return dir == '3'

def is_backwardlink(isBackward):
    return isBackward == '1'

def is_directedlink(strength):
    # if 2 link can be traversed both ways in the Brain,
    # but not when 3 (in Neo4j there is no difference)
    return strength == '2' or strength == '3'

def is_2waymode(siblmode):
    return siblmode == '2way'

def is_linktype(isType):
    return isType == '1'

def store2neo(root, cfg):
    neo4j_uri = cfg['Neo4j']['neo4j_uri']
    treeneodir = cfg['Convert']['tree_neodir']
    treeneoname = cfg['Convert']['tree_neoname']
    siblneoname = cfg['Convert']['sibl_neoname']
    siblmode = cfg['Convert']['sibl_mode']
    upper_linknames = cfg['Convert']['upper_linknames']

    # Creates a py2neo Graph object (does not connect to db yet)
    if neo4j_uri != '':
        graph = Graph(neo4j_uri)
    else:
        graph = Graph()

    try:
        # TODO in case there is an active connection during the lifetime of
        # this object better close it after first query
        cypher = graph.cypher
    except SocketError as e:
        log.error('SocketError, there is likely no active connection to database.')
        app_exit(1)

    log.info('Verifying provided database is empty.')
    results = cypher.execute("MATCH (n) RETURN n IS NULL AS isEmpty LIMIT 1;")
    if results.one is not None:
        log.warn('Provided database graph is not empty. Choose another one.')
        app_exit(0)

    thoughts = root.find('Thoughts').findall('Thought')
    # use to convert HTML to text, used for support of non-ascii characters
    h = HTMLParser.HTMLParser()
    # nodes is a dictionary of Node values with keys guid values
    nodes = {}
    # types is a dictionary of thought type names with keys guid values
    types = {}

    log.info('Parsing Thoughts.')
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
                log.error('Unsuccessful decoding of {} of type {} and length {}.'.
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

    # ignored link attributes
    # --------------------------------------------------------------------------
    # | name                 | explanation                                     |
    # --------------------------------------------------------------------------
    # | labelForward         | ? (empty by default)                            |
    # | labelBackward        | ? (empty by default)                            |
    # | creationDateTime     | timestamp                                       |
    # | modificationDateTime | timestamp                                       |
    # | color                | color of link in the Brain                      |
    # | thickness            | ? (0 by default)                                |
    # | meaning              | 2 if link between labels, 1 otherwise           |
    # --------------------------------------------------------------------------

    log.info('Parsing Link Types.')
    for link in links:
        isType = link.find('isType').text
        guid = link.find('guid').text
        name = link.find('name').text

        if is_linktype(isType):
            linktypes[guid] = linkname(h, name, upper_linknames)

    log.info('Parsing Links.')
    for link in links:
        # ignore type links
        isType = link.find('isType').text
        if isType == '1':
            continue

        guid = link.find('guid').text
        idA = link.find('idA').text
        idB = link.find('idB').text
        dir = link.find('dir').text
        name = link.find('name').text
        strength = link.find('strength').text
        linkTypeID = link.find('linkTypeID').text

        # decide name
        if name is not None:
            relType = linkname(h, name, upper_linknames)
        elif linkTypeID is not None:
            relType = linktypes[linkTypeID]
        elif is_treelink(dir):
            relType = treeneoname
        elif is_siblinglink(dir):
            relType = siblneoname

        # decide direction
        treebraindir = tree_braindir(dir)
        if is_treelink(dir):
            if treebraindir == treeneodir:
                id1, id2 = idA, idB
            else:
                id1, id2 = idB, idA
        elif is_siblinglink(dir):
            isBackward = link.find('isBackward').text
            if not is_backwardlink(isBackward):
                id1, id2 = idA, idB
            else:
                id1, id2 = idB, idA
        else:
            # dir=0 when isType is 1
            continue

        updateRelationship(id1, relType, id2, guid, nodes, types, relationships)
        if (is_siblinglink(dir) and not is_directedlink(strength) and
                is_2waymode(siblmode)):
            backguid = '{}-B'.format(guid)
            updateRelationship(id2, relType, id1, backguid, nodes, types,
                               relationships)

    log.info('Creating graph entities.')
    log.info('Creating {} nodes.'.format(len(nodes)))
    create_entities(graph, nodes)
    log.info('Creating {} relationships.'.format(len(relationships)))
    create_entities(graph, relationships)


def print_validation_errors(config, res):
    for entry in flatten_errors(config, res):
        # each entry is a tuple
        section_list, key, error = entry
        if key is not None:
            section_list.append(key)
        else:
            section_list.append('[missing section]')
        section_string = ', '.join(section_list)
        if error is False:
            error = 'Missing value or section.'
        log.error('{} = {}'.format(section_string, error))


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
        print_validation_errors(config, res)
        raise ValueError('Failed to validate file {} using '
                         'specification {}'.format(cfgfile,
                                                   cfgspecfile))


def get_cfg(xmlfile):
    f, ext = os.path.splitext(xmlfile)
    cfgfile = '{}.cfg'.format(f)
    cfgspecfile = resource_filename(__name__,
                                    os.path.join('spec', 'specification.cfg'))

    if not os.path.isfile(cfgfile):
        log.warn('Warning configuration file {} does not exist'.format(cfgfile))
        log.warn('Generating empty configuration file {} (=default behavior)'
                 .format(cfgfile))

        # try to create file (can fail due to any kind of race condition)
        try:
            open(cfgfile, 'a').close()
        except IOError as e:
            log.error("I/O error({0}) while generating {2}: {1}"
                      .format(e.errno, e.strerror, cfgfile))
            raise

    return get_cfgobj(cfgfile, cfgspecfile)


def get_root(xmlfile):
    tree = ET.parse(xmlfile)
    return tree.getroot()


def app_exit(status):
    log.info('Exiting...')
    exit(status)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='Brain XML file to be parsed',
                        required=True)
    parser.add_argument("-v", "--verbose", action="count",
                        help="increase output verbosity")

    args = parser.parse_args()
    xmlfile = args.file
    if args.verbose == 2:
        log.basicConfig(level=log.DEBUG)
    elif args.verbose == 1:
        log.basicConfig(level=log.INFO)
    else:
        log.basicConfig(level=log.WARN)

    try:
        log.info('Getting root element from XML {}.'.format(xmlfile))
        root = get_root(xmlfile)
    except ET.ParseError as e:
        log.error("Error while parsing {0}: {1}".format(xmlfile, e))
        app_exit(1)
    except IOError as e:
        log.error("I/O error({0}): {1}".format(e.errno, e.strerror))
        app_exit(1)

    try:
        log.info('Getting configuration of XML {}.'.format(xmlfile))
        cfg = get_cfg(xmlfile)
    except IOError as e:
        log.error("I/O error({0}): {1}".format(e.errno, e.strerror))
        app_exit(1)

    store2neo(root, cfg)

if __name__ == '__main__':
    main()