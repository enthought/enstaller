.. image:: https://travis-ci.org/enthought/enstaller.png
  :target: https://travis-ci.org/enthought/enstaller

.. image:: https://coveralls.io/repos/enthought/enstaller/badge.png?branch=master
  :target: https://coveralls.io/r/enthought/enstaller?branch=master


The Enstaller (version 4) project is a package management and installation
tool for egg-based Python distributions.

Installation
============

The preferred and easiest way to install Enstaller is from the executable egg,
i.e. the Enstaller egg contains a bash header and on Unix systems you can
download the egg and type::

   $ bash enstaller-4.6.1-1.egg
   Bootstrapping: ...
   283 KB [.................................................................]

Once Enstaller is installed, it can update itself.  Note that,
as Enstaller is the install tool for the Enthought Python Distribution (EPD),
all EPD installers already include Enstaller.

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
