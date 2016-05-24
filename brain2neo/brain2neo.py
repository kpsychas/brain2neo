#!/usr/bin/env python

import os
import operator as op
import logging as log

from pkg_resources import resource_filename

import xml.etree.ElementTree as ET

from py2neo import Graph, Node, Relationship
from py2neo.packages.httpstream.http import SocketError
from configobj import ConfigObj, flatten_errors
from validate import Validator

import HTMLParser

# use to convert HTML to text, used for support of non-ascii characters
h = HTMLParser.HTMLParser()
logger = log.getLogger('brain2neo')


def chunks(l, n):
    ''' Yield successive n-sized chunks from l. '''
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def create_entities(graph, entities):
    entities_v = entities.values()

    s = 1
    batch_size = 100
    logger.debug('Batch size: {}'.format(batch_size))
    for entities_batch in chunks(entities_v, batch_size):
        logger.debug('Batch: {}-{}'.format(s, s + len(entities_batch) - 1))
        s += batch_size
        graph.create(reduce(op.or_, entities_batch))


def update_type(id1, id2, types, nodes):
    if id1 in types and id2 in nodes:
        nodes[id2].add_label(types[id1])
    elif id2 in types and id1 in nodes:
        nodes[id1].add_label(types[id2])


def is_private(accesscontrol_type):
    return accesscontrol_type == '1'


def ignore_thought(thought, cfg):
    # ignore forgotten thoughts or private thoughts if configuration
    # requires it
    forgotten = thought.find('forgottenDateTime') is not None
    accesscontrol_type = thought.find('accessControlType').text

    ignore_private = cfg['Convert']['ignore_private']
    ignore_forgotten = cfg['Convert']['ignore_forgotten']

    return (forgotten and ignore_forgotten) \
        or (is_private(accesscontrol_type) and ignore_private)


def braindir(direction):
    if direction == '1':
        return 'parent_to_child'
    elif direction == '2':
        return 'child_to_parent'
    else:
        return 'sibling'


def linkname(h, name, upper_linknames):
    if upper_linknames:
        return h.unescape(name).upper()
    else:
        return h.unescape(name)


def is_treedir(direction):
    return direction == '1' or direction == '2'


def is_siblingdir(direction):
    return direction == '3'


def is_backwardlink(link):
    return link.find('isBackward').text == '1'


def is_directedlink(link):
    # if 2 link can be traversed both ways in the Brain,
    # but not when 3 (in Neo4j there is no difference)
    strength = link.find('strength').text
    return strength == '2' or strength == '3'


def is_2waylink(link):
    direction = link.find('dir').text
    return is_siblingdir(direction) and not is_directedlink(link)


def is_2waymode(siblmode):
    return siblmode == '2way'


def is_linktype(link):
    return link.find('isType').text == '1'


def is_thoughttype(thought):
    # 1 type, 3 label, 2?
    return thought.find('isType').text != '0'


def get_graph(cfg):
    neo4j_uri = cfg['Neo4j']['neo4j_uri']

    try:
        if neo4j_uri != '':
            return Graph(neo4j_uri)
        else:
            return Graph()
    except SocketError:
        fatal_error('SocketError, there is likely no '
                    'active connection to database.')


def is_empty(graph):
    logger.info('Verifying provided database is empty.')
    results = graph.run('MATCH (n) RETURN n IS NULL AS isEmpty LIMIT 1;')

    return results.evaluate() is None


def verify_empty(graph):
    if not is_empty(graph):
        logger.warn('Provided database graph is not empty. '
                    'Choose another one.')
        app_exit(0)


def is_url(attachment_type):
    return attachment_type == '3'


def is_path(attachment_type):
    return attachment_type == '2'


def ignore_attachments(cfg):
    return cfg['Convert']['ignore_attachments']


def parse_attachments(root, nodes, cfg):
    '''
    attachment attributes - only attributes with * are parsed
    --------------------------------------------------------------------------
    | name                 | explanation                                     |
    --------------------------------------------------------------------------
    | guid                 | unique id                                       |
    | AttachmentEntries    | objects with associated entry information       |
    | objectID*            | guid of associated thought                      |
    | name                 | attachment name                                 |
    | attachmentType*      | type of attachment (2 path, 3 URL)              |
    | location*            | url or path or other                            |
    | dataLength           | 0 for url or path attachment                    |
    | format               | file extension                                  |
    | creationDateTime     | timestamp                                       |
    | modificationDateTime | timestamp                                       |
    | deletedDateTime      | timestamp                                       |
    --------------------------------------------------------------------------
    '''

    if ignore_attachments(cfg):
        return

    attachments = root.find('Attachments').findall('Attachment')

    logger.info('Parsing Attachments.')
    for attachment in attachments:
        attachment_type = attachment.find('attachmentType').text
        location = attachment.find('location').text
        object_id = attachment.find('objectID').text

        if is_url(attachment_type):
            nodes[object_id].properties['URL'] = location
        elif is_path(attachment_type):
            nodes[object_id].properties['path'] = location


def parse_thoughts(root, cfg):
    '''
    thought attributes - only attributes with * are parsed
    --------------------------------------------------------------------------
    | name                        | explanation                              |
    --------------------------------------------------------------------------
    | guid*                       | unique id                                |
    | name*                       | thought name                             |
    | label                       | Non empty for types and labels,          |
    |                             | same as name                             |
    | creationDateTime            | timestamp                                |
    | realModificationDateTime    | timestamp                                |
    | displayModificationDateTime | timestamp                                |
    | forgottenDateTime           | timestamp                                |
    | deletedDateTime             | timestamp                                |
    | activationDateTime          | timestamp                                |
    | linksModificationDateTime   | timestamp                                |
    | isType*                     | type of thought(not boolean)             |
    | color                       | color of thought in the Brain            |
    | accessControlType*          | is thought private                       |
    --------------------------------------------------------------------------
    '''

    thoughts = root.find('Thoughts').findall('Thought')
    # nodes is a dictionary of Node values with keys guid values
    nodes = {}
    # types is a dictionary of thought type names with keys guid values
    types = {}

    logger.info('Parsing Thoughts.')
    for thought in thoughts:
        name = thought.find('name').text
        guid = thought.find('guid').text

        # ignore forgotten thoughts
        if not ignore_thought(thought, cfg):
            try:
                name = h.unescape(name)
            except:
                log.error('Unsuccessful decoding of {} of type {}'
                          'and length {}.'.format(name, type(name), len(name)))
                raise

            if is_thoughttype(thought):
                types[guid] = name
            else:
                nodes[guid] = Node(name=name)

    return nodes, types


def parse_linktypes(root, cfg):
    upper_linknames = cfg['Convert']['upper_linknames']

    links = root.find('Links').findall('Link')

    # linktypes is a dictionary of link type names with keys guid values
    linktypes = {}

    h = HTMLParser.HTMLParser()

    logger.info('Parsing Link Types.')
    for link in links:
        guid = link.find('guid').text
        name = link.find('name').text

        if is_linktype(link):
            linktypes[guid] = linkname(h, name, upper_linknames)

    return linktypes


def get_relationname(link, linktypes, cfg):
    upper_linknames = cfg['Convert']['upper_linknames']
    treeneoname = cfg['Convert']['tree_neoname']
    siblneoname = cfg['Convert']['sibl_neoname']

    name = link.find('name').text
    link_typeid = link.find('linkTypeID').text
    direction = link.find('dir').text

    if name is not None:
        return linkname(h, name, upper_linknames)
    elif link_typeid is not None:
        return linktypes[link_typeid]
    elif is_treedir(direction):
        return treeneoname
    elif is_siblingdir(direction):
        return siblneoname


def get_order(link, cfg):
    treeneodir = cfg['Convert']['tree_neodir']

    ida = link.find('idA').text
    idb = link.find('idB').text
    direction = link.find('dir').text

    if is_treedir(direction):
        # is configured direction of tree links the same as the direction
        # of particular link
        if braindir(direction) == treeneodir:
            return ida, idb
        else:
            return idb, ida
    elif is_siblingdir(direction):
        if not is_backwardlink(link):
            return ida, idb
        else:
            return idb, ida
    else:
        return None, None  # link is type


def parse_regularlinks(root, linktypes, nodes, types, cfg):
    '''
    link attributes - only attributes with * are parsed
    --------------------------------------------------------------------------
    | name                 | explanation                                     |
    --------------------------------------------------------------------------
    | guid*                | unique id                                       |
    | idA*                 | guid of first thought                           |
    | idB*                 | guid of second thought                          |
    | dir*                 | direction of link (parent-child, sibling)       |
    | name*                | name of link                                    |
    | labelForward         | ? (empty by default)                            |
    | labelBackward        | ? (empty by default)                            |
    | creationDateTime     | timestamp                                       |
    | modificationDateTime | timestamp                                       |
    | deletedDateTime      | timestamp                                       |
    | followDateTime       | timestamp                                       |
    | isType*              | is link a type                                  |
    | color                | color of link in the Brain                      |
    | thickness            | ? (0 by default)                                |
    | meaning              | 2 if link between labels, 1 otherwise           |
    | linkTypeID*          | guid of associated type  if any                 |
    --------------------------------------------------------------------------
    '''

    links = root.find('Links').findall('Link')

    # relationships is a dictionary of Relationship values
    # with keys guid values
    relationships = {}

    mode2way = is_2waymode(cfg['Convert']['sibl_mode'])

    logger.info('Parsing Regular Links.')
    for link in links:
        # ignore type links
        if is_linktype(link):
            continue

        # decide relation name
        rel_type = get_relationname(link, linktypes, cfg)

        # decide order of connected thoughts
        id1, id2 = get_order(link, cfg)

        guid = link.find('guid').text
        try:
            relationships[guid] = Relationship(nodes[id1], rel_type,
                                               nodes[id2])
            if (is_2waylink(link) and mode2way):
                relationships[guid+'-B'] = Relationship(nodes[id2], rel_type,
                                                        nodes[id1])
        except KeyError:
            # might occur for ignored thoughts or connections with types
            update_type(id1, id2, types, nodes)

    return relationships


def store2neo(root, cfg):
    # Creates a py2neo Graph object (does not connect to db yet)
    graph = get_graph(cfg)

    verify_empty(graph)

    nodes, types = parse_thoughts(root, cfg)

    parse_attachments(root, nodes, cfg)

    linktypes = parse_linktypes(root, cfg)

    relationships = parse_regularlinks(root, linktypes, nodes, types, cfg)

    logger.info('Creating graph entities.')
    logger.info('Creating {} nodes.'.format(len(nodes)))
    create_entities(graph, nodes)
    logger.info('Creating {} relationships.'.format(len(relationships)))
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
        raise ValueError('Configuration file is the same as specification '
                         'file: {}.'.format(cfgspecfile))

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
                         'specification {}'.format(cfgfile, cfgspecfile))


def get_cfg(xmlfile):
    # get name, ignore extension
    f, _ = os.path.splitext(xmlfile)
    cfgfile = '{}.cfg'.format(f)
    cfgspecfile = resource_filename(__name__,
                                    os.path.join('spec', 'specification.cfg'))

    if not os.path.isfile(cfgfile):
        logger.warn('Warning configuration file {} does not exist'
                    .format(cfgfile))
        logger.warn('Generating empty configuration file {} '
                    '(=default behavior)'.format(cfgfile))

        # try to create file (can fail due to any kind of race condition)
        try:
            open(cfgfile, 'a').close()
        except IOError as e:
            logger.error('I/O error({0}) while generating {2}: {1}'
                         .format(e.errno, e.strerror, cfgfile))
            raise

    return get_cfgobj(cfgfile, cfgspecfile)


def get_root(xmlfile):
    tree = ET.parse(xmlfile)
    return tree.getroot()


def fatal_error(*messages):
    for m in messages:
        logger.error(m)
    app_exit(1)


def app_exit(status):
    logger.info('Exiting...')
    exit(status)


def setup_logging(args):
    if args.verbose == 2:
        logger.setLevel(log.DEBUG)
    elif args.verbose == 1:
        logger.setLevel(log.INFO)
    else:
        logger.setLevel(log.WARN)

    sh = log.StreamHandler()
    formatter = log.Formatter('%(name)s - %(message)s')
    sh.setFormatter(formatter)
    logger.addHandler(sh)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='Brain XML file to be parsed',
                        required=True)
    parser.add_argument('-v', '--verbose', action='count',
                        help='increase output verbosity')

    args = parser.parse_args()

    setup_logging(args)

    xmlfile = args.file
    logger.info('Getting root element from XML {}.'.format(xmlfile))
    try:
        root = get_root(xmlfile)
    except ET.ParseError as e:
        fatal_error('Error while parsing {0}: {1}'.format(xmlfile, e))
    except IOError as e:
        fatal_error('I/O error({0}): {1}'.format(e.errno, e.strerror))

    logger.info('Getting configuration of XML {}.'.format(xmlfile))
    try:
        cfg = get_cfg(xmlfile)
    except IOError as e:
        fatal_error('I/O error({0}): {1}'.format(e.errno, e.strerror))

    store2neo(root, cfg)


if __name__ == '__main__':
    main()
