# D-314: local ingress tool only; no application source or secrets enter this build.
FROM nginx@sha256:84ed8c0dd296c188bfc24ed506f46589e9285fb0b11cf3a04d91d524d3067e11
# The approved proxy configuration loads no dynamic modules and never calls curl.
# Remove those features and their orphan libraries, rather than retaining known
# vulnerable curl/libcurl/brotli packages in an otherwise unchanged nginx 1.30.6.
RUN apk --no-network del curl nginx-module-acme nginx-module-geoip nginx-module-image-filter nginx-module-njs nginx-module-xslt
USER 101:101
