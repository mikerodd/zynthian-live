# -*- coding: utf-8 -*-
"""Shared helpers for resolving untrusted relative paths safely."""

import os
from typing import Any


def safe_resolve_path(base_dir: str, relative_path: str) -> str | None:
    """Resolve *relative_path* under *base_dir* without escaping it.

    Returns the resolved absolute path, or ``None`` when the input is
    invalid: null bytes, absolute paths, URLs, or any traversal that would
    leave *base_dir*.
    """
    if not isinstance(relative_path, str):
        return None
    if '\x00' in relative_path:
        return None
    if os.path.isabs(relative_path) or '://' in relative_path:
        return None

    base = os.path.abspath(base_dir)
    target = os.path.normpath(os.path.join(base, relative_path))
    if target != base and not target.startswith(base + os.sep):
        return None
    return target
