# D-315: infrastructure build only, no website code or credentials.
FROM debian@sha256:1e1a22175fbf1b32157ddaf0219e1db4e5401fab2b94ed285add64d18587cd2d AS builder
WORKDIR /inputs
COPY . /inputs
RUN --network=none sha256sum -c inputs.sha256 \
    && dpkg --force-confdef --force-confold -i /inputs/builder-debs/*.deb \
    && test -z "$(dpkg --audit)" \
    && printf 'pgbuild:x:10001:10001:Build user:/tmp:/bin/sh\n' >> /etc/passwd \
    && printf 'pgbuild:x:10001:\n' >> /etc/group \
    && mkdir -p /build /out \
    && tar -xjf /inputs/postgresql-18.6.tar.bz2 -C /build \
    && chown -R 10001:10001 /build /out
USER 10001:10001
WORKDIR /build/postgresql-18.6
ENV SOURCE_DATE_EPOCH=1793318400
RUN --network=none export DEB_BUILD_MAINT_OPTIONS=hardening=+all \
    && eval "$(dpkg-buildflags --export=sh)" \
    && printf '%s\n' "$CFLAGS" "$CPPFLAGS" "$LDFLAGS" > /build/security-buildflags.txt \
    && ./configure --prefix=/usr/local/pgsql \
      --with-openssl --with-icu --with-lz4 --with-zstd \
      --without-libxml --without-libxslt \
    && make -j2 world-bin \
    && make check \
    && make install-world-bin DESTDIR=/out

FROM postgres@sha256:f4b419e350fd98d4a8429603295208976dea4c8fb8326d818d346d3e29f1db6f AS official_entrypoint

FROM debian@sha256:1e1a22175fbf1b32157ddaf0219e1db4e5401fab2b94ed285add64d18587cd2d
RUN --network=none --mount=type=bind,source=.,target=/inputs,readonly \
    cd /inputs && sha256sum -c inputs.sha256 \
    && dpkg --force-confdef --force-confold -i /inputs/runtime-debs/*.deb \
    && test -z "$(dpkg --audit)" \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8 \
    && groupadd -g 999 postgres \
    && useradd -u 999 -g postgres -d /var/lib/postgresql -s /bin/bash postgres \
    && mkdir -p /var/lib/postgresql /var/run/postgresql /docker-entrypoint-initdb.d \
    && chown postgres:postgres /var/lib/postgresql /var/run/postgresql \
    && chmod 3775 /var/run/postgresql
COPY --from=builder /out/usr/local/pgsql /usr/local/pgsql
COPY --from=builder /build/security-buildflags.txt /usr/local/share/postgresql-build-evidence/buildflags.txt
COPY --from=official_entrypoint /usr/local/bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENV PATH=/usr/local/pgsql/bin:$PATH LANG=en_US.utf8 PG_MAJOR=18 PG_VERSION=18.6 PGDATA=/var/lib/postgresql/18/docker
VOLUME /var/lib/postgresql
EXPOSE 5432
STOPSIGNAL SIGINT
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
