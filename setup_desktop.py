"""One-time local setup. Never overwrites existing local collected data."""
import os, sqlite3, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
NAMES=('radar.sqlite','brampton_sources.sqlite','business_discovery.sqlite')
def source_dirs():
 roots=[Path.home()/'Desktop'/'new data',Path.home()/'OneDrive'/'Desktop'/'new data',ROOT.parent,ROOT.parent.parent]
 seen=set(); out=[]
 for base in roots:
  if not base.is_dir(): continue
  for d in base.glob('GTA_RADAR*/data'):
   key=d.resolve()
   if key==DATA.resolve() or key in seen: continue
   seen.add(key); out.append(d)
 return out
def backup_db(src,dst):
 temp=dst.with_name(dst.name+'.setup-incomplete')
 if dst.exists(): return True
 if temp.exists():
  print('Incomplete prior setup file exists:',temp);return False
 try:
  srcdb=sqlite3.connect(f'file:{src.as_posix()}?mode=ro',uri=True)
  try:
   dstdb=sqlite3.connect(str(temp))
   try:
    srcdb.backup(dstdb,pages=1000,sleep=0.15)
    if dstdb.execute('PRAGMA quick_check').fetchone()[0]!='ok': raise RuntimeError('Database integrity check failed')
   finally: dstdb.close()
  finally: srcdb.close()
  temp.replace(dst);return True
 except Exception as ex:
  print('Database copy failed:',ex)
  try:temp.unlink(missing_ok=True)
  except OSError:pass
  return False
def main():
 print('GTA Radar one-time desktop setup. Original folders remain unchanged.')
 DATA.mkdir(exist_ok=True); dirs=source_dirs()
 for name in NAMES:
  dst=DATA/name
  if dst.exists():print('KEEP:',name);continue
  matches=[d/name for d in dirs if (d/name).is_file()]
  if not matches:print('NOT FOUND (skipped):',name);continue
  src=max(matches,key=lambda x:x.stat().st_mtime)
  print('Copying newest',name,'from',src.parent.parent.name)
  if not backup_db(src,dst):return 1
 if not (DATA/'radar.sqlite').is_file():
  print('No existing radar.sqlite found; scheduling skipped.');return 2
 if os.name!='nt':return 0
 launcher=ROOT/'DAILY_RUN.bat'
 if not launcher.is_file():print('Missing DAILY_RUN.bat');return 3
 cmd=['schtasks','/Create','/F','/SC','DAILY','/ST','06:00','/TN','GTA Commercial Radar Daily','/TR','cmd.exe /c ""'+str(launcher)+'""']
 result=subprocess.run(cmd,capture_output=True,text=True)
 if result.returncode:
  print('Scheduling failed:',result.stderr or result.stdout);return 4
 print('SUCCESS: collection scheduled daily 06:00 (when PC is available).')
 print('No GitHub auto-update enabled; future code updates require approval.')
 return 0
if __name__=='__main__':raise SystemExit(main())
