# -*- coding: utf-8 -*-
"""Load a track JSON file, applying its optional single-level inheritance.

A track may name a parent with a top-level ``"inherit"`` key holding the
file name of another track in the same directory::

    {
      "inherit": "verse.json",
      "display": ["leadsheet", "structure"]
    }

The parent's top-level keys are taken, then the child's replace them one by
one, so a short child inherits everything it does not mention -- typically
``leadsheet`` and ``structure`` -- and states only what differs::

    parent = {"display": [...], "leadsheet": [...], "structure": {...}}
    child  = {"inherit": "parent.json", "display": ["structure"]}
    merged = {"display": ["structure"], "leadsheet": [...], "structure": {...}}

The merge is shallow on purpose: a top-level key is replaced wholesale, so a
child that redefines ``structure`` gets exactly its own table rather than a
half-overridden one.  Only one level is followed -- a parent that itself
inherits contributes its own content and its ``inherit`` is ignored -- so a
cycle of tracks can never loop.

A parent that is missing, unreadable, invalid or outside the track directory
is a warning, not an error: the child renders on its own.  Failing to read
the *child* remains an error, exactly as before inheritance existed.
"""

import json
import logging
import os

LOGGER = logging.getLogger(__name__)

#: Top-level key naming the parent track file.
INHERIT_KEY = 'inherit'


def load_track(path):
    """Read a track JSON file and merge in its parent if it names one.

    Parameters
    ----------
    path : str
        Path to the track JSON file.

    Returns
    -------
    dict
        The track data, with its parent's top-level keys filled in and
        ``inherit`` removed.

    Raises
    ------
    OSError, ValueError
        If the track itself cannot be read or is not valid JSON.  Failures
        of the *parent* are logged and ignored.
    """
    child = _read_json(path)

    inherit = child.get(INHERIT_KEY)
    if inherit is None:
        return child
    if not isinstance(inherit, str) or not inherit:
        LOGGER.warning(
            'Ignoring invalid %r in %s: expected a file name, got %r',
            INHERIT_KEY, path, inherit)
        return child

    try:
        parent_path = _resolve_parent(path, inherit)
    except ValueError as exc:
        LOGGER.warning('Ignoring %r in %s: %s', INHERIT_KEY, path, exc)
        return child

    try:
        parent = _read_json(parent_path)
    except (OSError, ValueError) as exc:
        LOGGER.warning(
            'Ignoring %r in %s: cannot read parent %s: %s',
            INHERIT_KEY, path, parent_path, exc)
        return child

    if not isinstance(parent, dict):
        LOGGER.warning(
            'Ignoring %r in %s: parent %s is not a JSON object',
            INHERIT_KEY, path, parent_path)
        return child

    if INHERIT_KEY in parent:
        LOGGER.warning(
            'Parent %s of %s also has an %r; only one level of inheritance '
            'is supported, using its own content',
            parent_path, path, INHERIT_KEY)

    merged = dict(parent)
    merged.update(child)
    merged.pop(INHERIT_KEY, None)
    return merged


def _read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _resolve_parent(child_path, inherit):
    """Resolve an ``inherit`` value against the child's directory.

    The parent must stay inside that directory, so a track file cannot pull
    in arbitrary JSON from elsewhere on the device.
    """
    if '\x00' in inherit:
        raise ValueError('contains a null byte')
    if os.path.isabs(inherit) or '://' in inherit:
        raise ValueError(
            'must be a name inside the track directory, not a path or URL: '
            '{!r}'.format(inherit))

    base = os.path.dirname(os.path.abspath(child_path))
    parent = os.path.normpath(os.path.join(base, inherit))
    if parent != base and not parent.startswith(base + os.sep):
        raise ValueError('points outside the track directory: {!r}'.format(inherit))
    return parent
