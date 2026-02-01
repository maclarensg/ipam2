# Dockerfile for IPAM2 - Enterprise IP Address Management
FROM python:3.14-slim

# Labels
LABEL maintainer="Gavin Yap <maclarensg@gmail.com>"
LABEL description="Enterprise IP Address Management CLI"
LABEL version="2.0"

# Install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application
WORKDIR /app
COPY ipam2.py ipam2.py
COPY models.py models.py
COPY allocator.py allocator.py
COPY config.yaml config.yaml

# Create volume mount point for database
VOLUME ["/data"]

# Default database path
ENV IPAM_DB="/data/ipam.db"

# Entrypoint
ENTRYPOINT ["python3", "ipam2.py"]

# Default command
CMD ["--help"]
