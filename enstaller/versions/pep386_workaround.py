from .pep386 import IrrationalVersionError, NormalizedVersion


def normalize_version_string(version_string):
    """
    Normalize the given version string to a string that can be converted to
    a NormalizedVersion.

    This function applies various special cases needed for EPD/Canopy and not
    handled in NormalizedVersion parser.

    Parameters
    ----------
    version_string: str
        The version to convert

    Returns
    -------
    normalized_version: str
        The normalized version string. Note that this is not guaranteed to be
        convertible to a NormalizedVersion
    """
    # This hack makes it possible to use 'rc' in the version, where
    # 'rc' must be followed by a single digit.
    version_string = version_string.replace('rc', '.dev99999')
    # This hack allows us to deal with single number versions (e.g.
    # pywin32's style '214').
    if not "." in version_string:
        version_string += ".0"

    if version_string.endswith(".dev"):
        version_string += "1"
    return version_string
