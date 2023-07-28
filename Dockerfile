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
    python3-wheel && \
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
  tini && \
  rm -rf /var/lib/apt/lists/*

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
