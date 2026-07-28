# -*- coding: utf-8 -*-
import logging

try:
    import pyliblo3 as liblo
    LIBLO_AVAILABLE = True
except ImportError:
    try:
        import liblo
        LIBLO_AVAILABLE = True
    except ImportError:
        LIBLO_AVAILABLE = False

ZYNTHIAN_UI_OSC_ADDR = None


def init_osc(host='localhost', port=1370):
    global ZYNTHIAN_UI_OSC_ADDR
    if LIBLO_AVAILABLE:
        ZYNTHIAN_UI_OSC_ADDR = liblo.Address(host, port, liblo.UDP)
        logging.info("OSC initialized: {}:{}".format(host, port))
    else:
        logging.warning("pyliblo3/liblo not available, OSC disabled")


def load_zs3(zs3_id):
    if ZYNTHIAN_UI_OSC_ADDR is None:
        logging.warning("OSC not initialized, cannot load ZS3 '{}'".format(zs3_id))
        return False
    try:
        liblo.send(ZYNTHIAN_UI_OSC_ADDR, "/CUIA/ZS3_LOAD", ("s", str(zs3_id)))
        logging.info("Sent ZS3_LOAD: {}".format(zs3_id))
        return True
    except Exception as e:
        logging.error("Failed to send ZS3_LOAD '{}': {}".format(zs3_id, e))
        return False
