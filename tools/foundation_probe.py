"""Fixed local foundation observations. Run only inside the actual app container.

Read-only SQL/config/library probes, no HTTP inspector endpoint and no business acts.
Host runner supplies only a fixed view/profile. Secrets never leave this process.
"""
import importlib.metadata as metadata
import inspect
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys

VIEWS = ('foundation-runtime-versions','foundation-settings','foundation-db-roles',
         'foundation-dependencies','foundation-deploy-check','foundation-audit-redaction')

def execute(view, profile):
    if view not in VIEWS or profile not in ('local-http','deployment-audit'):
        raise ValueError('Unsupported fixed probe')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'estakada.settings.' + profile.replace('-','_')
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection, NotSupportedError
    if view == 'foundation-settings':
        names = {'debug':'DEBUG','middleware':'MIDDLEWARE','sslRedirect':'SECURE_SSL_REDIRECT','hstsSeconds':'SECURE_HSTS_SECONDS',
          'secureProxySslHeader':'SECURE_PROXY_SSL_HEADER','useXForwardedHost':'USE_X_FORWARDED_HOST','allowedHosts':'ALLOWED_HOSTS',
          'sessionCookieSecure':'SESSION_COOKIE_SECURE','csrfCookieSecure':'CSRF_COOKIE_SECURE','sessionCookieHttpOnly':'SESSION_COOKIE_HTTPONLY',
          'sessionCookieSameSite':'SESSION_COOKIE_SAMESITE','csrfCookieSameSite':'CSRF_COOKIE_SAMESITE','sessionCookieDomain':'SESSION_COOKIE_DOMAIN',
          'csrfCookieDomain':'CSRF_COOKIE_DOMAIN','sessionCookieName':'SESSION_COOKIE_NAME','csrfCookieName':'CSRF_COOKIE_NAME','secretReferenceId':'SECRET_REFERENCE_ID'}
        data = {key:getattr(settings,name) for key,name in names.items()}
        data.update(profile=profile,templateAutoescape=settings.TEMPLATES[0]['OPTIONS']['autoescape'])
        from django.urls import get_resolver, URLPattern
        def exempt(patterns):
            found=[]
            for p in patterns:
                if isinstance(p,URLPattern):
                    if getattr(p.callback,'csrf_exempt',False):found.append(str(p.pattern))
                else:found += exempt(p.url_patterns)
            return found
        data['csrfExemptApplicationRoutes'] = exempt(get_resolver().url_patterns)
        if profile == 'local-http':
            probes=[]
            for missing,key in [('django-secret-key','ESTAKADA_DJANGO_SECRET_FILE'),('database-password','ESTAKADA_DB_PASSWORD_FILE')]:
                env=os.environ.copy();env[key]='/run/secrets/missing-required-credential'
                proc=subprocess.run([sys.executable,'manage.py','check'],env=env,capture_output=True,text=True,timeout=10)
                captured=proc.stdout+proc.stderr
                probes.append(dict(missing=missing,exitCode=proc.returncode,usedFallback=proc.returncode==0,
                    canaryLeakCount=sum(s in captured for s in [settings.SECRET_KEY,settings.DATABASES['default']['PASSWORD']] if len(s)>=32)))
            data['missingConfigurationProbes']=probes
        return data
    if view == 'foundation-runtime-versions':
        import platform,psycopg
        packages={d.metadata['Name'].lower().replace('_','-'):d.version for d in metadata.distributions()}
        with connection.cursor() as c:c.execute('SHOW server_version_num');version=int(c.fetchone()[0])
        try:
            with connection.cursor() as c:c.execute("SELECT XMLPARSE(DOCUMENT '<probe/>')")
        except NotSupportedError as e:xml_state=getattr(e.__cause__,'sqlstate',None)
        else:xml_state='unexpected-success'
        ssl_pkg=subprocess.check_output(['dpkg-query','-W','-f=${Version}','libssl3t64'],text=True)
        return dict(python=platform.python_version(),implementation=platform.python_implementation(),packages=packages,
            psycopgImplementation=psycopg.pq.__impl__,libpqVersionNum=psycopg.pq.version(),systemOpenSSLPackage=ssl_pkg,
            postgresqlServerVersionNum=version,postgresqlEngine='PostgreSQL',postgresqlXmlProbeSqlstate=xml_state)
    if view == 'foundation-db-roles':
        with connection.cursor() as c:
            c.execute('SELECT current_user,session_user');current,session=c.fetchone()
            c.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='app'");migrator=c.fetchone()[0]
            c.execute('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()');bootstrap=c.fetchone()[0]
            c.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user')
            flags=dict(zip(('superuser','createDb','createRole','replication','bypassRls'),c.fetchone()))
            c.execute("SELECT has_database_privilege(current_user,current_database(),'CREATE'),has_schema_privilege(current_user,'app','CREATE'),pg_has_role(current_user,%s,'MEMBER'),pg_has_role(current_user,%s,'MEMBER'),has_database_privilege(current_user,current_database(),'CONNECT')",[migrator,bootstrap])
            effective=dict(zip(('databaseCreate','schemaCreate','memberOfMigrator','memberOfBootstrap','connect'),c.fetchone()))
            c.execute("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls) AND pg_has_role(current_user,oid,'MEMBER'))")
            effective['memberOfPrivilegedRole']=c.fetchone()[0]
        flags.update(name=current,databaseOwner=current==bootstrap,schemaOwner=current==migrator)
        return dict(currentUser=current,sessionUser=session,runtime=flags,migrator={'name':migrator},bootstrap={'name':bootstrap},effectivePrivileges=effective)
    if view == 'foundation-dependencies':
        import email,hashlib,zipfile
        installed=[{'name':d.metadata['Name'].lower().replace('_','-'),'version':d.version} for d in metadata.distributions()]
        artifacts=[]
        for p in sorted(Path('/wheels').glob('*.whl')):
            with zipfile.ZipFile(p) as z:info=email.message_from_bytes(z.read(next(n for n in z.namelist() if n.endswith('.dist-info/METADATA'))))
            artifacts.append(dict(name=info['Name'].lower().replace('_','-'),version=info['Version'],artifactSha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()))
        return dict(installed=installed,artifacts=artifacts,appDependencyLockSha256=hashlib.file_digest(Path('/app/runtime-requirements.lock').open('rb'),'sha256').hexdigest())
    if view == 'foundation-deploy-check':
        from django.core import checks
        proc=subprocess.run([sys.executable,'manage.py','check','--deploy'],env=os.environ.copy(),capture_output=True,text=True,timeout=15)
        found=checks.run_checks(include_deployment_checks=True)
        return dict(commandRef='DJANGO_CHECK_DEPLOY',profile=profile,exitCode=proc.returncode,silencedSystemChecks=settings.SILENCED_SYSTEM_CHECKS,
            errors=[{'id':m.id} for m in found if m.level>=checks.ERROR],
            warnings=[dict(id=m.id,reasonRef='LOCAL-NO-TLS-HSTS' if m.id=='security.W004' else 'UNASSESSED') for m in found if m.level==checks.WARNING],
            secretLeakCount=sum(s in (proc.stdout+proc.stderr) for s in [settings.SECRET_KEY,settings.DATABASES['default']['PASSWORD']] if len(s)>=32))
    if view == 'foundation-audit-redaction':
        from audit.formatters import SafeJsonFormatter
        fields=['authorization','cookie','password','request-comment','request-phone','secret-key','token']
        canaries=['FOUNDATION-SYNTHETIC-AUTH','FOUNDATION-SYNTHETIC-COOKIE','FOUNDATION-SYNTHETIC-PASSWORD','FOUNDATION-SYNTHETIC-COMMENT','+70000000000','FOUNDATION-SYNTHETIC-SECRET','FOUNDATION-SYNTHETIC-TOKEN']
        payload=dict(zip(fields,canaries));r=logging.LogRecord('estakada.audit',logging.WARNING,'',1,payload,(),None)
        r.__dict__.update(payload);r.event_code='FOUNDATION-LOG-BENIGN'
        return dict(formatterLoadedFromApplication=inspect.getfile(SafeJsonFormatter)=='/app/audit/formatters.py',exercisedFields=fields,
            formattedText=SafeJsonFormatter().format(r))

if __name__=='__main__':
    try:
        result=execute(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else 'local-http')
        print(json.dumps(result,ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'errorClass':type(e).__name__}),file=sys.stderr)
        sys.exit(1)
