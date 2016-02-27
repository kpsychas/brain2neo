#!/usr/bin/env python

import os
import logging as log

from pkg_resources import resource_filename

import xml.etree.ElementTree as ET

from py2neo import Graph, Node, Relationship, GraphError
from py2neo.packages.httpstream.http import SocketError
from configobj import ConfigObj, flatten_errors
from validate import Validator

import HTMLParser

# use to convert HTML to text, used for support of non-ascii characters
h = HTMLParser.HTMLParser()


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


def update_type(id1, id2, types, nodes):
    if id1 in types and id2 in nodes:
        nodes[id2].labels.add(types[id1])
    elif id2 in types and id1 in nodes:
        nodes[id1].labels.add(types[id2])


def is_private(accesscontrol_type):
    return accesscontrol_type == '1'


def ignore(forgotten, accesscontrol_type, cfg):
    # ignore forgotten thoughts or private thoughts if configuration
    # requires it
    ignore_private = cfg['Convert']['ignore_private']
    ignore_forgotten = cfg['Convert']['ignore_forgotten']

    return (forgotten and ignore_forgotten) \
        or (is_private(accesscontrol_type) and ignore_private)


def tree_braindir(direction):
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


def is_treelink(direction):
    return direction == '1' or direction == '2'


def is_siblinglink(direction):
    return direction == '3'


def is_backwardlink(is_backward):
    return is_backward == '1'


def is_directedlink(strength):
    # if 2 link can be traversed both ways in the Brain,
    # but not when 3 (in Neo4j there is no difference)
    return strength == '2' or strength == '3'


def is_2waymode(siblmode):
    return siblmode == '2way'


def is_linktype(is_type):
    return is_type == '1'


def is_thoughttype(is_type):
    # 1 type, 3 label, 2?
    return is_type != '0'


def get_graph(cfg):
    neo4j_uri = cfg['Neo4j']['neo4j_uri']

    if neo4j_uri != '':
        return Graph(neo4j_uri)
    else:
        return Graph()


def get_cypher(graph):
    try:
        # TODO in case there is an active connection during the lifetime of
        # this object better close it after first query
        return graph.cypher
    except SocketError as e:
        log.error('SocketError, there is likely no active connection to database.')
        app_exit(1)
    except GraphError as e:
        log.error('GraphError: {}'.format(e.message))
        log.error('If you use default user and password, try changing them')
        app_exit(1)


def is_empty(cypher):
    log.info('Verifying provided database is empty.')
    results = cypher.execute("MATCH (n) RETURN n IS NULL AS isEmpty LIMIT 1;")

    return results.one is None


def verify_empty(cypher):
    if not is_empty(cypher):
        log.warn('Provided database graph is not empty. Choose another one.')
        app_exit(0)


def is_url(attachment_type):
    return attachment_type == '3'


def is_path(attachment_type):
    return attachment_type == '2'


def parse_attachments(root, nodes):
    # attachment attributes - only attributes with * are parsed
    # --------------------------------------------------------------------------
    # | name                 | explanation                                     |
    # --------------------------------------------------------------------------
    # | guid                 | unique id                                       |
    # | AttachmentEntries    | objects with associated entry information       |
    # | objectID*            | guid of associated thought                      |
    # | name                 | attachment name                                 |
    # | attachmentType*      | type of attachment (2 path, 3 URL)              |
    # | location*            | url or path or other                            |
    # | dataLength           | 0 for url or path attachment                    |
    # | format               | file extension                                  |
    # | creationDateTime     | timestamp                                       |
    # | modificationDateTime | timestamp                                       |
    # | deletedDateTime      | timestamp                                       |
    # --------------------------------------------------------------------------

    attachments = root.find('Attachments').findall('Attachment')

    log.info('Parsing Attachments.')
    for attachment in attachments:
        attachment_type = attachment.find('attachmentType').text
        location = attachment.find('location').text
        object_id = attachment.find('objectID').text

        if is_url(attachment_type):
            nodes[object_id].properties['URL'] = location
        elif is_path(attachment_type):
            nodes[object_id].properties['path'] = location


def parse_thoughts(root, cfg):
    # thought attributes - only attributes with * are parsed
    # --------------------------------------------------------------------------
    # | name                        | explanation                              |
    # --------------------------------------------------------------------------
    # | guid*                       | unique id                                |
    # | name*                       | thought name                             |
    # | label                       | Non empty for types and labels,          |
    # |                             | same as name                             |
    # | creationDateTime            | timestamp                                |
    # | realModificationDateTime    | timestamp                                |
    # | displayModificationDateTime | timestamp                                |
    # | forgottenDateTime           | timestamp                                |
    # | deletedDateTime             | timestamp                                |
    # | activationDateTime          | timestamp                                |
    # | linksModificationDateTime   | timestamp                                |
    # | isType*                     | type of thought(not boolean)             |
    # | color                       | color of thought in the Brain            |
    # | accessControlType*          | is thought private                       |
    # --------------------------------------------------------------------------

    thoughts = root.find('Thoughts').findall('Thought')
    # nodes is a dictionary of Node values with keys guid values
    nodes = {}
    # types is a dictionary of thought type names with keys guid values
    types = {}

    log.info('Parsing Thoughts.')
    for thought in thoughts:
        name = thought.find('name').text
        guid = thought.find('guid').text

        is_type = thought.find('isType').text
        forgotten = thought.find('forgottenDateTime') is not None
        accesscontrol_type = thought.find('accessControlType').text

        # ignore forgotten thoughts
        if not ignore(forgotten, accesscontrol_type, cfg):
            try:
                name = h.unescape(name)
            except:
                log.error('Unsuccessful decoding of {} of type {} and length {}.'.
                          format(name, type(name), len(name)))
                raise

            if is_thoughttype(is_type):
                types[guid] = name
            else:
                nodes[guid] = Node(name=name)

    return nodes, types


def parse_linktypes(root, cfg):
    links = root.find('Links').findall('Link')

    # linktypes is a dictionary of link type names with keys guid values
    linktypes = {}

    upper_linknames = cfg['Convert']['upper_linknames']

    h = HTMLParser.HTMLParser()

    log.info('Parsing Link Types.')
    for link in links:
        is_type = link.find('isType').text
        guid = link.find('guid').text
        name = link.find('name').text

        if is_linktype(is_type):
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
    elif is_treelink(direction):
        return treeneoname
    elif is_siblinglink(direction):
        return siblneoname


def get_order(ida, idb, link, cfg):
    treeneodir = cfg['Convert']['tree_neodir']
    direction = link.find('dir').text

    treebraindir = tree_braindir(direction)
    if is_treelink(direction):
        # is configured direction of tree links the same as the direction
        # of particular link
        if treebraindir == treeneodir:
            return ida, idb
        else:
            return idb, ida
    elif is_siblinglink(direction):
        is_backward = link.find('isBackward').text
        if not is_backwardlink(is_backward):
            return ida, idb
        else:
            return idb, ida
    else:
        # dir=0 when isType is 1
        return None, None


def parse_regularlinks(root, linktypes, nodes, types, cfg):
    # link attributes
    # --------------------------------------------------------------------------
    # | name                 | explanation                                     |
    # --------------------------------------------------------------------------
    # | guid*                | unique id                                       |
    # | idA*                 | guid of first thought                           |
    # | idB*                 | guid of second thought                          |
    # | dir*                 | direction of link (parent-child, sibling)       |
    # | name*                | name of link                                    |
    # | labelForward         | ? (empty by default)                            |
    # | labelBackward        | ? (empty by default)                            |
    # | creationDateTime     | timestamp                                       |
    # | modificationDateTime | timestamp                                       |
    # | deletedDateTime      | timestamp                                       |
    # | followDateTime       | timestamp                                       |
    # | isType*              | is link a type                                  |
    # | color                | color of link in the Brain                      |
    # | thickness            | ? (0 by default)                                |
    # | meaning              | 2 if link between labels, 1 otherwise           |
    # | linkTypeID*          | guid of associated type  if any                 |
    # --------------------------------------------------------------------------

    links = root.find('Links').findall('Link')

    # relationships is a dictionary of Relationship values with keys guid values
    relationships = {}

    siblmode = cfg['Convert']['sibl_mode']

    log.info('Parsing Regular Links.')
    for link in links:
        # ignore type links
        is_type = link.find('isType').text
        if is_linktype(is_type):
            continue

        # decide relation name
        rel_type = get_relationname(link, linktypes, cfg)

        id1 = link.find('idA').text
        id2 = link.find('idB').text

        # decide order of connected thoughts
        id1, id2 = get_order(id1, id2, link, cfg)

        if id1 is None:
            continue

        guid = link.find('guid').text
        strength = link.find('strength').text
        try:
            relationships[guid] = Relationship(nodes[id1], rel_type,
                                               nodes[id2])
        except KeyError:
            # might occur for ignored thoughts or connections with types
            update_type(id1, id2, types, nodes)

        direction = link.find('dir').text
        if (is_siblinglink(direction) and not is_directedlink(strength) and
                is_2waymode(siblmode)):
            try:
                relationships[guid+'-B'] = Relationship(nodes[id2], rel_type,
                                                        nodes[id1])
            except KeyError:
                # might occur for ignored thoughts
                pass

    return relationships


def store2neo(root, cfg):
    # Creates a py2neo Graph object (does not connect to db yet)
    graph = get_graph(cfg)

    cypher = get_cypher(graph)

    verify_empty(cypher)

    nodes, types = parse_thoughts(root, cfg)

    parse_attachments(root, nodes)

    linktypes = parse_linktypes(root, cfg)

    relationships = parse_regularlinks(root, linktypes, nodes, types, cfg)

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
    # get name, ignore extension
    f, _ = os.path.splitext(xmlfile)
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
