#!/usr/bin/env python
#
#   Wenet Web GUI
#
#   Copyright (C) 2019  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
#   A really hacky first attempt at a live-updating web interface that displays wenet imagery.
#
#   Run this instead of rx_gui in the startup scripts, and then access at http://localhost:5003/
#
#   TODO:
#       [ ] Automatic re-scaling of images in web browser.
#       [ ] Add Display of GPS telemetry and text messages.
#
import json
import logging
import flask
from flask_socketio import SocketIO
import time
import traceback
import socket
import sys
import datetime
from threading import Thread, Lock
from io import BytesIO

from WenetPackets import *

# Define Flask Application, and allow automatic reloading of templates for dev
app = flask.Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# SocketIO instance
socketio = SocketIO(app)


# Latest Image
latest_image = None
latest_image_lock = Lock()


#
#   Flask Routes
#

@app.route("/")
def flask_index():
    """ Render main index page """
    return flask.render_template('index.html')


@app.route("/latest.jpg")
def serve_latest_image():
    global latest_image, latest_image_lock
    if latest_image == None:
        flask.abort(404)
    else:
        # Grab image bytes.
        latest_image_lock.acquire()
        _temp_image = bytes(latest_image)
        latest_image_lock.release()

        return flask.send_file(
            BytesIO(_temp_image),
            mimetype='image/jpeg',
            as_attachment=False)



def flask_emit_event(event_name="none", data={}):
    """ Emit a socketio event to any clients. """
    socketio.emit(event_name, data, namespace='/update_status') 


# SocketIO Handlers

@socketio.on('client_connected', namespace='/update_status')
def update_client_display(data):
    pass



def update_image(filename, description):
    global latest_image, latest_image_lock
    try:
        with open(filename, 'rb') as _new_image:
            _data = _new_image.read()

        latest_image_lock.acquire()
        latest_image = bytes(_data)
        latest_image_lock.release()

        # Trigger the clients to update.
        flask_emit_event('image_update', data={'text':description})

        logging.debug("Loaded new image: %s" % filename)

    except Exception as e:
        logging.error("Error loading new image %s - %s" % (filename, str(e)))


def handle_telemetry(packet):
    """ Handle GPS and Text message packets from the wenet receiver """

    # Decode GPS and IMU packets, and pass onto their respective GUI update functions.
    packet_type = decode_packet_type(packet)

    if packet_type == WENET_PACKET_TYPES.GPS_TELEMETRY:
        # GPS data from the payload
        gps_data = gps_telemetry_decoder(packet)
        if gps_data['error'] == 'None':
            flask_emit_event('gps_update', data=gps_data)

    elif packet_type == WENET_PACKET_TYPES.TEXT_MESSAGE:
        # A text message from the payload.
        text_data = decode_text_message(packet)
        if text_data['error'] == 'None':
            flask_emit_event('text_update', data=text_data)

    elif packet_type == WENET_PACKET_TYPES.ORIENTATION_TELEMETRY:
        # Orientation data from the payload
        orientation_data = orientation_telemetry_decoder(packet)
        if orientation_data['error'] == 'None':
            flask_emit_event('orientation_update', data=orientation_data)

    elif packet_type == WENET_PACKET_TYPES.IMAGE_TELEMETRY:
        # image data from the payload
        image_data = image_telemetry_decoder(packet)
        if image_data['error'] == 'None':
            flask_emit_event('image_telem_update', data=image_data)

    else:
        # Discard any other packet type.
        pass


def process_udp(packet):

    packet_dict = json.loads(packet.decode('ascii'))

    if 'filename' in packet_dict:
        # New image to load
        update_image(packet_dict['filename'], packet_dict['text'])

    elif 'uploader_status' in packet_dict:
        # Information from the uploader process.
        flask_emit_event('uploader_update', data=packet_dict)

    elif 'snr' in packet_dict:
        # Modem statistics packet
        flask_emit_event('modem_stats', data=packet_dict)

    elif 'type' in packet_dict:
        # Generic telemetry packet from the wenet RX.
        # This could be GPS telemetry, text data, or something else..
        if packet_dict['type'] == 'WENET':
            handle_telemetry(packet_dict['packet'])



udp_listener_running = False
def udp_rx_thread():
    """ Listen on a port for UDP broadcast packets, and pass them onto process_udp()"""
    global udp_listener_running
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.settimeout(1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except:
        pass
    s.bind(('',WENET_IMAGE_UDP_PORT))
    logging.info("Started UDP Listener Thread.")
    udp_listener_running = True
    while udp_listener_running:
        try:
            m = s.recvfrom(8192)
        except socket.timeout:
            m = None
        
        if m != None:
            try:
                process_udp(m[0])
            except:
                traceback.print_exc()
                pass
    
    logging.info("Closing UDP Listener")
    s.close()



if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--listen_port",default=5003,help="Port to run Web Server on. (Default: 5003)")
    parser.add_argument("-v", "--verbose", action='store_true', help="Enable debug output.")
    args = parser.parse_args()


    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.ERROR

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=log_level)

    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.getLogger("socketio").setLevel(logging.ERROR)
    logging.getLogger("engineio").setLevel(logging.ERROR)
    logging.getLogger("geventwebsocket").setLevel(logging.ERROR)

    t = Thread(target=udp_rx_thread)
    t.start()

    # Run the Flask app, which will block until CTRL-C'd.
    socketio.run(app, host='0.0.0.0', port=args.listen_port)

    udp_listener_running = False



