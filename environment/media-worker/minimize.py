"""Drop unused native modules and only their unique private libraries in worker."""
import hashlib,json,pathlib,re,subprocess
root=pathlib.Path('/usr/local/lib/python3.14/site-packages')
pil=root/'PIL'; libs=root/'pillow.libs'
extensions=sorted(pil.glob('*.so'))
keep=[p for p in extensions if p.name.startswith(('_imaging.','_webp.'))]
if len(keep)!=2:raise RuntimeError('Unexpected core extension inventory')
required=set()
for path in keep:
    output=subprocess.run(['ldd',str(path)],check=True,capture_output=True,text=True).stdout
    if 'not found' in output:raise RuntimeError('Core native dependency missing')
    for match in re.findall(r'=> (/[^\s]+)',output):
        dep=pathlib.Path(match).resolve()
        if dep.is_relative_to(libs):required.add(dep)
removed=[]
for path in extensions+sorted(libs.iterdir()):
    if path in keep or path.resolve() in required:continue
    if not path.is_file() or path.is_symlink():raise RuntimeError('Unexpected optional native file')
    removed.append({'path':str(path.relative_to(root)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    path.unlink()
for path in keep:
    output=subprocess.run(['ldd',str(path)],check=True,capture_output=True,text=True).stdout
    if 'not found' in output:raise RuntimeError('Minimal core native dependency missing')
report={'purpose':'D-325 worker only, no font/AVIF/CMS/Tk/math/morph APIs','source_wheel_sha256':'e91c2b1cbeae768c98752e67e717e283d68dae45717b41f2d91eaee648e37b7d','retained_extensions':[str(p.relative_to(root)) for p in keep],'retained_private_libraries':sorted(str(p.relative_to(root)) for p in required),'removed':removed}
pathlib.Path('/usr/local/share/estakada-media-minimization.json').write_text(json.dumps(report,indent=2))