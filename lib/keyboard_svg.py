# -*- coding: utf-8 -*-
"""Generate a color-coded keyboard split SVG diagram.

Ported from chord-grid-gen/genkeyb2.py — returns the SVG as a string
instead of writing to a file.

Supports single and multi-keyboard layouts (side-by-side).
All SVG uses basic SVG 1.1 elements for iPad 2 compatibility.
"""

WHITE_KEY_WIDTH = 28
WHITE_KEY_HEIGHT = 180
BLACK_KEY_WIDTH = 17
BLACK_KEY_HEIGHT = 108
STROKE_WIDTH = 1
BLACK_KEY_OFFSET = 19
FONT_SIZE = 10
BANK_LABEL_HEIGHT = 42
BANK_FONT_SIZE = 30
KEYBOARD_GAP = 40

WHITE_NOTES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
WHITE_NOTE_INDEX = {n: i for i, n in enumerate(WHITE_NOTES)}

BLACK_TO_LEFT_WHITE = {
    'C#': 'C', 'Db': 'C',
    'D#': 'D', 'Eb': 'D',
    'F#': 'F', 'Gb': 'F',
    'G#': 'G', 'Ab': 'G',
    'A#': 'A', 'Bb': 'A',
}

BLACK_KEY_POSITIONS = [0, 1, 3, 4, 5]

# Default colors for up to 6 zones (RGB floats 0..1)
DEFAULT_COLORS = [
    [1.0, 0.0, 0.0],   # red
    [0.0, 1.0, 0.0],   # green
    [0.0, 0.0, 1.0],   # blue
    [1.0, 0.0, 1.0],   # magenta
    [1.0, 1.0, 0.0],   # yellow
    [0.0, 1.0, 1.0],   # cyan
]


def rgb_to_hex(rgb):
    r, g, b = [max(0, min(255, int(round(c * 255)))) for c in rgb]
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


def _note_to_white_index(note_str, keyb_begin):
    if len(note_str) < 2:
        return -1, False
    note_name = note_str[:-1]
    octave = int(note_str[-1])
    if note_name in WHITE_NOTE_INDEX:
        return (octave - keyb_begin) * 7 + WHITE_NOTE_INDEX[note_name], False
    if note_name in BLACK_TO_LEFT_WHITE:
        left_white = BLACK_TO_LEFT_WHITE[note_name]
        white_idx = WHITE_NOTE_INDEX[left_white]
        return (octave - keyb_begin) * 7 + white_idx, True
    return -1, False


def _color_white(white_idx, split_indices, hex_colors):
    for i, (split_idx, _) in enumerate(split_indices):
        if white_idx < split_idx:
            return hex_colors[i]
    return hex_colors[-1]


def _color_black(left_white_idx, split_indices, hex_colors):
    for i, (split_idx, _) in enumerate(split_indices):
        if left_white_idx < split_idx:
            return hex_colors[i]
    return hex_colors[-1]


def _bank_label_x(bank_idx, split_indices, num_white_keys):
    if bank_idx == 0:
        start_key = 0
    else:
        start_key = split_indices[bank_idx - 1][0]
    if bank_idx == len(split_indices):
        end_key = num_white_keys - 1
    else:
        end_key = split_indices[bank_idx][0]
    center_key = (start_key + end_key) / 2
    return center_key * WHITE_KEY_WIDTH


def _render_keyboard_inner(keyb_begin, splits, split_colors,
                           banks=None,
                           num_white_keys=None):
    """Render keyboard keys and labels as SVG element lines (no outer <svg>).

    ``num_white_keys`` is the exact number of white keys to display.
    """
    num_octaves_display = (num_white_keys + 6) // 7

    hex_colors = [rgb_to_hex(c) for c in split_colors]
    split_indices = [_note_to_white_index(s, keyb_begin) for s in splits]

    lines = []

    # White keys
    for i in range(num_white_keys):
        x = i * WHITE_KEY_WIDTH
        color = _color_white(i, split_indices, hex_colors)
        lines.append(
            '<rect x="{}" y="0.5" width="{}" height="{}" '
            'stroke="{}" fill="white" stroke-width="{}"/>'.format(
                x + 0.5, WHITE_KEY_WIDTH - 1, WHITE_KEY_HEIGHT - 1,
                color, STROKE_WIDTH))

    # Black keys
    for octave in range(num_octaves_display):
        octave_offset = octave * 7 * WHITE_KEY_WIDTH
        for idx, white_idx in enumerate(BLACK_KEY_POSITIONS):
            absolute_white = octave * 7 + white_idx
            if absolute_white + 1 >= num_white_keys:
                continue
            x = octave_offset + white_idx * WHITE_KEY_WIDTH + BLACK_KEY_OFFSET
            color = _color_black(absolute_white, split_indices, hex_colors)
            lines.append(
                '<rect x="{}" y="0.5" width="{}" height="{}" '
                'stroke="{}" fill="grey" stroke-width="{}"/>'.format(
                    x + 0.5, BLACK_KEY_WIDTH - 1, BLACK_KEY_HEIGHT - 1,
                    color, STROKE_WIDTH))

    # Bank labels
    if banks:
        for bank_idx, bank_name in enumerate(banks):
            if bank_idx >= len(hex_colors):
                break
            x = _bank_label_x(bank_idx, split_indices, num_white_keys)
            y = WHITE_KEY_HEIGHT + BANK_LABEL_HEIGHT / 2 + 2
            color = hex_colors[bank_idx]
            lines.append(
                '<text x="{}" y="{}" font-size="{}" '
                'font-family="sans-serif" text-anchor="middle" '
                'fill="{}">{}</text>'.format(
                    x, y, BANK_FONT_SIZE, color, bank_name))

    return lines


def generate_keyboard_svg(keyb_begin, splits=None,
                          split_colors=None, banks=None,
                          num_white_keys=None, **kw):
    """Generate a keyboard split SVG and return it as a string."""
    total_width = num_white_keys * WHITE_KEY_WIDTH
    total_height = WHITE_KEY_HEIGHT + BANK_LABEL_HEIGHT

    inner = _render_keyboard_inner(keyb_begin, splits, split_colors,
                                   banks,
                                   num_white_keys=num_white_keys)

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 {} {}">'.format(total_width, total_height),
    ]
    for el in inner:
        lines.append('  ' + el)
    lines.append('</svg>')
    return '\n'.join(lines)


def generate_multi_keyboard_svg(device_skins):
    """Generate multiple keyboards side-by-side in a single SVG.

    ``device_skins`` is a list of dicts, each containing:

        splits, split_colors, banks, keyb_begin, num_white_keys

    Returns an SVG string with keyboards horizontally centered.
    Uses only basic SVG 1.1 elements for iPad 2 compatibility.
    """
    if not device_skins:
        return ''
    if len(device_skins) == 1:
        return generate_keyboard_svg(**device_skins[0])

    # Generate each keyboard's inner SVG elements
    keyboards = []
    for skin in device_skins:
        inner = _render_keyboard_inner(
            skin['keyb_begin'],
            skin['splits'], skin['split_colors'], skin.get('banks'),
            num_white_keys=skin.get('num_white_keys'))
        keyboards.append(inner)

    # Calculate individual keyboard dimensions
    widths = []
    heights = []
    for skin in device_skins:
        nw = skin.get('num_white_keys')
        widths.append(nw * WHITE_KEY_WIDTH)
        heights.append(WHITE_KEY_HEIGHT + BANK_LABEL_HEIGHT)

    total_width = sum(widths) + KEYBOARD_GAP * (len(widths) - 1)
    total_height = max(heights)

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 {} {}">'.format(total_width, total_height),
    ]

    # Position each keyboard using <g transform="translate(x,y)">
    x_offset = 0
    for content, w, h, skin in zip(keyboards, widths, heights, device_skins):
        y_offset = (total_height - h) // 2
        lines.append('<g transform="translate({},{})">'.format(
            x_offset, y_offset))
        for el in content:
            lines.append('  ' + el)
        lines.append('</g>')
        x_offset += w + KEYBOARD_GAP

    lines.append('</svg>')
    return '\n'.join(lines)
