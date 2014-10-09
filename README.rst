.. image:: https://travis-ci.org/enthought/enstaller.png
  :target: https://travis-ci.org/enthought/enstaller

.. image:: https://coveralls.io/repos/enthought/enstaller/badge.png?branch=master
  :target: https://coveralls.io/r/enthought/enstaller?branch=master


The Enstaller (version 4) project is a package management and installation
tool for egg-based Python distributions.

It supports python >= 2.6 and python >= 3.3.

Installation
============

The preferred and easiest way to install enstaller on any platform is to
download
`bootstrap.py <http://s3.amazonaws.com/enstaller-assets/enstaller/bootstrap.py>`_
 and then execute it with the python interpreter::

   $ python bootstrap.py
   enstaller-4.7.5-py2.7.egg                          [installing egg]
      4.34 MB [......................................................]

Once Enstaller is installed, it can update itself.  Note that,
as Enstaller is the install tool for Canopy and EPD, those products
already include enstaller. The bootstrap script may be used to repair
broken environments where enpkg is not usable.

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
