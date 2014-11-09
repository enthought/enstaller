
Additional tools
================

Enstaller contains a set of tools beyond enpkg. We describe here how to
use those.

.. note:: Those tools are not meant to be used outside Enthought. We make
          no stability or even existence guarantee.

.. note:: repack is a rewrite of endist' build_egg -r option. Endist is
          deprecated, please contact the build team @ Enthought if you
          miss some features of endist not in repack.

Repack
------

Repack is a tool to repack eggs built by setuptools into a format
understaood by enstaller. While enstaller can install any standard egg,
converting them to the Enthought format allows you to specify dependencies
(including non-egg dependencies), etc...

Simple usage::

    # Repack the egg foo-1.0.0-py2.7.egg, with the build number 1
    python -m enstaller.tools.repack -b 1 foo-1.0.0-py2.7.egg

By default, the tool will try to detect your platform and set the egg to
this platform. If this fails, or if you want to set the platform manually,
you should use the ``-a`` flag::

    python -m enstaller.tools.repack -b 1 -a win-32 foo-1.0.0-py2.7.egg

Customizing metadata
~~~~~~~~~~~~~~~~~~~~

The repack tool supports customization of egg medata through the ``endist.dat``
file. The ``endist.dat`` is actually exec-ed, and the following variables
are understood::

    # endist.dat

    # To override the package name
    name = "foo" 
    # To override the version
    version = "1.2.3" 
    # To override the build
    build = 2

    # To add runtime dependencies
    packages = [
        "bar 1.2",
        "fubar 1.3",
    ]

    # To add files not in the original egg
    # The format is a list of triples (dir_path, regex, archive_dir),
    # where regex is the regular expression to match for files in
    # dir_path, to put in the "EGG-INFO/foo" directory inside the egg.
    add_files = [("foo", "*.txt", "EGG-INFO/foo")]
