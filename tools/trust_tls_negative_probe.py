"""TN15: bounded synthetic TLS fixture; no Django, database or real credentials."""
import base64
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HEAD = {'incarnation': '00000000-0000-4000-8000-000000000017',
        'generation': '13', 'writerEpoch': '2', 'mode': 'ACTIVE', 'digest': '1' * 64}
ROOT = Path('/tmp/tn15')


def ensure(value, code):
    if not value:
        raise RuntimeError(code)


def openssl(*args):
    r = subprocess.run(['openssl', *args], capture_output=True, timeout=15)
    ensure(r.returncode == 0, 'TN_OPENSSL_FAILED')
    return r.stdout


def generate():
    ROOT.mkdir(mode=0o700)
    (ROOT / 'index').write_text('')
    (ROOT / 'serial').write_text('1000\n')
    (ROOT / 'config').write_text('''[ca]
default_ca=authority
[authority]
database=/tmp/tn15/index
serial=/tmp/tn15/serial
new_certs_dir=/tmp/tn15
certificate=/tmp/tn15/ca.pem
private_key=/tmp/tn15/ca.key
default_md=sha256
policy=names
[names]
commonName=supplied
[server]
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:trust-ingress
[wrong]
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:wrong.invalid
''')
    for name in ('ca', 'other'):
        openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
                '-days', '30', '-subj', '/CN=TN15-' + name,
                '-addext', 'basicConstraints=critical,CA:TRUE',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign',
                '-keyout', str(ROOT / (name + '.key')), '-out', str(ROOT / (name + '.pem')))
    for name, extension, end in [('valid', 'server', '20350101000000Z'),
                                  ('wrong', 'wrong', '20350101000000Z'),
                                  ('expired', 'server', '20210101000000Z')]:
        openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-sha256',
                '-subj', '/CN=' + name, '-keyout', str(ROOT / (name + '.key')),
                '-out', str(ROOT / (name + '.csr')))
        openssl('ca', '-batch', '-notext', '-config', str(ROOT / 'config'),
                '-extensions', extension, '-startdate', '20200101000000Z', '-enddate', end,
                '-in', str(ROOT / (name + '.csr')), '-out', str(ROOT / (name + '.pem')))
    openssl('verify', '-x509_strict', '-CAfile', str(ROOT / 'ca.pem'), str(ROOT / 'valid.pem'))
    names = ['ca.pem', 'other.pem'] + [n + ext for n in ('valid', 'wrong', 'expired') for ext in ('.pem', '.key')]
    print(json.dumps({'files': {n: base64.b64encode((ROOT / n).read_bytes()).decode() for n in names}}))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/v1/head':
            self.send_error(404)
            return
        raw = json.dumps({'head': HEAD}, separators=(',', ':')).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


def load_consumer():
    spec = importlib.util.spec_from_file_location('tn15_consumer', '/probe/consumer.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def direct(ca, hostname='trust-ingress', version=None):
    context = ssl.create_default_context(cafile='/fixtures/' + ca)
    if version is not None:
        context.minimum_version = context.maximum_version = version
    with socket.create_connection(('trust-ingress', 8443), timeout=3) as raw:
        with context.wrap_socket(raw, server_hostname=hostname) as tls:
            return tls.version()


def verify_error(ca, expected, hostname='trust-ingress'):
    try:
        direct(ca, hostname)
    except ssl.SSLCertVerificationError as error:
        ensure(error.verify_code == expected, 'TN_WRONG_VERIFY_REASON')
        return {'verifyCode': error.verify_code, 'rejected': True}
    raise RuntimeError('TN_BAD_CERT_ACCEPTED')


def worker(ca, accepted):
    c = load_consumer()
    reader = c.HTTPSReader('/fixtures/' + ca, 'synthetic-reader', 'a' * 64)
    try:
        value = reader('/v1/head', 6)
    except c.SnapshotRejected as error:
        ensure(not accepted and error.code == 'SNAPSHOT_TRANSPORT_REJECTED', 'TN_WORKER_WRONG_REJECTION')
        return {'rejected': True, 'code': error.code}
    ensure(accepted and value == {'head': HEAD}, 'TN_WORKER_BAD_POSITIVE')
    return {'accepted': True, 'headMatchesSyntheticFixture': True}


def downgrade(version):
    # MemoryBIO records actual generated ClientHello and actual server records.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.set_ciphers('ALL:@SECLEVEL=0')
    context.minimum_version = context.maximum_version = version
    incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
    engine = context.wrap_bio(incoming, outgoing, server_hostname='trust-ingress')
    try:
        engine.do_handshake()
    except ssl.SSLWantReadError:
        pass
    hello = outgoing.read()
    ensure(len(hello) >= 11 and hello[0] == 22 and hello[5] == 1,
           'TN_NO_CLIENT_HELLO')
    expected = b'\x03\x01' if version == ssl.TLSVersion.TLSv1 else b'\x03\x02'
    ensure(hello[9:11] == expected, 'TN_WRONG_CLIENT_VERSION')
    with socket.create_connection(('trust-ingress', 8443), timeout=3) as raw:
        raw.sendall(hello)
        received = b''
        while len(received) < 7:
            block = raw.recv(7 - len(received))
            ensure(block, 'TN_NO_SERVER_ALERT')
            received += block
    ensure(received[0] == 21 and received[3:5] == b'\x00\x02'
           and received[5:] == b'\x02\x46', 'TN_NO_PROTOCOL_VERSION_ALERT')
    return {'clientHelloBytes': len(hello), 'clientHelloSha256': hashlib.sha256(hello).hexdigest(),
            'clientHelloVersionHex': expected.hex(), 'serverAlertHex': received.hex(),
            'serverAlertDescription': 70, 'rejectedByServer': True}


def probe(kind):
    if kind == 'valid':
        return {'id': 'TN15-001', 'tls12': direct('ca.pem', version=ssl.TLSVersion.TLSv1_2),
                'tls13': direct('ca.pem', version=ssl.TLSVersion.TLSv1_3),
                'worker': worker('ca.pem', True)}
    if kind == 'bad-ca':
        return {'id': 'TN15-002', 'direct': verify_error('other.pem', 20),
                'worker': worker('other.pem', False)}
    if kind == 'wrong-name':
        return {'id': 'TN15-003', 'direct': verify_error('ca.pem', 62),
                'correctNameControl': direct('ca.pem', 'wrong.invalid')}
    if kind == 'expired':
        details = ssl._ssl._test_decode_cert('/fixtures/expired.pem')
        ensure(ssl.cert_time_to_seconds(details['notAfter']) < __import__('time').time(), 'TN_FIXTURE_NOT_EXPIRED')
        return {'id': 'TN15-004', 'notAfter': details['notAfter'], 'direct': verify_error('ca.pem', 10)}
    if kind == 'downgrade':
        return {'id': 'TN15-005', 'tls10': downgrade(ssl.TLSVersion.TLSv1),
                'tls11': downgrade(ssl.TLSVersion.TLSv1_1),
                'tls12After': direct('ca.pem', version=ssl.TLSVersion.TLSv1_2)}
    raise RuntimeError('TN_UNKNOWN_CASE')


if __name__ == '__main__':
    try:
        ensure(len(sys.argv) == 2, 'TN_ARGUMENTS')
        if sys.argv[1] == 'serve':
            ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
        elif sys.argv[1] == 'generate':
            generate()
        else:
            result = probe(sys.argv[1])
            print(json.dumps({'status': 'PASS', **result}, sort_keys=True))
    except Exception as error:
        code = str(error) if type(error) is RuntimeError else type(error).__name__
        failure = {'status': 'FAIL', 'code': code if code.replace('_', '').isalnum() else 'TN_FAILED'}
        if isinstance(error, ssl.SSLCertVerificationError):
            failure['verifyCode'] = error.verify_code
        print(json.dumps(failure))
        raise SystemExit(1) from None
