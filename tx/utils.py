import numpy as np
class BinaryDebug(object):
    """ Debug binary 'transmitter' Class
    Used to write packet data to a file in one-bit-per-char (i.e. 0 = 0x00, 1 = 0x01)
    format for use with codec2-dev's fsk modulator.
    Useful for debugging, that's about it.
    """
    def __init__(self, rs232=True, f=None):
        if f:
            self.f = f
        else:
            self.f = open("debug.bin",'wb')
        self.rs232 = rs232 # RS232 framing

    def write(self,data):
        raw_data = np.array([],dtype=np.uint8)
        for d in data:
            d_array = np.unpackbits(np.frombuffer(d.to_bytes(1),dtype=np.uint8))
            if self.rs232:
                raw_data = np.concatenate((raw_data,[0],d_array[::-1],[1]))
            else:
                raw_data = np.concatenate((raw_data,d_array))

        self.f.write(raw_data.astype(np.uint8).tostring())
    def close(self):
        self.f.close()