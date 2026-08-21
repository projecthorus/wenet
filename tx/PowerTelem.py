from smbus2 import SMBus
import ads1115

class WenetPiHAT():
    """
    Class for polling power and temperature data from ADS1115 ADC
    """
    def __init__(self, i2c=1, address=0x48):
        bus = SMBus(i2c)
        # Initialize ADC with gain of 1
        self.adc = ads1115.ADS1115(bus, address, 1)

    def read(self):
        # 0.000125 = 4.096 / 32768

        batt_v = self.adc.read(4,0)
        batt_i = self.adc.read(4,1)
        temp =  self.adc.read(4,2)

        # print(batt_v, batt_i, temp)

        batt_v = int(batt_v * 5000.0 * 0.000125) # batt voltage in mV
        batt_i = int(batt_i * 1000.0 * 0.000125) # batt current in mA
        temp =  temp * 100.0 * 0.000125 # LM35 temperature (10mV/decC)

        return  {'batt_v': batt_v, 'batt_i': batt_i,  'aux_temp': temp}
    
if __name__ == "__main__":
       import time

       power_telem = WenetPiHAT(i2c=1, address=0x48)

       try:
               while True:
                       power_data = power_telem.read()
                       print(f"V: {power_data['batt_v']:.0f}mV, I: {power_data['batt_i']:.0f}mA, Temp: {power_data['aux_temp']:0.1f}C")
                       time.sleep(0.5)

       except KeyboardInterrupt:
               print("Keyboard Interrupt Exit")