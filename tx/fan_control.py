"""
Closed-loop PWM fan controller for Wenet Pi HAT.

Drives GPIO12 (hardware PWM0) proportionally based on ADS1115 aux_temp:
  - 35°C  ->  0% duty cycle
  - 60°C  -> 100% duty cycle
  - Linear interpolation, clamped at both ends.

Requires the PWM overlay in /boot/firmware/config.txt:
    dtoverlay=pwm,pin=12,func=4

Install: pip install rpi-hardware-pwm

PWM chip number varies by Pi model:
    Pi 4: chip=0
    Pi 5: chip=2
"""

import time
import RPi.GPIO as GPIO
from rpi_hardware_pwm import HardwarePWM
from PowerTelem import WenetPiHAT

PWM_CHANNEL = 0       # GPIO12 = PWM channel 0
PWM_CHIP    = 0       # chip=2 for Pi 5; use chip=0 for Pi 4
PWM_FREQ    = 25000   # 25 kHz — standard 4-pin PWM fan frequency
TEMP_MIN    = 35.0    # °C — fan fully off below this
TEMP_MAX    = 60.0    # °C — fan fully on at or above this
POLL_PERIOD = 2.0     # seconds between temperature reads

GPIO_PIN    = 24      # BCM numbering — on/off output
GPIO_HIGH   = 85.0    # °C — turn GPIO18 off at or above this
GPIO_LOW    = 75.0    # °C — turn GPIO18 on at or below this
GPIO_DEBOUNCE = 3     # consecutive over-threshold samples needed to turn off


def temp_to_duty(temp: float) -> float:
    """Return duty cycle in [0.0, 100.0] for a given temperature."""
    if temp <= TEMP_MIN:
        return 0.0
    if temp >= TEMP_MAX:
        return 100.0
    return (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN) * 100.0


def main():
    pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=PWM_FREQ, chip=PWM_CHIP)
    pwm.start(0)

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.OUT)
    # Leave the pin as-is at startup; only drive it on if we turned it off.
    gpio_off = False
    over_count = 0    # consecutive samples at or above GPIO_HIGH

    hat = WenetPiHAT(i2c=1, address=0x48)

    print(f"Fan controller started — PWM channel {PWM_CHANNEL}, {PWM_FREQ} Hz")
    print(f"  0% duty at {TEMP_MIN}°C, 100% duty at {TEMP_MAX}°C")
    print(f"  GPIO{GPIO_PIN} off above {GPIO_HIGH}°C, on below {GPIO_LOW}°C")

    try:
        while True:
            data = hat.read()
            temp = data['aux_temp']
            duty = temp_to_duty(temp)

            pwm.change_duty_cycle(duty)

            if temp >= GPIO_HIGH:
                over_count += 1
            else:
                over_count = 0

            if over_count >= GPIO_DEBOUNCE and not gpio_off:
                gpio_off = True
                GPIO.output(GPIO_PIN, GPIO.LOW)
            elif temp <= GPIO_LOW and gpio_off:
                gpio_off = False
                GPIO.output(GPIO_PIN, GPIO.HIGH)

            print(f"Temp: {temp:.1f}°C  ->  duty: {duty:.1f}%  GPIO{GPIO_PIN}: {'OFF' if gpio_off else 'ON'}")
            time.sleep(POLL_PERIOD)

    except KeyboardInterrupt:
        print("\nShutting down — fan set to 100% for safety")
        pwm.change_duty_cycle(100.0)
        pwm.stop()
        GPIO.cleanup()


if __name__ == "__main__":
    main()
