#!/usr/bin/env python
#
#   Example generation of some basic 'Secondary Payload' packets.
#   This is a method by which another process or payload can inject data into
#   the Wenet downlink telemetry channel.
#   
#   Refer to the equivalent sec_payload_rx_example in wenet/rx/
#   for how to receive these packets on the ground-station end.
#
#   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#

import socket, struct, time, json, random


def emit_secondary_packet(id=0, packet="", repeats = 1, hostname='<broadcast>', port=55674):
    """ Send a Secondary Payload data packet into the network, to (hopefully) be
        transmitted by a Wenet transmitter.

        Keyword Arguments:
        id (int): Payload ID number, 0 - 255
        packet (): Packet data, packed as a byte array. Maximum of 254 bytes in size.
        repeats (int): Number of times to re-transmit this packet. Defaults to 1.
        hostname (str): Hostname of the Wenet transmitter. Defaults to using UDP broadcast.
        port (int): UDP port of the Wenet transmitter. Defaults to 55674.

    """


    telemetry_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    # Set up the telemetry socket so it can be re-used.
    telemetry_socket.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
    telemetry_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # We need the following if running on OSX.
    try:
        telemetry_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except:
        pass

    # Place data into dictionary.
    data = {'type': 'WENET_TX_SEC_PAYLOAD', 'id': int(id), 'repeats': int(repeats), 'packet': list(bytearray(packet))}

    # Send to target hostname. If this fails just send to localhost.
    try:
        telemetry_socket.sendto(json.dumps(data).encode(), (hostname, port))
    except socket.error:
        telemetry_socket.sendto(json.dumps(data).encode(), ('127.0.0.1', port))

    telemetry_socket.close()


# Global text message counter.
text_message_counter = 0

def create_text_message(message):
    """ Create a text message packet, for transmission within a 'secondary payload' message.
    This is in the same format as a standard wenet text message, however the maximum message
    length is shortened by 2 bytes to 250 bytes, due to the extra header overhead.

    Keyword Arguments:
    message(str): A text message as a string, up to 250 characters in length.
    """

    global text_message_counter

    text_message_counter = (text_message_counter+1)%65536
    # Clip message if required.
    if len(message) > 250:
        message = message[:250]

    # We will use the Wenet standard text message format, which has a packet type of 0x00,
    # and consists of a length field, a message count, and then the message itself.
    _PACKET_TYPE = 0x00
    _PACKET_LEN = len(message)
    _PACKET_COUNTER = text_message_counter

    # Assemble the packet.
    _packet = struct.pack(">BBH", _PACKET_TYPE, _PACKET_LEN, _PACKET_COUNTER) + message.encode('ascii')

    return _packet


def create_arbitrary_float_packet(data=[0.0, 0.1]):
    """ Create a payload that contains a list of floating point numbers.
    
    Keyword Arguments:
    data (list): A list of floating point numbers to package and send.
    """

    # Clip the amount of numbers to send to a maximum of 63 (we only have 252 bytes to fit data into)
    if len(data) > 63:
        data = data[:63]

    # Our packet format will consist of a packet type, a length field, and then the data.
    _PACKET_TYPE = 0x10  # We will define a packet type of 0x10 to be a list of floats.
    _PACKET_LEN = len(data)

    # Convert the list of floats into a byte array representation.
    _float_bytes = b""

    for _val in data:
        _float_bytes += struct.pack(">f", _val)

    # Now assemble the final packet.
    _packet = struct.pack(">BB", _PACKET_TYPE, _PACKET_LEN) + _float_bytes


    return _packet




if __name__ == "__main__":

    # Define ourselves to be 'sub-payload' number 3.
    PAYLOAD_ID = 3

    try:
        while True:
            # Create and transmit a text message packet
            _txt_packet = create_text_message("This is a test from payload %d" % PAYLOAD_ID)
            emit_secondary_packet(id=PAYLOAD_ID, packet=_txt_packet)
            print("Sent Text Message.")

            time.sleep(1)

            # Generate some random numbers and send them.
            _len = random.randint(1,63)
            _data = []
            for i in range(_len):
                _data.append(random.random())

            _float_packet = create_arbitrary_float_packet(_data)
            emit_secondary_packet(id=PAYLOAD_ID, packet=_float_packet)
            print("Sent list of floats: " + str(_data))

            time.sleep(1)


    # Keep going unless we get a Ctrl + C event
    except KeyboardInterrupt:
        print("Closing")