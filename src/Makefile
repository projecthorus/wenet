# Build fsk_demod and drs232_ldpc

CC=gcc
CFLAGS= -O3 -Wall

all: fsk_demod drs232_ldpc wenet_ldpc
	@cp fsk_demod ../rx/
	@cp drs232_ldpc ../rx/
	@cp wenet_ldpc ../rx/
	@echo "Binaries copied to ../rx/"

fsk_demod: fsk_demod.o fsk.o kiss_fft.o
	@gcc  -o fsk_demod fsk_demod.o fsk.o kiss_fft.o -lm
	@echo "Built fsk_demod."

drs232_ldpc: drs232_ldpc.o mpdecode_core.o phi0.o
	@gcc -o drs232_ldpc drs232_ldpc.o mpdecode_core.o phi0.o -lm
	@echo "Built drs232_ldpc"

wenet_ldpc: wenet_ldpc.o mpdecode_core.o phi0.o
	@gcc -o wenet_ldpc wenet_ldpc.o mpdecode_core.o phi0.o -lm
	@echo "Built wenet_ldpc"

.c.o:	$(CC)  $(CFLAGS) -c $< -o $@

clean:
	rm -f fsk_demod drs232_ldpc wenet_ldpc *.o 
