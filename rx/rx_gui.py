#!/usr/bin/env python
#
#   SSDV RX GUI
#
#   Copyright (C) 2019  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
#   TODO:
#       [x] Make functional under Python 2 & Python 3
#       [ ] Completely replace with a browser-based interface.
#
import argparse
import logging
import json
import socket
import sys
import time
from WenetPackets import *
from threading import Thread
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import Qt

try:
    # Python 2
    from Queue import Queue
except ImportError:
    # Python 3
    from queue import Queue


# Auto-resizing Widget, to contain displayed image.
class Label(QtWidgets.QLabel):
    def __init__(self, img):
        super(Label, self).__init__()
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        self.pixmap = QtGui.QPixmap()


    def paintEvent(self, event):
        size = self.size()
        painter = QtGui.QPainter(self)
        point = QtCore.QPoint(0,0)
        scaledPix = self.pixmap.scaled(size, Qt.KeepAspectRatio, transformMode = Qt.SmoothTransformation)
        # start painting the label from left upper corner
        point.setX((size.width() - scaledPix.width())/2)
        point.setY((size.height() - scaledPix.height())/2)
        painter.drawPixmap(point, scaledPix)


class MyWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MyWindow, self).__init__(parent)
        self.label = Label(self)
        self.statusLabel = QtWidgets.QLabel("SSDV: No data yet.")
        self.statusLabel.setFixedHeight(20)
        self.uploaderLabel = QtWidgets.QLabel("Uploader: No Data Yet.")
        self.uploaderLabel.setFixedHeight(20)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.statusLabel)
        self.layout.addWidget(self.uploaderLabel)
        self.rxqueue = Queue(32)


    @QtCore.pyqtSlot(str)
    def changeImage(self, pathToImage, text_message):
        """ Load and display the supplied image, and update the status text field. """
        logging.debug("New image: %s" % pathToImage)
        pixmap = QtGui.QPixmap(pathToImage)
        self.label.pixmap = pixmap
        self.statusLabel.setText(text_message)
        self.label.repaint()
        logging.debug("Re-painted GUI.")


    @QtCore.pyqtSlot(str)
    def update_upload_status(self, queued, uploaded, discarded):
        self.uploaderLabel.setText("Uploader: %d queued, %d uploaded, %d discarded." % (queued, uploaded, discarded))


    def read_queue(self):
        """ This function is called every 100ms in the QtGui thread. """
        try:
            new_packet = self.rxqueue.get_nowait()
            packet_data = json.loads(new_packet)
            if 'filename' in packet_data:
                self.changeImage(packet_data['filename'],packet_data['text'])
            elif 'uploader_status' in packet_data:
                self.update_upload_status(packet_data['queued'], packet_data['uploaded'], packet_data['discarded'])
        except:
            # If there is nothing in the queue we will get a queue.Empty error, so we just return.
            pass


# UDP Listener
udp_listener_running = False
udp_callback = None

def udp_rx():
    global udp_listener_running, udp_callback
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.settimeout(1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except:
        pass
        
    s.bind(('',WENET_IMAGE_UDP_PORT))
    print("Started UDP Listener Thread.")
    udp_listener_running = True
    while udp_listener_running:
        try:
            m = s.recvfrom(512)
        except socket.timeout:
            m = None
        
        if m != None:
            try:
                udp_callback(m[0])
            except Exception as e:
                pass



    print("Closing UDP Listener")
    s.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action='store_true', default=False, help="Verbose output")
    parser.add_argument("--image_port", type=int, default=None, help="UDP port used for communication between Wenet decoder processes. Default: 7890")
    args = parser.parse_args()

    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=log_level)

    # Overwrite the image UDP port if it has been provided
    if args.image_port:
        WENET_IMAGE_UDP_PORT = args.image_port

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('SSDV Viewer')

    main = MyWindow()
    main.resize(800,600)
    main.setWindowTitle("SSDV Viewer")

    udp_callback = main.rxqueue.put_nowait
    t = Thread(target=udp_rx)
    t.start()

    timer = QtCore.QTimer()
    timer.timeout.connect(main.read_queue)
    timer.start(100)

    main.show()

    app.exec_()

    udp_listener_running = False

    sys.exit()
