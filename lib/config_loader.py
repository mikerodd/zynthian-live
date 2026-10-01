# -*- coding: utf-8 -*-
"""Load the live-session gig config, splicing in the files it includes.

A gig config may list sibling config files under a top-level ``"includes"``
key, so a set of gigs can be authored once and reused by the aggregate
config instead of being copied into it::

    {
      "includes": ["config-the-spokes.json", "config-tribute-rolling-stones.json"],
      "gigs": [
        {"name": "All tracks", "tracks": [...]},
        {"name": "RSPro", "tracks": [...]}
      ]
    }

The included file is an ordinary config with its own ``"gigs"`` array; its
gigs are appended, in the order listed, after the including file's own gigs.
Keeping ``includes`` a sibling of ``gigs`` rather than an entry inside it
means the array stays a plain list of gigs: nothing has to tell a real gig
apart from an include directive.

Paths are resolved against the *including* config's directory, so
``json_filename`` inside an included gig keeps meaning the same thing it did
in the file that declared it, and no rewriting is needed when includes live
next to each other.  Only one level is followed -- an included file that has
an ``includes`` key of its own is reported and its own gigs used -- so a
cycle of configs can never loop.

A missing or malformed include is an error rather than a warning.  Silently
dropping gigs would leave a performer with a set list that quietly lost
songs, which is much worse than a loud failure.  A missing *root* config is
still reported as an empty config, which is how a device with no data
mounted keeps serving an empty page.
"""

import json
import logging
import os

LOGGER = logging.getLogger(__name__)

#: Top-level key naming sibling config files to merge in.
INCLUDES_KEY = 'includes'


def load_config(path):
    """Read a gig config and append the gigs of every file it includes.

    Parameters
    ----------
    path : str
        Path to the config JSON file.

    Returns
    -------
    dict
        A config with a single ``gigs`` key: the file's own gigs followed by
        those of each include, in the order listed.

    Raises
    ------
    OSError, ValueError
        If the config itself cannot be read or is not valid JSON, or if an
        included file is missing, unreadable, malformed, or not a JSON
        object.
    """
    if not os.path.isfile(path):
        return {'gigs': []}

    config = _read_config(path)
    gigs = list(config.get('gigs', []))

    for include in config.get(INCLUDES_KEY, []):
        gigs.extend(_load_include(path, include))

    return {'gigs': gigs}


def _load_include(config_path, include):
    """Return the gigs contributed by one ``includes`` entry."""
    if not isinstance(include, str) or not include:
        raise ValueError(
            '{} in {} must be a file name, got {!r}'.format(
                INCLUDES_KEY, config_path, include))

    included_path = _resolve_include(config_path, include)

    try:
        included = _read_config(included_path)
    except (OSError, ValueError) as exc:
        raise ValueError(
            'cannot read included config {} (from {}): {}'.format(
                included_path, config_path, exc)) from exc

    if INCLUDES_KEY in included:
        # One level only.  Warn rather than recurse: a cycle cannot loop,
        # and the nested file's own gigs are still perfectly usable.
        LOGGER.warning(
            'Included config %s also has an %r; only one level of includes '
            'is supported, using its own gigs',
            included_path, INCLUDES_KEY)

    return included.get('gigs', [])


def _read_config(path):
    config = _read_json(path)
    if not isinstance(config, dict):
        raise ValueError(
            '{} is not a JSON object'.format(path))
    return config


def _read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _resolve_include(config_path, include):
    """Resolve an ``includes`` value against the including config's directory.

    The include must stay inside that directory, so a config cannot pull in
    arbitrary JSON from elsewhere on the device.
    """
    if '\x00' in include:
        raise ValueError('contains a null byte')
    if os.path.isabs(include) or '://' in include:
        raise ValueError(
            'must be a name inside the config directory, not a path or URL: '
            '{!r}'.format(include))

    base = os.path.dirname(os.path.abspath(config_path))
    target = os.path.normpath(os.path.join(base, include))
    if target != base and not target.startswith(base + os.sep):
        raise ValueError(
            'points outside the config directory: {!r}'.format(include))
    return target
