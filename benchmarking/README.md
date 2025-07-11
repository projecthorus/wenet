# Wenet Performance Benchmarking
Some attempts at benchmarking the performance of the Wenet decode chains, so we know if we've broken things in the future.


## Setup
* Have the wenet rx code built. `fsk_demod` and `drs232_ldpc` should exist within wenet/rx/  (../rx/)
* Have csdr available on path. Doesnt really matter which fork, we just need the convert_u8_f and convert_f_u8 utils.

Make some directories
```
mkdir samples
mkdir generated
```

We also need numpy available for python3. You could get that via system packages, or create a venv and install with pip.

## Test Samples
To generate the low SNR files, we need a very high SNR (not overloading though) original sample.

If we have a wenet payload available, we can just dump some samples from rtl_sdr, e.g.:

```
rtl_sdr -s 921416 -f 443298440 -g 5 - > test_samples.cu8
```

We need this test sample in float32 format, which we can do using csdr:
```
cat test_samples.cu8 | csdr convert_u8_f > samples/wenet_sample_fs921416_float.bin
```

For 'traditional' Wenet (115177 baud, RS232 framing), a suitable sample set (~95s of received packets) is available here: https://www.dropbox.com/scl/fi/plazem0luo37l2dujbwuo/wenet_sample_fs921416Hz.cu8?rlkey=m4jftwmbazok9ry9kimhpd6kl&dl=0
(this still needs to be converted to float32 as above).

## Generating Low SNR Samples
Check generate_lowsnr.py for the list of files to be used as source material for low-snr generation.

Then, run: python generate_lowsnr.py

You should now have a bunch of files in the generated directory.

Note - this can be quite a lot of data! 

Note that the value in dB in the filenames is Eb/N0, so effectively snr-per-bit, normalised for baud rate.

## Running demod tests

Can do a quick check to make sure the highest SNR sample (which should have very good decode) works by running:
```
% python test_demod.py -m wenet_rs232_demod --quick
Command: cat ./generated/wenet_sample_fs921416_float_20.0dB.bin | csdr convert_f_u8 | ../rx/fsk_demod --cu8 -s --stats=100 2 921416 115177 - - 2> stats.txt | ../rx/drs232_ldpc - - 2> /dev/null  |  wc -c
wenet_sample_fs921416_float_20.0dB.bin, 530688, 11.156
```
Output consists of:
* filename
* number of bytes received (only packets with valid CRC are output from the decoder)
* Time taken to run the decode

Our performance metric is the number of bytes received.

We can then go ahead and run the tests using the full set of generated samples:

```
% python test_demod.py -m wenet_rs232_demod 
Command: cat ./generated/wenet_sample_fs921416_float_05.0dB.bin | csdr convert_f_u8 | ../rx/fsk_demod --cu8 -s --stats=100 2 921416 115177 - - 2> stats.txt | ../rx/drs232_ldpc - - 2> /dev/null  |  wc -c
wenet_sample_fs921416_float_05.0dB.bin, 0, 12.870
wenet_sample_fs921416_float_05.5dB.bin, 0, 13.500
wenet_sample_fs921416_float_06.0dB.bin, 0, 12.332
wenet_sample_fs921416_float_06.5dB.bin, 0, 12.375
wenet_sample_fs921416_float_07.0dB.bin, 0, 13.308
wenet_sample_fs921416_float_07.5dB.bin, 1280, 19.061
wenet_sample_fs921416_float_08.0dB.bin, 32512, 20.793
wenet_sample_fs921416_float_08.5dB.bin, 298240, 12.358
wenet_sample_fs921416_float_09.0dB.bin, 503040, 12.685
wenet_sample_fs921416_float_09.5dB.bin, 528128, 13.180
wenet_sample_fs921416_float_10.0dB.bin, 529920, 14.041
wenet_sample_fs921416_float_10.5dB.bin, 530176, 12.373
wenet_sample_fs921416_float_11.0dB.bin, 530432, 15.980
wenet_sample_fs921416_float_11.5dB.bin, 530176, 12.871
wenet_sample_fs921416_float_12.0dB.bin, 530432, 13.491
wenet_sample_fs921416_float_12.5dB.bin, 530432, 12.516
wenet_sample_fs921416_float_13.0dB.bin, 530432, 12.867
```

Things to look at:
* What Eb/N0 the number of received bytes starts to rise. With LDPC FEC it's a fairly quick increase from nothing to complete decodes. In the above case, our 50% packet-error-rate point is around 8.5 dB.
* How long it takes to run the decode chain. We see a slight increase in runtime around the weak-snr point, when we get a lot of unique-word detections, but where the LDPC decoder runs to maximum iterations (5) without a successful decode.

Currently there are demod chain tests for:
* `wenet_rs232_demod` - Wenet 'traditional' (v1?), 115177 baud, RS232 framing, with complex u8 samples going into fsk_demod
* `wenet_rs232_demod_c16` - Same as above, but feeding complex signed-16-bit samoples into fsk_demod (should give the same results).



## Baud Rate Error

If we compile the `tsrc` [resampling utility](https://github.com/projecthorus/radiosonde_auto_rx/blob/master/utils/tsrc.c) from radiosonde_auto_rx and place that in the working directory, we can also investigate how baud rate error effects the modem. We emulate baud rate error by resampling the test samples before feeding them into the demodulator. The --resample argument to test_demod.py allows this.

The short version of the results below is that at 0.3% baud rate error, the demodulator is barely affected. At 0.4 to 0.5% we start to see some significant degradation in performance. At 0.6% error the demodulator falls over completely.

Some detailed results below:

0.3% baud rate error (resampling 1.003)
```
wenet_sample_fs921416_float_05.0dB.bin, 0, 11.616
wenet_sample_fs921416_float_05.5dB.bin, 0, 11.082
wenet_sample_fs921416_float_06.0dB.bin, 0, 10.958
wenet_sample_fs921416_float_06.5dB.bin, 0, 11.502
wenet_sample_fs921416_float_07.0dB.bin, 0, 11.689
wenet_sample_fs921416_float_07.5dB.bin, 512, 10.945
wenet_sample_fs921416_float_08.0dB.bin, 44288, 12.450
wenet_sample_fs921416_float_08.5dB.bin, 319744, 10.885
wenet_sample_fs921416_float_09.0dB.bin, 498176, 12.270
wenet_sample_fs921416_float_09.5dB.bin, 517888, 11.823
wenet_sample_fs921416_float_10.0dB.bin, 524800, 11.473
wenet_sample_fs921416_float_10.5dB.bin, 527872, 12.089
wenet_sample_fs921416_float_11.0dB.bin, 527616, 10.763
wenet_sample_fs921416_float_11.5dB.bin, 529408, 10.672
wenet_sample_fs921416_float_12.0dB.bin, 528640, 10.982
wenet_sample_fs921416_float_12.5dB.bin, 529920, 10.786
wenet_sample_fs921416_float_13.0dB.bin, 530432, 11.128
wenet_sample_fs921416_float_13.5dB.bin, 530432, 11.618
wenet_sample_fs921416_float_14.0dB.bin, 530688, 13.131
wenet_sample_fs921416_float_14.5dB.bin, 530176, 11.227
```

0.4% baud rate error (resampling 1.004)
```
wenet_sample_fs921416_float_05.0dB.bin, 0, 14.871
wenet_sample_fs921416_float_05.5dB.bin, 0, 12.558
wenet_sample_fs921416_float_06.0dB.bin, 0, 11.828
wenet_sample_fs921416_float_06.5dB.bin, 0, 11.590
wenet_sample_fs921416_float_07.0dB.bin, 0, 11.789
wenet_sample_fs921416_float_07.5dB.bin, 768, 39.762
wenet_sample_fs921416_float_08.0dB.bin, 33024, 11.199
wenet_sample_fs921416_float_08.5dB.bin, 233472, 11.640
wenet_sample_fs921416_float_09.0dB.bin, 383744, 11.952
wenet_sample_fs921416_float_09.5dB.bin, 423424, 11.615
wenet_sample_fs921416_float_10.0dB.bin, 443392, 13.541
wenet_sample_fs921416_float_10.5dB.bin, 464640, 11.773
wenet_sample_fs921416_float_11.0dB.bin, 473600, 14.853
wenet_sample_fs921416_float_11.5dB.bin, 489728, 12.342
wenet_sample_fs921416_float_12.0dB.bin, 492800, 11.302
wenet_sample_fs921416_float_12.5dB.bin, 509184, 14.049
wenet_sample_fs921416_float_13.0dB.bin, 514816, 10.986
wenet_sample_fs921416_float_13.5dB.bin, 516864, 11.716
wenet_sample_fs921416_float_14.0dB.bin, 521216, 11.401
wenet_sample_fs921416_float_14.5dB.bin, 526592, 11.116
```

0.5% baud rate error (resampling 1.005)
```
wenet_sample_fs921416_float_05.0dB.bin, 0, 11.811
wenet_sample_fs921416_float_05.5dB.bin, 0, 12.631
wenet_sample_fs921416_float_06.0dB.bin, 0, 19.314
wenet_sample_fs921416_float_06.5dB.bin, 0, 23.884
wenet_sample_fs921416_float_07.0dB.bin, 0, 17.919
wenet_sample_fs921416_float_07.5dB.bin, 256, 24.970
wenet_sample_fs921416_float_08.0dB.bin, 5120, 13.781
wenet_sample_fs921416_float_08.5dB.bin, 41472, 12.175
wenet_sample_fs921416_float_09.0dB.bin, 70400, 23.371
wenet_sample_fs921416_float_09.5dB.bin, 93952, 14.122
wenet_sample_fs921416_float_10.0dB.bin, 105728, 12.069
wenet_sample_fs921416_float_10.5dB.bin, 116992, 18.710
wenet_sample_fs921416_float_11.0dB.bin, 141056, 13.651
wenet_sample_fs921416_float_11.5dB.bin, 143616, 20.215
wenet_sample_fs921416_float_12.0dB.bin, 169216, 13.285
wenet_sample_fs921416_float_12.5dB.bin, 178944, 13.912
wenet_sample_fs921416_float_13.0dB.bin, 198656, 15.465
wenet_sample_fs921416_float_13.5dB.bin, 219392, 14.138
wenet_sample_fs921416_float_14.0dB.bin, 228864, 22.024
wenet_sample_fs921416_float_14.5dB.bin, 255744, 18.072
```


## Weak Signal Tests

Aim here is to try and verify the 'minimum detectable signal' level of the different Wenet modes.

Receiver: RTLSDR + UpuTronics 440 MHz filtered preamp. Noise figure of this setup should be somewhere around 1-2 dB. 

Transmitter is a wenet payload in a metal box, situated across my house. Approx 90 dB attenuation at the output of the box, then ~20m LMR400 coax, then a step attenuator (0-90 dB in 1dB steps), then the receiver.

First step is to work out the minimum signal level at the input to the preamp, where wenet signals are barely decodable. 

Approach here is:
- Set a gain setting on the RTLSDR.
- Add attenuation until decoding starts to break (e.g. we start to see breakup in images)
- Add gain on the RTLSDR (this will decrease the system noise figure)

Ended up at maximum RTLSDR gain, which will be best noise figure (approx 6 dB NF for the RTLSDR itself, < 1 dB for the preamp).

Once decode threshold is reached, stop transmitter, but leave it in carrier mode, and measure carrier level on spectrum analyzer.

### UART Mode

Resultant MDS level for UART mode (115200 baud) with 50 dB manual gain: -114.8 dBm

Enabled AGC on RTLSDR... decoding again. MDS now -116.5 dBm
Suggests that enabling the AGC switches in some additional gain, which improves the system noise figure a little. Will continue testing with AGC enabled.

### I2S Mode
Note this uses a deviation of baudrate//2
MDS with AGC Enabled: Approx -116.6 dBm dBm
Expected approx 0.8 dB improvement, but difficult to quantify these measurements to that precision.