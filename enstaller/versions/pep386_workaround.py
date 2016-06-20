from egginst.vendor.okonomiyaki.versions.pep386_workaround import (
    PEP386WorkaroundVersion
)


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
    if version_string.endswith(".dev"):
        version_string += "1"
    return version_string
