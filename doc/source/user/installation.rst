Installation
------------

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
