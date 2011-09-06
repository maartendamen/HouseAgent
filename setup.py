#!/usr/bin/env python

from distutils.core import setup
import os

version = '0.01'

def find_package_files(workingdir, subdir):
    currentDir = os.getcwd()
    # Go into the working directory
    os.chdir(workingdir)
    # Get the list of all files in the sub directory
    packageFiles = []
    for root, dirs, files in os.walk(subdir):
        fileList = []
        if files:
            for filename in files:
                if not filename.endswith('.py'):
                    fileList.append(os.path.join(root, filename))
        if fileList:
            packageFiles.extend(fileList)
    # Return back to the original directory
    os.chdir(currentDir)
    return packageFiles

# List all of the files under 'templates' since they are needed.
template_files = find_package_files('houseagent', 'templates')

data = dict(
    name =          'HouseAgent',
    version =       version,
    url =           'http://projects.maartendamen.com/projects/houseagent',
    download_url =  'https://github.com/maartendamen/HouseAgent/tarball/master',
    description =   'HouseAgent is a multi platform, open source home automation application.',
    author =        'Maarten Damen',
    author_email =  'm.damen [at] gmail.com',
    packages =      ['houseagent','houseagent.core', 'houseagent.plugins', 'houseagent.utils', 'houseagent.pages'],
    package_data =  {'houseagent': template_files},
    scripts =       ['HouseAgent.py'],
    data_files =    [('/etc/HouseAgent', ['HouseAgent.conf', 'specs/amqp0-8.xml']),
                     ('share/HouseAgent', ['houseagent.db'])],
    ) 


setup(**data)