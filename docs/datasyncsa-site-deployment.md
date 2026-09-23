# DataSyncSA Brand Site Deployment

This document covers only the static brand site located at:

```text
services/web/datasyncsa
```

It does not deploy the repository's databases, ETL, Dagster, Market Watch,
Redis, Portainer or admin services.

## Production topology

```text
datasyncsa.com / www.datasyncsa.com
  -> Cloudflare
  -> tunnel prd-web-01
  -> Docker network web-ingress
  -> datasyncsa-site:80
```

The production VM is `prd-web-01` at `192.168.10.33`. The site has no host
port and receives traffic only through the shared Docker network used by
`cloudflared`.

## Build and publication

The site is plain HTML, CSS, JavaScript and images. Its Dockerfile uses Nginx
and copies only the static site files.

The workflow is:

```text
.github/workflows/publish-datasyncsa-site.yml
```

A push to `main` that changes the site or its workflow publishes:

```text
ghcr.io/acartin/datasyncsa-site:main
ghcr.io/acartin/datasyncsa-site:sha-{full commit SHA}
```

## Normal deployment

1. Change the site in a development branch.
2. Commit and push the change.
3. Merge it into `main`.
4. Wait for `Publish DataSyncSA site image` to finish successfully in GitHub
   Actions.
5. From `ds-dev`, run:

```bash
ssh prd-web-01 'cd /opt/web/datasyncsa && ./deploy.sh'
```

The script pulls `main`, waits for the container health check, verifies the
public domain and prints the final container status.

## Rollback

Use an image tag from a previously successful workflow:

```bash
ssh prd-web-01 \
  'cd /opt/web/datasyncsa && ./deploy.sh sha-{full commit SHA}'
```

Production downloads images from GHCR. It does not clone this repository or
build the site on the server.

## Production files

Repository sources:

```text
ops/production/datasyncsa-site.compose.yml
ops/production/deploy-datasyncsa-site.sh
```

Installed paths on `prd-web-01`:

```text
/opt/web/datasyncsa/compose.yml
/opt/web/datasyncsa/deploy.sh
```

## Cloudflare routes

After the container is running, configure both published application routes in
the `prd-web-01` tunnel:

```text
datasyncsa.com      -> http://datasyncsa-site:80
www.datasyncsa.com  -> http://datasyncsa-site:80
```

The public DNS records must be proxied through Cloudflare and target the
Cloudflare Tunnel rather than an old origin IP.
