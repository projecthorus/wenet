#!/usr/bin/env python
#
#   LDPC Encoder and interleaver Functions.
#   Uses ctypes to call the encode function from ldpc_enc.c
#
#   ldpc_enc.c needs to be compiled to a .so before this will work, with:
#   gcc -fPIC -shared -o ldpc_enc.so ldpc_enc.c
#
#   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#

import codecs
import ctypes
from numpy.ctypeslib import ndpointer
import numpy as np
import time
import sys


# Attempt to load in ldpc_enc.so on startup.
try:
    _ldpc_enc = ctypes.CDLL("./ldpc_enc.so")
    _ldpc_enc.encode.restype = None
    _ldpc_enc.encode.argtypes = (ndpointer(ctypes.c_ubyte, flags="C_CONTIGUOUS"), ndpointer(ctypes.c_ubyte, flags="C_CONTIGUOUS"))

    _ldpc_enc.init_interleaver.restype = None
    _ldpc_enc.init_interleaver.argtypes = (ctypes.c_int,)

    _ldpc_enc.interleave_symbols.restype = None
    _ldpc_enc.interleave_symbols.argtypes = (ndpointer(ctypes.c_ubyte, flags="C_CONTIGUOUS"),)

except OSError as e:
    print("WARNING: Could not find ldpc_enc.so! Have you compiled ldpc_enc.c? \n gcc -fPIC -shared -o ldpc_enc.so ldpc_enc.c")
    sys.exit(1)

#
#   LDPC Encoder.
#   Accepts a 258 byte string as input, returns the LDPC parity bits.
#

def ldpc_encode(payload, Nibits = 2064, Npbits = 516):
    if len(payload) != 258:
        raise TypeError("Payload MUST be 258 bytes in length! (2064 bit codeword)")

    # Get input data into the right form (list of 0s and 1s)
    ibits = np.unpackbits(np.frombuffer(payload,dtype=np.uint8)).astype(np.uint8)
    pbits = np.zeros(Npbits).astype(np.uint8)

    _ldpc_enc.encode(ibits, pbits)

    return np.packbits(np.array(list(pbits)).astype(np.uint8)).tobytes()


#
#   Interleaver functions - Note that these are not used in Wenet right now.
#   These also may not work under Python 3
#

# These variables need to be synchronised with those in ldpc_enc.c, until i figure out a better way
# of passing this info around.

INTERLEAVER_SIZE = 256
INTERLEAVER_SIZE_BYTES = INTERLEAVER_SIZE/8
INTERLEAVER_DEPTH = 10

interleaver_byte_buffer = ""

def interleaver_init(forward=True):
    if forward:
        _ldpc_enc.init_interleaver(0)
    else:
        _ldpc_enc.init_interleaver(1)

# Input symbols into the interleaver, and get symbols to be transmitted
# This function will only accept a symbol array of length INTERLEAVER_SIZE
def interleave_symbols(symbols):
    if len(symbols)%INTERLEAVER_SIZE != 0:
        raise IOError("Input not a multiple of the interleaver width!")

    data = np.array(symbols).astype(np.uint8)

    _ldpc_enc.interleave_symbols(data)

    return data

# Interleave bytes,  passed in as a string
def interleave_bytes(data):
    # Clip to interleaver width
    # Need to do something a bit nicer here.
    if (len(data)%INTERLEAVER_SIZE_BYTES) > 0:
        clip_length = INTERLEAVER_SIZE_BYTES*int(len(data)/INTERLEAVER_SIZE_BYTES)
        data = data[:clip_length]
        print("WARNING: Clipped data")

    output = ""

    for x in range(int(len(data)/INTERLEAVER_SIZE_BYTES)):
        # Get current chunk of data and convert to bits.
        chunk = data[x*INTERLEAVER_SIZE_BYTES:x*INTERLEAVER_SIZE_BYTES+INTERLEAVER_SIZE_BYTES]
        chunk_bits = np.unpackbits(np.fromstring(chunk,dtype=np.uint8))
        new_chunk = interleave_symbols(chunk_bits)
        print(new_chunk)
        new_chunk = np.packbits(new_chunk).tostring()
        output += new_chunk

    return output


def interleave_test():
    pass


# Some testing functions, to time encoding performance.

def generate_dummy_packet():
    payload = np.arange(0,256,1)
    payload = np.append(payload,[0,0]).astype(np.uint8).tobytes() # Add on dummy checksum, for a total of 258 bytes.
    return payload

def main():
    # Generate a dummy test packet, and convert it to an array of 0 and 1.
    payload = generate_dummy_packet()

    print("Input (hex):" + codecs.encode(payload,'hex').decode())

    # Now run ldpc_encode over it X times.
    parity = ""
    start = time.time()
    for x in range(1000):
        #print(x)
        parity = ldpc_encode(payload)

    stop = time.time()
    print("time delta: %.3f" % (stop-start))

    print("LDPC Parity Bits (hex):" + codecs.encode(parity,'hex').decode())
    print("Done!")

# Some basic test code.
if __name__ == "__main__":
    main()
