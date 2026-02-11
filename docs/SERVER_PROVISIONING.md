# Server Provisioning Guide: DatasyncSA Infrastructure

This guide details the steps to configure a fresh Debian/Ubuntu server (Hetzner VPS or Local Machine) to host the DatasyncSA Docker stack with R2 storage integration.

## 1. Prerequisites
- **OS**: Debian 12 (Bookworm) or Ubuntu 22.04 LTS recommended.
- **User**: A non-root user with sudo privileges (e.g., `acartin`).
- **Cloudflare API**: Access Key ID and Secret Access Key for R2.

## 2. Docker Installation
Install the official Docker Engine and Compose plugin.

```bash
# Update and install dependencies
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable for non-root user
sudo usermod -aG docker $USER
# LOGOUT AND LOGIN AGAIN FOR GROUPS TO UPDATE
```

## 3. Storage Configuration (R2 Mount)
We use `rclone` to mount the Cloudflare R2 bucket as a local file system. This allows legacy applications to interact with cloud storage as if it were a local disk, providing a zero-friction migration path.

### 3.1 Install & Configure Rclone
```bash
sudo apt-get install -y rclone fuse3

# Interactive Configuration
rclone config
# 1. New remote -> Name: "r2-remote" (Un nombre genérico para la conexión)
# 2. Type: "s3"
# 3. Provider: "Cloudflare"
# 4. Access Key ID: <YOUR_R2_ACCESS_KEY>
# 5. Secret Access Key: <YOUR_R2_SECRET_KEY>
# 6. Endpoint: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
# 7. ACL: private
# 8. Finish and verify with: rclone lsd r2-remote:
```

### 3.2 Create Directory & Systemd Service
Create the mount point and the service to auto-mount on boot.

```bash
# Create mount points
sudo mkdir -p /srv/datasyncsa/volumes/r2_storage
sudo chown -R $USER:$USER /srv/datasyncsa/volumes/r2_storage
sudo mkdir -p /srv/datasyncsa/volumes/staging
sudo chown -R $USER:$USER /srv/datasyncsa/volumes/staging

# Create Service File
sudo nano /etc/systemd/system/rclone-mount.service
```

Paste the following configuration. Replace `datasync-dev` with the actual bucket name you want to mount (e.g., `datasync-dev` for Ryzen, `datasync-prod` for Hetzner).

```ini
[Unit]
Description=Rclone Mount for R2 Storage
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
User=acartin
Group=acartin
# NOTA: r2-remote es la conexión, datasync-dev es el bucket
ExecStart=/usr/bin/rclone mount r2-remote:datasync-dev /srv/datasyncsa/volumes/r2_storage \
    --allow-other \
    --vfs-cache-mode full \
    --vfs-cache-max-size 10G \
    --log-file /var/log/rclone-storage.log \
    --log-level INFO
ExecStop=/bin/fusermount -u /srv/datasyncsa/volumes/r2_storage
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3.3 Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rclone-mount.service
# Check status
systemctl status rclone-mount.service
# Verify mount works
ls /srv/datasyncsa/volumes/r2_storage
```

## 4. Application Deployment
Clone the repo (or copy files) to `/srv/datasyncsa`.

```bash
# 1. Copy config
cp .env.example .env
nano .env # Edit secrets like DB_PASSWORD, R2_KEYS

# 2. Deploy Stack
docker compose up -d --build
```
