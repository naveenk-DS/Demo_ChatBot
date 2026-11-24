#!/usr/bin/env bash
# EstateAI Automated EC2 Setup Script (Ubuntu 22.04 / 24.04 LTS)
set -euo pipefail

echo "=========================================================="
echo " Starting EstateAI EC2 Setup"
echo "=========================================================="

# 1. Update OS and install prerequisites
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    build-essential \
    nginx \
    git \
    curl

# 2. Install Node.js 20 LTS for frontend build
if ! command -v node &> /dev/null; then
    echo "Installing Node.js 20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# 3. Setup application directory
APP_DIR="/var/www/estateai"
sudo mkdir -p "$APP_DIR"
sudo chown -R ubuntu:ubuntu "$APP_DIR"

echo "Directory $APP_DIR created and permissions granted."
echo "Clone or copy your project repository into $APP_DIR"

# 4. Instructions printed for operator
echo "=========================================================="
echo " Next Steps to Complete Deployment on EC2:"
echo " 1. cd $APP_DIR/backend && python3.11 -m venv .venv"
echo " 2. source .venv/bin/activate && pip install -r requirements.txt"
echo " 3. cp .env.example .env && nano .env (configure AWS_REGION & S3_BUCKET_NAME)"
echo " 4. cd $APP_DIR/frontend && npm install && npm run build"
echo " 5. sudo cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/estateai"
echo " 6. sudo ln -s /etc/nginx/sites-available/estateai /etc/nginx/sites-enabled/"
echo " 7. sudo rm -f /etc/nginx/sites-enabled/default"
echo " 8. sudo nginx -t && sudo systemctl restart nginx"
echo " 9. sudo cp $APP_DIR/deploy/estateai.service /etc/systemd/system/"
echo " 10. sudo systemctl daemon-reload && sudo systemctl enable --now estateai"
echo "=========================================================="
