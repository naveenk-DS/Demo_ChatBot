# AWS EC2 Production Deployment Guide for EstateAI

This guide provides step-by-step instructions for deploying the refactored **EstateAI** application to an Amazon EC2 instance with Bedrock and S3 integration.

---

## 1. AWS Architecture Overview

- **Compute:** Amazon EC2 instance (Ubuntu 22.04 / 24.04 LTS, recommended `t3.medium` or `t3.large`).
- **AI / LLM Orchestration:** Amazon Bedrock (Anthropic Claude 3.5 Sonnet / Haiku & Amazon Titan Embeddings v2).
- **Document & Catalog Storage:** Amazon S3 (Brochures, CSV, Excel, and JSON catalog files).
- **Vector Search:** Local FAISS persistent on EC2 instance EBS volume (`data/faiss_index/`).
- **Reverse Proxy & Web Server:** Nginx (Serving built React frontend & reverse-proxying `/api/` to FastAPI Uvicorn).
- **IAM Security:** EC2 Instance Profile with IAM Role (zero hardcoded AWS credentials in code or `.env`).

---

## 2. Prerequisites & AWS Configuration

### Step 2.1: Enable Amazon Bedrock Model Access
1. In the AWS Management Console, navigate to **Amazon Bedrock** in your target region (e.g., `us-east-1` or `us-west-2`).
2. In the left navigation, click **Model access**.
3. Request / verify access is granted for:
   - `Anthropic: Claude 3.5 Sonnet` / `Claude 3 Haiku`
   - `Amazon: Titan Text Embeddings V2`

### Step 2.2: Create S3 Storage Bucket
1. Go to **Amazon S3** -> **Create bucket**.
2. Name: e.g. `estateai-documents-prod-<unique-id>`.
3. Enable standard server-side encryption (SSE-S3).
4. Create folder prefix: `documents/`.
5. Upload your structured property files and PDF brochures:
   - `chennai_properties_catalog.json`
   - `chennai_premium_listings.csv`
   - `chennai_excel_inventory.xlsx`
   - PDF brochures

### Step 2.3: Create EC2 IAM Role
1. Navigate to **IAM** -> **Roles** -> **Create role**.
2. Select **AWS service** -> **EC2**.
3. Create a policy using `deploy/ec2_bedrock_s3_policy.json`, replacing `YOUR_ESTATEAI_BUCKET_NAME` with your S3 bucket name.
4. Attach this policy to your role, e.g. `EstateAI-EC2-Bedrock-S3-Role`.

---

## 3. EC2 Instance Launch

1. Launch an EC2 instance:
   - **AMI:** Ubuntu Server 22.04 LTS or 24.04 LTS (64-bit x86).
   - **Instance Type:** `t3.medium` (2 vCPU, 4 GiB RAM) recommended.
   - **Storage:** 20 GiB or 30 GiB GP3 EBS volume.
   - **IAM Instance Profile:** Select `EstateAI-EC2-Bedrock-S3-Role`.
   - **Security Group Inbound Rules:**
     - SSH (Port 22) - from your IP.
     - HTTP (Port 80) - `0.0.0.0/0`.
     - HTTPS (Port 443) - `0.0.0.0/0`.

---

## 4. EC2 Instance Setup & Code Deployment

### Step 4.1: SSH into EC2
```bash
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

### Step 4.2: Run Automated Setup Script
```bash
# Clone the repository
git clone <YOUR_OFFICE_REPO_URL> /var/www/estateai
cd /var/www/estateai

# Make setup script executable and run
chmod +x deploy/setup_ec2.sh
./deploy/setup_ec2.sh
```

### Step 4.3: Configure Backend Environment
```bash
cd /var/www/estateai/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure .env
cp .env.example .env
nano .env
```
Ensure `.env` has:
```ini
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
S3_BUCKET_NAME=estateai-documents-prod-<unique-id>
S3_DOCUMENT_PREFIX=documents/
ENABLE_ATHENA=false
ENABLE_GLUE=false
```
*(Notice: No AWS keys needed because the EC2 IAM Instance Profile is used automatically!)*

### Step 4.4: Build Frontend
```bash
cd /var/www/estateai/frontend
npm install
npm run build
```

---

## 5. Configure Nginx and Systemd Service

### Step 5.1: Nginx Configuration
```bash
sudo cp /var/www/estateai/deploy/nginx.conf /etc/nginx/sites-available/estateai
sudo ln -sf /etc/nginx/sites-available/estateai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### Step 5.2: Systemd Service Configuration
```bash
sudo cp /var/www/estateai/deploy/estateai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable estateai
sudo systemctl start estateai
```

### Step 5.3: Verify Running Services
```bash
sudo systemctl status estateai
curl http://localhost:8000/health
```
You should see:
```json
{"status":"ok","provider":"bedrock","s3_connected":true,"verified_properties":11}
```

---

## 6. Alternative: Run via Docker Compose

If you prefer running via Docker on EC2:
```bash
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu
# Log out and log back in
docker compose up -d --build
```

---

## 7. Troubleshooting & Operations

- **Check Backend Logs:**
  `journalctl -u estateai -f -n 50`
- **Check Nginx Access/Error Logs:**
  `tail -f /var/log/nginx/error.log`
- **Re-index Documents / Refresh S3:**
  The server automatically verifies and pulls S3 updates on startup or when uploading via `/api/documents/upload`.

