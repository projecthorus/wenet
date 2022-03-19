#!/usr/bin/env python
#
#   Example reception of some basic 'Secondary Payload' packets.
#   This is a method by which another process or payload can inject data into
#   the Wenet downlink telemetry channel. This script listens for packets
#   emitted by the wenet receive process via UDP, and parses the 'sub-payload' telemetry.
#   
#   Refer to the equivalent sec_payload_tx_example in wenet/tx/examples/
#   for how to send packets from a payload.
#
#   This script requires that a Wenet receiver be running.
#   i.e. start one using the start_rx.sh script.
#
#   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#

import json
import socket
import struct
import datetime
import traceback
from WenetPackets import *



def process_sec_text_message(payload):
    """ Convert a text message payload into a string for display.

    Keyword Arguments:
    payload (str): The packet payload as a string, or a list.
    """
    # Convert the payload into a string if it isn't already.
    payload = bytes(bytearray(payload))

    # Attempt to decode the text message from the payload.
    try:
        #_len = struct.unpack("B",payload[1])[0]
        _len = payload[1]
        _count = struct.unpack(">H",payload[2:4])[0]
        _text = payload[4:4+_len]
    except:
        traceback.print_exc()
        return "Error: Could not decode text message."

    # Return the message as a string.
    return "Text Message %s: %s" % (_count, _text)


def process_sec_floats(payload):
    """ Convert a list-of-floats payload into a string for display

    Keyword Arguments:
    payload (str): The packet payload as a string, or a list.
    """
    # Convert the payload into a string if it isn't already.
    payload = bytes(bytearray(payload))

    output = []

    try:
        # Second byte in the packet is the number of floats present.
        #_len = struct.unpack("B", payload[1])[0]
        _len = payload[1]

        for _i in range(_len):
            _float = struct.unpack(">f", payload[2+_i*4: 6+_i*4])[0]
            output.append(_float)
    except:
        traceback.print_exc()
        return []

    return output




def process_sec_payload(id, payload):
    """ Process data from a secondary payload and print it as a string. 

    Keyword Arguments:
    id (int): The secondary payload id.
    payload (str): The packet's payload.
    """

    # First byte of the payload is a packet type.
    _packet_type = list(bytearray(payload))[0]

    if _packet_type == 0x00:
        # We have a text message packet.
        # Pass this onto process_sec_text_message() to extract the message.

        _payload_str = process_sec_text_message(payload)


    elif _packet_type == 0x10:
        # This is a list of floating point numbers.
        _floats = process_sec_floats(payload)
        _payload_str = "Floats:" + str(_floats)


    print("Sub-Payload #%d - %s" % (id, _payload_str))




def process_udp(udp_packet):
    """ Process received UDP packets. """

    # Parse JSON
    packet_dict = json.loads(udp_packet.decode())

    # There may be other UDP traffic on this port, so we filter for just 'WENET'
    # telemetry packets.
    if packet_dict['type'] == 'WENET':
        # Extract the actual packet contents from the JSON blob.
        packet = packet_dict['packet']

        print(packet)

        # Check for a 'secondary payload' packet
        if decode_packet_type(packet) == WENET_PACKET_TYPES.SEC_PAYLOAD_TELEMETRY:
            # If we have one, extract the secondary payload ID, and the packet contents.
            sec_payload = sec_payload_decode(packet)
            # Send it off to be processed.
            process_sec_payload(id=sec_payload['id'], payload=sec_payload['payload'])

        elif decode_packet_type(packet) == WENET_PACKET_TYPES.GPS_TELEMETRY:
            gps_data = gps_telemetry_decoder(packet)


        else:
            pass


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

    s.bind(('',WENET_TELEMETRY_UDP_PORT))
    print("Started UDP Listener")
    while True:
        try:
            m = s.recvfrom(2048)
        except socket.timeout:
            m = None
        
        if m != None:
            try:
                process_udp(m[0])
            except:
                traceback.print_exc()
                pass
    
    print("Closing UDP Listener")
    s.close()


if __name__ == "__main__":
    try:
        # Start listening for UDP packets
        udp_rx_thread()

    # Keep on going until we get Ctrl-C'd
    except KeyboardInterrupt:
        # Stop the UDP listener.
        udp_listener_running = False