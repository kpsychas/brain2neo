About
=====

This project is a tool for converting XML documents exported from
[The Brain](http://www.thebrain.com/) application to a 
[Neo4j](http://neo4j.com/) database.

An example XML is given in `src/data/example.xml`.
It can be imported in the free version of The Brain,
although it cannot be exported again.

The specification of exported XML can be found 
[here](http://www.thebrain.com/dtd/BrainData1.dtd). 
Some notes on how script converts XML to database format are
given in REFERENCE.md.

The script was tested for TheBrain version 8.0.2.1 and Neo4j 2.3.1
If things don't work for other versions consider submitting an issue
or a pull request with a fix. 

Quick Demo
----------
1. Edit the following line in `src/data/example.cfg`

    	neo4j_uri = http://localhost:7474/db/data/

	to respective URI of your database. Include any credentials in URI like
	what is described in [py2neo documentation](http://py2neo.org/2.0/essentials.html)

2. While being in src folder run

		$ python brain2neo.py

3. Access database using the web interface or any other preferred UI and `src/data/example.xml`
using the import feature of [The Brain](http://www.thebrain.com/) app to make a comparison.