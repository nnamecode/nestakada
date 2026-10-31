# D-325 local candidate only; base ID verified by build receipt before build.
FROM nestakada-local/python-runtime:3.14.10-security-20261030
USER 0:0
RUN --network=none --mount=type=bind,source=.,target=/inputs,readonly python -m pip --isolated install --no-index --no-deps --no-cache-dir --find-links=/inputs --require-hashes -r /inputs/requirements.lock && python -m pip check && python /inputs/minimize.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /worker
USER 10002:10001