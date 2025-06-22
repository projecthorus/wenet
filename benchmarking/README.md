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

