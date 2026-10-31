"""Preparation tool only; no project application or Django settings are created.

Run in the approved, pinned Linux Python container. Downloads have no secrets.
The runtime import smoke must run separately without network access.
"""
import argparse
import email
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import urllib.request
import zipfile

DIRECT = ['Django==5.2.18', 'psycopg[binary]==3.3.6', 'django-csp==4.0']


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def prepare(root, lock):
    wheels = root / 'wheels'
    wheels.mkdir(exist_ok=False)  # Never mix an old resolver result with this run.
    subprocess.run([sys.executable, '-m', 'pip', '--isolated', 'download',
                    '--only-binary=:all:', '--index-url', 'https://pypi.org/simple',
                    '--disable-pip-version-check', '--dest', str(wheels), *DIRECT], check=True)
    rows = []
    for wheel in sorted(wheels.glob('*.whl')):
        with zipfile.ZipFile(wheel) as archive:
            info_names = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            if len(info_names) != 1:
                raise ValueError('Ambiguous wheel metadata')
            info = email.message_from_bytes(archive.read(info_names[0]))
        name, version = info['Name'], info['Version']
        digest = hashlib.file_digest(wheel.open('rb'), 'sha256').hexdigest()
        url = f'https://pypi.org/pypi/{name}/{version}/json'
        with urllib.request.urlopen(url, timeout=45) as response:
            data = json.load(response)
        matches = [a for a in data['urls'] if a['filename'] == wheel.name]
        if len(matches) != 1 or matches[0]['digests']['sha256'] != digest or matches[0].get('yanked'):
            raise ValueError('Wheel hash, identity or yanked status rejected')
        row = dict(name=name, version=version, filename=wheel.name, sha256=digest,
                   source=matches[0]['url'], metadataSource=url,
                   licenseExpression=info.get('License-Expression'), license=info.get('License'),
                   vulnerabilities=data.get('vulnerabilities', []))
        rows.append(row)
    save(root / 'artifacts.json', {'python': platform.python_version(), 'pip': metadata.version('pip'),
                                 'direct': DIRECT, 'artifacts': rows})
    if any(row['vulnerabilities'] for row in rows):
        raise RuntimeError('PyPI reports vulnerabilities; inspect saved evidence before installation')
    lock.write_text('# Linux amd64 / CPython 3.14; D-311 / D-312\n' + ''.join(
        f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\n" for r in rows), encoding='utf8')
    save(root / 'python-components.cdx.json', {
        'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
        'components': [dict(type='library', name=r['name'], version=r['version'],
                            purl=f"pkg:pypi/{r['name'].lower().replace('_', '-')}@{r['version']}",
                            hashes=[{'alg': 'SHA-256', 'content': r['sha256']}]) for r in rows]})
    subprocess.run([sys.executable, '-m', 'pip', '--isolated', 'install', '--no-index',
                    '--find-links', str(wheels), '--require-hashes', '--no-compile',
                    '--target', str(root / 'runtime'), '-r', str(lock),
                    '--disable-pip-version-check'], check=True)
    print(json.dumps({'downloadedAndInstalled': len(rows), 'pypiAdvisories': 0}))


def smoke(root, backend):
    # Disposable library-level settings in memory; not a project or application.
    from django.conf import settings
    from django.http import HttpResponse
    from django.test import RequestFactory
    from csp.middleware import CSPMiddleware
    import psycopg
    from psycopg import pq
    settings.configure(SECRET_KEY='synthetic-preflight-only-not-a-project-key', DEBUG=False,
                       ALLOWED_HOSTS=['testserver'],
                       CONTENT_SECURITY_POLICY_REPORT_ONLY={'DIRECTIVES': {
                           'default-src': ["'self'"], 'script-src': ["'self'"],
                           'object-src': ["'none'"], 'base-uri': ["'self'"],
                           'frame-ancestors': ["'none'"], 'form-action': ["'self'"]}})
    response = CSPMiddleware(lambda request: HttpResponse('library smoke'))(RequestFactory().get('/'))
    assert response.status_code == 200
    header = response.headers['Content-Security-Policy-Report-Only']
    assert "default-src 'self'" in header and "object-src 'none'" in header
    assert 'Content-Security-Policy' not in response.headers
    adapter = 'psycopg-c' if backend == 'c' else 'psycopg-binary'
    selected = {'django': '5.2.18', 'django-csp': '4.0', 'psycopg': '3.3.6', adapter: '3.3.6'}
    actual = {name: metadata.version(name) for name in selected}
    assert actual == selected and platform.python_version() == '3.14.10'
    assert pq.__impl__ == backend
    assert pq.version() == (170011 if backend == 'c' else 180006)
    save(root / 'import-smoke.json', dict(python=platform.python_version(), packages=actual,
                                         uid=os.getuid(), libpq=pq.version(),
                                         psycopgImplementation=pq.__impl__, cspHeader=header,
                                         network='none; host-side inspect recorded separately'))
    print('Pinned imports and CSP report-only response: PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'smoke'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--lock', type=Path)
    parser.add_argument('--backend', choices=['c', 'binary'], default='c')
    args = parser.parse_args()
    if args.mode == 'prepare':
        if args.backend != 'binary':
            parser.error('D-315 system-library preparation uses Python.security.Dockerfile; binary replay requires --backend binary')
        prepare(args.root, args.lock)
    else:
        smoke(args.root, args.backend)
