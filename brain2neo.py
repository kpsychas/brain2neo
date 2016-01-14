import xml.etree.ElementTree as ET

from py2neo import Graph, Node, Relationship

import HTMLParser

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
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

def store2neo(root):
    # This imports the Graph class from py2neo and creates a instance
    # bound to the default Neo4j server URI, http://localhost:7474/db/data/.
    graph = Graph()

    cypher = graph.cypher
    results = cypher.execute("MATCH (n) RETURN n IS NULL AS isEmpty LIMIT 1;")
    if results.one is not None:
        raise Exception('Graph is not empty')

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

        # ignore forgotten thoughts
        if not forgotten:
            try:
                name = h.unescape(name)
            except:
                print('Unsuccessful decoding of {} of type {} and length {}'.
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

def main():
    tree = ET.parse('example.xml')
    root = tree.getroot()

    store2neo(root)

if __name__ == '__main__':
    main()