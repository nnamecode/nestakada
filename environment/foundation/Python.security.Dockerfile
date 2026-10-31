# D-315: local foundation tool image, no website code or credentials.
FROM python@sha256:ec6a14df5b63e3fbb3498e3240f7f640c230f9dca67683d23265db3866697f2d AS builder
WORKDIR /inputs
COPY . /inputs
RUN --network=none sha256sum -c inputs.sha256 \
    && echo '29c568426ad61c1b702c7d73505c43ca2c9fc5d97a8431d8d9049e731e319ff8  psycopg_c-3.3.6.tar.gz' | sha256sum -c - \
    && DEBIAN_FRONTEND=noninteractive dpkg --force-confdef --force-confold -i /inputs/builder-debs/*.deb \
    && test -z "$(dpkg --audit)" \
    && python -m pip --isolated install --no-index --find-links /inputs/build-wheels --require-hashes -r /inputs/build-wheels/requirements.lock
ENV SOURCE_DATE_EPOCH=1793318400
RUN --network=none export DEB_BUILD_MAINT_OPTIONS=hardening=+all \
    && export CFLAGS="$(dpkg-buildflags --get CFLAGS)" \
    && export CPPFLAGS="$(dpkg-buildflags --get CPPFLAGS)" \
    && export LDFLAGS="$(dpkg-buildflags --get LDFLAGS)" \
    && mkdir -p /out \
    && python -c 'import json,os;open("/out/build-flags.json","w").write(json.dumps({k:os.environ[k] for k in ["CFLAGS","CPPFLAGS","LDFLAGS"]},indent=2))' \
    && python -m pip --isolated wheel --no-index --no-deps --no-build-isolation --wheel-dir /out /inputs/psycopg_c-3.3.6.tar.gz

FROM python@sha256:ec6a14df5b63e3fbb3498e3240f7f640c230f9dca67683d23265db3866697f2d
RUN --network=none --mount=type=bind,source=.,target=/inputs,readonly \
    cd /inputs && sha256sum -c inputs.sha256 \
    && DEBIAN_FRONTEND=noninteractive dpkg --force-confdef --force-confold -i /inputs/runtime-debs/*.deb \
    && test -z "$(dpkg --audit)"
COPY runtime-wheels /wheels
COPY --from=builder /out/ /wheels/
# The six upstream wheels have the separately verified runtime lock. The C wheel
# is an output of the pinned source/compiler stage, not an upstream binary wheel.
RUN --network=none python -m pip --isolated install --no-index --find-links /wheels --require-hashes -r /wheels/requirements.lock \
    && python -m pip --isolated install --no-index --no-deps /wheels/psycopg_c-3.3.6-*.whl \
    && python -m pip check
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PSYCOPG_IMPL=c
USER 10001:10001
