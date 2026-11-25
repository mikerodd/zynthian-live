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
from track_renderer import render_chart, build_play_along_html
import spaph_client

logging.basicConfig(format='%(levelname)s:%(module)s: %(message)s',
                    stream=sys.stderr, level=logging.INFO)
logging.getLogger().setLevel(level=logging.INFO)

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


# Play-along mode is a single server-side switch shared by every device.
PLAY_ALONG = {'enabled': False}

# Transport commands for the backing track, as spaph console commands.
SEEK_STEP_SECONDS = 10
VOLUME_STEP_DB = 2
BACKING_COMMANDS = {
    'pause': 'backing pause',
    'stop': 'backing stop',
    'begin': 'backing begin',
    'back': 'backing seek -{}'.format(SEEK_STEP_SECONDS),
    'forward': 'backing seek +{}'.format(SEEK_STEP_SECONDS),
    'volume-down': 'backing volume -{}'.format(VOLUME_STEP_DB),
    'volume-up': 'backing volume +{}'.format(VOLUME_STEP_DB),
}
# The file spaph has loaded for play-along. spaph does not report back, so this is what
# the server last asked for; a Play for a different file loads it first.
BACKING = {'file': None}


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return True

    def get_template_path(self):
        return TEMPLATE_DIR

    def spaph_result(self, call):
        try:
            call()
        except OSError as e:
            logging.error('spaph request failed: %s', e)
            self.set_status(503)
            self.write({'ok': False, 'error': 'spaph unreachable'})
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
        commands = paths.get('winthian_commands') or []
        if not commands:
            commands = ['plugin unload all']
        for cmd in commands:
            try:
                spaph_client.command(cmd)
            except OSError as e:
                logging.error('winthian command failed: %s', e)
        controls_html = ''
        if PLAY_ALONG['enabled']:
            controls_html = build_play_along_html(gig_id, track_idx, paths['play_along'])
        try:
            chart_body = render_chart(
                gig_id=gig_id,
                track_json_path=paths['json_path'],
                zss_path=paths['snapshot_path'],
                zs3_id=zs3_id,
                title=paths['name'],
                notes=paths['notes'],
                input_devices=paths['input_devices'],
                controls_html=controls_html,
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
            if BACKING['file'] != track:
                spaph_client.command('backing load ' + track)
                BACKING['file'] = track
            spaph_client.command('backing play')

        self.spaph_result(start)


class ApiBackingActionHandler(BaseHandler):
    def post(self, action):
        command = BACKING_COMMANDS.get(action)
        if command is None:
            self.send_error(404)
            return
        self.spaph_result(lambda: spaph_client.command(command))


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
        (r'/api/backing/(pause|stop|begin|back|forward|volume-down|volume-up)$', ApiBackingActionHandler),
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
