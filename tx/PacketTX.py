#!/usr/bin/env python2.7
#
# Wenet Packet Transmitter Class
#
#   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
# Frames packets (preamble, unique word, checksum)
# and transmits them out of a serial port.
#
#
#  NOTE: The RPi UART isn't spot on with its baud rate.
#  Recent firmware updates have improved the accuracy slightly, but it's still
#  a bit off. Consequently, 115200 baud is actually around 115177 baud.
#


import serial
import sys
import os
import datetime
import crcmod
import json
import socket
import struct
import traceback
from time import sleep
from threading import Thread
import numpy as np
from ldpc_encoder import *
from queue import Queue

class PacketTX(object):
    """ Packet Transmitter Class

    The core of the Wenet transmitter stack.
    This class handles framing, FEC, and transmission of packets via a
    serial port. 

    Intended to be used with the David Rowe's fsk_demod software, with receiver
    glue code available in the 'rx' directory of this repository.

    Packet framing is as follows:
        Preamble: 16 repeats of 0x55. May not be required, but helps with timing estimation on the demod.
        Unique Word: 0xABCDEF01  Used for packet detection in the demod chain.
        Packet: 256 bytes of arbitrary binary data.
        Checksum: CRC16 checksum.
        Parity bits: 516 bits (zero-padded to 65 bytes) of LDPC parity bits, using a r=0.8 Repeat-accumulate code, developed by
                     Bill Cowley, VK5DSP. See ldpc_enc.c for more details.

    Packets are transmitted from two queues, named 'telemetry' and 'ssdv'.
    The 'telemetry' queue is intended for immediate transmission of low-latency telemetry packets,
    for example, GPS or IMU data. Care must be taken to not over-use this queue, at the detriment of image transmission.
    The 'ssdv' queue is used for transmission of large amounts of image (SSDV) data, and up to 4096 packets can be queued for transmit.

    """

    # Transmit Queues.
    ssdv_queue = Queue(4096) # Up to 1MB of 256 byte packets
    telemetry_queue = Queue(256) # Keep this queue small. It's up to the user not to over-use this queue.

    # Framing parameters
    unique_word = b"\xab\xcd\xef\x01"
    preamble = b"\x55"*16

    # Idle sequence, transmitted if there is nothing in the transmit queues.
    idle_sequence = b"\x56"*256

    # Transmit thread active flag.
    transmit_active = False

    # Internal counter for text messages.
    text_message_count = 0
    image_telem_count = 0

    # WARNING: 115200 baud is ACTUALLY 115386.834 baud, as measured using a freq counter.
    def __init__(self,
        serial_port="/dev/ttyAMA0", 
        serial_baud=115200, 
        payload_length=256, 
        fec=True, 
        debug = False, 
        callsign="N0CALL",
        udp_listener = None,
        log_file = None):
        
        # Instantiate our low-level transmit interface, be it a serial port, or the BinaryDebug class.
        if debug == True:
            self.s = BinaryDebug()
            self.debug = True
        else:
            self.debug = False
            self.s = serial.Serial(serial_port,serial_baud)


        self.payload_length = payload_length
        self.callsign = callsign.encode('ascii')
        self.fec = fec

        self.crc16 = crcmod.predefined.mkCrcFun('crc-ccitt-false')

        self.idle_message = self.frame_packet(self.idle_sequence,fec=fec)

        if log_file != None:
            self.log_file = open(log_file,'a')
            self.log_file.write("Started Transmitting at %s\n" % datetime.datetime.utcnow().isoformat())
        else:
            self.log_file = None

        # Startup the UDP listener, if enabled.
        self.listener_thread = None
        self.udp = None
        self.udp_listener_running = False

        if udp_listener != None:
            self.udp_port = udp_listener
            self.start_udp()


    def start_tx(self):
        self.transmit_active = True
        txthread = Thread(target=self.tx_thread)
        txthread.start()



    def frame_packet(self,packet, fec=False):
        # Ensure payload size is equal to the desired payload length
        if len(packet) > self.payload_length:
            packet = packet[:self.payload_length]

        if len(packet) < self.payload_length:
            packet = packet + b"\x55"*(self.payload_length - len(packet))

        crc = struct.pack("<H",self.crc16(packet))

        if fec:
            parity = ldpc_encode(packet + crc)
            return self.preamble + self.unique_word + packet + crc + parity
        else:
            return self.preamble + self.unique_word + packet + crc 


    def set_idle_message(self, message):
        temp_msg = b"\x00" + b"DE %s: \t%s" % (self.callsign, message.encode('ascii'))
        self.idle_message = self.frame_packet(temp_msg,fec=self.fec)


    def generate_idle_message(self):
        # Append a \x00 control code before the data
        return b"\x00" + b"DE %s: \t%s" % (self.callsign,self.idle_message)


    def tx_thread(self):
        """ Main Transmit Thread.
            
            Checks telemetry and image queues in order, and transmits a packet.
        """
        while self.transmit_active:
            if self.telemetry_queue.qsize()>0:
                packet = self.telemetry_queue.get_nowait()
                self.s.write(packet)
            elif self.ssdv_queue.qsize()>0:
                packet = self.ssdv_queue.get_nowait()
                self.s.write(packet)
            else:
                if not self.debug:
                    self.s.write(self.idle_message)
                else:
                    # TODO: Tune this value.
                    sleep(0.05)
        
        print("Closing Thread")
        self.s.close()


    def close(self):
        self.transmit_active = False
        self.udp_listener_running = False
        #self.listener_thread.join()


    # Deprecated function
    def tx_packet(self,packet,blocking = False):
        self.ssdv_queue.put(self.frame_packet(packet, self.fec))

        if blocking:
            while not self.ssdv_queue.empty():
                sleep(0.01)


    # Deprecated function.
    def wait(self):
        while (not self.ssdv_queue.empty()) and self.transmit_active:
            sleep(0.01)

    # New packet queueing and queue querying functions (say that 3 times fast)

    def queue_image_packet(self,packet):
        self.ssdv_queue.put(self.frame_packet(packet, self.fec))


    def queue_image_file(self, filename):
        """ Read in <filename> and transmit it, 256 bytes at a time.
            Intended for transmitting SSDV images.
        """
        file_size = os.path.getsize(filename)
        try:
            f = open(filename,'rb')
            for x in range(file_size//256):
                data = f.read(256)
                self.queue_image_packet(data)
            f.close()
            return True
        except:
            return False

    def image_queue_empty(self):
        return self.ssdv_queue.qsize() == 0


    def queue_telemetry_packet(self, packet, repeats = 1):
        for n in range(repeats):
            self.telemetry_queue.put(self.frame_packet(packet, self.fec))


    def telemetry_queue_empty(self):
        return self.telemetry_queue.qsize() == 0


#
#   Various Telemetry Packet Generation functions
#

    def transmit_text_message(self,message, repeats = 1):
        """ Generate and Transmit a Text Message Packet

        Keyword Arguments:
        message: A string, up to 252 characters long, to transmit.
        repeats: An optional field, defining the number of time to
                 transmit the packet. Can be used to increase chances
                 of receiving the packet, at the expense of higher
                 channel usage.

        """
        # Increment text message counter.
        self.text_message_count = (self.text_message_count+1)%65536
        # Clip message if required.
        if len(message) > 252:
            message = message[:252]

        packet = b"\x00" + struct.pack(">BH",len(message),self.text_message_count) + message.encode('ascii')

        self.queue_telemetry_packet(packet, repeats=repeats)
        log_string = "TXing Text Message #%d: %s" % (self.text_message_count,message)

        if self.log_file != None:
            self.log_file.write(datetime.datetime.now().isoformat() + "," + log_string + "\n")

        print(log_string)


    def transmit_gps_telemetry(self, gps_data):
        """ Generate and Transmit a GPS Telemetry Packet.

        Keyword Arguments:
        gps_data: A dictionary, as produced by the UBloxGPS class. It must have the following fields:
                  latitude, longitude, altitude, ground_speed, ascent_rate, heading, gpsFix, numSV,
                  week, iTOW, leapS, dynamic_model.

        The generated packet format is in accordance with the specification in:
        https://docs.google.com/document/d/12230J1X3r2-IcLVLkeaVmIXqFeo3uheurFakElIaPVo/edit?usp=sharing

        The corresponding decoder for this packet format is within rx/WenetPackets.py, in the function
        gps_telemetry_decoder

        """

        try:
            gps_packet = struct.pack(">BHIBffffffBBB",
                1,  # Packet ID for the GPS Telemetry Packet.
                gps_data['week'],
                int(gps_data['iTOW']*1000), # Convert the GPS week value to milliseconds, and cast to an int.
                gps_data['leapS'],
                gps_data['latitude'],
                gps_data['longitude'],
                gps_data['altitude'],
                gps_data['ground_speed'],
                gps_data['heading'],
                gps_data['ascent_rate'],
                gps_data['numSV'],
                gps_data['gpsFix'],
                gps_data['dynamic_model']
                )

            self.queue_telemetry_packet(gps_packet)
        except:
            traceback.print_exc()

    def transmit_orientation_telemetry(self, week, iTOW, leapS, orientation_data):
        """ Generate and Transmit an Payload Orientation telemetry packet.

        Keyword Arguments:
        week: GPS week number
        iTOW: GPS time-of-week (Seconds)
        leapS: GPS leap-seconds value (necessary to convert GPS time to UTC time)

        orientation_data: A dictionary, as produced by the BNO055 Class. It must have the following fields:


        The generated packet format is in accordance with the specification in 
        https://docs.google.com/document/d/12230J1X3r2-IcLVLkeaVmIXqFeo3uheurFakElIaPVo/edit?usp=sharing

        The corresponding decoder for this packet format is within rx/WenetPackets.py, in the function
        orientation_telemetry_decoder

        """
        try:
            orientation_packet = struct.pack(">BHIBBBBBBBbfffffff",
                2,  # Packet ID for the Orientation Telemetry Packet.
                week,
                int(iTOW*1000), # Convert the GPS week value to milliseconds, and cast to an int.
                leapS,
                orientation_data['sys_status'],
                orientation_data['sys_error'],
                orientation_data['sys_cal'],
                orientation_data['gyro_cal'],
                orientation_data['accel_cal'],
                orientation_data['magnet_cal'],
                orientation_data['temp'],
                orientation_data['euler_heading'],
                orientation_data['euler_roll'],
                orientation_data['euler_pitch'],
                orientation_data['quaternion_x'],
                orientation_data['quaternion_y'],
                orientation_data['quaternion_z'],
                orientation_data['quaternion_w']
                )

            self.queue_telemetry_packet(orientation_packet)
        except:
            traceback.print_exc()

        return

    def transmit_image_telemetry(self, gps_data, orientation_data, image_id=0, callsign='N0CALL', repeats=1):
        """ Generate and Transmit an Image telemetry packet.

        Keyword Arguments:
        gps_data: A dictionary, as produced by the UBloxGPS class. It must have the following fields:
                  latitude, longitude, altitude, ground_speed, ascent_rate, heading, gpsFix, numSV,
                  week, iTOW, leapS, dynamic_model.

        orientation_data: A dictionary, as produced by the BNO055 Class. It must have the following fields:


        image_id: The ID of the image related to the above position and orientation data.

        The generated packet format is in accordance with the specification in 
        https://docs.google.com/document/d/12230J1X3r2-IcLVLkeaVmIXqFeo3uheurFakElIaPVo/edit?usp=sharing

        The corresponding decoder for this packet format is within rx/WenetPackets.py, in the function
        image_telemetry_decoder

        """
        self.image_telem_count = (self.image_telem_count+1)%65536

        try:
            image_packet = struct.pack(">BH7pBHIBffffffBBBBBBBBBbfffffff",
                0x54,   # Packet ID for the GPS Telemetry Packet.
                self.image_telem_count,
                callsign.encode(),
                image_id,
                gps_data['week'],
                int(gps_data['iTOW']*1000), # Convert the GPS week value to milliseconds, and cast to an int.
                gps_data['leapS'],
                gps_data['latitude'],
                gps_data['longitude'],
                gps_data['altitude'],
                gps_data['ground_speed'],
                gps_data['heading'],
                gps_data['ascent_rate'],
                gps_data['numSV'],
                gps_data['gpsFix'],
                gps_data['dynamic_model'],
                orientation_data['sys_status'],
                orientation_data['sys_error'],
                orientation_data['sys_cal'],
                orientation_data['gyro_cal'],
                orientation_data['accel_cal'],
                orientation_data['magnet_cal'],
                orientation_data['temp'],
                orientation_data['euler_heading'],
                orientation_data['euler_roll'],
                orientation_data['euler_pitch'],
                orientation_data['quaternion_x'],
                orientation_data['quaternion_y'],
                orientation_data['quaternion_z'],
                orientation_data['quaternion_w']
                )

            self.queue_telemetry_packet(image_packet, repeats=repeats)
        except:
            traceback.print_exc()


    def transmit_secondary_payload_packet(self, id=1, data=[], repeats=1):
        """ Generate and transmit a packet supplied by a 'secondary' payload.
        These will usually be provided via a UDP messaging system, described in the functions
        further below.

        Keyword Arguments:
        id (int): A payload ID number, 0-255.
        data (list): The payload contents, as a list of integers. Maximum of 254 bytes.
        repeats (int): (Optional) The number of times to transmit this packet.
        """

        # Clip the id to 0-255.
        _id = int(id) % 256

        # Convert the provided data to a string
        _data = bytes(bytearray(data))
        # Clip to 254 bytes.
        if len(_data) > 254:
            _data = _data[:254]

        
        _packet = b"\x03" + struct.pack(">B",_id) + _data

        self.queue_telemetry_packet(_packet, repeats=repeats)


        
    #
    # UDP messaging functions.
    #

    def handle_udp_packet(self, packet):
        ''' Process a received UDP packet '''
        try:
            packet_dict = json.loads(packet.decode())

            if packet_dict['type'] == 'WENET_TX_TEXT':
                # Transmit an arbitrary text packet.
                # We assume the data is a string.
                self.transmit_text_message(packet_dict['packet'])

            elif packet_dict['type'] == 'WENET_TX_SEC_PAYLOAD':
                # This is a 'secondary' payload packet. It needs to have a 'id' field,
                # and a 'data' field which contains the packet contents, provided as a *list of integers*.
                # The user can optionally provide a 'repeats' integer, which defines the number of times
                # to repeat transmission of the packet.
                _id = int(packet_dict['id'])

                if 'repeats' in packet_dict:
                    _repeats = int(packet_dict['repeats'])
                else:
                    _repeats = 1


                self.transmit_secondary_payload_packet(id=_id, data=packet_dict['packet'], repeats=_repeats)

            else:
                pass


        except Exception as e:
            print("Could not parse packet: %s" % str(e))
            traceback.print_exc()


    def udp_rx_thread(self):
        ''' Listen for Broadcast UDP packets '''

        self.udp = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.udp.settimeout(1)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except:
            pass
        self.udp.bind(('',self.udp_port))
        print("Started UDP Listener Thread.")
        self.udp_listener_running = True

        while self.udp_listener_running:
            try:
                m = self.udp.recvfrom(4096)
            except socket.timeout:
                m = None
            except:
                traceback.print_exc()
            
            if m != None:
                self.handle_udp_packet(m[0])
        
        print("Closing UDP Listener")
        self.udp.close()


    def start_udp(self):
        if self.listener_thread is None:
            self.listener_thread = Thread(target=self.udp_rx_thread)
            self.listener_thread.start()





class BinaryDebug(object):
    """ Debug binary 'transmitter' Class
    Used to write packet data to a file in one-bit-per-char (i.e. 0 = 0x00, 1 = 0x01)
    format for use with codec2-dev's fsk modulator.
    Useful for debugging, that's about it.
    """
    def __init__(self):
        self.f = open("debug.bin",'wb')

    def write(self,data):
        # TODO: Add in RS232 framing
        raw_data = np.array([],dtype=np.uint8)
        for d in data:
            d_array = np.unpackbits(np.fromstring(d,dtype=np.uint8))
            raw_data = np.concatenate((raw_data,[0],d_array[::-1],[1]))

        self.f.write(raw_data.astype(np.uint8).tostring())

    def close(self):
        self.f.close()


if __name__ == "__main__":
    """ Test script, which transmits a text message repeatedly. """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--txport", default="/dev/ttyAMA0", type=str, help="Transmitter serial port. Defaults to /dev/ttyAMA0")
    parser.add_argument("--baudrate", default=115200, type=int, help="Transmitter baud rate. Defaults to 115200 baud.")
    args = parser.parse_args()
    debug_output = False # If True, packet bits are saved to debug.bin as one char per bit.


    tx = PacketTX(
        debug=debug_output,
        serial_port=args.txport,
        serial_baud=args.baudrate,
        udp_listener=55674)
    tx.start_tx()

    try:
        while True:
            # Transmit a text message.
            tx.transmit_text_message("This is a test!")

            time.sleep(1)

    except KeyboardInterrupt:
        tx.close()
        print("Closing")