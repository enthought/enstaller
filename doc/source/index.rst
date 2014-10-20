Welcome to enstaller's documentation!
=====================================

Enstaller is Enthought's package manager.

User Guide
----------

This part of the documentations describes the usage of enpkg and egginst,
the main tools available from enstaller.

To install enstaller, simply executes the
`bootstrap.py
<https://s3.amazonaws.com/enstaller-assets/enstaller/bootstrap.py>`_
script::

   $ python bootstrap.py
   enstaller-4.7.6-py2.7.egg                          [installing egg]
      4.34 MB [......................................................]

The main CLI tool available is ``enpkg``, which is used to install
packages with their dependencies::

    enpkg <requirement>

``enpkg`` uses the file ``~/.enstaller4rc`` to store credentials, and various
configuration settings.

.. toctree::
   :maxdepth: 1


Dev Guide
---------

This part of the documentation explains the main concepts of enstaller
from a developer POV, that is people willing to use/extend enstaller in
their application.

Enstaller is currently being rewritten as a library with enpkg being a
CLI on top of it, so the API is still in flux.

.. toctree::
   :maxdepth: 2

   examples

Reference
---------

.. toctree::
   :maxdepth: 2

   reference/transition_to_4.7.0_api.rst
   reference/api.rst
   reference/contents.rst
