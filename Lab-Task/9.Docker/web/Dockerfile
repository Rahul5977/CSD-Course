# Front end: nginx serves the Lab 7 demo page and proxies the API routes to
# the api service. Build context is ../7.ProximitySearchAPI (for index.html).
FROM nginx:1.27-alpine
# files in templates/ go through envsubst at start-up (API_UPSTREAM)
COPY --from=conf nginx.conf.template /etc/nginx/templates/default.conf.template
COPY app/static/index.html /usr/share/nginx/html/index.html
ENV API_UPSTREAM=api:8000
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/nginx-health || exit 1
