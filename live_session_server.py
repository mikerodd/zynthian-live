#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import logging
import asyncio
import tornado.web
import tornado.ioloop

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from zs3_handler import init_osc, load_zs3
from gig_handler import list_gigs, load_gig, get_chart_path, list_charts

logging.basicConfig(format='%(levelname)s:%(module)s: %(message)s',
                    stream=sys.stderr, level=logging.INFO)
logging.getLogger().setLevel(level=logging.INFO)

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

current_state = {
    'gig_id': None,
    'active_track': None
}


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return True

    def get_template_path(self):
        return TEMPLATE_DIR


class GigListHandler(BaseHandler):
    def get(self):
        gigs = list_gigs()
        self.render('gig_list.html', gigs=gigs)


class LiveViewHandler(BaseHandler):
    def get(self, gig_id):
        gig = load_gig(gig_id)
        if gig is None:
            self.send_error(404)
            return
        charts = list_charts(gig_id)
        tracks_json = json.dumps(gig.get('tracks', []))
        self.render('live_view.html', gig=gig, gig_id=gig_id, charts=charts, tracks_json=tracks_json)


class ChartHandler(BaseHandler):
    def get(self, gig_id, filename):
        fpath = get_chart_path(gig_id, filename)
        if fpath is None:
            self.send_error(404)
            return
        with open(fpath, 'r') as f:
            raw = f.read()
        import re
        m = re.search(r'<body[^>]*>(.*)</body>', raw, re.DOTALL | re.IGNORECASE)
        body = m.group(1) if m else raw
        title = filename.replace('.html', '').replace('-', ' ').title()
        notes = ''
        gig = load_gig(gig_id)
        if gig:
            for track in gig.get('tracks', []):
                if track.get('chart') == filename:
                    title = track.get('name', title)
                    notes = track.get('notes', '')
                    break
        self.set_header('Content-Type', 'text/html')
        self.render('chart_view.html', gig_id=gig_id, title=title, notes=notes, chart_body=body)


class ApiSelectTrackHandler(BaseHandler):
    def post(self, gig_id, track_index):
        logging.info("POST /api/select/{}/{} received".format(gig_id, track_index))
        gig = load_gig(gig_id)
        if gig is None:
            self.write({'error': 'Gig not found'})
            return
        try:
            idx = int(track_index)
            tracks = gig.get('tracks', [])
            if idx < 0 or idx >= len(tracks):
                self.write({'error': 'Invalid track index'})
                return
            track = tracks[idx]
            zs3_id = track.get('zs3_id')
            if zs3_id:
                success = load_zs3(zs3_id)
            else:
                success = True
            current_state['gig_id'] = gig_id
            current_state['active_track'] = idx
            self.write({
                'success': True,
                'track': track,
                'active_track': idx,
                'zs3_loaded': success
            })
            logging.info("Track {} selected: {}".format(idx, track.get('name', '')))
        except ValueError:
            self.write({'error': 'Invalid track index'})


class ApiStateHandler(BaseHandler):
    def get(self, gig_id):
        if current_state['gig_id'] == gig_id:
            self.write(current_state)
        else:
            self.write({'gig_id': gig_id, 'active_track': None})


def make_app():
    settings = {
        'template_path': TEMPLATE_DIR,
        'static_path': STATIC_DIR,
        'template_whitespace': 'single',
        'cookie_secret': 'zynthian_live_session',
        'login_url': '/login',
        'debug': False,
    }
    return tornado.web.Application([
        (r'/$', GigListHandler),
        (r'/gig/([^/]+)$', LiveViewHandler),
        (r'/chart/([^/]+)/([^/]+)$', ChartHandler),
        (r'/api/select/([^/]+)/([^/]+)$', ApiSelectTrackHandler),
        (r'/api/state/([^/]+)$', ApiStateHandler),
        (r'/static/(.*)$', tornado.web.StaticFileHandler, {'path': STATIC_DIR}),
    ], **settings)


async def ashutdown():
    logging.info("Live Session server stopped")

async def amain():
    init_osc()
    app = make_app()
    port = int(os.environ.get('LIVE_SESSION_PORT', 8080))
    app.listen(port, address='0.0.0.0')
    logging.info("Live Session server started on port {}".format(port))
    await asyncio.Event().wait()


if __name__ == '__main__':
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("Shutting down on SIGINT")
    finally:
        asyncio.run(ashutdown())
