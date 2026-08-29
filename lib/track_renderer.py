# -*- coding: utf-8 -*-
"""Render a chart page body: leadsheet + keyboard split + track table.

Combines leadsheet.py, zss_parser.py, and keyboard_svg.py to produce the
HTML fragment embedded in templates/chart.html (which extends base.html).
CSS and fonts are served by the local tornado server from /static,
so no internet connection is needed - safe for offline gigs.
"""

import os
import json
import html as html_mod

from leadsheet import parse_leadsheet, transpose_sheet
from zss_parser import (
    parse_zss, get_zs3_splits_with_devices, splits_for_device, trim_label,
)
from keyboard_svg import (
    generate_keyboard_svg, generate_multi_keyboard_svg, rgb_to_hex,
    DEFAULT_COLORS,
)

DATA_DIR = os.environ.get(
    'ZYNTHIAN_MY_DATA_DIR', '/zynthian/zynthian-my-data')


import re as _re
_CHORD_ROOT = _re.compile(r'^([A-G])([#b]?.*)')


def _format_note_root(note_str):
    """Format a note/chord root with accidental in superscript.

    ``Db``    → ``D<sup>b</sup>``
    ``F#``    → ``F<sup>#</sup>``
    ``C``     → ``C``
    """
    m = _CHORD_ROOT.match(note_str)
    if not m:
        return html_mod.escape(note_str)
    root, ext = m.group(1), m.group(2)
    if not ext:
        return html_mod.escape(root)
    return '{}<sup>{}</sup>'.format(
        html_mod.escape(root), html_mod.escape(ext))


def _format_chord(chord):
    """Format a chord string with the extension in superscript.

    ``A9sus4``    → ``A<sup>9sus4</sup>``
    ``Cmaj7``     → ``C<sup>maj7</sup>``
    ``Db/Eb``     → ``D<sup>b</sup>/E<sup>b</sup>``
    ``E-7/F#``    → ``E<sup>-7</sup>/F<sup>#</sup>``
    """
    # Handle slash bass separately — it stays at baseline
    parts = chord.split('/', 1)
    main = parts[0]
    bass = parts[1] if len(parts) > 1 else None

    m = _CHORD_ROOT.match(main)
    if not m:
        return html_mod.escape(chord)
    root, ext = m.group(1), m.group(2)
    if bass is None:
        if not ext:
            return html_mod.escape(root)
        return '{}<sup>{}</sup>'.format(
            html_mod.escape(root), html_mod.escape(ext))
    # Bass note: use same root+accidental formatting
    bass_fmt = _format_note_root(bass)
    if not ext:
        return html_mod.escape(root) + '/' + bass_fmt
    return '{}<sup>{}</sup>/{}'.format(
        html_mod.escape(root), html_mod.escape(ext), bass_fmt)


_DOTS = '<div class="ls-bar-dots"><div class="ls-bar-dot"></div><div class="ls-bar-dot"></div></div>'
_STROKE = '<div class="ls-bar-stroke"></div>'


def _beat_time_html(beat_str):
    """Render a time signature as a vertical fraction (e.g. 4/4 → 4 over 4)."""
    parts = beat_str.split('/')
    if len(parts) == 2:
        return '<div class="ls-beat-time"><span class="num">{}</span><div class="bar"></div><span class="num">{}</span></div>'.format(
            html_mod.escape(parts[0]), html_mod.escape(parts[1]))
    return '<div class="ls-beat-time">{}</div>'.format(html_mod.escape(beat_str))


def _barline_html(bar_type):
    """Return HTML for a barline element (pure CSS, no font rendering)."""
    if bar_type == 'start-repeat':
        return '<div class="ls-barline">{}{}</div>'.format(_STROKE, _DOTS)
    if bar_type in ('end-repeat', 'end'):
        return '<div class="ls-barline">{}{}</div>'.format(_DOTS, _STROKE)
    if bar_type in ('final', 'double'):
        return '<div class="ls-barline">{}{}</div>'.format(_STROKE, _STROKE)
    return '<div class="ls-barline">{}</div>'.format(_STROKE)


def _build_leadsheet_html(sheet, semitones):
    """Render parsed leadsheet data as an HTML string."""
    if semitones != 0:
        sheet = transpose_sheet(sheet, semitones)
    parts = []
    for line in sheet.get('lines', []):
        label = line.get('lineText', '').strip()
        # Strip leading alignment markers (< > $)
        clean_label = label
        for ch in ('<', '>', '$'):
            clean_label = clean_label.replace(ch, '')
        clean_label = clean_label.strip()

        if clean_label:
            parts.append(
                '<div class="ls-section-label">{}</div>'.format(
                    html_mod.escape(clean_label)))

        measures = line.get('measures', [])
        if not measures:
            continue

        parts.append('<div class="ls-line">')

        # Bar line BEFORE the first measure (startBar)
        start_bar = line.get('startBar', '')
        start_beat = line.get('startBeat', '')
        if start_beat:
            parts.append(_beat_time_html(start_beat))
        if start_bar == 'single':
            parts.append(_barline_html('single'))
        elif start_bar:
            parts.append(_barline_html(start_bar))

        for mi, m in enumerate(measures):
            # Volta label above the measure box
            if mi == 0:
                volta = line.get('startBarVolta', '')
            else:
                volta = measures[mi - 1].get('barLineVolta', '')
            if volta:
                parts.append(
                    '<div class="ls-volta">{}</div>'.format(
                        html_mod.escape(volta)))

            parts.append('<div class="ls-measure">')
            parts.append('<div class="ls-beats-row">')
            for beat in m.get('beats', []):
                b = beat.strip()
                if not b:
                    parts.append('<div class="ls-beat empty">-</div>')
                elif b == '/':
                    parts.append('<div class="ls-beat slash">/</div>')
                elif b == '%':
                    parts.append('<div class="ls-beat lazy">%</div>')
                else:
                    parts.append(
                        '<div class="ls-beat">{}</div>'.format(
                            _format_chord(b)))
            parts.append('</div>')  # ls-beats-row
            parts.append('</div>')  # ls-measure

            # Beat indicator + bar line AFTER the measure
            bar_beat = m.get('barBeat', '')
            if bar_beat:
                parts.append(_beat_time_html(bar_beat))
            bar = m.get('barLine', 'single')
            if bar in ('start-repeat', 'end-repeat', 'end', 'final', 'double'):
                parts.append(_barline_html(bar))
            else:
                parts.append(_barline_html('single'))

        parts.append('</div>')  # ls-line

    return '\n'.join(parts)


def _build_track_table_html(track_data):
    """Render the track structure table (section headers + bank rows)."""
    headers = track_data.get('headers', [])
    rows = track_data.get('rows', [])
    if not headers or not rows:
        return ''
    parts = ['<table class="track-table">']
    # header row
    parts.append('<tr>')
    for h in headers:
        parts.append('<th>{}</th>'.format(html_mod.escape(h)))
    parts.append('</tr>')
    # data rows
    for row_idx, row in enumerate(rows):
        color = rgb_to_hex(DEFAULT_COLORS[row_idx % len(DEFAULT_COLORS)])
        parts.append('<tr>')
        for cell in row.get('cells', []):
            if cell == 1:
                parts.append(
                    '<td style="background:{}">&nbsp;</td>'.format(color))
            elif cell == 0:
                parts.append('<td>&nbsp;</td>')
            else:
                parts.append(
                    '<td><span class="cell-text">{}</span></td>'.format(
                        html_mod.escape(str(cell))))
        parts.append('</tr>')
    parts.append('</table>')
    return '\n'.join(parts)


def _build_page(title, notes, gig_id, semitones, display,
                leadsheet_html, keyboard_svg, table_html):
    """Assemble the chart page body (nav bar + sections)."""
    transpose_label = '{:+d}'.format(semitones) if semitones else '0'
    back_url = '/gig/{}'.format(html_mod.escape(str(gig_id)))

    body_parts = []
    # Nav bar
    body_parts.append('<div class="chart-nav">')
    body_parts.append('  <a href="{}">&#8592;</a>'.format(back_url))
    body_parts.append(
        '  <span class="nav-title">{}</span>'.format(
            html_mod.escape(title)))
    if notes:
        body_parts.append(
            '  <span class="nav-notes">{}</span>'.format(
                html_mod.escape(notes)))
    body_parts.append('  <div class="nav-spacer"></div>')
    # Transpose controls
    t_down = semitones - 1
    t_up = semitones + 1
    body_parts.append(
        '  <a class="transpose-btn" href="?transpose={}">&minus;</a>'.format(
            t_down))
    body_parts.append(
        '  <span class="transpose-val">{}</span>'.format(transpose_label))
    body_parts.append(
        '  <a class="transpose-btn" href="?transpose={}">+</a>'.format(
            t_up))
    body_parts.append('</div>')

    # Chart body
    body_parts.append('<div class="chart-body">')
    for block in display:
        if block == 'leadsheet' and leadsheet_html:
            body_parts.append(leadsheet_html)
        elif block == 'split' and keyboard_svg:
            body_parts.append('<div class="split-container">')
            body_parts.append(keyboard_svg)
            body_parts.append('</div>')
        elif block == 'structure' and table_html:
            body_parts.append(table_html)
    body_parts.append('</div>')

    return '\n'.join(body_parts)


# ── public API ──────────────────────────────────────────────────────────

def render_chart(gig_id, track_json_path,
                 zss_path=None, zs3_id=None,
                 title='', notes='', semitones=0,
                 input_devices=None):
    """Render a chart page body and return it as an HTML fragment.

    Parameters
    ----------
    gig_id : str or int
        Gig identifier (used for the back-link URL).
    track_json_path : str
        Path to the track JSON file (display, leadsheet, structure).
    zss_path : str or None
        Path to the .zss snapshot file.  Used to extract keyboard splits.
    zs3_id : str or None
        ZS3 entry ID within the snapshot (e.g. 'zs3-10').
    title : str
        Track title (from config.json).
    notes : str
        Subtitle / notes text shown in the nav bar.
    semitones : int
        Transposition offset in semitones (0 = original key).
    input_devices : list or None
        List of input device dicts with 'midi_chan', 'keys', 'begins'.
    """
    # Load track data
    with open(track_json_path, 'r', encoding='utf-8') as f:
        track_data = json.load(f)
    if not title:
        title = track_data.get('title', 'Untitled')

    display = track_data.get('display', ['leadsheet', 'split', 'structure'])
    time_sig = track_data.get('time', '4/4')

    # Leadsheet
    leadsheet_html = ''
    leadsheet_data = track_data.get('leadsheet', [])
    if leadsheet_data:
        sheet = parse_leadsheet(leadsheet_data, time_sig)
        leadsheet_html = _build_leadsheet_html(sheet, semitones)

    # Keyboard split from ZSS
    keyboard_svg = ''
    if zss_path and zs3_id and input_devices and os.path.isfile(zss_path):
        zss = parse_zss(zss_path)
        zones = get_zs3_splits_with_devices(zss, zs3_id, input_devices)
        if zones:
            skins = []
            color_offset = 0
            for dev in input_devices:
                chan = dev['midi_chan']
                chan_zones = [z for z in zones if z['midi_chan'] == chan]
                if not chan_zones:
                    continue
                sd = splits_for_device(dev, chan_zones,
                                       global_color_offset=color_offset)
                sd['banks'] = [trim_label(b) for b in sd['banks']]
                skins.append(sd)
                color_offset += len(chan_zones)
            if len(skins) == 1:
                keyboard_svg = generate_keyboard_svg(**skins[0])
            else:
                keyboard_svg = generate_multi_keyboard_svg(skins)

    # Track structure table
    structure = track_data.get('structure', {})
    table_html = _build_track_table_html(structure)

    return _build_page(
        title=title,
        notes=notes,
        gig_id=gig_id,
        semitones=semitones,
        display=display,
        leadsheet_html=leadsheet_html,
        keyboard_svg=keyboard_svg,
        table_html=table_html,
    )
