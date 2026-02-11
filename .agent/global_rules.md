# Global Infrastructure Rules

These rules apply to all services within the DataSyncSA consolidated instance.

## 🐳 Docker Standards
- Use `docker-compose.yml` in the root for orchestration.
- Container names should follow the pattern `datasync-[service-name]`.
- Always verify network connectivity within the `datasync-network`.

## 🌐 Nginx Proxy Manager (NPM)
- All web services must be proxied through NPM.
- Do not expose ports directly to the host unless necessary for debugging.
- Configuration for proxy hosts should be documented in the corresponding service `specs.md`.

## 📁 Persistence & Volumes
- All persistent data must reside in `/srv/datasyncsa/volumes/[service-name]`.
- Do not use relative paths for volumes in `docker-compose.yml`; use absolute paths or mapped volume names.

## 📝 Logging
- Standardize logs to be accessible via `docker logs`.
- Critical services should mirror logs to `/srv/datasyncsa/volumes/logs/[service-name]`.
