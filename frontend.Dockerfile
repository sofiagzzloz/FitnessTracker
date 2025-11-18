FROM nginx:1.27-alpine

# Build argument for cache busting - change this value to force rebuild of static files
ARG CACHE_BUST=1
RUN echo "Cache bust: ${CACHE_BUST}"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY static /usr/share/nginx/html/static
COPY templates /usr/share/nginx/html/

EXPOSE 80