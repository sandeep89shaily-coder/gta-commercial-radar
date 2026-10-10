"""Windows interactive first-time setup: DPAPI encrypt DeepSeek key and schedule daily."""
from pathlib import Path
import os,subprocess,sys,getpass
ROOT=Path(__file__).resolve().parent

def main():
    if os.name!='nt':
        print('Daily installation is supported on Windows only.');return 2
    settings=ROOT/'settings';settings.mkdir(exist_ok=True)
    vault=settings/'deepseek_key.dpapi'
    if not vault.exists():
        key=getpass.getpass('Paste your DeepSeek API key (hidden; press Enter to skip AI): ').strip()
        if key:
            # Do not put key in command line; pass via stdin to PowerShell, store encrypted under current Windows user.
            script=("$ErrorActionPreference='Stop';$raw=[Console]::In.ReadLine();$s=ConvertTo-SecureString -String $raw -AsPlainText -Force;"
                    "$s | ConvertFrom-SecureString | Set-Content -LiteralPath '"+str(vault).replace("'","''")+"'")
            r=subprocess.run(['powershell','-NoProfile','-Command',script],input=key+'\n',text=True,capture_output=True)
            if r.returncode:
                print('Could not secure the key. Daily job will run with AI disabled.');return 3
            print('DeepSeek key encrypted for this Windows account.')
        else:print('No key saved: daily collection will continue without AI.')
    task='GTA Commercial Radar Daily'
    bat=ROOT/'DAILY_RUN.bat'
    params=['schtasks','/Create','/F','/SC','DAILY','/ST','06:00','/TN',task,'/TR',f'cmd.exe /c ""{bat}""']
    r=subprocess.run(params,capture_output=True,text=True)
    if r.returncode:
        print('Automatic scheduling was blocked by Windows:',(r.stderr or r.stdout).strip())
        print('Your current installation remains untouched.');return 1
    print('Daily run installed at 6:00 AM local PC time (while your PC is on).')
    print('Daily DeepSeek limit: USD $0.50 maximum reserved; 50 leads maximum.')
    print('The first setup START_RADAR.bat must have completed before daily jobs can run.')
    return 0
if __name__=='__main__':raise SystemExit(main())
