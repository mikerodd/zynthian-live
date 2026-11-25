#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import html
import json
import logging
import asyncio
import tornado.web

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from zs3_handler import init_osc, load_snapshot, load_zs3
from gig_handler import list_gigs, load_gig, get_track_paths
from track_renderer import render_chart
import mpd_client
from mpd_client import SEEK_STEP

logging.basicConfig(format='%(levelname)s:%(module)s: %(message)s',
                    stream=sys.stderr, level=logging.INFO)
logging.getLogger().setLevel(level=logging.INFO)

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


# Play-along mode is a single server-side switch shared by every device.
PLAY_ALONG = {'enabled': False}

MPD_ACTIONS = {
    'pause': lambda: mpd_client.pause(),
    'stop': lambda: mpd_client.stop(),
    'begin': lambda: mpd_client.begin(),
    'back': lambda: mpd_client.seek(-SEEK_STEP),
    'forward': lambda: mpd_client.seek(SEEK_STEP),
}


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return True

    def get_template_path(self):
        return TEMPLATE_DIR

    def mpd_result(self, call):
        try:
            call()
        except mpd_client.MpdError as e:
            self.set_status(409)
            self.write({'ok': False, 'error': str(e)})
        except OSError as e:
            logging.error('MPD request failed: %s', e)
            self.set_status(503)
            self.write({'ok': False, 'error': 'MPD unreachable'})
        else:
            self.write({'ok': True})


class GigListHandler(BaseHandler):
    def get(self):
        gigs = list_gigs()
        self.render('gig_list.html', gigs=gigs,
                    play_along_mode=PLAY_ALONG['enabled'])


class LiveViewHandler(BaseHandler):
    def get(self, gig_id):
        gig = load_gig(gig_id)
        if gig is None:
            self.send_error(404)
            return
        self.render('live_view.html', gig=gig, gig_id=gig_id)


class ChartRenderHandler(BaseHandler):
    def get(self, gig_id, track_idx):
        paths = get_track_paths(gig_id, track_idx)
        if paths is None:
            self.send_error(404)
            return
        zs3_id = paths['zs3_id']
        if zs3_id:
            load_zs3(zs3_id)
        try:
            chart_body = render_chart(
                gig_id=gig_id,
                track_json_path=paths['json_path'],
                zss_path=paths['snapshot_path'],
                zs3_id=zs3_id,
                title=paths['name'],
                notes=paths['notes'],
                input_devices=paths['input_devices'],
            )
        except ValueError as e:
            # includes json.JSONDecodeError: a malformed track file, which
            # says exactly where it went wrong, so pass it on rather than
            # making the user hunt through the journal
            name = os.path.basename(paths['json_path'] or '')
            logging.error('invalid JSON in track %s: %s', name, e)
            self.set_status(500)
            self.finish(
                '<!doctype html><meta charset="utf-8">'
                '<title>Invalid track JSON</title>'
                '<h1>Invalid JSON in {}</h1><p>{}</p>'
                '<p>The file must be valid JSON; check the position above.</p>'
                .format(html.escape(name), html.escape(str(e))))
            return
        except Exception as e:
            logging.error("render_chart failed: %s", e)
            self.send_error(500)
            return
        self.render('chart.html', title=paths['name'], chart_body=chart_body,
                    gig_id=gig_id, track_idx=track_idx,
                    play_along=paths['play_along'],
                    play_along_mode=PLAY_ALONG['enabled'])


class ApiLoadSnapshotHandler(BaseHandler):
    def post(self, bank, program):
        logging.info("POST /api/load-snapshot/{}/{}".format(bank, program))
        try:
            success = load_snapshot(int(bank), int(program))
            self.write({'success': success})
        except Exception as e:
            logging.error("load-snapshot failed: {}".format(e))
            self.write({'success': False, 'error': str(e)})


class ApiPlayAlongModeHandler(BaseHandler):
    def get(self):
        self.write({'enabled': PLAY_ALONG['enabled']})

    def post(self):
        try:
            body = json.loads(self.request.body or b'{}')
        except ValueError:
            self.set_status(400)
            self.write({'ok': False, 'error': 'invalid JSON'})
            return
        PLAY_ALONG['enabled'] = bool(body.get('enabled'))
        logging.info('play-along mode: %s', PLAY_ALONG['enabled'])
        self.write({'enabled': PLAY_ALONG['enabled']})


class ApiPlayAlongPlayHandler(BaseHandler):
    def post(self, gig_id, track_idx):
        paths = get_track_paths(gig_id, track_idx)
        if paths is None:
            self.send_error(404)
            return
        track = paths['play_along']
        if not track:
            self.set_status(400)
            self.write({'ok': False, 'error': 'no play-along track for this song'})
            return

        def start():
            state, current = mpd_client.state_and_file()
            if current == track and state == 'pause':
                mpd_client.resume()
            elif current == track and state == 'play':
                return
            else:
                mpd_client.play_track(track)

        self.mpd_result(start)


class ApiMpdActionHandler(BaseHandler):
    def post(self, action):
        call = MPD_ACTIONS.get(action)
        if call is None:
            self.send_error(404)
            return
        self.mpd_result(call)


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
        (r'/chart/([^/]+)/(\d+)$', ChartRenderHandler),
        (r'/api/load-snapshot/([^/]+)/([^/]+)$', ApiLoadSnapshotHandler),
        (r'/api/play-along$', ApiPlayAlongModeHandler),
        (r'/api/play-along/play/([^/]+)/(\d+)$', ApiPlayAlongPlayHandler),
        (r'/api/mpd/(pause|stop|begin|back|forward)$', ApiMpdActionHandler),
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
    logging.info("REMINDER: check that the MIDI Master Channel is configured in Zynthian "
                 "webconf (Settings -> MIDI -> Master Channel). Snapshot loading via bank/"
                 "program change only works if it is set.")
    await asyncio.Event().wait()


if __name__ == '__main__':
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("Shutting down on SIGINT")
    finally:
        asyncio.run(ashutdown())
