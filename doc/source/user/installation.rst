Installation
============

Installing a released version
-----------------------------

To install enstaller, simply executes the
`bootstrap.py
<https://s3.amazonaws.com/enstaller-assets/enstaller/bootstrap.py>`_
script::

   $ python bootstrap.py
   enstaller-4.7.6-py2.7.egg                          [installing egg]
      4.34 MB [......................................................]

Installing from sources
-----------------------

While you can install with the usual `setup.py install` dance, it is
advised to build enstaller and install it through the bootstrap script::

    $ python setup.py bdist_enegg # build dist/enstaller-<version>.egg
    $ python scripts/bootstrap.py dist/enstaller-<version>.egg

..note:: you can safely reinstall various versions of enstaller by
         re-executing the boostrap script, as it ensures the old enstaller
         is removed before installing the new one.

Testing the installation
------------------------

The main CLI tool available is ``enpkg``, which is used to install
packages with their dependencies::

    enpkg <requirement>

``enpkg`` uses the file ``~/.enstaller4rc`` to store credentials, and various
configuration settings.
