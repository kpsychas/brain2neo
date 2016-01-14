Conversion between formats
--------------------------

Thoughts are converted to Nodes and Links to Relationships
if certain conditions are satisfied.

Regular Thoughts (isType = 0) will be converted to Nodes.
Thought name (name tag) will be converted to Node named attribute
"name: <name>".

Any linked types (isType = 1) and labels
(isType = 3) will be added as unnamed attributes.

If Thought is forgotten (forgottenDateTime exists) Thought will be ignored.

Links connecting Thoughts added as Nodes will be converted to Relationships.
Links will be named after the name that appears on the link in The Brain App.
If there is no name parent child links (dir=1 or dir=2)
will have Relationship name CHILD or RELATED in a different case (dir=3).
Relationships must have a name in Neo4j.

Direction is always from parent to child (dir=1 or dir=2)
or inferred from link attributes (isBackward, idA, idB)
in a different case (dir=3).
Relationships must have a direction in Neo4j.

Database configuration
----------------------
Currently there is no support for database customization and it is assumed that
Neo4j uses the default URL assuming no authorization.
By default authorization is required in Neo4j and shouldn't be disabled
if network is insecure.
More [here](http://neo4j.com/docs/stable/security-server.html).

One can edit line

    graph = Graph()

to

    graph = Graph("http://<user>:<pass>@<IP>:<port>/db/data/")

where all fields in brackets should be replaced with their respective values.

Database must have no Nodes initially.