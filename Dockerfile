FROM python:3.11-slim

# Install OpenVPN and other dependencies
RUN apt-get update && apt-get install -y openvpn procps curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else
COPY . .

# Create a startup script to run VPN and then the App
RUN echo '#!/bin/bash\n\
if [ -f "adityagcp.ovpn" ]; then\n\
    echo "Starting OpenVPN..."\n\
    openvpn --config adityagcp.ovpn --daemon\n\
    sleep 10 # Wait for VPN to establish\n\
fi\n\
echo "Starting Application..."\n\
gunicorn --bind 0.0.0.0:$PORT Adoption_Dashboard:app\n\
' > /app/run.sh && chmod +x /app/run.sh

EXPOSE 8087

CMD ["/app/run.sh"]
