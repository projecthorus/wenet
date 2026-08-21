#!/usr/bin/env python
'''
UBlox binary protocol handling

Copyright Andrew Tridgell, October 2012
https://github.com/tridge/pyUblox
Released under GNU GPL version 3 or later

Added UBloxGPS abstraction layer class for use with Wenet TX system.
'''

import struct
import datetime
from threading import Thread, Lock
import time, os, json, calendar, math, traceback, socket, argparse

# protocol constants
PREAMBLE1 = 0xb5
PREAMBLE2 = 0x62

# message classes
CLASS_NAV = 0x01    # Navigation
CLASS_RXM = 0x02    # Receiver Manager
CLASS_INF = 0x04    # Inforation
CLASS_ACK = 0x05    # Message ACKs
CLASS_CFG = 0x06    # Configuration
CLASS_UPD = 0x09    # Firmware Updates
CLASS_MON = 0x0A    # Monitoring
CLASS_AID = 0x0B    # AssistNow Aiding
CLASS_TIM = 0x0D    # Timing
CLASS_ESF = 0x10    # External Sensor Fusion
CLASS_MGA = 0x13    # Multiple-GNSS Assistance
CLASS_LOG = 0x21    # Logging
CLASS_SEC = 0x27    # Security
CLASS_HNR = 0x28    # High-Rate Navigation

# ACK messages
MSG_ACK_NACK = 0x00
MSG_ACK_ACK = 0x01

# NAV messages
MSG_NAV_POSECEF   = 0x1
MSG_NAV_POSLLH    = 0x2
MSG_NAV_STATUS    = 0x3
MSG_NAV_DOP       = 0x4
MSG_NAV_SOL       = 0x6
MSG_NAV_POSUTM    = 0x8
MSG_NAV_VELNED    = 0x12
MSG_NAV_VELECEF   = 0x11
MSG_NAV_TIMEGPS   = 0x20
MSG_NAV_TIMEUTC   = 0x21
MSG_NAV_CLOCK     = 0x22
MSG_NAV_SVINFO    = 0x30
MSG_NAV_SAT       = 0x35
MSG_NAV_AOPSTATUS = 0x60
MSG_NAV_DGPS      = 0x31
MSG_NAV_DOP       = 0x04
MSG_NAV_EKFSTATUS = 0x40
MSG_NAV_SBAS      = 0x32
MSG_NAV_SOL       = 0x06
MSG_NAV_PVT       = 0x07

# RXM messages
MSG_RXM_RAW    = 0x10
MSG_RXM_SFRB   = 0x11
MSG_RXM_SVSI   = 0x20
MSG_RXM_EPH    = 0x31
MSG_RXM_ALM    = 0x30
MSG_RXM_PMREQ  = 0x41

# AID messages
MSG_AID_ALM    = 0x30
MSG_AID_EPH    = 0x31
MSG_AID_ALPSRV = 0x32
MSG_AID_AOP    = 0x33
MSG_AID_DATA   = 0x10
MSG_AID_ALP    = 0x50
MSG_AID_DATA   = 0x10
MSG_AID_HUI    = 0x02
MSG_AID_INI    = 0x01
MSG_AID_REQ    = 0x00

# CFG messages
MSG_CFG_PRT = 0x00
MSG_CFG_ANT = 0x13
MSG_CFG_DAT = 0x06
MSG_CFG_EKF = 0x12
MSG_CFG_ESFGWT = 0x29
MSG_CFG_CFG = 0x09
MSG_CFG_USB = 0x1b
MSG_CFG_RATE = 0x08
MSG_CFG_SET_RATE = 0x01
MSG_CFG_NAV5 = 0x24
MSG_CFG_FXN = 0x0E
MSG_CFG_INF = 0x02
MSG_CFG_ITFM = 0x39
MSG_CFG_MSG = 0x01
MSG_CFG_NAVX5 = 0x23
MSG_CFG_NMEA = 0x17
MSG_CFG_NVS = 0x22
MSG_CFG_PM2 = 0x3B
MSG_CFG_PM = 0x32
MSG_CFG_RINV = 0x34
MSG_CFG_RST = 0x04
MSG_CFG_RXM = 0x11
MSG_CFG_SBAS = 0x16
MSG_CFG_TMODE2 = 0x3D
MSG_CFG_TMODE = 0x1D
MSG_CFG_TPS = 0x31
MSG_CFG_TP = 0x07
MSG_CFG_GNSS = 0x3E
MSG_CFG_ESFALG = 0x56
MSG_CFG_ESFA = 0x4C
MSG_CFG_ESFG = 0x4D
MSG_CFG_ESFWT = 0x82
MSG_CFG_HNR = 0x5C
MSG_CFG_VALSET = 0x8A
MSG_CFG_VALGET = 0x8B

# ESF messages
MSG_ESF_MEAS   = 0x02
MSG_ESF_STATUS = 0x10
MSG_ESF_ALG    = 0x14
MSG_ESF_INS    = 0x15
MSG_ESF_RAW    = 0x03

# INF messages
MSG_INF_DEBUG  = 0x04
MSG_INF_ERROR  = 0x00
MSG_INF_NOTICE = 0x02
MSG_INF_TEST   = 0x03
MSG_INF_WARNING= 0x01

# MON messages
MSG_MON_SCHD  = 0x01
MSG_MON_HW    = 0x09
MSG_MON_HW2   = 0x0B
MSG_MON_IO    = 0x02
MSG_MON_MSGPP = 0x06
MSG_MON_RXBUF = 0x07
MSG_MON_RXR   = 0x21
MSG_MON_TXBUF = 0x08
MSG_MON_VER   = 0x04

# TIM messages
MSG_TIM_TP   = 0x01
MSG_TIM_TM2  = 0x03
MSG_TIM_SVIN = 0x04
MSG_TIM_VRFY = 0x06

# HNR Messages
MSG_HNR_ATT  = 0x01
MSG_HNR_INS  = 0x02
MSG_HNR_PVT  = 0x00

# port IDs
PORT_DDC    =0
PORT_SERIAL1=1
PORT_SERIAL2=2
PORT_USB    =3
PORT_SPI    =4

# dynamic models
DYNAMIC_MODEL_PORTABLE   = 0
DYNAMIC_MODEL_STATIONARY = 2
DYNAMIC_MODEL_PEDESTRIAN = 3
DYNAMIC_MODEL_AUTOMOTIVE = 4
DYNAMIC_MODEL_SEA        = 5
DYNAMIC_MODEL_AIRBORNE1G = 6
DYNAMIC_MODEL_AIRBORNE2G = 7
DYNAMIC_MODEL_AIRBORNE4G = 8

#reset items
RESET_HOT  = 0
RESET_WARM = 1
RESET_COLD = 0xFFFF

RESET_HW            = 0
RESET_SW            = 1
RESET_SW_GPS        = 2
RESET_HW_GRACEFUL   = 4
RESET_GPS_STOP      = 8
RESET_GPS_START     = 9

# new UBX > 23.01 configuration keys
CFG_UART1INPROT_UBX     = 0x10730001
CFG_UART1INPROT_NMEA    = 0x10730002
CFG_UART1INPROT_RTCM3X  = 0x10730004
CFG_UART2INPROT_UBX     = 0x10750001
CFG_UART2INPROT_NMEA    = 0x10750002
CFG_UART2INPROT_RTCM3X  = 0x10750004
CFG_USBINPROT_UBX       = 0x10770001
CFG_USBINPROT_NMEA      = 0x10770002
CFG_USBINPROT_RTCM3X    = 0x10770004

CFG_UART1OUTPROT_UBX    = 0x10740001
CFG_UART1OUTPROT_NMEA   = 0x10740002
CFG_UART1OUTPROT_RTCM3X = 0x10740004
CFG_UART2OUTPROT_UBX    = 0x10760001
CFG_UART2OUTPROT_NMEA   = 0x10760002
CFG_UART2OUTPROT_RTCM3X = 0x10760004
CFG_USBOUTPROT_UBX      = 0x10780001
CFG_USBOUTPROT_NMEA     = 0x10780002
CFG_USBOUTPROT_RTCM3X   = 0x10780004
CFG_I2CINPROT_UBX       = 0x10710001
CFG_I2CINPROT_NMEA      = 0x10710002
CFG_I2CINPROT_RTCM3X    = 0x10710004
CFG_I2COUTPROT_UBX      = 0x10720001
CFG_I2COUTPROT_NMEA     = 0x10720002
CFG_I2COUTPROT_RTCM3X   = 0x10720004

# CFG-MSGOUT-UBX-NAV-SAT output rate keys (SPG 5.10 / UBX >= 23.01)
CFG_MSGOUT_NAV_SAT_I2C  = 0x20910015
CFG_MSGOUT_NAV_SAT_UART1 = 0x20910016
CFG_MSGOUT_NAV_SAT_UART2 = 0x20910017
CFG_MSGOUT_NAV_SAT_USB  = 0x20910018

# UART baudrate config keys (SPG 5.10 / UBX >= 23.01)
CFG_UART1_BAUDRATE      = 0x40520001
CFG_UART2_BAUDRATE      = 0x40530001

# CFG-VALSET layer masks
VALSET_LAYER_RAM        = 0x01
VALSET_LAYER_BBR        = 0x02
VALSET_LAYER_FLASH      = 0x04

class UBloxError(Exception):
    '''Ublox error class'''
    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.message = msg

class UBloxAttrDict(dict):
    '''allow dictionary members as attributes'''
    def __init__(self):
        dict.__init__(self)

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if self.__dict__.has_key(name):
            # allow set on normal attributes
            dict.__setattr__(self, name, value)
        else:
            self.__setitem__(name, value)

def ArrayParse(field):
    '''parse an array descriptor'''
    arridx = field.find('[')
    if arridx == -1:
        return (field, -1)
    alen = int(field[arridx+1:-1])
    fieldname = field[:arridx]
    return (fieldname, alen)

class UBloxDescriptor:
    '''class used to describe the layout of a UBlox message'''
    def __init__(self, name, msg_format, fields=[], count_field=None, format2=None, fields2=None):
        self.name = name
        self.msg_format = msg_format
        self.fields = fields
        self.count_field = count_field
        self.format2 = format2
        self.fields2 = fields2
	
    def unpack(self, msg):
        '''unpack a UBloxMessage, creating the .fields and ._recs attributes in msg'''
        msg._fields = {}

        # unpack main message blocks. A comm
        formats = self.msg_format.split(',')
        buf = msg._buf[6:-2]
        count = 0
        msg._recs = []
        fields = self.fields[:]
        
        for fmt in formats:
            size1 = struct.calcsize(fmt)
            if size1 > len(buf):
                raise UBloxError("%s INVALID_SIZE1=%u" % (self.name, len(buf)))
            f1 = list(struct.unpack(fmt, buf[:size1]))
            i = 0
            while i < len(f1):
                field = fields.pop(0)
                (fieldname, alen) = ArrayParse(field)
                if alen == -1:
                    msg._fields[fieldname] = f1[i]
                    if self.count_field == fieldname:
                        count = int(f1[i])
                    i += 1
                else:
                    msg._fields[fieldname] = [0]*alen
                    for a in range(alen):
                        msg._fields[fieldname][a] = f1[i]
                        i += 1
            buf = buf[size1:]
            if len(buf) == 0:
                break

        if self.count_field == '_remaining':
            count = len(buf) // struct.calcsize(self.format2)

        if count == 0:
            msg._unpacked = True
            if len(buf) != 0:
                raise UBloxError("EXTRA_BYTES=%u" % len(buf))
            return

        size2 = struct.calcsize(self.format2)
        for c in range(count):
            r = UBloxAttrDict()
            if size2 > len(buf):
                raise UBloxError("INVALID_SIZE=%u, " % len(buf))
            f2 = list(struct.unpack(self.format2, buf[:size2]))
            for i in range(len(self.fields2)):
                r[self.fields2[i]] = f2[i]
            buf = buf[size2:]
            msg._recs.append(r)
        if len(buf) != 0:
            raise UBloxError("EXTRA_BYTES=%u" % len(buf))
        msg._unpacked = True

    def pack(self, msg, msg_class=None, msg_id=None):
        '''pack a UBloxMessage from the .fields and ._recs attributes in msg'''
        f1 = []
        if msg_class is None:
            msg_class = msg.msg_class()
        if msg_id is None:
            msg_id = msg.msg_id()
        msg._buf = ''

        fields = self.fields[:]
        for f in fields:
            (fieldname, alen) = ArrayParse(f)
            if not fieldname in msg._fields:
                break
            if alen == -1:
                f1.append(msg._fields[fieldname])
            else:
                for a in range(alen):
                    f1.append(msg._fields[fieldname][a])                    
        try:
            # try full length message
            fmt = self.msg_format.replace(',', '')
            msg._buf = struct.pack(fmt, *tuple(f1))
        except Exception as e:
            # try without optional part
            fmt = self.msg_format.split(',')[0]
            msg._buf = struct.pack(fmt, *tuple(f1))

        length = len(msg._buf)
        if msg._recs:
            length += len(msg._recs) * struct.calcsize(self.format2)
        header = struct.pack('<BBBBH', PREAMBLE1, PREAMBLE2, msg_class, msg_id, length)
        msg._buf = header + msg._buf

        for r in msg._recs:
            f2 = []
            for f in self.fields2:
                f2.append(r[f])
            msg._buf += struct.pack(self.format2, *tuple(f2))            
        msg._buf += struct.pack('<BB', *msg.checksum(data=msg._buf[2:]))

    def format(self, msg):
        '''return a formatted string for a message'''
        if not msg._unpacked:
            self.unpack(msg)
        ret = self.name + ': '
        for f in self.fields:
            (fieldname, alen) = ArrayParse(f)
            if not fieldname in msg._fields:
                continue
            v = msg._fields[fieldname]
            if isinstance(v, list):
                ret += '%s=[' % fieldname
                for a in range(alen):
                    ret += '%s, ' % v[a]
                ret = ret[:-2] + '], '
            elif isinstance(v, str):
                ret += '%s="%s", ' % (f, v.rstrip(' \0'))
            else:
                ret += '%s=%s, ' % (f, v)
        for r in msg._recs:
            ret += '[ '
            for f in self.fields2:
                v = r[f]
                ret += '%s=%s, ' % (f, v)
            ret = ret[:-2] + ' ], '
        return ret[:-2]
        

# list of supported message types.
msg_types = {
    (CLASS_ACK, MSG_ACK_ACK)    : UBloxDescriptor('ACK_ACK',
                                                  '<BB', 
                                                  ['clsID', 'msgID']),
    (CLASS_ACK, MSG_ACK_NACK)   : UBloxDescriptor('ACK_NACK',
                                                  '<BB', 
                                                  ['clsID', 'msgID']),
    (CLASS_CFG, MSG_CFG_USB)    : UBloxDescriptor('CFG_USB',
                                                  '<HHHHHH32s32s32s',
                                                  ['vendorID', 'productID', 'reserved1', 'reserved2', 'powerConsumption',
                                                   'flags', 'vendorString', 'productString', 'serialNumber']),
    (CLASS_CFG, MSG_CFG_PRT)    : UBloxDescriptor('CFG_PRT',
                                                  '<BBHIIHHHH',
                                                  ['portID', 'reserved0', 'txReady', 'mode', 'baudRate', 'inProtoMask', 
                                                   'outProtoMask', 'reserved4', 'reserved5']),
    (CLASS_CFG, MSG_CFG_CFG)    : UBloxDescriptor('CFG_CFG',
                                                  '<III,B',
                                                  ['clearMask', 'saveMask', 'loadMask', 'deviceMask']),
    (CLASS_CFG, MSG_CFG_RST)    : UBloxDescriptor('CFG_RST',
                                                  '<HBB',
                                                  ['navBbrMask ', 'resetMode', 'reserved1']),
    (CLASS_CFG, MSG_CFG_SBAS)   : UBloxDescriptor('CFG_SBAS',
                                                  '<BBBBI',
                                                  ['mode', 'usage', 'maxSBAS', 'scanmode2', 'scanmode1']),
    (CLASS_CFG, MSG_CFG_GNSS)   : UBloxDescriptor('CFG_GNSS',
                                                  '<BBBBBBBBI',
                                                  ['msgVer', 'numTrkChHw', 'numTrkChUse', 'numConfigBlocks', 'gnssId',
                                                   'resTrkCh', 'maxTrkCh', 'resetved1', 'flags']),
    (CLASS_CFG, MSG_CFG_RATE)   : UBloxDescriptor('CFG_RATE',
                                                  '<HHH',
                                                  ['measRate', 'navRate', 'timeRef']),
    (CLASS_CFG, MSG_CFG_MSG)    : UBloxDescriptor('CFG_MSG',
                                                  '<BB6B',
                                                  ['msgClass', 'msgId', 'rates[6]']),
    (CLASS_CFG, MSG_CFG_ESFALG) : UBloxDescriptor('CFG_ESFALG',
                                                  '<BBBBIhh',
                                                  ['bitfield', 'unused1', 'unused2', 'unused3', 'yaw', 'pitch', 'roll']),
    (CLASS_NAV, MSG_NAV_PVT) :  UBloxDescriptor('NAV_PVT',
                                                  '<IhBBBBBBIiBBBBiiiiIIiiiiiIIHHBBBBihH', 
                                                  ['iTOW', 'year', 'month', 'day', 'hour', 'min', 'sec', 'valid', 'tAcc', 'nano', 'fixType', 'flags', 'flags2', 'numSV', 'Longitude', 'Latitude', 'height', 'hMSL', 'hAcc', 'vAcc', 'velN', 'velE', 'velD', 'gSpeed', 'headMot', 'sAcc', 'headAcc', 'pDOP', 'flags3', 'reserved1', 'reserved2', 'reserved3', 'reserved4', 'headVeh', 'magDec', 'magAcc']),
    (CLASS_NAV, MSG_NAV_POSLLH) : UBloxDescriptor('NAV_POSLLH',
                                                  '<IiiiiII', 
                                                  ['iTOW', 'Longitude', 'Latitude', 'height', 'hMSL', 'hAcc', 'vAcc']),
    (CLASS_NAV, MSG_NAV_VELNED) : UBloxDescriptor('NAV_VELNED',
                                                  '<IiiiIIiII', 
                                                  ['iTOW', 'velN', 'velE', 'velD', 'speed', 'gSpeed', 'heading', 
                                                   'sAcc', 'cAcc']),
    (CLASS_NAV, MSG_NAV_DOP)    : UBloxDescriptor('NAV_DOP',
                                                  '<IHHHHHHH', 
                                                  ['iTOW', 'gDOP', 'pDOP', 'tDOP', 'vDOP', 'hDOP', 'nDOP', 'eDOP']),
    (CLASS_NAV, MSG_NAV_STATUS) : UBloxDescriptor('NAV_STATUS',
                                                  '<IBBBBII', 
                                                  ['iTOW', 'gpsFix', 'flags', 'fixStat', 'flags2', 'ttff', 'msss']),
    (CLASS_NAV, MSG_NAV_SOL)    : UBloxDescriptor('NAV_SOL',
                                                  '<IihBBiiiIiiiIHBBI',
                                                  ['iTOW', 'fTOW', 'week', 'gpsFix', 'flags', 'ecefX', 'ecefY', 'ecefZ',
                                                   'pAcc', 'ecefVX', 'ecefVY', 'ecefVZ', 'sAcc', 'pDOP', 'reserved1', 
                                                   'numSV', 'reserved2']),
    (CLASS_NAV, MSG_NAV_POSUTM) : UBloxDescriptor('NAV_POSUTM',
                                                  '<Iiiibb',
                                                  ['iTOW', 'East', 'North', 'Alt', 'Zone', 'Hem']),
    (CLASS_NAV, MSG_NAV_SBAS)   : UBloxDescriptor('NAV_SBAS',
                                                  '<IBBbBBBBB',
                                                  ['iTOW', 'geo', 'mode', 'sys', 'service', 'cnt', 'reserved01', 'reserved02', 'reserved03' ],
                                                  'cnt',
                                                  'BBBBBBhHh',
                                                  ['svid', 'flags', 'udre', 'svSys', 'svService', 'reserved1',
                                                   'prc', 'reserved2', 'ic']),
    (CLASS_NAV, MSG_NAV_POSECEF): UBloxDescriptor('NAV_POSECEF',
                                                  '<IiiiI',
                                                  ['iTOW', 'ecefX', 'ecefY', 'ecefZ', 'pAcc']),
    (CLASS_NAV, MSG_NAV_VELECEF): UBloxDescriptor('NAV_VELECEF',
                                                  '<IiiiI',
                                                  ['iTOW', 'ecefVX', 'ecefVY', 'ecefVZ', 'sAcc']),
    (CLASS_NAV, MSG_NAV_TIMEGPS): UBloxDescriptor('NAV_TIMEGPS',
                                                  '<IihbBI',
                                                  ['iTOW', 'fTOW', 'week', 'leapS', 'valid', 'tAcc']),
    (CLASS_NAV, MSG_NAV_TIMEUTC): UBloxDescriptor('NAV_TIMEUTC',
                                                  '<IIiHBBBBBB',
                                                  ['iTOW', 'tAcc', 'nano', 'year', 'month', 'day', 'hour', 'min', 'sec', 'valid']),
    (CLASS_NAV, MSG_NAV_CLOCK)  : UBloxDescriptor('NAV_CLOCK',
                                                  '<IiiII',
                                                  ['iTOW', 'clkB', 'clkD', 'tAcc', 'fAcc']),
    (CLASS_NAV, MSG_NAV_DGPS)   : UBloxDescriptor('NAV_DGPS',
                                                  '<IihhBBH',
                                                  ['iTOW', 'age', 'baseId', 'baseHealth', 'numCh', 'status', 'reserved1'],
                                                  'numCh',
                                                  '<BBHff',
                                                  ['svid', 'flags', 'ageC', 'prc', 'prrc']),
    (CLASS_NAV, MSG_NAV_SVINFO) : UBloxDescriptor('NAV_SVINFO',
                                                  '<IBBH',
                                                  ['iTOW', 'numCh', 'globalFlags', 'reserved2'],
                                                  'numCh',
                                                  '<BBBBBbhi',
                                                  ['chn', 'svid', 'flags', 'quality', 'cno', 'elev', 'azim', 'prRes']),
    (CLASS_NAV, MSG_NAV_SAT)   : UBloxDescriptor('NAV_SAT',
                                                  '<IBBH',
                                                  ['iTOW', 'version', 'numSvs', 'reserved1'],
                                                  'numSvs',
                                                  '<BBBbhhI',
                                                  ['gnssId', 'svId', 'cno', 'elev', 'azim', 'prRes', 'flags']),
    (CLASS_RXM, MSG_RXM_SVSI)   : UBloxDescriptor('RXM_SVSI',
                                                  '<IhBB',
                                                  ['iTOW', 'week', 'numVis', 'numSV'],
                                                  'numSV',
                                                  '<BBhbB',
                                                  ['svid', 'svFlag', 'azim', 'elev', 'age']),
    (CLASS_RXM, MSG_RXM_EPH)    : UBloxDescriptor('RXM_EPH',
                                                  '<II , 8I 8I 8I',
                                                  ['svid', 'how',
                                                   'sf1d[8]', 'sf2d[8]', 'sf3d[8]']),
    (CLASS_AID, MSG_AID_EPH)    : UBloxDescriptor('AID_EPH',
                                                  '<II , 8I 8I 8I',
                                                  ['svid', 'how',
                                                   'sf1d[8]', 'sf2d[8]', 'sf3d[8]']),
    (CLASS_AID, MSG_AID_HUI)    : UBloxDescriptor('AID_HUI',
                                                  '<LddihhhhhhffffffffL',
                                                  ['health','utcA0','utcA1','utcTOW','utcWNT','utcLS','utcWNF','utcDN','utcLSF','utcSpare',
                                                  'klobA0','klobA1','klobA2','klobA3',
                                                  'klobB0','klobB1','klobB2','klobB3','flags']),
    (CLASS_AID, MSG_AID_AOP)    : UBloxDescriptor('AID_AOP',
                                                  '<B47B , 48B 48B 48B',
                                                  ['svid', 'data[47]', 'optional0[48]', 'optional1[48]', 'optional1[48]']),
    (CLASS_RXM, MSG_RXM_RAW)   : UBloxDescriptor('RXM_RAW',
                                                  '<ihBB',
                                                  ['iTOW', 'week', 'numSV', 'reserved1'],
                                                  'numSV',
                                                  '<ddfBbbB',
                                                  ['cpMes', 'prMes', 'doMes', 'sv', 'mesQI', 'cno', 'lli']),
    (CLASS_RXM, MSG_RXM_SFRB)  : UBloxDescriptor('RXM_SFRB',
                                                  '<BB10I',
                                                  ['chn', 'svid', 'dwrd[10]']),
    (CLASS_AID, MSG_AID_ALM)   : UBloxDescriptor('AID_ALM',
                                                  '<II',
                                                 '_remaining',
                                                 'I',
                                                 ['dwrd']),
    (CLASS_RXM, MSG_RXM_ALM)   : UBloxDescriptor('RXM_ALM',
                                                  '<II , 8I',
                                                  ['svid', 'week', 'dwrd[8]']),
    (CLASS_CFG, MSG_CFG_NAV5)   : UBloxDescriptor('CFG_NAV5',
                                                  '<HBBiIbBHHHHBBIII',
                                                  ['mask', 'dynModel', 'fixMode', 'fixedAlt', 'fixedAltVar', 'minElev', 
                                                   'drLimit', 'pDop', 'tDop', 'pAcc', 'tAcc', 'staticHoldThresh', 
                                                   'dgpsTimeOut', 'reserved2', 'reserved3', 'reserved4']),
    (CLASS_CFG, MSG_CFG_NAVX5)   : UBloxDescriptor('CFG_NAVX5',
                                                  '<HHIBBBBBBBBBBHIBBBBBBHII',
                                                  ['version', 'mask1', 'reserved0', 'reserved1', 'reserved2',
                                                   'minSVs', 'maxSVs', 'minCNO', 'reserved5', 'iniFix3D', 
                                                   'reserved6', 'reserved7', 'reserved8', 'wknRollover',
                                                   'reserved9', 'reserved10', 'reserved11',
                                                   'usePPP', 'useAOP', 'reserved12', 'reserved13', 
                                                   'aopOrbMaxErr', 'reserved3', 'reserved4']),
    (CLASS_MON, MSG_MON_HW)     : UBloxDescriptor('MON_HW',
                                                  '<IIIIHHBBBBIB25BHIII',
                                                  ['pinSel', 'pinBank', 'pinDir', 'pinVal', 'noisePerMS', 'agcCnt', 'aStatus',
						   'aPower', 'flags', 'reserved1', 'usedMask', 
						   'VP[25]',                                                  
						   'jamInd', 'reserved3', 'pinInq',
						   'pullH', 'pullL']),
    (CLASS_MON, MSG_MON_HW2)    : UBloxDescriptor('MON_HW2',
                                                  '<bBbBB3BI8BI4B',
                                                  ['ofsI', 'magI', 'ofsQ', 'magQ', 'cfgSource', 'reserved1[3]',
                                                   'lowLevCfg', 'reserved2[8]', 'postStatus', 'reserved3[4]']),
    (CLASS_MON, MSG_MON_SCHD)   : UBloxDescriptor('MON_SCHD',
                                                  '<IIIIHHHBB',
                                                  ['tskRun', 'tskSchd', 'tskOvrr', 'tskReg', 'stack',
                                                   'stackSize', 'CPUIdle', 'flySly', 'ptlSly']),
    (CLASS_MON, MSG_MON_VER)    : UBloxDescriptor('MON_VER',
                                                  '<30s10s,30s',
                                                  ['swVersion', 'hwVersion', 'romVersion'],
                                                  '_remaining',
                                                  '30s',
                                                  ['extension']),
    (CLASS_TIM, MSG_TIM_TP)     : UBloxDescriptor('TIM_TP',
                                                  '<IIiHBB',
                                                  ['towMS', 'towSubMS', 'qErr', 'week', 'flags', 'reserved1']),
    (CLASS_TIM, MSG_TIM_TM2)    : UBloxDescriptor('TIM_TM2',
                                                  '<BBHHHIIIII',
                                                  ['ch', 'flags', 'count', 'wnR', 'wnF', 'towMsR', 'towSubMsR', 
                                                   'towMsF', 'towSubMsF', 'accEst']),
    (CLASS_TIM, MSG_TIM_SVIN)   : UBloxDescriptor('TIM_SVIN',
                                                  '<IiiiIIBBH',
                                                  ['dur', 'meanX', 'meanY', 'meanZ', 'meanV',
                                                   'obs', 'valid', 'active', 'reserved1']),
    (CLASS_INF, MSG_INF_ERROR)  : UBloxDescriptor('INF_ERR', '<18s', ['str']),
    (CLASS_INF, MSG_INF_DEBUG)  : UBloxDescriptor('INF_DEBUG', '<18s', ['str']),
    (CLASS_ESF, MSG_ESF_ALG)    : UBloxDescriptor('ESF_ALG',
                                                 '<iBBBBIhh',
                                                 ['iTOW', 'version', 'flags', 'error', 'reserved1', 'yaw', 'pitch', 'roll'])
}


class UBloxMessage:
    '''UBlox message class - holds a UBX binary message'''
    def __init__(self):
        self._buf = b""
        self._fields = {}
        self._recs = []
        self._unpacked = False
        self.debug_level = 0

    def __str__(self):
        '''format a message as a string'''
        if not self.valid():
            return 'UBloxMessage(INVALID)'
        type = self.msg_type()
        if type in msg_types:
            return msg_types[type].format(self)
        return 'UBloxMessage(UNKNOWN %s, %u)' % (str(type), self.msg_length())

    def __getattr__(self, name):
        '''allow access to message fields'''
        try:
            return self._fields[name]
        except KeyError:
            if name == 'recs':
                return self._recs
            raise AttributeError(name)

    def __setattr__(self, name, value):
        '''allow access to message fields'''
        if name.startswith('_'):
            self.__dict__[name] = value
        else:
            self._fields[name] = value

    def have_field(self, name):
        '''return True if a message contains the given field'''
        return name in self._fields

    def debug(self, level, msg):
        '''write a debug message'''
        if self.debug_level >= level:
            print(msg)

    def unpack(self):
        '''unpack a message'''
        if not self.valid():
            raise UBloxError('INVALID MESSAGE')
        type = self.msg_type()
        if not type in msg_types:
            raise UBloxError('Unknown message %s length=%u' % (str(type), len(self._buf)))
        msg_types[type].unpack(self)

    def pack(self):
        '''pack a message'''
        if not self.valid():
            raise UBloxError('INVALID MESSAGE')
        type = self.msg_type()
        if not type in msg_types:
            raise UBloxError('Unknown message %s' % str(type))
        msg_types[type].pack(self)

    def name(self):
        '''return the short string name for a message'''
        if not self.valid():
            raise UBloxError('INVALID MESSAGE')
        type = self.msg_type()
        if not type in msg_types:
            raise UBloxError('Unknown message %s length=%u' % (str(type), len(self._buf)))
        return msg_types[type].name

    def msg_class(self):
        '''return the message class'''
        return self._buf[2]

    def msg_id(self):
        '''return the message id within the class'''
        return self._buf[3]

    def msg_type(self):
        '''return the message type tuple (class, id)'''
        return (self.msg_class(), self.msg_id())

    def msg_length(self):
        '''return the payload length'''
        (payload_length,) = struct.unpack('<H', self._buf[4:6])
        return payload_length

    def valid_so_far(self):
        '''check if the message is valid so far'''
        if len(self._buf) > 0 and self._buf[0] != PREAMBLE1:
            return False
        if len(self._buf) > 1 and self._buf[1] != PREAMBLE2:
            self.debug(1, "bad pre2")
            return False
        if self.needed_bytes() == 0 and not self.valid():
            if len(self._buf) > 8:
                self.debug(1, "bad checksum len=%u needed=%u" % (len(self._buf), self.needed_bytes()))
            else:
                self.debug(1, "bad len len=%u needed=%u" % (len(self._buf), self.needed_bytes()))
            return False
        return True

    def add(self, bytes):
        '''add some bytes to a message'''
        self._buf += bytes
        while not self.valid_so_far() and len(self._buf) > 0:
            self._buf = self._buf[1:]
        if self.needed_bytes() < 0:
            self._buf = b""

    def checksum(self, data=None):
        '''return a checksum tuple for a message'''
        if data is None:
            data = self._buf[2:-2]
        cs = 0
        ck_a = 0
        ck_b = 0
        for i in data:
            ck_a = (ck_a + i) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        return (ck_a, ck_b)

    def valid_checksum(self):
        '''check if the checksum is OK'''
        (ck_a, ck_b) = self.checksum()
        d = self._buf[2:-2]
        (ck_a2, ck_b2) = struct.unpack('<BB', self._buf[-2:])
        return ck_a == ck_a2 and ck_b == ck_b2

    def needed_bytes(self):
        '''return number of bytes still needed'''
        if len(self._buf) < 6:
            return 8 - len(self._buf)
        return self.msg_length() + 8 - len(self._buf)

    def valid(self):
        '''check if a message is valid'''
        return len(self._buf) >= 8 and self.needed_bytes() == 0 and self.valid_checksum()


class UBlox:
    '''main UBlox control class.

    port can be a file (for reading only) or a serial device
    '''
    def __init__(self, port, baudrate=115200, timeout=0):

        self.serial_device = port
        self.baudrate = baudrate
        self.use_sendrecv = False
        self.use_i2c = False
        self.i2c_addr = 0x42
        self.read_only = False
        self.debug_level = 0

        if self.serial_device.startswith("tcp:"):
            import socket
            a = self.serial_device.split(':')
            destination_addr = (a[1], int(a[2]))
            self.dev = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.dev.connect(destination_addr)
            self.dev.setblocking(1)
            self.dev.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
            self.use_sendrecv = True
        elif self.serial_device.startswith("i2c:"):
            tail = self.serial_device[4:]
            if ':' in tail:
                i2c_path, addr_str = tail.rsplit(':', 1)
                self.i2c_addr = int(addr_str, 0)
            else:
                i2c_path = tail
            import smbus2
            bus_num = int(i2c_path.split('-')[-1])
            self.dev = smbus2.SMBus(bus_num)
            self.use_i2c = True
        elif os.path.isfile(self.serial_device):
            self.read_only = True
            self.dev = open(self.serial_device, mode='rb')
        else:
            import serial
            self.dev = serial.Serial(self.serial_device, baudrate=self.baudrate,
                                     dsrdtr=False, rtscts=False, xonxoff=False, timeout=timeout)
        self.logfile = None
        self.log = None
        self.preferred_dynamic_model = None
        self.preferred_usePPP = None
        self.preferred_dgps_timeout = None

    def close(self):
        '''close the device'''
        self.dev.close()
        self.dev = None

    def set_debug(self, debug_level):
        '''set debug level'''
        self.debug_level = debug_level

    def debug(self, level, msg):
        '''write a debug message'''
        if self.debug_level >= level:
            print(msg)

    def set_logfile(self, logfile, append=False):
        '''setup logging to a file'''
        if self.log is not None:
            self.log.close()
            self.log = None
        self.logfile = logfile
        if self.logfile is not None:
            if append:
                mode = 'ab'
            else:
                mode = 'wb'
            self.log = open(self.logfile, mode=mode)

    def set_preferred_dynamic_model(self, model):
        '''set the preferred dynamic model for receiver'''
        self.preferred_dynamic_model = model
        if model is not None:
            self.configure_poll(CLASS_CFG, MSG_CFG_NAV5)

    def set_preferred_dgps_timeout(self, timeout):
        '''set the preferred DGPS timeout for receiver'''
        self.preferred_dgps_timeout = timeout
        if timeout is not None:
            self.configure_poll(CLASS_CFG, MSG_CFG_NAV5)

    def set_preferred_usePPP(self, usePPP):
        '''set the preferred usePPP setting for the receiver'''
        if usePPP is None:
            self.preferred_usePPP = None
            return
        self.preferred_usePPP = int(usePPP)
        self.configure_poll(CLASS_CFG, MSG_CFG_NAVX5)

    def nmea_checksum(self, msg):
        d = msg[1:]
        cs = 0
        for i in d:
            cs ^= ord(i)
        return cs

    def write(self, buf):
        '''write some bytes'''
        if not self.read_only:
            if self.use_i2c:
                buf = bytes(buf)
                for i in range(0, len(buf), 32):
                    self.dev.write_i2c_block_data(self.i2c_addr, 0xFF, list(buf[i:i+32]))
                return
            if self.use_sendrecv:
                return self.dev.send(buf)
            return self.dev.write(buf)

    def read(self, n):
        '''read some bytes'''
        if self.use_i2c:
            avail_raw = self.dev.read_i2c_block_data(self.i2c_addr, 0xFD, 2)
            avail = (avail_raw[0] << 8) | avail_raw[1]
            if avail == 0 or avail == 0xFFFF:
                time.sleep(0.05)
                return b''
            return bytes(self.dev.read_i2c_block_data(self.i2c_addr, 0xFF, min(n, avail, 32)))
        if self.use_sendrecv:
            import socket
            try:
                return self.dev.recv(n)
            except socket.error as e:
                return ''
        return self.dev.read(n)

    def send_nmea(self, msg):
        if not self.read_only:
            s = msg + "*%02X" % self.nmea_checksum(msg)
            self.write(s.encode('ascii'))

    def set_binary(self):
        '''put a UBlox into binary mode using a NMEA string'''
        if not self.read_only:
            print("try set binary at %u" % self.baudrate)
            self.send_nmea("$PUBX,41,0,0007,0001,%u,0" % self.baudrate)
            self.send_nmea("$PUBX,41,1,0007,0001,%u,0" % self.baudrate)
            self.send_nmea("$PUBX,41,2,0007,0001,%u,0" % self.baudrate)
            self.send_nmea("$PUBX,41,3,0007,0001,%u,0" % self.baudrate)
            self.send_nmea("$PUBX,41,4,0007,0001,%u,0" % self.baudrate)
            self.send_nmea("$PUBX,41,5,0007,0001,%u,0" % self.baudrate)

    def seek_percent(self, pct):
        '''seek to the given percentage of a file'''
        self.dev.seek(0, 2)
        filesize = self.dev.tell()
        self.dev.seek(pct*0.01*filesize)

    def special_handling(self, msg):
        '''handle automatic configuration changes'''
        try:
            name = msg.name()
        except UBloxError:
            return
        if name == 'CFG_NAV5':
            msg.unpack()
            sendit = False
            pollit = False
            if self.preferred_dynamic_model is not None and msg.dynModel != self.preferred_dynamic_model:
                msg.dynModel = self.preferred_dynamic_model
                sendit = True
                pollit = True
            if self.preferred_dgps_timeout is not None and msg.dgpsTimeOut != self.preferred_dgps_timeout:
                msg.dgpsTimeOut = self.preferred_dgps_timeout
                self.debug(2, "Setting dgpsTimeOut=%u" % msg.dgpsTimeOut)
                sendit = True
                # we don't re-poll for this one, as some receivers refuse to set it
            if sendit:
                msg.pack()
                self.send(msg)
                if pollit:
                    self.configure_poll(CLASS_CFG, MSG_CFG_NAV5)
        if name == 'CFG_NAVX5' and self.preferred_usePPP is not None:
            msg.unpack()
            if msg.usePPP != self.preferred_usePPP:
                msg.usePPP = self.preferred_usePPP
                msg.mask = 1<<13
                msg.pack()
                self.send(msg)
                self.configure_poll(CLASS_CFG, MSG_CFG_NAVX5)


    def receive_message(self, ignore_eof=False):
        '''blocking receive of one ublox message'''
        msg = UBloxMessage()
        while True:
            n = msg.needed_bytes()
            b = self.read(n)
            if not b:
                if ignore_eof:
                    time.sleep(0.01)
                    continue
                return None
            msg.add(b)
            if self.log is not None:
                self.log.write(b)
                self.log.flush()
            if msg.valid():
                self.special_handling(msg)
                return msg

    def receive_message_noerror(self, ignore_eof=False):
        '''blocking receive of one ublox message, ignoring errors'''
        try:
            return self.receive_message(ignore_eof=ignore_eof)
        except UBloxError as e:
            print(e)
            return None
        except OSError as e:
            # Occasionally we get hit with 'resource temporarily unavailable'
            # messages here on the serial device, catch them too.
            print(e)
            return None

    def send(self, msg):
        '''send a preformatted ublox message'''
        if not msg.valid():
            self.debug(1, "invalid send")
            return
        if not self.read_only:
            self.write(msg._buf)        

    def send_message(self, msg_class, msg_id, payload):
        '''send a ublox message with class, id and payload'''
        msg = UBloxMessage()
        msg._buf = struct.pack('<BBBBH', 0xb5, 0x62, msg_class, msg_id, len(payload))
        msg._buf += payload
        (ck_a, ck_b) = msg.checksum(msg._buf[2:])
        msg._buf += struct.pack('<BB', ck_a, ck_b)
        self.send(msg)

    def configure_solution_rate(self, rate_ms=200, nav_rate=1, timeref=0):
        '''configure the solution rate in milliseconds'''
        payload = struct.pack('<HHH', rate_ms, nav_rate, timeref)
        self.send_message(CLASS_CFG, MSG_CFG_RATE, payload)

    def configure_message_rate(self, msg_class, msg_id, rate):
        '''configure the message rate for a given message'''
        payload = struct.pack('<BBB', msg_class, msg_id, rate)
        self.send_message(CLASS_CFG, MSG_CFG_SET_RATE, payload)

    def configure_port(self, port=1, inMask=3, outMask=3, mode=2240, baudrate=None):
        '''configure a IO port'''
        if baudrate is None:
            baudrate = self.baudrate
        payload = struct.pack('<BBHIIHHHH', port, 0xff, 0, mode, baudrate, inMask, outMask, 0xFFFF, 0xFFFF)
        self.send_message(CLASS_CFG, MSG_CFG_PRT, payload)

    def configure_loadsave(self, clearMask=0, saveMask=0, loadMask=0, deviceMask=0):
        '''configure configuration load/save'''
        payload = struct.pack('<IIIB', clearMask, saveMask, loadMask, deviceMask)
        self.send_message(CLASS_CFG, MSG_CFG_CFG, payload)

    def configure_poll(self, msg_class, msg_id, payload=b''):
        '''poll a configuration message'''
        self.send_message(msg_class, msg_id, payload)

    def configure_poll_port(self, portID=None):
        '''poll a port configuration'''
        if portID is None:
            self.configure_poll(CLASS_CFG, MSG_CFG_PRT)
        else:
            self.configure_poll(CLASS_CFG, MSG_CFG_PRT, struct.pack('<B', portID))

    def configure_min_max_sats(self, min_sats=4, max_sats=32):
        '''Set the minimum/maximum number of satellites for a solution in the NAVX5 message'''
        payload = struct.pack('<HHIBBBBBBBBBBHIBBBBBBHII', 0, 4, 0, 0, 0, min_sats, max_sats, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        self.send_message(CLASS_CFG, MSG_CFG_NAVX5, payload)

    def configure_value_set(self, key, value: bytes | bool, layers=1, transaction=0):
        '''set configuration field with UBX > 23.01 scheme'''
        if isinstance(value, bool):
            _value = bytes((value,))
        else:
            _value = value
        payload = struct.pack('<BBBBI', 0, layers, transaction, 0, key) + _value
        self.send_message(CLASS_CFG, MSG_CFG_VALSET, payload)

    def set_baudrate(self, baudrate, uart=1, layers=None):
        '''Set UART baudrate via CFG-VALSET (UBX >= 23.01).
        NOTE: the new baudrate takes effect immediately on the GPS side, so no
        ACK can be received at the old baudrate. Close and reopen the port at
        the new baudrate after calling this.
        uart: 1 = UART1, 2 = UART2'''
        key_map = {1: CFG_UART1_BAUDRATE, 2: CFG_UART2_BAUDRATE}
        if uart not in key_map:
            raise UBloxError("Unsupported UART %d (must be 1 or 2)" % uart)
        if layers is None:
            layers = VALSET_LAYER_RAM | VALSET_LAYER_BBR | VALSET_LAYER_FLASH
        self.configure_value_set(key_map[uart], struct.pack('<I', baudrate), layers=layers)

    def module_reset(self, set, mode):
        ''' Reset the module for hot/warm/cold start'''
        payload = struct.pack('<HBB', set, mode, 0)
        self.send_message(CLASS_CFG, MSG_CFG_RST, payload)

# Begin additions for Wenet
class UBloxGPS(object):
    """ UBlox GPS Abstraction Layer Class """

    def __init__(self,port='/dev/ublox', baudrate=115200, timeout=2,
            callback=None,
            update_rate_ms=500,
            dynamic_model=DYNAMIC_MODEL_AIRBORNE1G,
            debug_ptr = None,
            log_file = None,
            ntpd_update = False,
            satellites = False,
            prot_ver=23.01):

        """ Initialise a UBloxGPS Abstraction layer object.
        
        Keyword Arguments:
        port:   Serial Port where uBlox is connected. See 99-usb-serial.rules for suitable udev rules to make a /dev/ublox symlink.
        baudrate: Serial port baud-rate.
        timeout: Serial port timeout.

        callback: reference to a callback function that will be passed a copy of the above
                  state dictionary upon receipt of a GPS fix from the uBlox.
                  NOTE: The callback will be called in a separate thread.

        update_rate_ms: Requested GPX fix rate. uBlox chip is capable of max 10Hz (100ms) updates.
        dynamic_model: Dynamic model to use. See above for list of possible models.

        debug_ptr:  Reference to a function which can handle debug messages and do something useful with them.
                    In the wenet payload, we use this to link this object to the PacketTX object to be able to
                    transit debug messages to the ground.

        log_file:   An optional filename in which to log GPS state data. Data will be stored as lines of JSON data.
                    Data is written whenever the gps_callback function is called.

        ntpd_update:  If set to true, use ntpdshm to push time information into NTPD via the Shared Memory Interface.
                      This uses shared memory 'unit 2', and so the following lines need to be added to /etc/ntp.conf:
                        server 127.127.28.2 minpoll 4 maxpoll 4
                        fudge 127.127.28.2 time1 0.09 refid PYTH stratum 2
                      Adjust the '0.09' in the fudge line to compensate for processing delays (which are hopefully constant).
                      This GPS time sync should be good to maybe +/- 50 mS or so.
                      This requires the ntpdshm python library: https://pypi.python.org/pypi/ntpdshm/0.2.1

        satellites: If set, MSG-NAV-SAT will be requested from the GPS and included in the state data. This can be useful for
                    troubleshooting and viewing satellite C/N0 values. 


        """

        # Copy supplied values.
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.dynamic_model = dynamic_model
        self.update_rate_ms = update_rate_ms
        self.debug_ptr = debug_ptr
        self.callback = callback
        self.ntpd_shm = None
        self.satellites = satellites
        self.prot_ver = prot_ver


        # Internal state dictionary, updated on receipt of GPS messages.
        self.state = {
            'latitude':      0.0,
            'longitude':     0.0,
            'altitude':      0.0,
            'ground_speed':  0.0,
            'ascent_rate':   0.0,
            'heading':       0.0,
            'gpsFix':        0,
            'numSV':         0,
            'week':          0,
            'iTOW':          0,
            'leapS':         0,
            'timestamp':     " ",
            'datetime':      datetime.datetime.now(datetime.timezone.utc),
            'dynamic_model': 255,
            'satellites':    [],
        }
        self._state_lock = Lock()

        # Open log file, if one has been given.
        if log_file != None:
            self.log_file = open(log_file,'a')
            self.log_file.write("Opened Log File.\n")
        else:
            self.log_file = None

        # Attempt to inialise.
        self.gps = UBlox(self.port, self.baudrate, self.timeout)
        self.setup_ublox()

        if ntpd_update:
            try:
                # Attempt to import and set up a NTPD SHM interface.
                import ntpdshm
                self.ntpd_shm = ntpdshm.NtpdShm(unit=2)
                self.ntpd_shm.mode = 0
                self.ntpd_shm.precision = -5
                self.ntpd_shm.leap = 0
                self.debug_message("Setup NTPD Interface OK")
            except:
                self.ntpd_shm = None
                self.debug_message("Failed to start NTPD Interface")

        # Start RX thead.
        self.rx_thread = Thread(target=self.rx_loop, daemon=True)
        self.rx_thread.start()

    def setup_ublox(self):
        """ Configure the uBlox GPS """
        if not self.gps.use_i2c:
            self.gps.set_binary()
        
        # Query protocol version
        # Assume < 23.01 unless PROTO_VER tells otherwise
        self.gps.configure_poll(CLASS_MON, MSG_MON_VER)
        msg = None
        while msg is None or msg.name() != "MON_VER":
            msg = self.gps.receive_message()

        msg.unpack()
        proto_read = False
        for rec in msg._recs:
            if 'extension' in rec:
                extension = rec['extension'].split(b'\0', 1)[0].decode('utf-8')
                if 'PROTVER' in extension:
                    self.prot_ver = float(extension.split('=')[1])
                    self.debug_message(f"Read UBX protocol version: {self.prot_ver}")
                    proto_read = True

        if not proto_read:
            self.debug_message(f"Using UBX protocol version: {self.prot_ver}")

        # For 6/7/8 series modules
        if self.prot_ver <= 23.01:
            self.gps.configure_poll_port()
            self.gps.configure_poll(CLASS_CFG, MSG_CFG_USB)
            self.gps.configure_port(port=PORT_SERIAL1, inMask=1, outMask=1)
            self.gps.configure_port(port=PORT_USB, inMask=1, outMask=1)
            self.gps.configure_port(port=PORT_SERIAL2, inMask=1, outMask=1)
            self.gps.configure_poll_port()
            self.gps.configure_poll_port(PORT_SERIAL1)
            self.gps.configure_poll_port(PORT_SERIAL2)
            self.gps.configure_poll_port(PORT_USB)

            self.gps.configure_solution_rate(rate_ms=self.update_rate_ms)

            self.gps.set_preferred_dynamic_model(self.dynamic_model)

            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_POSLLH, 1)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_STATUS, 1)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_SOL, 1)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_VELNED, 1)
            self.gps.configure_message_rate(CLASS_CFG, MSG_CFG_NAV5, 1)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_TIMEGPS, 1)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_CLOCK, 5)
        else:
            # set UBX protocol to be only protocol on USB, UARTs, and I2C (if active)
            self.gps.configure_value_set(CFG_UART1INPROT_UBX, True)
            self.gps.configure_value_set(CFG_UART2INPROT_UBX, True)
            self.gps.configure_value_set(CFG_USBINPROT_UBX, True)
            if self.gps.use_i2c:
                self.gps.configure_value_set(CFG_I2CINPROT_UBX, True)
                self.gps.configure_value_set(CFG_I2CINPROT_NMEA, False)
                self.gps.configure_value_set(CFG_I2CINPROT_RTCM3X, False)

            self.gps.configure_value_set(CFG_UART1OUTPROT_UBX, True)
            self.gps.configure_value_set(CFG_UART1OUTPROT_NMEA, False)
            self.gps.configure_value_set(CFG_UART1OUTPROT_RTCM3X, False)
            self.gps.configure_value_set(CFG_UART2OUTPROT_UBX, True)
            self.gps.configure_value_set(CFG_UART2OUTPROT_NMEA, False)
            self.gps.configure_value_set(CFG_UART2OUTPROT_RTCM3X, False)
            self.gps.configure_value_set(CFG_USBOUTPROT_UBX, True)
            self.gps.configure_value_set(CFG_USBOUTPROT_NMEA, False)
            self.gps.configure_value_set(CFG_USBOUTPROT_RTCM3X, False)
            if self.gps.use_i2c:
                self.gps.configure_value_set(CFG_I2COUTPROT_UBX, True)
                self.gps.configure_value_set(CFG_I2COUTPROT_NMEA, False)
                self.gps.configure_value_set(CFG_I2COUTPROT_RTCM3X, False)

            self.gps.configure_solution_rate(rate_ms=self.update_rate_ms)

            self.gps.set_preferred_dynamic_model(self.dynamic_model)

            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_POSLLH, 0)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_STATUS, 0)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_VELNED, 0)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_PVT, 1)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_TIMEGPS, 1)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_CLOCK, 5)
            
            nav_sat_rate = bytes([1 if self.satellites else 0])
            self.gps.configure_value_set(CFG_MSGOUT_NAV_SAT_UART1, nav_sat_rate)
            self.gps.configure_value_set(CFG_MSGOUT_NAV_SAT_UART2, nav_sat_rate)
            self.gps.configure_value_set(CFG_MSGOUT_NAV_SAT_USB, nav_sat_rate)
            if self.gps.use_i2c:
                self.gps.configure_value_set(CFG_MSGOUT_NAV_SAT_I2C, nav_sat_rate)

    def debug_message(self, message):
        """ Write a debug message.
        If debug_ptr was set to a function during init, this will
        pass the message to that function, else it will just print it.
        This is used mainly to get error and other state updates into the Wenet downlink.
        """
        message = "GPS Debug: " + message
        if self.debug_ptr != None:
            self.debug_ptr(message)
        else:
            print(message)

    # Thread-safe read/write access into the internal state dictionary
    def write_state(self, value, parameter):
        with self._state_lock:
            self.state[value] = parameter

    def read_state(self):
        with self._state_lock:
            return self.state.copy()

    # Function called whenever we have a new GPS fix.
    def gps_callback(self):
        """ Pass the latest GPS state to an external callback function """
        # Grab latest state.
        latest_state = self.read_state()

        if self.callback != None:
            self.callback(latest_state)

        # Write into the log file, if we are using one.
        if self.log_file != None:
            # Quick hack to stop json trying to serialise a datetime object.
            latest_state['datetime'] = latest_state['timestamp']
            self.log_file.write(json.dumps(latest_state) + '\n')


    # Utility function to convert GPS time to UTC time.
    def weeksecondstoutc(self, gpsweek, gpsseconds, leapseconds):
        """ Convert time in GPS time (GPS Week, seconds-of-week) to a UTC timestamp """
        epoch = datetime.datetime.strptime("1980-01-06 00:00:00","%Y-%m-%d %H:%M:%S")
        elapsed = datetime.timedelta(days=(gpsweek*7),seconds=(gpsseconds))
        timestamp = epoch + elapsed - datetime.timedelta(seconds=leapseconds)
        return (timestamp.isoformat(), timestamp)

    rx_running = True
    rx_counter = 0
    def rx_loop(self):
        """ Main RX Loop 
            In here we process all incoming messages from the uBlox GPS unit,
            and update our internal state table.

            Based on a bit of testing, with the above setup of polling, the uBlox chip
            seems to consistently output messages every fix in the following order:
                NAV_SOL
                NAV_STATUS
                NAV_POSLLH
                NAV_VELNED
            These messages are all from the same GPS solution, and so we can use the arrival
            of a NAV_VELNED packet to signify that we have a 'complete' GPS solution, which can
            then be passed off to a callback function.
        """
        while self.rx_running:
            try:
                msg = self.gps.receive_message()
                if msg is None:
                    continue
                msg_name = msg.name()
                #print(msg_name)
            except Exception as e:
                self.debug_message("WARNING: GPS Failure - " + str(e))
                self.write_state('numSV',0)
                # Attempt to re-open GPS.
                time.sleep(5)
                try:
                    self.gps.close()
                except:
                    pass

                try:
                    self.gps = UBlox(self.port, self.baudrate, self.timeout)
                    self.setup_ublox()
                    self.debug_message("WARNING: GPS Re-connected.")
                except:
                    pass
                continue

            # If we have received a message we care about, unpack it and update our state dict.
            if msg_name == "NAV_SOL":
                msg.unpack()
                self.write_state('numSV', msg.numSV)
                self.write_state('gpsFix', msg.gpsFix)

            elif msg_name == "NAV_POSLLH":
                msg.unpack()
                self.write_state('latitude', msg.Latitude*1.0e-7)
                self.write_state('longitude', msg.Longitude*1.0e-7)
                self.write_state('altitude', msg.height*1.0e-3)

            elif msg_name == "NAV_VELNED":
                msg.unpack()
                self.write_state('ground_speed', msg.gSpeed*0.036) # Convert to kph
                self.write_state('heading', msg.heading*1.0e-5)
                self.write_state('ascent_rate', -1.0*msg.velD/100.0)

            elif msg_name == "NAV_PVT":
                msg.unpack()
                self.write_state('numSV', msg.numSV)
                self.write_state('gpsFix', msg.fixType)
                self.write_state('latitude', msg.Latitude*1.0e-7)
                self.write_state('longitude', msg.Longitude*1.0e-7)
                self.write_state('altitude', msg.height*1.0e-3)
                self.write_state('ground_speed', msg.gSpeed*0.0036) # Convert to kph
                self.write_state('heading', msg.headMot*1.0e-5)
                self.write_state('ascent_rate', -1.0*msg.velD/1000.0)

            elif msg_name == "NAV_TIMEGPS":
                msg.unpack()
                self.write_state('week',msg.week)
                self.write_state('iTOW', msg.iTOW*1.0e-3)
                self.write_state('leapS', msg.leapS)
                (time_isotime, time_datetime) = self.weeksecondstoutc(msg.week, msg.iTOW*1.0e-3, msg.leapS)
                self.write_state('timestamp', time_isotime)
                self.write_state('datetime', time_datetime)

                # Update the NTPD Interface, if it exists, and ONLY if we are on a whole-second boundary.
                if self.ntpd_shm != None and ((msg.iTOW*1.0e-3 - math.floor(msg.iTOW*1.0e-3)) == 0.0):
                    utc_timestamp = calendar.timegm(time_datetime.utctimetuple())
                    self.ntpd_shm.update(utc_timestamp)

                # We now have a 'complete' GPS solution, and can pass it onto a callback,
                # if we were given one when we were initialised.
                self.rx_counter += 1

                # Poll for a CFG_NAV5 message occasionally.
                if self.rx_counter % 20 == 0:
                    # A message with only 0x00 in the payload field is a poll.
                    self.gps.send_message(CLASS_CFG, MSG_CFG_NAV5,b'\x00')

                # Additional checks to be sure we're in the right dynamic model.
                if self.rx_counter % 40 == 0:
                    self.gps.set_preferred_dynamic_model(self.dynamic_model)

                # Send data to the callback function.
                # daemon=True: thread won't prevent process exit and won't
                # accumulate if the callback is occasionally slow.
                callback_thread = Thread(target=self.gps_callback, daemon=True)
                callback_thread.start()

            elif msg_name == "NAV_SAT":
                msg.unpack()
                satellites = []
                for sv in msg._recs:
                    satellites.append({
                        'gnssId': sv.gnssId,
                        'svId':   sv.svId,
                        'cno':    sv.cno,
                        'elev':   sv.elev,
                        'azim':   sv.azim,
                        'flags':  sv.flags,
                    })
                self.write_state('satellites', satellites)

            elif msg_name == "CFG_NAV5":
                msg.unpack()
                self.write_state('dynamic_model',msg.dynModel)
                if msg.dynModel != self.dynamic_model:
                    self.debug_message("Dynamic model changed.")
                    self.gps.set_preferred_dynamic_model(self.dynamic_model)

            else:
                pass

        
        print("GPS RX thread closed.")

    def close(self):
        """ Close GPS Connection """
        self.rx_running = False
        time.sleep(2)
        self.gps.close()
        if self.log_file != None:
            self.log_file.close()

if __name__ == "__main__":
    """ Basic test script for the above UBloxGPS class. 
    Sets up GPS and prints out basic position information.
    """
    import argparse
    import logging
    import sys
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument("serial_port", type=str, help="Serial port (/dev/ttyS0), I2C bus (/dev/i2c-1 with --i2c), or TCP address (tcp:host:port).")
    parser.add_argument("--baudrate", default=115200, type=int, help="Serial baud rate. Ignored for USB and I2C. Default: 115200.")
    parser.add_argument("--i2c", action='store_true', default=False, help="Use I2C (DDC) instead of UART. serial_port should be the I2C bus device, e.g. /dev/i2c-1.")
    parser.add_argument("--i2c-addr", default=0x42, type=lambda x: int(x, 0), help="I2C address of the GPS module. Default: 0x42.")
    parser.add_argument("--set-baudrate", default=None, type=int, help="Set the specified UART's baudrate and save to BBR+Flash (SPG 5.10+). Exits after configuring.")
    parser.add_argument("--uart", default=1, type=int, choices=[1, 2], help="UART port to configure with --set-baudrate (1 or 2). Default: 1")
    parser.add_argument("--no-flash", action='store_true', default=False, help="With --set-baudrate: write to RAM+BBR only, skip Flash layer (for modules without external flash).")
    parser.add_argument("--waitforlock", default=None, type=int, help="If set, exit after the GPS has obtained lock, or a timeout (in minutes) is reached.")
    parser.add_argument("--lockcount", default=60, type=int, help="If waitforlock is specified, wait until the GPS reports lock for this many sequential fixes. Default: 60")
    parser.add_argument("--locksats", default=None, type=int, help="If waitforlock is specified, also wait until the GPS reports this many SVs used in its solution. Default: None")
    parser.add_argument("--ntp", action='store_true', default=False, help="Push time updates into NTPDSHM.")
    parser.add_argument("--satellites", action='store_true', default=False, help="Request satellite data from GPS.")
    parser.add_argument("--pretty", action='store_true', default=False, help="Clear the terminal on each fix and render a formatted GPS status display.")
    parser.add_argument("-v", "--verbose", action='store_true', default=False, help="Show additional debug info.")
    args = parser.parse_args()

    _GNSS_NAMES = {0: 'GPS', 1: 'SBAS', 2: 'Galileo', 3: 'BeiDou', 4: 'IMES', 5: 'QZSS', 6: 'GLONASS', 7: 'NavIC'}
    _FIX_NAMES  = {0: 'No Fix', 1: 'DR Only', 2: '2D Fix', 3: '3D Fix', 4: 'GPS+DR', 5: 'Time Only'}

    def _pretty_gps(state):
        ts    = state.get('timestamp', '---')
        fix   = _FIX_NAMES.get(state.get('gpsFix', 0), '?')
        numSV = state.get('numSV', 0)
        lat   = state.get('latitude', 0.0)
        lon   = state.get('longitude', 0.0)
        alt   = state.get('altitude', 0.0)
        spd   = state.get('ground_speed', 0.0)
        asc   = state.get('ascent_rate', 0.0)
        hdg   = state.get('heading', 0.0)
        sats  = state.get('satellites') or []

        out = ['\033[2J\033[H']  # clear + cursor home
        out.append(f'GPS Monitor  {ts}')
        out.append('\u2500' * 56)
        out.append(f'Fix: {fix:<12}  SVs used: {numSV}  tracked: {len(sats)}')
        out.append(f'Lat: {lat:+.6f}\u00b0   Lon: {lon:+.6f}\u00b0   Alt: {alt:.1f} m')
        out.append(f'Speed: {spd:.2f} km/h   Asc: {asc:+.2f} m/s   Hdg: {hdg:.1f}\u00b0')

        if sats:
            out.append('')
            out.append(f"  {'GNSS':<8} {'SvID':>4}  {'dBHz':>4}  {'\u2501'*20}  {'El':>3} {'Az':>3}")
            out.append('  ' + '\u2500' * 50)
            for sv in sorted(sats, key=lambda s: (-(s['flags'] & 0x08), -s['cno'])):
                used  = bool(sv['flags'] & 0x08)
                gnss  = _GNSS_NAMES.get(sv['gnssId'], f"#{sv['gnssId']}")
                cno   = sv['cno']
                filled = min(cno * 20 // 50, 20)
                bar   = f"{'█' * filled:<20}"
                mark  = ' \u25c4' if used else ''
                if used:
                    color = '\033[92m'   # bright green
                elif cno > 0:
                    color = '\033[93m'   # yellow
                else:
                    color = '\033[2m'    # dim
                out.append(f"  {color}{gnss:<8} {sv['svId']:>4}  {cno:>4}  {bar}  {sv['elev']:>3}\u00b0 {sv['azim']:>3}\u00b0{mark}\033[0m")

        return '\n'.join(out) + '\n'

    if args.verbose:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    # Set up logging
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging_level)

    port = f"i2c:{args.serial_port}:{args.i2c_addr:#x}" if args.i2c else args.serial_port

    if args.set_baudrate:
        layers = VALSET_LAYER_RAM | VALSET_LAYER_BBR
        if not args.no_flash:
            layers |= VALSET_LAYER_FLASH
        logging.info(f"Connecting to {args.serial_port} at {args.baudrate} baud...")
        u = UBlox(port, baudrate=args.baudrate, timeout=2)
        logging.info(f"Setting UART{args.uart} baudrate to {args.set_baudrate} bps...")
        u.set_baudrate(args.set_baudrate, uart=args.uart, layers=layers)
        u.close()
        logging.info(f"Done. GPS will now communicate at {args.set_baudrate} bps.")
        sys.exit(0)

    gps = None
    lock_counter = 0
    start_time = time.time()

    lock_acheived = False

    def gps_callback(state):
        global args, lock_counter, start_time, gps, lock_acheived

        if args.waitforlock:

            # If we have a GPS fix
            if state['gpsFix'] == 3:
                if args.locksats:
                    if state['numSV'] >= args.locksats:
                        lock_counter += 1
                    else:
                        lock_counter = 0
                else:
                    lock_counter += 1
            else:
                lock_counter = 0
            logging.info(f"Lock Counter: {lock_counter}/{args.lockcount}")

            if lock_counter >= args.lockcount:
                logging.info(f"GNSS lock maintained for {lock_counter} fixes! Exiting..")
                lock_acheived = True

        if args.pretty:
            sys.stdout.write(_pretty_gps(state))
            sys.stdout.flush()
        else:
            logging.info(f"GPS State: {state}")


    gps = UBloxGPS(
        port=port,
        baudrate=args.baudrate,
        callback=gps_callback, 
        update_rate_ms=500, 
        dynamic_model=DYNAMIC_MODEL_AIRBORNE1G, 
        ntpd_update=args.ntp,
        satellites=args.satellites,
        debug_ptr=logging.info
        )

    try:
        while True:
            time.sleep(1)

            if args.waitforlock:
                if ((time.time() - start_time) > (args.waitforlock*60)):
                    logging.critical("Reached lock timeout! Exiting...")
                    gps.close()
                    sys.exit(0)

                if lock_acheived:
                    logging.info("Acheived GNSS lock!")
                    gps.close()
                    time.sleep(2)
                    sys.exit(0)

    except KeyboardInterrupt:
        gps.close()


