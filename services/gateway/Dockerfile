# API gateway: nginx. The config template is filled in from DEV_* env vars at start.
FROM nginx:1.27-alpine

# Only substitute our own variables, never nginx's ($host, $request_id, ...).
ENV NGINX_ENVSUBST_FILTER=^DEV_

RUN rm /etc/nginx/conf.d/default.conf
COPY templates/ /etc/nginx/templates/
COPY snippets/ /etc/nginx/snippets/

EXPOSE 8000
HEALTHCHECK --interval=5s --retries=20 CMD wget -qO- http://127.0.0.1:8000/health || exit 1
