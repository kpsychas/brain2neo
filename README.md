About
=====

This project is a tool for converting XML documents exported from
[The Brain](http://www.thebrain.com/) application to a 
[Neo4j](http://neo4j.com/) database.

An example XML is given in example.xml.
It can be imported even in the free version of The Brain,
although it cannot be exported again.

The specification of exported XML can be found 
[here](http://www.thebrain.com/dtd/BrainData1.dtd). 
Some notes on how script converts XML to database format are
given in REFERENCE.txt.

The script was tested for TheBrain version 8.0.2.1 and Neo4j 2.3.1
If things don't work for other versions consider submitting an issue
or a pull request with a fix. 
