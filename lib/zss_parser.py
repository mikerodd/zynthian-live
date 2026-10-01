# -*- coding: utf-8 -*-
"""Extract keyboard splits and instrument names from Zynthian .zss snapshots.

Reads a .zss file, locates a ZS3 entry by ID, and returns the note ranges
per active chain together with the preset (instrument) name.
"""

import json
import os

# ── MIDI note helpers ──────────────────────────────────────────────────

_NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
_WHITE_SEMITONES = {0, 2, 4, 5, 7, 9, 11}  # C D E F G A B


def midi_to_note_name(n):
    """Convert a MIDI note number to a note name like 'C4'."""
    return _NOTES[n % 12] + str(n // 12 - 1)


def count_white_keys(midi_begin, num_keys):
    """Count white keys in a physical keyboard range starting at midi_begin."""
    return sum(1 for n in range(midi_begin, midi_begin + num_keys)
               if n % 12 in _WHITE_SEMITONES)


# ── ZSS parsing ────────────────────────────────────────────────────────

def parse_zss(path):
    """Read and parse a .zss JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _preset_name(processors, proc_id):
    """Get the display preset name for a processor.

    Falls back to the bank name if the preset name is empty or just a
    number (SoundFont program numbers like '24' are not useful labels).
    """
    proc = processors.get(str(proc_id), {})
    preset = None
    preset_info = proc.get('preset_info')
    if isinstance(preset_info, list) and len(preset_info) > 2:
        preset = preset_info[2]
    elif isinstance(preset_info, str):
        preset = preset_info

    bank = None
    bank_info = proc.get('bank_info')
    if isinstance(bank_info, list) and len(bank_info) > 2:
        bank = bank_info[2]

    # Use preset if it looks like a real name; otherwise fall back to bank
    if preset and preset not in ('None', 'N/A', '') and not preset.isdigit():
        return preset
    if bank and bank not in ('None', 'N/A', ''):
        return bank
    return preset or bank


def trim_label(name, max_len=20):
    """Trim a preset/instrument name for keyboard zone labels.

    If the name is longer than *max_len*, it is truncated with a trailing
    ellipsis.
    """
    if not name or len(name) <= max_len:
        return name
    return name[:max_len - 1].rstrip() + '\u2026'


def _chain_processors(chains_global, chain_id):
    """Return list of (proc_id, short_name) for a chain from global chain defs."""
    chain = chains_global.get(str(chain_id), {})
    result = []
    for slot in chain.get('slots', []):
        for pid, shortname in slot.items():
            result.append((pid, shortname))
    return result


def _is_chain_muted(processors, chains_global, chain_id):
    """Check if any processor in a chain has mute=1 (MI insert or similar)."""
    for pid, _ in _chain_processors(chains_global, chain_id):
        proc = processors.get(str(pid), {})
        controllers = proc.get('controllers', {})
        if controllers.get('mute', {}).get('value') == 1:
            return True
    return False


def _find_preset(processors, chains_global, chain_id):
    """Return (preset_name, short_name) for the first valid processor in a chain."""
    proc_list = _chain_processors(chains_global, chain_id)
    for pid, sname in proc_list:
        p = _preset_name(processors, pid)
        if p and p not in ('None', 'N/A', ''):
            return p, sname
    short = proc_list[0][1] if proc_list else '?'
    return short, short


def get_zs3_splits(zss_data, zs3_id):
    """Extract keyboard split info from a ZS3 entry.

    Returns a list of dicts sorted by note_low, one per active chain zone::

        [
            {
                'chain_id': 1,
                'note_low': 3,       # MIDI note (0-127)
                'note_high': 71,     # MIDI note (0-127)
                'midi_chan': 0,       # MIDI channel (0-indexed)
                'preset_name': 'Grand Steinway D (Hamburg)',
                'short_name': 'PT',
            },
            ...
        ]

    Only chains that define at least one of note_low / note_high are included.
    Exact duplicates (same channel + same note range) are merged into one zone
    with combined names.  Partial overlaps on the same channel are kept as-is.
    """
    zs3 = zss_data.get('zs3', {})
    entry = zs3.get(zs3_id)
    if entry is None:
        return []

    chains_data = entry.get('chains', {})
    processors = entry.get('processors', {})
    chains_global = zss_data.get('chains', {})
    mixer = entry.get('mixer', {})

    raw = []
    for chain_id_str, chain_state in chains_data.items():
        if not isinstance(chain_state, dict):
            continue
        nl = chain_state.get('note_low')
        nh = chain_state.get('note_high')
        if nl is None and nh is None:
            continue

        # Skip muted chains
        global_chain = chains_global.get(chain_id_str, {})
        mixer_chan = global_chain.get('mixer_chan')
        if mixer_chan is not None:
            chan_key = 'chan_{:02d}'.format(mixer_chan)
            if mixer.get(chan_key, {}).get('mute', 0) == 1:
                continue

        # Also check processor-level mute (MI insert mute controller)
        if _is_chain_muted(processors, chains_global, chain_id_str):
            continue

        preset, short = _find_preset(processors, chains_global, chain_id_str)

        raw.append({
            'chain_id': int(chain_id_str),
            'note_low': nl if nl is not None else 0,
            'note_high': nh if nh is not None else 127,
            'midi_chan': chain_state.get('midi_chan'),
            'preset_name': preset or short,
            'short_name': short,
        })

    # Merge exact duplicates (same channel + same note range) into one
    # zone with combined names.  Partial overlaps are kept as-is.
    by_key = {}
    for z in raw:
        key = (z.get('midi_chan'), z['note_low'], z['note_high'])
        if key in by_key:
            existing = by_key[key]
            existing['preset_name'] += ' / ' + z['preset_name']
            existing['short_name'] += '/' + z['short_name']
        else:
            by_key[key] = z

    zones = sorted(by_key.values(), key=lambda z: z['note_low'])
    return zones


def get_zs3_splits_with_devices(zss_data, zs3_id, input_devices):
    """Like get_zs3_splits(), but also includes unmuted chains without note
    ranges, assigning them the full range of their matching input device.

    This handles the common case where a chain is active (unmuted) but the
    ZS3 snapshot didn't save explicit note ranges for it.
    """
    zones = get_zs3_splits(zss_data, zs3_id)

    # Index zones by midi_chan for quick lookup
    zones_by_chan = {}
    for z in zones:
        zones_by_chan.setdefault(z.get('midi_chan'), set()).add(z['chain_id'])

    # Find chains without note ranges that should be included
    zs3 = zss_data.get('zs3', {})
    entry = zs3.get(zs3_id)
    if entry is None:
        return zones

    chains_data = entry.get('chains', {})
    processors = entry.get('processors', {})
    chains_global = zss_data.get('chains', {})

    # Build device range lookup: midi_chan -> (note_low, note_high)
    device_ranges = {}
    for dev in input_devices:
        chan = dev['midi_chan']
        begins = dev['begins']
        num_keys = dev['keys']
        device_ranges[chan] = (begins, begins + num_keys - 1)

    extra = []
    for chain_id_str, chain_state in chains_data.items():
        if not isinstance(chain_state, dict):
            continue
        # Skip chains that already have zones
        chain_id_int = int(chain_id_str)
        chan = chain_state.get('midi_chan')
        if chan in zones_by_chan and chain_id_int in zones_by_chan[chan]:
            continue
        # Skip chains that have note ranges (already handled by get_zs3_splits)
        if chain_state.get('note_low') is not None or chain_state.get('note_high') is not None:
            continue
        # Skip muted chains
        if _is_chain_muted(processors, chains_global, chain_id_str):
            continue
        # Only include if there's a matching device
        if chan not in device_ranges:
            continue

        preset, short = _find_preset(processors, chains_global, chain_id_str)

        note_low, note_high = device_ranges[chan]
        extra.append({
            'chain_id': chain_id_int,
            'note_low': note_low,
            'note_high': note_high,
            'midi_chan': chan,
            'preset_name': preset or short,
            'short_name': short,
        })

    all_zones = zones + extra

    # Merge exact duplicates across the combined set
    by_key = {}
    for z in all_zones:
        key = (z.get('midi_chan'), z['note_low'], z['note_high'])
        if key in by_key:
            existing = by_key[key]
            existing['preset_name'] += ' / ' + z['preset_name']
            existing['short_name'] += '/' + z['short_name']
        else:
            by_key[key] = z

    result = sorted(by_key.values(), key=lambda z: z['note_low'])
    return result



from keyboard_svg import DEFAULT_COLORS


def splits_for_device(device, zones, global_color_offset=0):
    """Convert filtered zones + device config into keyboard_svg parameters.

    Uses ``device['begins']`` and ``device['keys']`` for keyboard geometry
    (instead of deriving from zone ranges).  Colors start at
    ``global_color_offset`` for cross-keyboard distinction.
    """
    if not zones:
        return None

    keyb_begin_midi = device['begins']
    num_keys = device['keys']
    keyb_begin_octave = (keyb_begin_midi // 12) - 1
    num_white = count_white_keys(keyb_begin_midi, num_keys)

    splits = []
    banks = []
    for z in zones:
        banks.append(z['preset_name'])
        if z != zones[0]:
            splits.append(midi_to_note_name(z['note_low']))

    zone_colors = []
    for i in range(len(zones)):
        idx = (global_color_offset + i) % len(DEFAULT_COLORS)
        zone_colors.append(DEFAULT_COLORS[idx])

    return {
        'splits': splits,
        'split_colors': zone_colors,
        'banks': banks,
        'keyb_begin': keyb_begin_octave,
        'num_white_keys': num_white,
    }


def collect_skins(track_data, zss_path, zs3_id, input_devices):
    """Return one keyboard_svg parameter set per channel that has zones.

    ``track_data`` is accepted so callers can pass the parsed track JSON
    verbatim; the split geometry comes entirely from the snapshot and the
    gig's ``input_devices``, so it is unused here.

    Returns an empty list -- never raises -- when any of the inputs needed
    for a split is missing (no snapshot path, no zs3_id, no input devices,
    unreadable snapshot, or a ZS3 id that is not in the snapshot), so a
    ``split`` display block simply renders nothing.
    """
    if not (zss_path and zs3_id and input_devices and os.path.isfile(zss_path)):
        return []
    zss = parse_zss(zss_path)
    zones = get_zs3_splits_with_devices(zss, zs3_id, input_devices)
    if not zones:
        return []
    skins = []
    color_offset = 0
    for dev in input_devices:
        chan = dev['midi_chan']
        chan_zones = [z for z in zones if z['midi_chan'] == chan]
        if not chan_zones:
            continue
        sd = splits_for_device(dev, chan_zones, global_color_offset=color_offset)
        sd['banks'] = [trim_label(b) for b in sd['banks']]
        skins.append(sd)
        color_offset += len(chan_zones)
    return skins
