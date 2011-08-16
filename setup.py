#!/usr/bin/env python

from distutils.core import setup

version = '0.01'

data = dict(
    name =          'HouseAgent',
    version =       version,
    url =           'http://projects.maartendamen.com/projects/houseagent',
    download_url =  'https://github.com/maartendamen/HouseAgent/tarball/master',
    description =   'HouseAgent is a multi platform, open source home automation application.',
    author =        'Maarten Damen',
    author_email =  'm.damen [at] gmail.com',
    packages =      ['houseagent','houseagent.core', 'houseagent.plugins', 'houseagent.utils', ],
    scripts =       ['HouseAgent.py'],
    data_files =    [('/etc/HouseAgent', ['HouseAgent.conf', 'specs/amqp0-8.xml'])],
    ) 


setup(**data)
