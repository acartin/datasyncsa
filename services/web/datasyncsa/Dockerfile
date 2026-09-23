FROM nginx:alpine

COPY index.html /usr/share/nginx/html/index.html
COPY css /usr/share/nginx/html/css
COPY js /usr/share/nginx/html/js
COPY img /usr/share/nginx/html/img

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=4 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1
