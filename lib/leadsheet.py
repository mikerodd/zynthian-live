# -*- coding: utf-8 -*-
"""Parse leadsheet data from JSON and transpose chords.

Ported from leadsheet-generator/generator.js — only the parsing and
transposition logic; no rendering.
"""

import re

# ── constants ──────────────────────────────────────────────────────────

SHARP_SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLAT_SCALE  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

NOTE_VALUES = {
    'C': 0, 'B#': 0,
    'C#': 1, 'Db': 1,
    'D': 2,
    'D#': 3, 'Eb': 3,
    'E': 4, 'Fb': 4,
    'F': 5, 'E#': 5,
    'F#': 6, 'Gb': 6,
    'G': 7,
    'G#': 8, 'Ab': 8,
    'A': 9,
    'A#': 10, 'Bb': 10,
    'B': 11, 'Cb': 11,
}

BAR_SYMBOLS = {
    '|': 'single', '||': 'double', '|||': 'final',
    '>|': 'end', '}': 'end', '|<': 'start-repeat',
    '>|<': 'end-start-repeat',
}

_PAT_CHORD = re.compile(r'^([A-G][#b]?)(.*)')
_PAT_NOTE  = re.compile(r'^([A-G])([#b]?)')


# ── transposition ──────────────────────────────────────────────────────

def transpose_note(note_str, semitones):
    m = _PAT_NOTE.match(note_str)
    if not m:
        return note_str
    name, accidental = m.group(1), m.group(2)
    key = name + accidental
    if key not in NOTE_VALUES:
        return note_str
    new_idx = (NOTE_VALUES[key] + semitones % 12 + 12) % 12
    if semitones > 0:
        return SHARP_SCALE[new_idx]
    elif semitones < 0:
        return FLAT_SCALE[new_idx]
    return key


def transpose_chord(chord, semitones):
    trimmed = (chord or '').strip()
    if not trimmed or trimmed in ('/', '%', 'N.C.'):
        return chord
    parts = trimmed.split('/')
    main_str = parts[0]
    bass_str = parts[1] if len(parts) > 1 else None
    m = _PAT_CHORD.match(main_str)
    if not m:
        return chord
    root, quality = m.group(1), m.group(2)
    new_root = transpose_note(root, semitones)
    result = new_root + quality
    if bass_str:
        result += '/' + transpose_note(bass_str, semitones)
    return result


def transpose_sheet(sheet, semitones):
    if semitones == 0:
        return sheet
    out = dict(sheet)
    out['lines'] = []
    for line in sheet['lines']:
        new_line = dict(line)
        new_line['measures'] = []
        for measure in line['measures']:
            new_measure = dict(measure)
            new_measure['beats'] = [
                transpose_chord(b, semitones) for b in measure['beats']
            ]
            new_line['measures'].append(new_measure)
        out['lines'].append(new_line)
    return out


# ── chord line parser ──────────────────────────────────────────────────

def _parse_chord_line(chords_str, voltas_str='', beat_str=''):
    """Parse a single chord line string into a line data dict.

    Returns dict with: lineText, startBar, startBarVolta, startBeat,
    measures[].
    """
    data = {
        'lineText': '',
        'startBar': 'single',
        'startBarVolta': '',
        'startBeat': '',
        'measures': [],
    }
    if chords_str:
        parts = re.split(r'\s*(>\|<|\|\|\||\|\||\|<|>\||\||\})\s*', chords_str)
        parts = [p for p in parts if p.strip()]
        if parts:
            first = parts[0]
            if first in BAR_SYMBOLS:
                data['startBar'] = BAR_SYMBOLS[first]
                parts = parts[1:]
            i = 0
            while i + 1 < len(parts):
                beats_str = parts[i]
                bar_sym = parts[i + 1]
                beats = [b if b != '_' else '' for b in beats_str.split(' ')]
                data['measures'].append({
                    'beats': beats,
                    'barLine': BAR_SYMBOLS.get(bar_sym, 'single'),
                    'barLineVolta': '',
                    'barBeat': '',
                    'rehearsalMark': '',
                })
                i += 2
    if voltas_str:
        vparts = voltas_str.split(',')
        if vparts:
            data['startBarVolta'] = '' if vparts[0].strip() == '_' else vparts[0].strip()
        for idx, v in enumerate(vparts[1:]):
            if idx < len(data['measures']):
                data['measures'][idx]['barLineVolta'] = '' if v.strip() == '_' else v.strip()
    if beat_str:
        bparts = beat_str.split(',')
        if bparts:
            data['startBeat'] = '' if bparts[0].strip() == '_' else bparts[0].strip()
        for idx, b in enumerate(bparts[1:]):
            if idx < len(data['measures']):
                data['measures'][idx]['barBeat'] = '' if b.strip() == '_' else b.strip()
    return data


# ── JSON leadsheet parser ──────────────────────────────────────────────

def parse_leadsheet(lines_data, time_sig='4/4'):
    """Parse leadsheet lines from a JSON array into a sheet structure.

    Each entry in lines_data should have:
        label   - section label string
        chords  - chord line string (e.g. "| A9sus4 _ B11 _ |")
        voltas  - optional voltas string (e.g. "_,1,2.3,_")
        beat    - optional beat/time signature string (e.g. "4/4,_,_,2/4")

    Returns a dict with: title, timeSignature, lines[].
    """
    sheet = {
        'title': '',
        'timeSignature': time_sig,
        'lines': [],
    }
    for line in lines_data:
        data = _parse_chord_line(
            line.get('chords', ''),
            line.get('voltas', ''),
            line.get('beat', ''),
        )
        data['lineText'] = line.get('label', '')
        sheet['lines'].append(data)
    return sheet
