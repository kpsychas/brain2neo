#!/usr/bin/env python

from setuptools import setup


setup(name='brain2neo',
      description='convert XML exported from The Brain to Neo4j database',
      keywords=['Neo4j'],
      version='1.1',
      packages=['brain2neo'],
      install_requires=[
        'configobj >= 5.0.0',
        'py2neo >= 2.0.0'
      ],
      include_package_data = True,
      entry_points={
        "console_scripts": ['brain2neo = brain2neo.brain2neo:main']
      },
      url = "https://github.com/kpsychas/brain2neo"
     )