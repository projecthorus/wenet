# -------------------
# The build container
# -------------------
FROM debian:buster-slim AS build

# Install build dependencies.
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libusb-1.0-0-dev \
    pkg-config \
    libatlas-base-dev \
    python3 \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-numpy \
    python3-wheel \
    libairspy-dev libairspyhf-dev libavahi-client-dev libbsd-dev libfftw3-dev libhackrf-dev libiniparser-dev libncurses5-dev libopus-dev librtlsdr-dev libusb-1.0-0-dev libusb-dev portaudio19-dev libasound2-dev uuid-dev rsync && \
  rm -rf /var/lib/apt/lists/*

# Compile and install rtl-sdr.
RUN git clone https://github.com/steve-m/librtlsdr.git /root/librtlsdr && \
  mkdir -p /root/librtlsdr/build && \
  cd /root/librtlsdr/build && \
  cmake -DCMAKE_INSTALL_PREFIX=/root/target/usr/local -Wno-dev ../ && \
  make && \
  make install && \
  rm -rf /root/librtlsdr

# Compile and install ssdv.
RUN git clone https://github.com/fsphil/ssdv.git /root/ssdv && \
  cd /root/ssdv && \
  make && \
  DESTDIR=/root/target make install && \
  rm -rf /root/ssdv

# Compile and install pcmcat and tune from KA9Q-Radio
RUN git clone https://github.com/ka9q/ka9q-radio.git /root/ka9q-radio && \
  cd /root/ka9q-radio && \
  make -f Makefile.linux pcmcat tune && \
  mkdir -p /root/target/usr/local/bin/ && \
  cp pcmcat /root/target/usr/local/bin/ && \
  cp tune /root/target/usr/local/bin/ && \
  rm -rf /root/ka9q-radio

# Install Python packages.
# Removed numpy from this list, using system packages.
# --no-binary numpy
RUN --mount=type=cache,target=/root/.cache/pip pip3 install \
  --user --no-warn-script-location --ignore-installed \
    crcmod \
    flask \
    flask-socketio \
    simple-websocket \
    requests \
    sondehub


# Copy in wenet.
COPY . /root/wenet

# Build the binaries.
WORKDIR /root/wenet/src
RUN make

# -------------------------
# The application container
# -------------------------
FROM debian:buster-slim

EXPOSE 5003/tcp

# Install application dependencies.
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  bc \
  libusb-1.0-0 \
  python3 \
  python3-numpy \
  libbsd0 \
  avahi-utils \
  libnss-mdns \
  tini && \
  rm -rf /var/lib/apt/lists/*

# Allow mDNS resolution
RUN sed -i -e 's/files dns/files mdns4_minimal [NOTFOUND=return] dns/g' /etc/nsswitch.conf

# Copy compiled dependencies from the build container.
COPY --from=build /root/target /
RUN ldconfig

# Copy any additional Python packages from the build container.
COPY --from=build /root/.local /root/.local

# Copy wenet from the build container to /opt.
COPY --from=build /root/wenet/rx/ /opt/wenet/
COPY --from=build /root/wenet/LICENSE.txt /opt/wenet/

# Set the working directory.
WORKDIR /opt/wenet

# Ensure scripts from Python packages are in PATH.
ENV PATH=/root/.local/bin:$PATH

# Use tini as init.
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run start_rx_docker.sh.
CMD ["/opt/wenet/start_rx_docker.sh"]
