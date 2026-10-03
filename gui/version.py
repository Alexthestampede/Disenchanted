#!/usr/bin/env python3
"""
Disenchanted version management.

Versions use a date-based scheme: yyyymmdd.v, e.g. 20261003.1
- yyyymmdd: the date the version was created
- .v: bump counter for multiple releases on the same day (starting at 1)
"""

VERSION = "20261003.1"

APP_NAME = "Disenchanted"
GITHUB_REPO = "Alexthestampede/Disenchanted"


def version_tuple(version: str = VERSION):
    """Parse 'yyyymmdd.v' into (date_int, v)."""
    try:
        date_part, v = version.split(".", 1)
        return (int(date_part), int(v))
    except (ValueError, AttributeError):
        return (0, 0)


def is_newer(candidate: str, current: str = VERSION) -> bool:
    """True if candidate version is strictly newer than current."""
    return version_tuple(candidate) > version_tuple(current)