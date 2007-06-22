#------------------------------------------------------------------------------
# Copyright (c) 2007, Enthought, Inc.
# All rights reserved.
#
# This software is provided without warranty under the terms of the BSD license
# available at http://www.enthought.com/licenses/BSD.txt and may be
# redistributed only under the conditions described in the aforementioned
# license.
#
# Rick Ratzel - 2006-06-21
#------------------------------------------------------------------------------

import re
from types import ListType

from enthought.traits.api import \
     HasTraits, List, Str, Bool, Property, Instance, Enum

from enthought.enstaller.api import \
     ENTHOUGHT_REPO


################################################################################
## Helper functions for converting data read from text files to Python objects
## and back to text.
################################################################################

def config_value_to_list_of_strings( self, config_value ) :
    los = re.split( r"[,\ \n]+", config_value )
    if( los == [""] ) :
        los = []
    return los

def config_value_to_bool( self, config_value ) :
    if( config_value.lower() == "true" ) :
        return True
    elif( config_value.lower() == "false" ) :
        return False

def list_of_strings_to_config_value( self, los ) :
    return ", ".join( ["%s" % s for s in los] )

def other_to_config_value( self, val ) :
    return "%s" % val



################################################################################
## The Preference family of classes.
################################################################################

class Preference( HasTraits ) :
    """
    Base class for all Enstaller preference objects.

    Each object has a specific value type, view, and help description.
    """
    #
    # The property name, derived from the class name via a property getter
    #
    name = Property

    #
    # The section in the config file, used for writing the values back to
    # the right place in the config files.
    #
    section = Str

    #
    # The descriotion, mainly used for help
    #
    description = Str

    #
    # The (short) text show to the user describing what the preference is for.
    #
    label = Str

    #
    # The actual value...type is overridden by subclasses.
    #
    value = Str

    #
    # Conversion functions (overridden in subclasses):
    # Convert to py simply returns the value (already a Py type)
    # Convert to config maps to a conversion helper function to convert the
    #  py type to a string for a config file.
    #
    convert_to_py_type = classmethod( lambda self, val: val )
    convert_to_config_type = classmethod( other_to_config_value )

    #
    # Flag indicating value was changed and needs to be saved.
    #
    modified = Bool


    def update_config( self, config_obj ) :
        """
        Updates a config object (an instance of a RawConfigParser) in the
        config section with the current value.
        """
        if( self.modified ) :
            if( not( config_obj.has_section( self.section ) ) ) :
                config_obj.add_section( self.section )
                
            config_obj.set( self.section, self.name,
                            self.convert_to_config_type( self.value ) )

            return True

        return False


    #############################################################################
    # Traits handlers, defaults, etc.
    #############################################################################

    def _get_name( self ) :
        """
        Getter for name property...examines the class name to return pref. name.
        """
        name = self.__class__.__name__
        name = name[0].lower() + name[1:]
        name = re.sub( r"([A-Z])", r"_\1", name )
        name = name.lower()
        return name


    def _value_changed( self ) :
        """
        Mark this preference object if the value changed so it can be written
        back to the config file.
        """
        self.modified = True



################################################################################
## The individual preference classes for each preference used by Enstaller.
################################################################################
        
class EasyInstallPreference( Preference ) :
    """
    Base class for all preferences for easy_install.
    """
    section = Str( "easy_install" )


class EnstallerPreference( Preference ) :
    """
    Base class for all preferences for Enstaller.
    """
    section = Str( "enstaller" )


class FindLinks( EasyInstallPreference ) :
    value = List()
    label = "Repository URLs:"
    convert_to_py_type = classmethod( config_value_to_list_of_strings )
    convert_to_config_type = classmethod( list_of_strings_to_config_value )
    description = Str( \
"""Find packages using the URLs specified in this list. The default URL, 
<%s>, is always used.
""" % ENTHOUGHT_REPO )


class AllowHosts( EasyInstallPreference ) :
    value = List( Str )
    label = "Restrict repository URLs to:"
    convert_to_py_type = classmethod( config_value_to_list_of_strings )
    convert_to_config_type = classmethod( list_of_strings_to_config_value )
    same_as_find_links = Bool
    find_links = Instance( FindLinks )
    allow_hosts_value = List( Str )
    description = Str( \
"""Restricts downloading and spidering to hosts matching the specified glob 
patterns.  For example, "*.python.org" restricts web access so that only 
packages from machines in the python.org domain are  listed and downloadable.
The glob patterns must match the entire user/host/port section of the target 
URL(s). For example, '*.python.org' does NOT allow a URL like 
'http://python.org/foo' or 'http://www.python.org:8080/'. The default pattern 
is '*', which matches anything.
""" )

    def _same_as_find_links_changed( self, old, new ) :
        if( new == True ) :
            if( len( self.allow_hosts_value ) == 0 ) :
                self.allow_hosts_value = self.value
            self.value = self.find_links.value
        else :
            self.value = self.allow_hosts_value


class AlwaysUnzip( EnstallerPreference ) :
    value = Bool
    label = "Always unzip packages:"
    convert_to_py_type = classmethod( config_value_to_bool )
    description = Str( \
"""Do not install any packages as zip files, even if the packages are marked as
safe for running as a zip file.
""" )

    
class BuildDirectory( EasyInstallPreference ) :
    value = Str
    label = "Build directory:"
    description = Str( \
"""Download/extract/build in this directory and keep the results.
""" )


class ExcludeScripts( EasyInstallPreference ) :
    value = Bool
    label = "Do not install scripts:"
    convert_to_py_type = classmethod( config_value_to_bool )
    description = Str( \
"""This option is useful if you need to install multiple versions of a package, 
but do not want to reset the version that will be run by scripts that are 
already installed.
""" )


class IndexUrl( EasyInstallPreference ) :
    value = Str
    label = "Index URL:"
    description = Str( \
"""Use this URL instead of the Python Cheese Shop as the package index.
""" )


class InstallDir( EasyInstallPreference ) :
    value = Str
    label = "Install dir:"
    description = Str( \
"""Install packages to this directory instead of the default (site-packages).
""" )


class NoDeps( EasyInstallPreference ) :
    value = False
    label = "No deps:"
    description = Str( \
"""Do not install dependencies.
""" )


class Optimize( EasyInstallPreference ) :
    value = Enum( "-O0", "-O", "-O2" )
    label = "Optimize:"
    description = Str( \
"""Install modules with optimizations (.pyo files) in addition to .pyc files.
-O0 (the default) means no optimizations, -O is the first level (minor
 optimizations), -O2 is -O with all docstrings removed as well.
""" )


class Record( EasyInstallPreference ) :
    value = Str
    label = "Record files to:"
    description = Str( \
"""Write a record of all installed files to the file specified by this option. 
This option is basically the same as the option for the standard distutils
'install' command, and is included for compatibility with tools that expect to
pass this option to 'setup.py install'.
""" )


class ScriptDir( EasyInstallPreference ) :
    value = Str
    label = "Script installation directory:"
    description = Str( \
"""This option defaults to the install directory, so that the scripts can find 
their associated package installations. Otherwise, this setting defaults to the 
location where the distutils would normally install scripts, taking any 
distutils configuration file settings into account.
""" )


class ShowAllAvailableVersions( EnstallerPreference ) :
    value = Bool
    label = "Show all available versions:"
    convert_to_py_type = classmethod( config_value_to_bool )
    description = Str( \
"""For each package, show every version that is available for installation .""" )


class ZipOk( EasyInstallPreference ) :
    value = Bool
    label = "zip OK:"
    convert_to_py_type = classmethod( config_value_to_bool )
    description = Str( \
"""Install eggs in zipped form, even if their zip_safe flag is not set.

Setting this option is generally not necessary since eggs are installed by
default in zipped form, unless their zip_safe flag is not set.

WARNING: when an egg's zip_safe flag is not set, the egg usually will not work
as a zipped egg.
""" )

