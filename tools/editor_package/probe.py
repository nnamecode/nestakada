"""Candidate-only probes. Not the site's HTML policy, sanitizer, renderer or acceptance suite."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

PINS = {'html5lib':'1.1','tinycss2':'1.5.1','nh3':'0.3.7','six':'1.17.0','webencodings':'0.6.1'}
CASES = ('imports','html5-tree','danger-visible','css-tokens','nh3-positive','nh3-danger',
         'no-fetch','html-byte-boundary','html-node-boundary','css-large','pathological-depth','restricted-upstream-pocs')
TIMEOUT_SECONDS = 10.0
ADDRESS_SPACE_BYTES = 512 * 1024 * 1024


def require(value, code):
    if not value:
        raise AssertionError(code)


def local_name(tag):
    return tag.rsplit('}', 1)[-1].lower() if isinstance(tag, str) else '#comment'


def worker(name):
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_BYTES, ADDRESS_SPACE_BYTES))
    import html5lib
    import tinycss2
    import nh3
    import six
    import webencodings
    from unittest.mock import patch
    versions = {package:importlib.metadata.version(package) for package in PINS}
    for package, expected in PINS.items():
        require(versions[package] == expected, 'CANDIDATE_VERSION_MISMATCH_'+package)
    def parse(value):
        return html5lib.parseFragment(value, treebuilder='etree', namespaceHTMLElements=True)
    def elements(tree, tag):
        return [element for element in tree.iter() if local_name(element.tag) == tag]
    def clean(value):
        return nh3.clean(value, tags={'p','br','h2','strong','em','ul','ol','li','a','table','tbody','tr','td','th'},
                         attributes={'a':{'href','target'}}, url_schemes={'http','https'}, link_rel=None)
    safe = '<h2>Heading</h2><p>Text <strong>Bold</strong> <em>Italic</em> <a href="https://candidate.invalid/reference">link</a></p><ul><li>One</li><li>Two</li></ul><table><tbody><tr><th>A</th><th>B</th></tr><tr><td>10</td><td>20</td></tr></tbody></table>'
    if name == 'imports':
        require(sys.version_info[:2] == (3,14) and sys.implementation.name == 'cpython' and sys.platform == 'linux', 'CPYTHON314_LINUX_REQUIRED')
        return {'python':sys.version.split()[0], 'versions':versions, 'nh3NativeImported':bool(nh3.clean('<p>x</p>'))}
    if name == 'html5-tree':
        tree = parse('<TABLE><TR><TD>A<TD>B</TABLE><p data-note="A&amp;B">tail')
        require(len(elements(tree,'tbody')) == 1 and [node.text for node in elements(tree,'td')] == ['A','B'], 'HTML5_TABLE_TREE')
        require(elements(tree,'p')[0].attrib['data-note'] == 'A&B', 'HTML5_ENTITY_ATTRIBUTE')
        encoded = html5lib.serialize(tree, tree='etree', omit_optional_tags=False, quote_attr_values='always')
        require([node.text for node in elements(parse(encoded),'td')] == ['A','B'], 'HTML5_SERIALIZE_ROUNDTRIP')
        return {'impliedTbody':True,'cells':2,'entityDecoded':True}
    if name == 'danger-visible':
        tree = parse('<p onclick="void 0" style="position:fixed">x</p><a href="jav&#x61;script:void(0)">link</a><script>candidate-canary</script><iframe src="https://candidate.invalid/frame"></iframe><svg><script>svg-canary</script></svg>')
        require(elements(tree,'p')[0].attrib['onclick'] == 'void 0', 'PARSER_HID_EVENT_ATTRIBUTE')
        require(elements(tree,'a')[0].attrib['href'] == 'javascript:void(0)', 'PARSER_HID_DECODED_URL')
        require(len(elements(tree,'script')) == 2 and len(elements(tree,'iframe')) == 1 and len(elements(tree,'svg')) == 1, 'PARSER_HID_DANGEROUS_NODES')
        return {'eventAttributeVisible':True,'decodedJavascriptVisible':True,'scriptNodes':2,'iframeVisible':True,'svgNamespaceVisible':True}
    if name == 'css-tokens':
        values = tinycss2.parse_declaration_list(r'font-\73ize:16px;color:#112233;background-image:u\72l(https://candidate.invalid/css);width:e\78pression(1)', skip_comments=True, skip_whitespace=True)
        declarations = {value.lower_name:value for value in values if value.type == 'declaration'}
        require(set(declarations) == {'font-size','color','background-image','width'}, 'CSS_PROPERTY_DECODING')
        dimension = next(token for token in declarations['font-size'].value if token.type != 'whitespace')
        require(dimension.type == 'dimension' and dimension.value == 16 and dimension.lower_unit == 'px', 'CSS_DIMENSION_TOKEN')
        require(any(token.type == 'url' and token.value == 'https://candidate.invalid/css' for token in declarations['background-image'].value), 'CSS_ESCAPED_URL_TOKEN')
        require(any(token.type == 'function' and token.lower_name == 'expression' for token in declarations['width'].value), 'CSS_ESCAPED_FUNCTION_TOKEN')
        return {'escapedProperty':'font-size','sizePx':16,'dangerousUrlTokenVisible':True,'expressionTokenVisible':True}
    if name == 'nh3-positive':
        cleaned = clean(safe)
        require(clean(cleaned) == cleaned, 'NH3_NOT_IDEMPOTENT_ON_APPROVED_POSITIVE')
        tree = parse(cleaned)
        require(elements(tree,'h2')[0].text == 'Heading' and elements(tree,'strong')[0].text == 'Bold' and len(elements(tree,'li')) == 2, 'NH3_LOST_APPROVED_STRUCTURE')
        require([node.text for node in elements(tree,'td')] == ['10','20'] and elements(tree,'a')[0].attrib['href'] == 'https://candidate.invalid/reference', 'NH3_LOST_TABLE_OR_LINK')
        return {'positiveIdempotent':True,'approvedMeaningPreserved':True,'outputSha256':hashlib.sha256(cleaned.encode()).hexdigest()}
    if name == 'nh3-danger':
        cleaned = clean('<p onclick="void(0)">keep</p><script>secret-script</script><iframe src="https://candidate.invalid/x"></iframe><a href="javascript:void(0)">link</a>')
        tree = parse(cleaned)
        require(not elements(tree,'script') and not elements(tree,'iframe') and 'secret-script' not in cleaned and 'onclick' not in elements(tree,'p')[0].attrib, 'NH3_ACTIVE_MARKUP_REMAINED')
        require('href' not in elements(tree,'a')[0].attrib and elements(tree,'p')[0].text == 'keep', 'NH3_UNSAFE_URL_OR_POSITIVE_LOSS')
        return {'independentCleanerRemovedActiveMaterial':True,'notProductWholeInputRejection':True}
    if name == 'restricted-upstream-pocs':
        # Candidate-only defense in depth. Never enable nh3's affected CSS feature.
        allowed_tags = {'p','strong','em','span','a'}
        allowed_attributes = {'a':{'href','title'}}
        require('svg' not in allowed_tags and all('style' not in names for names in allowed_attributes.values()), 'RESTRICTED_PROFILE_DRIFT')
        def restricted_cleaner(value):
            return nh3.clean(value, tags=allowed_tags, attributes=allowed_attributes,
                             url_schemes={'http','https'}, link_rel=None)
        pocs = json.loads("{\"RUSTSEC-2021-0157\":\"<div style='background:url(\\\"cid:\\\\\\\");EVIL_CSS_HERE;background:url(\\\\\\\"cid:\\\")'>\",\"RUSTSEC-2021-0158\":\"<svg xmlns=\\\"http://www.w3.org/2000/svg\\\">\\n  <a>\\n    <animateMotion attributeName=\\\"href\\\" to=\\\"javascript:alert('SET_XSS')\\\"></animateMotion>\\n    <text y=\\\"30\\\">Click set</text>\\n  </a>\\n</svg>\",\"RUSTSEC-2026-0373\":\"<div style='background:URL(\\\"https://evil.com/ping\\\");'>\"}")
        positive = '<p>HARMLESS TEXT <strong>DATA-42</strong> <a href="#safe">ANCHOR</a></p>'
        results = []
        for advisory, poc in pocs.items():
            cleaned = restricted_cleaner(poc+positive)
            tree = parse(cleaned)
            require(not any(local_name(node.tag) in ['svg','animatemotion','animatetransform','animatecolor','script','style','iframe'] for node in tree.iter()), 'RESTRICTED_ACTIVE_NODE_'+advisory)
            require(not any('style' in node.attrib or any(key.lower().startswith('on') for key in node.attrib) for node in tree.iter()), 'RESTRICTED_ACTIVE_ATTRIBUTE_'+advisory)
            lower = cleaned.lower()
            require(not any(value in lower for value in ['javascript:','cid:','https:','http:','url(','evil_css_here','evil.com','tracking']), 'RESTRICTED_URL_OR_TRACKING_'+advisory)
            anchor = [node for node in elements(tree,'a') if node.text == 'ANCHOR']
            require(len(anchor) == 1 and anchor[0].attrib.get('href') == '#safe' and elements(tree,'strong')[0].text == 'DATA-42' and 'HARMLESS TEXT' in cleaned, 'RESTRICTED_POSITIVE_LOST_'+advisory)
            require(restricted_cleaner(cleaned) == cleaned, 'RESTRICTED_NOT_IDEMPOTENT_'+advisory)
            results.append({'advisory':advisory,'upstreamPocSha256':hashlib.sha256(poc.encode()).hexdigest(),
                            'outputSha256':hashlib.sha256(cleaned.encode()).hexdigest(),
                            'harmlessTextDataAnchorPreserved':True,'activeStyleSvgUrlAbsent':True})
        return {'styleAllowed':False,'svgAllowed':False,'filterStylePropertiesUsed':False,
                'regressions':results,'notProductSourceRejection':True}
    if name == 'no-fetch':
        attempts = []
        def blocked(*args, **kwargs):
            attempts.append(True)
            raise AssertionError('PYTHON_NETWORK_ATTEMPT')
        with patch('socket.socket.connect', blocked), patch('socket.socket.connect_ex', blocked), patch('socket.getaddrinfo', blocked), patch('urllib.request.urlopen', blocked):
            parse('<p style="background:url(https://candidate.invalid/remote)">x</p><img src="https://candidate.invalid/image">')
            tinycss2.parse_declaration_list('background:url(https://candidate.invalid/style)')
            clean('<p><a href="https://candidate.invalid/reference">safe</a><img src="https://candidate.invalid/image"></p>')
        require(not attempts, 'PARSER_FETCH_ATTEMPTS')
        return {'interceptedPythonNetworkAttempts':len(attempts),'nativeSyscallsNotInstrumented':True}
    if name == 'html-byte-boundary':
        prefix, suffix = '<!--', '--><p>ok</p>'
        value = prefix+'x'*(1024*1024-len(prefix)-len(suffix))+suffix
        require(len(value.encode()) == 1024*1024, 'BYTE_CORPUS_SIZE')
        tree = parse(value)
        require(elements(tree,'p')[0].text == 'ok', 'BYTE_BOUNDARY_POSITIVE_LOSS')
        return {'inputBytes':len(value.encode()),'nodes':sum(1 for _ in tree.iter()),'textMeaning':'ok'}
    if name == 'html-node-boundary':
        value = '<div>'+'<span>x</span>'*19998+'</div>'
        tree = parse(value)
        require(len(elements(tree,'span')) == 19998, 'NODE_BOUNDARY_POSITIVE_LOSS')
        return {'inputBytes':len(value.encode()),'elementsExcludingFragment':19999}
    if name == 'css-large':
        value = 'color:#112233;'*20000
        parsed = tinycss2.parse_declaration_list(value, skip_comments=True, skip_whitespace=True)
        require(sum(1 for declaration in parsed if declaration.type == 'declaration') == 20000, 'CSS_CORPUS_LOSS')
        return {'inputBytes':len(value.encode()),'declarations':20000,'notProductApprovedDeclarationCount':True}
    if name == 'pathological-depth':
        value = '<b>'*5000+'x'+'</b>'*5000
        tree = parse(value)
        return {'inputBytes':len(value.encode()),'nodes':sum(1 for _ in tree.iter()),'overProductDepth':True}
    raise ValueError('UNKNOWN_CLOSED_CASE')


def child(name):
    started = time.monotonic()
    try:
        facts = worker(name)
        value = {'status':'completed', 'facts':facts}
    except MemoryError:
        value = {'status':'controlled-memory-refusal'}
    except BaseException as exc:
        value = {'status':'error', 'errorClass':type(exc).__name__,
                 'code':str(exc) if str(exc).replace('_','').replace('-','').isalnum() and len(str(exc)) < 120 else 'CANDIDATE_PROBE_ERROR'}
    value['workerElapsedSeconds'] = round(time.monotonic()-started,6)
    print(json.dumps(value))
    return 0 if value['status'] == 'completed' else 2


def supervise(name):
    require(hasattr(os, 'wait4'), 'LINUX_WAIT4_REQUIRED')
    started = time.monotonic()
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--case', name],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    status = usage = None
    timed_out = False
    while True:
        finished, status, usage = os.wait4(process.pid, os.WNOHANG)
        if finished:
            break
        if time.monotonic()-started > TIMEOUT_SECONDS:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            until = time.monotonic()+0.5
            while time.monotonic() < until:
                finished, status, usage = os.wait4(process.pid, os.WNOHANG)
                if finished:
                    break
                time.sleep(0.01)
            if not finished:
                os.killpg(process.pid, signal.SIGKILL)
                _, status, usage = os.wait4(process.pid, 0)
            break
        time.sleep(0.01)
    process.returncode = os.waitstatus_to_exitcode(status)
    stdout, stderr = process.communicate(timeout=1)
    require(len(stdout) <= 16384 and len(stderr) <= 16384, 'CHILD_DIAGNOSTIC_BOUND')
    if timed_out:
        body = {'status':'controlled-timeout'}
    else:
        try:
            body = json.loads(stdout)
        except (ValueError, UnicodeError):
            body = {'status':'child-exit-without-json'}
    return {'case':name, **body, 'supervisorElapsedSeconds':round(time.monotonic()-started,6),
            'peakRssKiB':int(usage.ru_maxrss), 'exitCode':process.returncode,
            'qaTimeoutSeconds':TIMEOUT_SECONDS,'qaAddressSpaceBytes':ADDRESS_SPACE_BYTES}


REPORTS = []
class CandidateTests(unittest.TestCase):
    def run_case(self, name, allow_refusal=False):
        row = supervise(name)
        REPORTS.append(row)
        allowed = {'completed','controlled-timeout','controlled-memory-refusal'} if allow_refusal else {'completed'}
        self.assertIn(row['status'], allowed)
        self.assertGreater(row['peakRssKiB'], 0)
    def test_001_imports(self):self.run_case('imports')
    def test_002_html5_tree(self):self.run_case('html5-tree')
    def test_003_danger_visible(self):self.run_case('danger-visible')
    def test_004_css_tokens(self):self.run_case('css-tokens')
    def test_005_nh3_positive(self):self.run_case('nh3-positive')
    def test_006_nh3_danger(self):self.run_case('nh3-danger')
    def test_007_no_fetch(self):self.run_case('no-fetch')
    def test_008_html_bytes(self):self.run_case('html-byte-boundary')
    def test_009_html_nodes(self):self.run_case('html-node-boundary')
    def test_010_css_large(self):self.run_case('css-large')
    def test_011_pathological_depth(self):self.run_case('pathological-depth', allow_refusal=True)
    def test_012_restricted_upstream_pocs(self):self.run_case('restricted-upstream-pocs')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--case' and sys.argv[2] in CASES:
        return child(sys.argv[2])
    require(len(sys.argv) == 1, 'NO_UNREVIEWED_ARGUMENTS')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CandidateTests)
    result = unittest.TestResult()
    result.failfast = True
    suite.run(result)
    report = {'scope':'candidate-packages-only','status':'PASS' if result.wasSuccessful() else 'FAIL',
              'testsRun':result.testsRun,'failures':[case.id() for case, _ in result.failures],
              'errors':[case.id() for case, _ in result.errors],'cases':REPORTS,
              'boundedProductParserProven':False,'productSanitizerOrAuthorizationTested':False}
    print(json.dumps(report))
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(main())
