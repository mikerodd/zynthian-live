#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import logging
import asyncio
import tornado.web
import tornado.ioloop

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
from zs3_handler import init_osc, load_snapshot, load_zs3
from gig_handler import list_gigs, load_gig, get_track_paths
from track_renderer import render_chart

logging.basicConfig(format='%(levelname)s:%(module)s: %(message)s',
                    stream=sys.stderr, level=logging.INFO)
logging.getLogger().setLevel(level=logging.INFO)

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


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
        semitones = int(self.get_argument('transpose', '0'))
        try:
            chart_body = render_chart(
                gig_id=gig_id,
                track_json_path=paths['json_path'],
                zss_path=paths['snapshot_path'],
                zs3_id=zs3_id,
                title=paths['name'],
                notes=paths['notes'],
                semitones=semitones,
                input_devices=paths['input_devices'],
            )
        except Exception as e:
            logging.error("render_chart failed: %s", e)
            self.send_error(500)
            return
        self.render('chart.html', title=paths['name'], chart_body=chart_body)


class ApiLoadSnapshotHandler(BaseHandler):
    def post(self, bank, program):
        logging.info("POST /api/load-snapshot/{}/{}".format(bank, program))
        try:
            success = load_snapshot(int(bank), int(program))
            self.write({'success': success})
        except Exception as e:
            logging.error("load-snapshot failed: {}".format(e))
            self.write({'success': False, 'error': str(e)})


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
