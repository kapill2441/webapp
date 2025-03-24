FROM python:3.10

# Install required packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      sqlite3 \
      ca-certificates \
      wget \
      git && \
    rm -rf /var/lib/apt/lists/*

# Download and install Litestream
RUN wget https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.tar.gz && \
    tar -xzf litestream-v0.3.13-linux-amd64.tar.gz && \
    mv litestream /usr/local/bin/litestream && \
    rm litestream-v0.3.13-linux-amd64.tar.gz

# Create a non-root user and prepare directories
RUN useradd -r -u 1001 -m appuser 

# Create data directory
RUN mkdir -p /instance

# Copy the database file first
COPY ./instance/smart_event_organizer.db /instance/

WORKDIR /app

# Copy requirements and install dependencies first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Ensure correct permissions and setup
RUN chmod +x entrypoint.sh && \
    chown appuser:appuser /instance/smart_event_organizer.db && \
    chmod 644 /instance/smart_event_organizer.db && \
    chown -R appuser:appuser . && \
    chmod 755 /instance

# Switch to non-root user for runtime
USER appuser

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]