.. image:: https://travis-ci.org/enthought/enstaller.png
  :target: https://travis-ci.org/enthought/enstaller

.. image:: https://coveralls.io/repos/enthought/enstaller/badge.png?branch=master
  :target: https://coveralls.io/r/enthought/enstaller?branch=master


The Enstaller (version 4) project is a package management and installation
tool for egg-based Python distributions.

It supports python >= 2.6 and python >= 3.3, as well as pypi.

Installation
============

The preferred and easiest way to install enstaller on any platform is to
download the
`bootstrap.py
<https://s3.amazonaws.com/enstaller-assets/enstaller/bootstrap.py>`_
script and then execute it with the python interpreter::

   $ python bootstrap.py
   enstaller-4.7.5-1.egg                              [installing egg]
      4.34 MB [......................................................]

If you already have an enstaller egg, you can use the bootstrap script
offline::

   $ python bootstrap.py enstaller-4.7.3-py2.7.egg
   enstaller-4.7.3-1.egg                              [installing egg]
      4.31 MB [......................................................]

or request a specific version::

   $ python bootstrap.py -l
   4.6.5-1
   4.7.5-1
   4.7.6-1
   $ python bootstrap.py --version 4.6.5-1
   enstaller-4.6.5-1.egg                             [installing egg]
      766 KB [......................................................]

Once Enstaller is installed, it can update itself.  Note that, as Enstaller is
the install tool for Canopy and EPD, those products already include enstaller.
The bootstrap script may be used to repair broken environments where enpkg is
not usable anymore.

Installing a dev version
------------------------

To install a dev version, you should do as follows::

    # Build an egg compatible with Enthought format
    $ python setup.py bdist_enegg

    # Install it
    $ python scripts/bootstrap.py dist/<produced_egg>

Available features
==================

Enstaller consists of the sub-packages enstaller (package management tool) and
egginst (package (un)installation tool).

enstaller
---------

enstaller is a management tool for egginst-based installs. The CLI, called
enpkg, calls out to egginst to do the actual installation. Enpkg is concerned
with resolving dependencies, managing user configuration and fetching eggs
reliably.

egginst
-------

egginst is the underlying tool for installing and uninstalling eggs. It
installs modules and packages directly into site-packages, i.e.  no .egg
directories are created.
