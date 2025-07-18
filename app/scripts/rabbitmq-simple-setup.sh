#!/bin/bash

# Simple RabbitMQ Setup Script for Mining Environment EventBus
# Lightweight version that installs from Ubuntu repository

set -euo pipefail

# Configuration
RABBITMQ_USER="mining-user"
RABBITMQ_PASSWORD="my-custom-password-2024"
RABBITMQ_VHOST="/mining"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "🚀 Starting simple RabbitMQ setup for Mining Environment EventBus"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    log "❌ This script needs root privileges"
    exit 1
fi

# Fix hostname resolution
if ! grep -q "rabbitmq-cluster.mining.local" /etc/hosts; then
    echo "127.0.0.1 rabbitmq-cluster.mining.local" >> /etc/hosts
    log "✅ Added hostname resolution for rabbitmq-cluster.mining.local"
fi

# Remove broken repositories
log "🧹 Cleaning up broken repositories..."
rm -f /etc/apt/sources.list.d/erlang.list /etc/apt/sources.list.d/rabbitmq.list

# Install RabbitMQ
log "📦 Installing RabbitMQ from Ubuntu repository..."
apt-get update -qq
apt-get install -y --no-install-recommends rabbitmq-server

# Start RabbitMQ service
log "🔧 Starting RabbitMQ service..."
service rabbitmq-server start

# Wait for service to be ready
sleep 5

# Check if service is running
if ! service rabbitmq-server status >/dev/null 2>&1; then
    log "❌ RabbitMQ service failed to start"
    exit 1
fi

log "✅ RabbitMQ service started successfully"

# Create user and vhost
log "👤 Creating user and virtual host..."
rabbitmqctl add_user "$RABBITMQ_USER" "$RABBITMQ_PASSWORD" 2>/dev/null || true
rabbitmqctl add_vhost "$RABBITMQ_VHOST" 2>/dev/null || true
rabbitmqctl set_permissions -p "$RABBITMQ_VHOST" "$RABBITMQ_USER" ".*" ".*" ".*" 2>/dev/null || true

# Enable management plugin
log "🔧 Enabling management plugin..."
rabbitmq-plugins enable rabbitmq_management 2>/dev/null || true

# Check final status
log "🔍 Checking final status..."
if service rabbitmq-server status >/dev/null 2>&1; then
    log "✅ RabbitMQ setup completed successfully"
    log "📋 Configuration:"
    log "   - User: $RABBITMQ_USER"
    log "   - Password: $RABBITMQ_PASSWORD"
    log "   - VHost: $RABBITMQ_VHOST"
    log "   - Management UI: http://localhost:15672"
    log "   - AMQP Port: 5672"
else
    log "❌ RabbitMQ setup failed"
    exit 1
fi

log "🎉 Simple RabbitMQ setup completed!"