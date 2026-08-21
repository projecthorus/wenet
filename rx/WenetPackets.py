#!/usr/bin/env python2.7
#
# Wenet Packet Generators / Decoders
#
#   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
import struct
import traceback
import datetime
import logging
import json
import requests
import sys
from hashlib import sha256
from base64 import b64encode
import cbor2

# Check if we are running in Python 2 or 3
PY3 = sys.version_info[0] == 3

WENET_VERSION = "2.1.0"

WENET_IMAGE_UDP_PORT        = 7890
WENET_TELEMETRY_UDP_PORT    = 55672


class WENET_PACKET_TYPES:
    TEXT_MESSAGE            = 0x00
    GPS_TELEMETRY           = 0x01
    ORIENTATION_TELEMETRY   = 0x02
    SEC_PAYLOAD_TELEMETRY   = 0x03
    CBOR_PAYLOAD_TELEMETRY  = 0x05
    IMAGE_TELEMETRY         = 0x54
    SSDV                    = 0x55
    IDLE                    = 0x56


class WENET_PACKET_LENGTHS:
    GPS_TELEMETRY           = 81
    ORIENTATION_TELEMETRY   = 43
    IMAGE_TELEMETRY         = 80


def decode_packet_type(packet):
    # Convert packet to a list of integers before parsing.
    packet = list(bytearray(packet))
    return packet[0]


def packet_to_string(packet):
    packet_type = decode_packet_type(packet)

    if packet_type == WENET_PACKET_TYPES.TEXT_MESSAGE:
        return text_message_string(packet)
    elif packet_type == WENET_PACKET_TYPES.GPS_TELEMETRY:
        return gps_telemetry_string(packet)
    elif packet_type == WENET_PACKET_TYPES.ORIENTATION_TELEMETRY:
        return orientation_telemetry_string(packet)
    elif packet_type == WENET_PACKET_TYPES.SEC_PAYLOAD_TELEMETRY:
        return sec_payload_packet_string(packet)
    elif packet_type == WENET_PACKET_TYPES.CBOR_PAYLOAD_TELEMETRY:
        return cbor_payload_packet_string(packet)
    elif packet_type == WENET_PACKET_TYPES.IMAGE_TELEMETRY:
        return image_telemetry_string(packet)
    elif packet_type == WENET_PACKET_TYPES.SSDV:
        return ssdv_packet_string(packet)
    else:
        return "Unknown Packet Type: %d" % packet_type



#
# SSDV - Packets as per https://ukhas.org.uk/guides:ssdv
#

_ssdv_callsign_alphabet = '-0123456789---ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def ssdv_decode_callsign(code):
    """ Decode a SSDV callsign from a supplied array of ints,
        extract from a SSDV packet.

        Args:
            list: List of integers, corresponding to bytes 2-6 of a SSDV packet.

        Returns:
            str: Decoded callsign.

    """

    code = bytes(bytearray(code))
    code = struct.unpack('>I',code)[0]
    callsign = ''

    while code:
        callsign += _ssdv_callsign_alphabet[code % 40]
        code = code // 40
    
    return callsign


def ssdv_packet_info(packet):
    """ Extract various information out of a SSDV packet, and present as a dict. """
    packet = list(bytearray(packet))
    # Check packet is actually a SSDV packet.
    if len(packet) != 256:
        return {'error': "ERROR: Invalid Packet Length"}

    if packet[0] != 0x55: # A first byte of 0x55 indicates a SSDV packet.
        return {'error': "ERROR: Not a SSDV Packet."}

    # We got this far, may as well try and extract the packet info.
    try:
        packet_info = {
            'callsign' : ssdv_decode_callsign(packet[2:6]), # TODO: Callsign decoding.
            'packet_type' : "FEC" if (packet[1]==0x66) else "No-FEC",
            'image_id' : packet[6],
            'packet_id' : (packet[7]<<8) + packet[8],
            'width' : packet[9]*16,
            'height' : packet[10]*16,
            'error' : "None"
        }

        return packet_info
    except Exception as e:
        traceback.print_exc()
        return {'error': "ERROR: %s" % str(e)}


def ssdv_packet_string(packet):
    """ Produce a textual representation of a SSDV packet. """
    packet_info = ssdv_packet_info(packet)
    if packet_info['error'] != 'None':
        return "SSDV: Unable to decode."
    else:
        return "SSDV: %s, Callsign: %s, Img:%d, Pkt:%d, %dx%d" % (packet_info['packet_type'],packet_info['callsign'],packet_info['image_id'],packet_info['packet_id'],packet_info['width'],packet_info['height'])

#
# Text Messages
#
def decode_text_message(packet):
    """ Extract information from a text message packet """
    # We need the packet as a string, convert to a string in case we were passed a list of bytes.
    packet = bytes(bytearray(packet))
    message = {}
    try:
        message['len'] = struct.unpack("B",packet[1:2])[0]
        message['id'] = struct.unpack(">H",packet[2:4])[0]
        message['text'] = packet[4:4+message['len']].decode('ascii')
        message['error'] = 'None'
    except:
        traceback.print_exc()
        return {'error': 'Could not decode message packet.'}

    return message

def text_message_string(packet):
    message = decode_text_message(packet)

    if message['error'] != 'None':
        return "Text: ERROR Could not decode."
    else:
        return "Text Message #%d: \t%s" % (message['id'],message['text'])

#
# GPS Telemetry Decoder
#
# Refer Telemetry format documented in:
# https://docs.google.com/document/d/12230J1X3r2-IcLVLkeaVmIXqFeo3uheurFakElIaPVo/edit?usp=sharing
#
# The above 

def gps_weeksecondstoutc(gpsweek, gpsseconds, leapseconds):
    """ Convert time in GPS time (GPS Week, seconds-of-week) to a UTC timestamp """
    epoch = datetime.datetime.strptime("1980-01-06 00:00:00","%Y-%m-%d %H:%M:%S")
    elapsed = datetime.timedelta(days=(gpsweek*7),seconds=(gpsseconds))
    timestamp = epoch + elapsed - datetime.timedelta(seconds=leapseconds)
    return timestamp.isoformat()


def gps_telemetry_decoder(packet):
    """ Extract GPS telemetry data from a packet, and return it as a dictionary. 

    Keyword Arguments:
    packet: A GPS telemetry packet, as per
            https://github.com/projecthorus/wenet/wiki/Modem-&-Packet-Format-Details#0x01---gps-telemetry
            This can be provided as either a string, or a list of integers, which will be converted
            to a string prior to decoding.

    Return value:
            A dictionary containing the decoded packet data. 
            If the decode failed for whatever reason, a dictionary will still be returned, but will 
            contain the field 'error' with the decode fault description.
            This field (error) will be set to 'None' if decoding was successful.

    """

    # We need the packet as a string - convert to a string in case we were passed a list of bytes,
    # which occurs when we are decoding a packet that has arrived via a UDP-broadcast JSON blob.
    packet = bytes(bytearray(packet))
    gps_data = {}

    # Some basic sanity checking of the packet before we attempt to decode.
    if len(packet) < WENET_PACKET_LENGTHS.GPS_TELEMETRY:
        return {'error': 'GPS Telemetry Packet has invalid length.'}
    elif len(packet) > WENET_PACKET_LENGTHS.GPS_TELEMETRY:
        # If the packet is too big (which it will be, as it's padded with 0x55's), clip it. 
        packet = packet[:WENET_PACKET_LENGTHS.GPS_TELEMETRY]
    else:
        pass

    # Determine which optional field groups are present before unpacking.
    # Transmitters pad unused regions with 0x55 bytes, so test the raw byte
    # regions rather than individual decoded values (a single decoded field
    # can legitimately equal 0x5555 = 21845, e.g. batt_v of 21845 mV).
    # Field regions: [0:35] base telemetry, [35:73] 2024-09 system telemetry,
    # [73:81] 2025-11 power telemetry.
    sys_telem_valid = packet[35:73] != b'\x55' * 38
    power_telem_valid = packet[73:81] != b'\x55' * 8

    # Wrap the next bit in exception handling.
    try:
        # Unpack the packet into a list.
        data = struct.unpack(">BHIBffffffBBBffHfffffffHHf", packet)

        gps_data['week']    = data[1]
        gps_data['iTOW']    = data[2]/1000.0 # iTOW provided as milliseconds, convert to seconds.
        gps_data['leapS']   = data[3]
        gps_data['latitude'] = data[4]
        gps_data['longitude'] = data[5]
        gps_data['altitude'] = data[6]
        gps_data['ground_speed'] = data[7]
        gps_data['heading'] = data[8]
        gps_data['ascent_rate'] = data[9]
        gps_data['numSV']   = data[10]
        gps_data['gpsFix']  = data[11]
        gps_data['dynamic_model'] = data[12]
        # New fields 2024-09
        gps_data['sys_telem_valid'] = sys_telem_valid
        if sys_telem_valid:
            gps_data['radio_temp'] = round(data[13],1)
            gps_data['cpu_temp'] = round(data[14],1)
            gps_data['cpu_speed'] = data[15]
            gps_data['load_avg_1'] = round(data[16],3)
            gps_data['load_avg_5'] = round(data[17],3)
            gps_data['load_avg_15'] = round(data[18],3)
            gps_data['disk_percent'] = round(data[19],3)
            gps_data['lens_position'] = round(data[20],4)
            gps_data['sensor_temp'] = round(data[21],1)
            gps_data['focus_fom'] = int(data[22])
        # New fields 2025-11
        gps_data['power_telem_valid'] = power_telem_valid
        if power_telem_valid:
            gps_data['batt_v'] = data[23]/1000.0 # mv -> v
            gps_data['batt_i'] = data[24]
            gps_data['aux_temp'] = round(data[25],1)

        # Perform some post-processing on the data, to make some of the fields easier to read.

        # Produce a human-readable timestamp, in UTC time.
        gps_data['timestamp'] = gps_weeksecondstoutc(gps_data['week'], gps_data['iTOW'], gps_data['leapS'])

        # Produce a human-readable indication of GPS Fix state.
        if gps_data['gpsFix'] == 0:
            gps_data['gpsFix_str'] = 'No Fix'
        elif gps_data['gpsFix'] == 2:
            gps_data['gpsFix_str'] = '2D Fix'
        elif gps_data['gpsFix'] == 3:
            gps_data['gpsFix_str'] = '3D Fix'
        elif gps_data['gpsFix'] == 5:
            gps_data['gpsFix_str'] = 'Time Only'
        else:
            gps_data['gpsFix_str'] = 'Unknown (%d)' % gps_data['gpsFix']

        # Produce a human-readable indication of the current dynamic model.
        if gps_data['dynamic_model'] == 0:
            gps_data['dynamic_model_str'] = 'Portable'
        elif gps_data['dynamic_model'] == 1:
            gps_data['dynamic_model_str'] = 'Not Used'
        elif gps_data['dynamic_model'] == 2:
            gps_data['dynamic_model_str'] = 'Stationary'
        elif gps_data['dynamic_model'] == 3:
            gps_data['dynamic_model_str'] = 'Pedestrian'
        elif gps_data['dynamic_model'] == 4:
            gps_data['dynamic_model_str'] = 'Automotive'
        elif gps_data['dynamic_model'] == 5:
            gps_data['dynamic_model_str'] = 'Sea'
        elif gps_data['dynamic_model'] == 6:
            gps_data['dynamic_model_str'] = 'Airborne 1G'
        elif gps_data['dynamic_model'] == 7:
            gps_data['dynamic_model_str'] = 'Airborne 2G'
        elif gps_data['dynamic_model'] == 8:
            gps_data['dynamic_model_str'] = 'Airborne 4G'
        else:
            gps_data['dynamic_model_str'] = 'Unknown'

        gps_data['error'] = 'None'

        return gps_data

    except:
        traceback.print_exc()
        print(packet)
        return {'error': 'Could not decode GPS telemetry packet.'}


def gps_telemetry_string(packet):
    """ Produce a String representation of a GPS Telemetry packet"""

    # Decode packet to a dictionary 
    gps_data = gps_telemetry_decoder(packet)

    # Check if there was a decode error. If not, produce a string.
    if gps_data['error'] != 'None':
        return "GPS: ERROR Could not decode."
    else:
        gps_data_string = "GPS: %s Lat/Lon: %.5f,%.5f Alt: %dm, Speed: H %dkph V %.1fm/s, Heading: %d deg, Fix: %s, SVs: %d, DynModel: %s" % (
            gps_data['timestamp'],
            gps_data['latitude'],
            gps_data['longitude'],
            int(gps_data['altitude']),
            int(gps_data['ground_speed']),
            gps_data['ascent_rate'],
            int(gps_data['heading']),
            gps_data['gpsFix_str'],
            gps_data['numSV'],
            gps_data['dynamic_model_str']
            )
        
        if gps_data['sys_telem_valid']:
            gps_data_string = gps_data_string + ", Radio Temp: %.1f, CPU Temp: %.1f, CPU Speed: %d, Load Avg: %.2f, %.2f, %.2f, Disk Usage: %.1f%%, Lens Pos: %.4f, Sensor Temp: %.1f, FocusFoM: %d" % (
            gps_data['radio_temp'],
            gps_data['cpu_temp'],
            gps_data['cpu_speed'],
            gps_data['load_avg_1'],
            gps_data['load_avg_5'],
            gps_data['load_avg_15'],
            gps_data['disk_percent'],
            gps_data['lens_position'],
            gps_data['sensor_temp'],
            int(gps_data['focus_fom'])
            )

        if gps_data['power_telem_valid']:
            gps_data_string = gps_data_string + ", Batt V: %.2f, Batt I: %.0f, Aux Temp: %0.1f" % (
            gps_data['batt_v'],
            gps_data['batt_i'],
            gps_data['aux_temp']
            )

        return gps_data_string

#
# Orientation Telemetry Decoder
#
def orientation_telemetry_decoder(packet):
    """ Extract Orientation Telemetry data from a supplied packet, and return it as a dictionary.

    Keyword Arguments:
    packet: An Orientation telemetry packet, as per https://docs.google.com/document/d/12230J1X3r2-IcLVLkeaVmIXqFeo3uheurFakElIaPVo/edit?usp=sharing
            This can be provided as either a string, or a list of integers, which will be converted
            to a string prior to decoding.

    Return value:
            A dictionary containing the decoded packet data. 
            If the decode failed for whatever reason, a dictionary will still be returned, but will 
            contain the field 'error' with the decode fault description.
            This field (error) will be set to 'None' if decoding was successful.

    """

    # We need the packet as a string - convert to a string in case we were passed a list of bytes,
    # which occurs when we are decoding a packet that has arrived via a UDP-broadcast JSON blob.
    packet = bytes(bytearray(packet))

    # Some basic sanity checking of the packet before we attempt to decode.
    if len(packet) < WENET_PACKET_LENGTHS.ORIENTATION_TELEMETRY:
        return {'error': 'Orientation Telemetry Packet has invalid length.'}
    elif len(packet) > WENET_PACKET_LENGTHS.ORIENTATION_TELEMETRY:
        # If the packet is too big (which it will be, as it's padded with 0x55's), clip it. 
        packet = packet[:WENET_PACKET_LENGTHS.ORIENTATION_TELEMETRY]
    else:
        pass

    orientation_data = {}

    # Wrap the next bit in exception handling.
    try:
        # Unpack the packet into a list.
        data = struct.unpack('>BHIBBBBBBBbfffffff', packet)

        orientation_data['week']    = data[1]
        orientation_data['iTOW']    = data[2]/1000.0 # iTOW provided as milliseconds, convert to seconds.
        orientation_data['leapS']   = data[3]

        # Produce human readable timestamp.
        orientation_data['timestamp'] = gps_weeksecondstoutc(orientation_data['week'], orientation_data['iTOW'], orientation_data['leapS'])

        orientation_data['sys_status']  = data[4]
        orientation_data['sys_error']   = data[5]
        orientation_data['sys_cal']     = data[6]
        orientation_data['gyro_cal']    = data[7]
        orientation_data['accel_cal']   = data[8]
        orientation_data['magnet_cal']  = data[9]
        orientation_data['temp']        = data[10]

        orientation_data['euler_heading'] = data[11]
        orientation_data['euler_roll'] = data[12]
        orientation_data['euler_pitch'] = data[13]

        orientation_data['quaternion_x'] = data[14]
        orientation_data['quaternion_y'] = data[15]
        orientation_data['quaternion_z'] = data[16]
        orientation_data['quaternion_w'] = data[17]

        orientation_data['error'] = 'None'

        return orientation_data

    except:
        traceback.print_exc()
        print(packet)
        return {'error': 'Could not decode Orientation telemetry packet.'}


def orientation_telemetry_string(packet):
    """ Produce a String representation of an Orientation Telemetry packet"""

    orientation_data = orientation_telemetry_decoder(packet)

    # Check if there was a decode error. If not, produce a string.
    if orientation_data['error'] != 'None':
        return "Orientation: ERROR Could not decode."
    else:
        orientation_data_string = "Orientation: %s Status: %d Error: %d Cal: %d %d %d %d Temp: %d Euler: (%.1f,%.1f,%.1f) Quaternion: (%.1f, %.1f, %.1f, %.1f)" % (
            orientation_data['timestamp'],
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

        return orientation_data_string


#
# Image (Combined GPS/Orientation + Image ID) Telemetry Decoder
#
def image_telemetry_decoder(packet):
    """ Extract Image Telemetry data from a supplied packet, and return it as a dictionary.

    Keyword Arguments:
    packet: An Image telemetry packet, as per https://docs.google.com/document/d/12230J1X3r2-IcLVLkeaVmIXqFeo3uheurFakElIaPVo/edit?usp=sharing
            This can be provided as either a string, or a list of integers, which will be converted
            to a string prior to decoding.

    Return value:
            A dictionary containing the decoded packet data. 
            If the decode failed for whatever reason, a dictionary will still be returned, but will 
            contain the field 'error' with the decode fault description.
            This field (error) will be set to 'None' if decoding was successful.

    """

    # We need the packet as a string - convert to a string in case we were passed a list of bytes,
    # which occurs when we are decoding a packet that has arrived via a UDP-broadcast JSON blob.
    packet = bytes(bytearray(packet))

    image_data = {}

    
    # Some basic sanity checking of the packet before we attempt to decode.
    if len(packet) < WENET_PACKET_LENGTHS.IMAGE_TELEMETRY:
        return {'error': 'Image Telemetry Packet has invalid length.'}
    elif len(packet) > WENET_PACKET_LENGTHS.IMAGE_TELEMETRY:
        # If the packet is too big (which it will be, as it's padded with 0x55's), clip it. 
        packet = packet[:WENET_PACKET_LENGTHS.IMAGE_TELEMETRY]
    else:
        pass

    # Wrap the next bit in exception handling.
    try:
        # Unpack the packet into a list.
        data = struct.unpack('>BH7pBHIBffffffBBBBBBBBBbfffffff', packet)

        image_data['sequence_number'] = data[1]
        image_data['callsign'] = data[2].decode()
        image_data['image_id'] = data[3]
        image_data['week']  = data[4]
        image_data['iTOW']  = data[5]/1000.0 # iTOW provided as milliseconds, convert to seconds.
        image_data['leapS']     = data[6]
        image_data['latitude'] = data[7]
        image_data['longitude'] = data[8]
        image_data['altitude'] = data[9]
        image_data['ground_speed'] = data[10]
        image_data['heading'] = data[11]
        image_data['ascent_rate'] = data[12]
        image_data['numSV']     = data[13]
        image_data['gpsFix']    = data[14]
        image_data['dynamic_model'] = data[15]

        # Perform some post-processing on the data, to make some of the fields easier to read.

        # Produce a human-readable timestamp, in UTC time.
        image_data['timestamp'] = gps_weeksecondstoutc(image_data['week'], image_data['iTOW'], image_data['leapS'])

        # Produce a human-readable indication of GPS Fix state.
        if image_data['gpsFix'] == 0:
            image_data['gpsFix_str'] = 'No Fix'
        elif image_data['gpsFix'] == 2:
            image_data['gpsFix_str'] = '2D Fix'
        elif image_data['gpsFix'] == 3:
            image_data['gpsFix_str'] = '3D Fix'
        elif image_data['gpsFix'] == 5:
            image_data['gpsFix_str'] = 'Time Only'
        else:
            image_data['gpsFix_str'] = 'Unknown (%d)' % image_data['gpsFix']

        # Produce a human-readable indication of the current dynamic model.
        if image_data['dynamic_model'] == 0:
            image_data['dynamic_model_str'] = 'Portable'
        elif image_data['dynamic_model'] == 1:
            image_data['dynamic_model_str'] = 'Not Used'
        elif image_data['dynamic_model'] == 2:
            image_data['dynamic_model_str'] = 'Stationary'
        elif image_data['dynamic_model'] == 3:
            image_data['dynamic_model_str'] = 'Pedestrian'
        elif image_data['dynamic_model'] == 4:
            image_data['dynamic_model_str'] = 'Automotive'
        elif image_data['dynamic_model'] == 5:
            image_data['dynamic_model_str'] = 'Sea'
        elif image_data['dynamic_model'] == 6:
            image_data['dynamic_model_str'] = 'Airborne 1G'
        elif image_data['dynamic_model'] == 7:
            image_data['dynamic_model_str'] = 'Airborne 2G'
        elif image_data['dynamic_model'] == 8:
            image_data['dynamic_model_str'] = 'Airborne 4G'
        else:
            image_data['dynamic_model_str'] = 'Unknown'

        image_data['sys_status']    = data[16]
        image_data['sys_error'] = data[17]
        image_data['sys_cal']   = data[18]
        image_data['gyro_cal']  = data[19]
        image_data['accel_cal']     = data[20]
        image_data['magnet_cal']    = data[21]
        image_data['temp']      = data[22]

        image_data['euler_heading'] = data[23]
        image_data['euler_roll'] = data[24]
        image_data['euler_pitch'] = data[25]

        image_data['quaternion_x'] = data[26]
        image_data['quaternion_y'] = data[27]
        image_data['quaternion_z'] = data[28]
        image_data['quaternion_w'] = data[29]

        image_data['error'] = 'None'

        return image_data

    except:
        traceback.print_exc()
        print(packet)
        return {'error': 'Could not decode Image telemetry packet.'}

    # SHSSP Code goes here.

    return {'error': "Image Telemetry: Not Implemented."}

def image_telemetry_string(packet):
    """ Produce a String representation of an Image Telemetry packet"""

    image_data = image_telemetry_decoder(packet)

    # Check if there was a decode error. If not, produce a string.
    if image_data['error'] != 'None':
        return "Image Telemetry: ERROR Could not decode."
    else:
        image_data_string = "Image Telemetry: %s ID #%d, %s Lat/Lon: %.5f,%.5f Alt: %d m Fix: %s Euler: (%.1f,%.1f,%.1f)" % (
            image_data['callsign'],
            image_data['image_id'],
            image_data['timestamp'],
            image_data['latitude'],
            image_data['longitude'],
            image_data['altitude'],
            image_data['gpsFix_str'],
            image_data['euler_heading'],
            image_data['euler_roll'],
            image_data['euler_pitch'],
            )

        return image_data_string


def sec_payload_decode(packet):
    """ Split a secondary payload packet into fields """
    # We need the packet as a string, convert to a string in case we were passed a list of bytes.
    packet = bytes(bytearray(packet))
    message = {}
    try:
        #message['id'] = struct.unpack("B",packet[1:2])[0]
        message['id'] = packet[1]
        message['payload'] = packet[2:]
    except:
        return {'error': 'Could not decode secondary payload packet.'}

    return message


def sec_payload_packet_string(packet):
    """ Provide a string representation of a secondary payload packet. """

    _sec_payload = sec_payload_decode(packet)

    # Check if we could split the packet into its expected contents.
    if 'error' in _sec_payload:
        return "Secondary Payload Packet: Error - Could not Decode."

    _sec_payload_str = "Secondary Payload Packet (ID: #%d) - " % _sec_payload['id']

    if decode_packet_type(_sec_payload['payload']) == WENET_PACKET_TYPES.TEXT_MESSAGE:
        # Secondary payload contains a Text Message
        _message = text_message_string(_sec_payload['payload'])
        return _sec_payload_str + _message

    else:
        # Unknown Packet type.
        _payload_type = decode_packet_type(_sec_payload['payload'])

        return _sec_payload_str + "Payload Type %d" % _payload_type

def cbor_payload_decode(packet):
    """ Split a CBOR payload packet into fields """
    # We need the packet as a string, convert to a string in case we were passed a list of bytes.
    packet = bytes(bytearray(packet))

    if len(packet) < 2:
        return {'error': 'CBOR payload packet too short.'}

    # Packet layout is [0x05][length][CBOR]. packet[0] is the packet type, so the length
    # lives at packet[1] and the payload starts at packet[2].
    length = packet[1]
    payload = packet[2:2+length]

    if len(payload) < length:
        return {'error': 'CBOR payload packet truncated.'}

    try:
        return cbor2.loads(payload)
    except:
        return {'error': 'Could not decode CBOR payload packet.'}

def cbor_payload_packet_string(packet):
    """ Provide a string representation of a CBOR payload packet. """

    _cbor_payload = cbor_payload_decode(packet)

    # Check if we could split the packet into its expected contents. CBOR can legally
    # decode to a list or an integer, so test the type before testing for the error key.
    if not isinstance(_cbor_payload, dict):
        return "CBOR Payload Packet: %s" % _cbor_payload

    if 'error' in _cbor_payload:
        return "CBOR Payload Packet: Error - Could not Decode."

    return "CBOR Payload Packet: %s" % _cbor_payload
