# -*- coding: utf-8 -*-
"""Parse leadsheet data from JSON.

Ported from leadsheet-generator/generator.js — only the parsing logic; no
rendering.
"""

import re

# ── constants ──────────────────────────────────────────────────────────

BAR_SYMBOLS = {
    '|': 'single', '||': 'double', '|||': 'final',
    '>|': 'end', '}': 'end', '|<': 'start-repeat',
    '>|<': 'end-start-repeat',
}


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
