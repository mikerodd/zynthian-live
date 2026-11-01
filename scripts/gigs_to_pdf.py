#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print all leadsheets from zynthian-live config.json into a single PDF.

Renders every track of every gig exactly like the live-session web app
(reuses lib/ leadsheet + split + structure rendering) and converts the
combined HTML to PDF via headless Google Chrome.

Usage:
  python3 tmp/gigs_to_pdf.py [--config PATH] [--out FILE.pdf] [--keep-html]
                             [--gigs 0,2 | --gigs all] [--alpha] [--title T]

  --config     Path to config.json (default: ../zynthian-live-data/live-session/config.json)
                Its top-level "includes" are spliced in, so any config that
                happens to have none can be printed on its own.
  --out        Output PDF path (default: ../tmp/gigs_sheets.pdf)
  --keep-html  Keep the intermediate .html file used for printing
  --gigs       Comma-separated gig indexes to print (default: all).  The
               special value "all" instead collects every track from every
               gig (own gigs and included ones alike) into one global PDF,
               keeping only the first sheet per track name.  No "All tracks"
               gig is needed in the config for this.
  --alpha      Sort all tracks alphabetically (global A–Z) and add a
               clickable index page at the beginning of the PDF
  --title      Cover title for --gigs all (default: "All tracks")
"""

import argparse
import base64
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ZYNTHIAN_LIVE_DIR = os.path.dirname(HERE)
GIT_ROOT = os.path.dirname(ZYNTHIAN_LIVE_DIR)
sys.path.insert(0, os.path.join(ZYNTHIAN_LIVE_DIR, 'lib'))
sys.path.insert(0, ZYNTHIAN_LIVE_DIR)

# Warnings from lib/ (a missing image, an unreadable parent track, ...) are
# part of this command's report, so send them to stdout next to the progress
# lines instead of stderr, where they are easily lost when the output is
# piped or redirected.
logging.basicConfig(format='WARNING: %(message)s', stream=sys.stdout,
                    level=logging.WARNING)

from lib import track_renderer  # noqa: E402
from lib.config_loader import load_config  # noqa: E402
from lib.track_loader import load_track  # noqa: E402

DEFAULT_CONFIG = os.path.join(GIT_ROOT, 'zynthian-live-data', 'live-session', 'config.json')
DEFAULT_OUT = os.path.join(GIT_ROOT, 'tmp', 'gigs_sheets.pdf')

STATIC_CSS = os.path.join(ZYNTHIAN_LIVE_DIR, 'static', 'css', 'live-session.css')
STATIC_FONT = os.path.join(ZYNTHIAN_LIVE_DIR, 'static', 'fonts', 'MuseJazzText.otf')


def app_css():
    """Load the live-session CSS with the MuseJazzText font inlined.

    The app CSS references the font via an absolute /static/... URL that only
    works behind the tornado server. Embed it as a base64 data URI instead so
    headless Chrome can render from a bare file:// document.
    """
    with open(STATIC_CSS, 'r', encoding='utf-8') as fh:
        css = fh.read()
    if os.path.isfile(STATIC_FONT):
        with open(STATIC_FONT, 'rb') as fh:
            font_data = base64.b64encode(fh.read()).decode('ascii')
        css = css.replace(
            'url(/static/fonts/MuseJazzText.otf)',
            'url("data:font/opentype;base64,{}")'.format(font_data))
    else:
        print('WARNING: font not found at {}; chords will use default fonts'.format(
            STATIC_FONT), file=sys.stderr)
    return css

PRINT_CSS = """
@page { size: A4; margin: 12mm; }
html, body {
    margin: 0; padding: 0; background: #fff;
    height: auto !important; overflow: visible !important;
}
body { -webkit-print-color-adjust: exact; }
.chart-nav { display: none !important; }
.chart-body { padding: 0 !important; }
.gig-header { page-break-before: always; padding-top: 30mm; text-align: center; }
.gig-header h1 { font-family: 'Permanent Marker', cursive; font-size: 34px; }
.gig-header p { font-size: 16px; color: #555; }
.sheet { page-break-before: always; }
.sheet-back {
    flex: 0 0 auto; white-space: nowrap;
    font-size: 18px; color: #357; text-decoration: underline;
    padding-top: 6px;
}
.index { page-break-before: always; text-align: center; }
.index h1 {
    font-family: 'Permanent Marker', cursive;
    font-size: 34px; margin-bottom: 24px;
}
.index-list {
    column-gap: 40px;
    text-align: left;
    max-width: 700px; margin: 0 auto;
}
.index-list a {
    display: flex; justify-content: space-between; align-items: baseline;
    gap: 12px; font-size: 22px; color: #357;
    text-decoration: none; padding: 5px 0;
    border-bottom: 1px dotted #ccc;
}
.index-entry-left { flex: 1 1 auto; min-width: 0; }
.index-page { flex: 0 0 auto; text-align: right;
    font-size: 15px; color: #999; }
.index-list a:visited { color: #357; }
.index-gig { color: #999; font-size: 15px; margin-left: 8px; }
.sheet-meta {
    display: flex; justify-content: space-between;
    align-items: flex-start; gap: 16px;
    margin-bottom: 12px;
}
.sheet-meta-text { flex: 1 1 auto; min-width: 0; }
.sheet-title {
    font-family: 'Permanent Marker', cursive;
    font-size: 30px; font-weight: 700; margin: 0;
}
.sheet-notes { font-size: 15px; color: #444; margin: 2px 0 0; }
.sheet-gig { font-size: 13px; color: #888; margin: 2px 0 0; }
.sheet-leadsheet-divider { border-top: 2px solid #000; margin: 8px 0 12px; }
.split-container { margin: 12px 0; }
.security-cut { page-break-before: always; }
"""


def build_sheet_html(gig_name, track, zss_path, base_dir, anchor_id=None):
    import html as html_mod

    sheet_attrs = 'class="sheet"'
    if anchor_id:
        sheet_attrs += ' id="{}"'.format(anchor_id)

    track_path = os.path.join(base_dir, track.get('json_filename', ''))
    parts = []
    if not os.path.isfile(track_path):
        parts.append('<section {}>'.format(sheet_attrs))
        parts.append('<h2 class="sheet-title">{}</h2>'.format(
            html_mod.escape(track.get('name', 'Untitled'))))
        parts.append('<p class="sheet-notes">MISSING track file: {}</p>'.format(
            html_mod.escape(track.get('json_filename', ''))))
        parts.append('</section>')
        return '\n'.join(parts)

    try:
        track_data = load_track(track_path)
    except json.JSONDecodeError as e:
        print('\nERROR: invalid JSON in track file: {}'.format(track_path))
        print('  {}'.format(e))
        parts.append('<section {}>'.format(sheet_attrs))
        parts.append('<h2 class="sheet-title">{}</h2>'.format(
            html_mod.escape(track.get('name', 'Untitled'))))
        parts.append('<p class="sheet-notes">ERROR: invalid JSON track file: '
                     '{}</p>'.format(html_mod.escape(track.get('json_filename', ''))))
        parts.append('</section>')
        return '\n'.join(parts)

    zs3_id = track.get('zs3_id')
    input_devices = track.get('input_devices') or []

    parts.append('<section {}>'.format(sheet_attrs))
    parts.append('<div class="sheet-meta">')
    parts.append('<div class="sheet-meta-text">')
    parts.append('<h2 class="sheet-title">{}</h2>'.format(
        html_mod.escape(track.get('name', 'Untitled'))))
    if track.get('notes'):
        parts.append('<p class="sheet-notes">{}</p>'.format(
            html_mod.escape(track['notes'])))
    parts.append('<p class="sheet-gig">{}</p>'.format(html_mod.escape(gig_name)))
    parts.append('</div>')
    if anchor_id:
        parts.append('<a class="sheet-back" href="#index">&uarr; Index</a>')
    parts.append('</div>')

    # The blocks themselves are rendered by the same code the server uses;
    # only the sheet-level decoration below is specific to the PDF.
    for name, html in track_renderer.build_display_blocks(
            track_data, track_path, zss_path=zss_path, zs3_id=zs3_id,
            input_devices=input_devices):
        if name == 'leadsheet':
            parts.append('<div class="sheet-leadsheet-divider"></div>')
            parts.append(html)
        elif name == 'split':
            parts.append('<div class="split-container">{}</div>'.format(html))
        else:
            parts.append(html)

    parts.append('</section>')
    return '\n'.join(parts)


def _track_entries(gigs, data_root):
    """Yield (name, gig_name, track, snapshot_path) for every track.

    Each track dict is a shallow copy carrying its gig's ``input_devices``,
    matching what the server hands the renderer.
    """
    for gig in gigs:
        gig_name = gig.get('name', 'Unnamed gig')
        snapshot_path = os.path.normpath(
            os.path.join(data_root, gig.get('snapshot_path', '')))
        gig_input_devices = gig.get('input_devices', [])
        for track in gig.get('tracks', []):
            track = dict(track)
            track['input_devices'] = gig_input_devices
            yield (track.get('name', 'Untitled'), gig_name, track,
                   snapshot_path)


def _dedupe_by_name(entries):
    """Keep the first entry per track name, preserving the input order."""
    seen = set()
    unique = []
    for entry in entries:
        if entry[0] in seen:
            continue
        seen.add(entry[0])
        unique.append(entry)
    return unique


def build_html(config_path, gigs_filter=None, alpha=False, all_tracks=False,
               title=None, index_pages=None):
    config = load_config(config_path)
    base_dir = os.path.dirname(config_path)
    # Snapshot paths in config.json are relative to the data root (like
    # MY_DATA_DIR in gig_handler.py), NOT to the live-session/config dir.
    data_root = os.path.dirname(base_dir)

    gigs = config.get('gigs', [])
    if gigs_filter:
        wanted = set(gigs_filter)
        gigs = [g for i, g in enumerate(gigs) if str(i) in wanted]

    import html as html_mod
    sheets = []
    titles = []
    cover_title = None

    if all_tracks or alpha:
        entries = list(_track_entries(gigs, data_root))
        if all_tracks:
            # One global document from every track of every merged gig, with
            # the first occurrence of each track name winning.  This replaces
            # the old hand-maintained "All tracks" gig in config.json.
            entries = _dedupe_by_name(entries)
            cover_title = title or 'All tracks'
        else:
            cover_title = gigs[0].get('name', 'Gig') if gigs else 'All tracks'
        if alpha:
            entries.sort(key=lambda e: e[0].lower())

        # Title page
        sheets.append('<section class="gig-header">')
        sheets.append('<h1>{}</h1>'.format(html_mod.escape(cover_title)))
        sheets.append('<p>{} track(s)</p>'.format(len(entries)))
        sheets.append('</section>')

        if alpha:
            # Clickable index at the beginning
            sheets.append('<section class="index" id="index">')
            sheets.append('<h1>Index</h1>')
            sheets.append('<div class="index-list">')
            for i, (name, gig_name, track, snapshot_path) in enumerate(entries):
                suffix = track.get('notes') or gig_name
                left = '{}<span class="index-gig">{}</span>'.format(
                    html_mod.escape(name), html_mod.escape(suffix))
                page = None
                if index_pages is not None and i < len(index_pages):
                    page = index_pages[i]
                if page is None:
                    sheets.append(
                        '<a href="#track-{}">{}</a>'.format(i, left))
                else:
                    sheets.append(
                        '<a href="#track-{}"><span class="index-entry-left">'
                        '{}</span><span class="index-page">{}</span></a>'.format(
                            i, left, html_mod.escape(str(page))))
            sheets.append('</div>')
            sheets.append('</section>')

        # Sheets (alphabetical when --alpha, merged order otherwise)
        for entry in entries:
            anchor_id = 'track-{}'.format(len(titles)) if alpha else None
            sheets.append(
                build_sheet_html(entry[1], entry[2], entry[3], base_dir,
                                 anchor_id=anchor_id))
            titles.append(entry[0])
    else:
        for gig in gigs:
            gig_name = gig.get('name', 'Unnamed gig')
            tracks = gig.get('tracks', [])

            sheets.append('<section class="gig-header">')
            sheets.append('<h1>{}</h1>'.format(
                html_mod.escape(gig_name)))
            sheets.append('<p>{}</p>'.format(
                html_mod.escape(gig.get('description', ''))))
            sheets.append('<p>{} track(s)</p>'.format(len(tracks)))
            sheets.append('</section>')

            if not tracks:
                sheets.append('<section class="sheet">')
                sheets.append('<p class="sheet-notes">No tracks in this gig.</p>')
                sheets.append('</section>')
                continue

            snapshot_path = os.path.normpath(os.path.join(data_root, gig.get('snapshot_path', '')))
            gig_input_devices = gig.get('input_devices', [])

            for idx, track in enumerate(tracks):
                track = dict(track)
                track['input_devices'] = gig_input_devices
                sheets.append(build_sheet_html(gig_name, track, snapshot_path, base_dir))

    doc = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Track Sheets</title>
<style>
{css}
{print_css}
</style>
</head>
<body>
{body}
</body>
</html>""".format(
        css=app_css(),
        print_css=PRINT_CSS,
        body='\n'.join(sheets))
    return doc, titles, cover_title


def html_to_pdf(html_path, pdf_path):
    cmd = [
        'google-chrome', '--headless=new', '--no-sandbox',
        '--disable-gpu', '--disable-dev-shm-usage',
        '--no-pdf-header-footer',
        '--print-to-pdf={}'.format(pdf_path),
        Path(html_path).resolve().as_uri(),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(
            'Chrome failed ({}): {}'.format(
                proc.returncode, proc.stderr.decode('utf-8', 'replace')))


def pin_pdf_links(pdf_path, sheet_titles=None, cover_title=None):
    """Rewrite Chrome's named-destination links to explicit array destinations.

    Chrome/Skia exports internal anchors ('#index', '#track-N') as /Dest /name
    plus a separate /Dests dictionary. Old viewers like iOS 9's iBooks mishandle
    that form and can jump to the wrong page. Replacing every named destination
    with an inline '/Dest [page 0 R /XYZ ...]' array makes navigation reliable.

    Also sets the PDF outline from *sheet_titles* ('Index' + one entry per
    sheet).  Requires pymupdf; skipped with a warning when it is unavailable.
    """
    try:
        import pymupdf
    except ImportError:
        print('NOTE: pymupdf not installed, link destinations left as-is. '
              'Install with "pip install pymupdf" (or "apt install '
              'python3-pymupdf") for iBooks-compatible links.')
        return False

    doc = pymupdf.open(pdf_path)
    resolved = doc.resolve_names()
    converted = 0
    for pno in range(doc.page_count):
        page = doc[pno]
        for xref, typ, _ in page.annot_xrefs():
            raw = doc.xref_object(xref)
            m = re.search(r'/Dest\s*/([A-Za-z0-9_-]+)', raw)
            if not m:
                continue
            target = resolved.get(m.group(1))
            if not target:
                continue
            tp = target['page']
            doc.xref_set_key(xref, 'Dest',
                             '[%d 0 R /XYZ 0 %.2f 0]' % (
                                 doc.page_xref(tp), doc[tp].rect.height))
            converted += 1

    if sheet_titles and converted:
        toc = []
        if cover_title:
            toc.append([1, cover_title[:80], 1])
        idx = resolved.get('index')
        if idx is not None:
            toc.append([1, 'Index', idx['page'] + 1])
        for i, title in enumerate(sheet_titles):
            target = resolved.get('track-{}'.format(i))
            if target is not None:
                toc.append([1, title[:80], target['page'] + 1])
        if toc:
            doc.set_toc(toc)

    tmp = pdf_path + '.tmp'
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)
    print('Pinned {} link destinations (pymupdf)'.format(converted))
    return True



def resolve_track_pages(pdf_path, count):
    """Return the 1-based PDF page number of each ``track-N`` anchor."""
    try:
        import pymupdf
    except ImportError:
        return [None] * count
    doc = pymupdf.open(pdf_path)
    resolved = doc.resolve_names()
    pages = []
    for i in range(count):
        target = resolved.get('track-{}'.format(i))
        pages.append(target['page'] + 1 if target else None)
    doc.close()
    return pages


def add_page_numbers(pdf_path):
    """Overlay a centered page number in the bottom margin of every page."""
    try:
        import pymupdf
    except ImportError:
        print('NOTE: pymupdf not installed, page numbers not added.')
        return False
    doc = pymupdf.open(pdf_path)
    n = doc.page_count
    for pno in range(n):
        page = doc[pno]
        rect = page.rect
        mm = 2.834645669
        band = pymupdf.Rect(0, rect.height - 12 * mm, rect.width,
                            rect.height - 2 * mm)
        font_kwargs = {}
        if os.path.isfile(STATIC_FONT):
            font_kwargs = {'fontname': 'MuseJazzText', 'fontfile': STATIC_FONT}
        else:
            font_kwargs = {'fontname': 'helv'}
        page.insert_textbox(band, str(pno + 1), fontsize=11.25, align=1,
                            color=(0, 0, 0), **font_kwargs)
    tmp = pdf_path + '.tmp'
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)
    print('Added page numbers to {} page(s)'.format(n))
    return True



def main():
    parser = argparse.ArgumentParser(description='Print all gig sheets to PDF')
    parser.add_argument('--config', default=DEFAULT_CONFIG,
                        help='Path to config.json')
    parser.add_argument('--out', default=DEFAULT_OUT,
                        help='Output PDF path')
    parser.add_argument('--keep-html', action='store_true',
                        help='Keep the intermediate HTML file')
    parser.add_argument('--gigs', default='',
                        help='Comma-separated gig indexes to print, or "all" '
                             'for one global PDF of every track (default: all)')
    parser.add_argument('--alpha', action='store_true',
                        help='Sort all tracks alphabetically and add a clickable index page')
    parser.add_argument('--title', default=None,
                        help="Cover title for --gigs all (default: All tracks)")
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        print('Config not found: {}'.format(args.config))
        sys.exit(1)

    gigs_value = args.gigs.strip()
    all_tracks = gigs_value.lower() == 'all'
    if all_tracks:
        gigs_filter = []
    else:
        gigs_filter = [i.strip() for i in gigs_value.split(',') if i.strip()]

    html_path = os.path.splitext(args.out)[0] + '.html'
    pass_html = os.path.splitext(args.out)[0] + '.pass1.html'
    pass_pdf = os.path.splitext(args.out)[0] + '.pass1.pdf'

    index_pages = None
    titles = []
    cover_title = None
    html = None
    try:
        if args.alpha:
            # Two-pass: resolve each track's page number from a first render
            # so the index can show the right page, then rebuild with it.
            for _ in range(3):
                html, titles, cover_title = build_html(
                    args.config, gigs_filter, alpha=args.alpha,
                    all_tracks=all_tracks, title=args.title,
                    index_pages=index_pages)
                with open(pass_html, 'w', encoding='utf-8') as fh:
                    fh.write(html)
                html_to_pdf(pass_html, pass_pdf)
                new_pages = resolve_track_pages(pass_pdf, len(titles))
                if new_pages == index_pages:
                    break
                index_pages = new_pages
        else:
            html, titles, cover_title = build_html(
                args.config, gigs_filter, alpha=args.alpha,
                all_tracks=all_tracks, title=args.title)
    except (OSError, ValueError) as exc:
        # A broken config (missing/malformed include, bad JSON) is a user
        # mistake, not a crash: report it plainly and exit without a traceback.
        print('ERROR: {}'.format(exc), file=sys.stderr)
        sys.exit(1)

    if html is None:
        html, titles, cover_title = build_html(
            args.config, gigs_filter, alpha=args.alpha,
            all_tracks=all_tracks, title=args.title,
            index_pages=index_pages)

    with open(html_path, 'w', encoding='utf-8') as fh:
        fh.write(html)
    n = len(re.findall(r'<section class="sheet"', html))
    print('Rendered {} sheets -> {}'.format(n, html_path))

    html_to_pdf(html_path, args.out)
    print('PDF written: {} ({} bytes)'.format(args.out, os.path.getsize(args.out)))

    add_page_numbers(args.out)

    if args.alpha:
        pin_pdf_links(args.out, titles, cover_title=cover_title)

    for tmp in (pass_html, pass_pdf):
        try:
            os.remove(tmp)
        except FileNotFoundError:
            pass
    if not args.keep_html:
        os.remove(html_path)


if __name__ == '__main__':
    main()
