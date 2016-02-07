About
-----

This project is a tool for converting XML documents exported from
[`The Brain`](http://www.thebrain.com/) application to a
[`Neo4j`](http://neo4j.com/) database.

Motivation
----------
`The Brain` provides a nice user interface to create modify and navigate between thoughts,
which can be anything from quotes or ideas to songs, movies or people. Querying capabilities
on the other hand are limited so one cannot find e.g. How many thoughts of certain type
(e.g. songs) are there in the visualization. `Neo4j` can do that and even more, provided
the user has created the appropriate connections while creating the brain file (e.g. order singers by the number of their songs in database).

Quick Demo
----------
1. Edit the following line in `brain2neo/example/example.cfg`

    	neo4j_uri = http://localhost:7474/db/data/

	to respective URI of your database (should be empty initially). 
	Include any credentials in URI like what is described in 
	[py2neo documentation](http://py2neo.org/2.0/essentials.html)

2. Run your database server

3. Run the script in any of the following ways

	* While being in brain2neo folder run

		$ python brain2neo.py -f example/example.xml

	* While being in project's root folder run

    	$ python run_brain2neo.py -f brain2neo/example/example.xml

	* While being in project's root folder run

    	$ python -m brain2neo -f brain2neo/example/example.xml

4. Access database using the web interface or any other preferred UI and
`brain2neo/example/example.xml` using the import feature of
[The Brain](http://www.thebrain.com/) app to make a comparison.

The script was tested for TheBrain version 8.0.2.1 and Neo4j 2.3.1
If things don't work for other versions consider submitting an issue
or a pull request with a fix.


Install
-------
Install brain2neo as a command-line application in any of the following ways.

* Use pip:

		$ pip install brain2neo

* After cloning the repository and while being in project's root folder run

		$ python setup.py install

Then the following command runs the main script of demo above

	$ brain2neo -f <path_to_xml>

About Brain XML
---------------
An example XML is given in `brain2neo/example/example.xml`.
It can be imported in the free version of The Brain,
although it cannot be exported again.

The specification of exported XML can be found
[here](http://www.thebrain.com/dtd/BrainData1.dtd).
Some notes on how script converts XML to database format are
given in REFERENCE.md.


License
-------
This software is licensed under the [`BSD License`](http://www.opensource.org/licenses/bsd-license.php).