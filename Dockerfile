FROM zaproxy/zap-stable:latest

USER root

# Install Python and required packages
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    pip3 install --break-system-packages requests && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy scan script and set up directories
COPY zap_scan.py /zap/
WORKDIR /zap
RUN mkdir -p /zap/reports && chmod 777 /zap/reports

# Configure ZAP with API settings
CMD ["zap.sh", "-daemon", "-host", "0.0.0.0", "-port", "8088", \
     "-config", "api.key=zapp1ngk3y", \
     "-config", "api.addrs.addr.name=.*", \
     "-config", "api.addrs.addr.regex=true", \
     "-config", "connection.timeoutInSecs=60"]