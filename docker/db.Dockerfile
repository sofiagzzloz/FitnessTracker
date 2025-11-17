FROM postgres:16-alpine

ENV POSTGRES_DB=fitness \
    POSTGRES_USER=fitness \
    POSTGRES_PASSWORD=fitness

COPY docker/db-init.sql /docker-entrypoint-initdb.d/init.sql