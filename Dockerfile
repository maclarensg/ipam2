# Dockerfile for IPAM2 - Enterprise IP Address Management
FROM python:3.14-slim

# Labels
LABEL maintainer="Gavin Yap <maclarensg@gmail.com>"
LABEL description="Enterprise IP Address Management CLI - Hierarchical IP allocation"
LABEL version="2.0"
LABEL org.opencontainers.image.source="https://github.com/maclarensg/ipam2"
LABEL org.opencontainers.image.title="ipam2"
LABEL org.opencontainers.image.description="Enterprise IP Address Management CLI with Hierarchical Allocation"

# Install dependencies - use pre-compiled binaries for faster builds
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt

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
