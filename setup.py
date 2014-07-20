#!/usr/bin/env python
#
# Copyright (c) 2013, 2014 Matt Behrens <matt@zigg.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(
    name='octothorpe',
    version='0.5',
    description='Asterisk Manager Interface library for the Twisted engine',
    long_description=open('README.rst', 'r').read(),
    author='Matt Behrens',
    author_email='matt@zigg.com',
    url='http://www.zigg.com/code/octothorpe/',
    packages=['octothorpe', 'octothorpe.test'],
    requires=['Twisted'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Twisted',
        'License :: OSI Approved :: MIT License',
        'Topic :: Communications :: Telephony',
    ],
    install_requires=['Twisted'],
)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
