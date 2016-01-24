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

Script configuration
--------------------
Available configuration options are documented in specification.cfg
which includes their type (boolean, integer, string) and their default
value. The actual configuration is loaded from a file with extension `.cfg`
which has the same name (and is in same folder) as the corresponding 
XML file that is to be converted.

For example if we want to convert `foo.xml` to a database we should create 
a file `foo.cfg` following specification file `src/data/specification.cfg`
as template and run

    $ python brain2neo.py -f foo.xml

If `foo.cfg` does not exist an empty one will be created which behaves as
if default configuration is selected for every option.
`src/data/specification.xml` has a possible non default configuration.