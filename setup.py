#!/usr/bin/env python

import fnmatch
import glob
import os
import sys

from setuptools import setup

with open("requirements.txt") as f:
    required = f.read().splitlines()

VERSION = "1.0.2"

setup(
    name='shmooze',
    version=VERSION,
    description='Framework for processed-backed web applications',
    author='Zach Banks',
    author_email='zbanks@mit.edu',
    url='https://github.com/zbanks/shmooze',
    packages=[
        'shmooze', 
        'shmooze.wsgi', 
        'shmooze.modules', 
        'shmooze.lib', 
    ],
    download_url="https://github.com/zbanks/shmooze/tarball/{}".format(VERSION),
    zip_safe=False,
    install_requires=required,
    scripts=[
        "bin/shmooze", 
        "bin/shmz", 
    ],
    package_dir = {
    },
    package_data={
        'musicazoo': [
            "../supervisord.conf", 
            "../requirements.txt", 
            "../settings.json",
            '../static/settings.json', 
            '../static/*.js', 
            '../static/*.html', 
        ],
    },
)
