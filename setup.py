#!/usr/bin/env python
#_____________________________________________________________________________
#
# This file is part of gimp-captcha, a Gimp Python program for creating
# CAPTCHAs.
#
# :authors: Isis Lovecruft <isis@patternsinthevoid.net> 0xA3ADB67A2CDB8B35 
#           Darrin Thompson
# :copyright: (c) 2014 Isis Lovecruft
#             (c) 2013 Darrin Thompson
#             (c) 2013 SpiderOak, Inc.
# :license: see LICENSE for licensing information
#_____________________________________________________________________________

from __future__ import print_function

import os
import setuptools

# setup automatic versioning (see top-level versioneer.py file):
import versioneer
versioneer.versionfile_source = 'gimp-captcha/_version.py'
versioneer.versionfile_build = 'gimp-captcha/_version.py'

# when creating a release, tags should be prefixed with 'gimp-captcha-', like so:
#
#     git checkout -b release-6.6.6 develop
#     [do some stuff, merge whatever, test things]
#     git tag -S gimp-captcha-6.6.6
#     git push origin --tags
#     git checkout master
#     git merge -S --no-ff gimp-captcha-6.6.6
#     git checkout develop
#     git merge -S --no-ff master
#     git branch -d gimp-captcha-6.6.6
#
versioneer.tag_prefix = 'gimp-captcha-'
# source tarballs should unpack to a directory like 'gimp-captcha-6.6.6'
versioneer.parentdir_prefix = 'gimp-captcha-'

def get_cmdclass():
    """Get our cmdclass dictionary for use in setuptool.setup().

    This must be done outside the call to setuptools.setup() because we need
    to add our own classes to the cmdclass dictionary, and then update that
    dictionary with the one returned from versioneer.get_cmdclass().
    """
    cmdclass = {}
    cmdclass.update(versioneer.get_cmdclass())
    return cmdclass

def get_requirements():
    """Extract the list of requirements from our requirements.txt.

    :rtype: 2-tuple
    :returns: Two lists, the first is a list of requirements in the form of
        pkgname==version. The second is a list of URIs or VCS checkout strings
        which specify the dependency links for obtaining a copy of the
        requirement.
    """
    requirements_file = os.path.join(os.getcwd(), 'requirements.txt')
    requirements = []
    links=[]
    try:
        with open(requirements_file) as reqfile:
            for line in reqfile.readlines():
                line = line.strip()
                if line.startswith('#'):
                    continue
                elif line.startswith(
                        ('https://', 'git://', 'hg://', 'svn://')):
                    links.append(line)
                else:
                    requirements.append(line)

    except (IOError, OSError) as error:
        print(error)

    return requirements, links


#requires, deplinks = get_requirements()

setuptools.setup(
    name='gimp-captcha',
    version=versioneer.get_version(),
    description='Gimp Python plugin for CAPTCHA generation',
    author='Isis Lovecruft',
    author_email='isis at patternsinthevoid dot net',
    maintainer='Isis Lovecruft',
    maintainer_email='isis at patternsinthevoid dot net 0xA3ADB67A2CDB8B35',
    url='https://github.com/isislovecruft/gimp-captcha',
    download_url='https://github.com/isislovecruft/gimp-captcha',
    packages=['gimp-captcha'],
    scripts=['make-captchas'],
    cmdclass=get_cmdclass(),
    #install_requires=requires,
    #dependency_links=deplinks,
)
