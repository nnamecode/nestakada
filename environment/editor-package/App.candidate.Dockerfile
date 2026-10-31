# Candidate only. Context: work/dev07-package-cache/python after bounded install
# and installed-manifest verification. No package execution occurs in BuildKit.
# This recipe never modifies the foundation lock or independent media worker.
# Coordinator must inspect this existing tag == the exact D-315 ID before build.
FROM nestakada-local/python-runtime:3.14.10-security-20261030
USER 0
COPY --chown=0:0 site-packages/ /usr/local/lib/python3.14/site-packages/
USER 10001:10001
