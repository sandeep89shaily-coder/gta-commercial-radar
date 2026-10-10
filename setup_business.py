"""One-time non-destructive import of previous v0.7 data via SQLite online backup."""
from pathlib import Path
import shutil,sqlite3,sys
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
CANDIDATES=('gta_commercial_radar_v07_integrated_candidate','gta_commercial_radar_v07_rollout_corrected','gta_commercial_radar_v07_regional_batch','gta_commercial_radar_v06_easy_setup')

def main():
    if (DATA/'radar.sqlite').exists():
        print('Existing v0.8 radar database found. No copy performed; history protected.')
        return 0
    found=[ROOT.parent/name/'data' for name in CANDIDATES if (ROOT.parent/name/'data'/'radar.sqlite').exists()]
    if not found:
        print('Could not automatically find an existing working v0.7 data folder.')
        print('Keep the old installation. Copy its complete data folder into this release, OR run:')
        print('python business_discovery.py run --data-dir "FULL_PATH_TO_OLD_DATA_FOLDER"')
        return 1
    origin=found[0]
    DATA.mkdir(exist_ok=True)
    temporary=DATA/'radar.sqlite.copying'
    if temporary.exists():
        print('Interrupted prior copy detected. Investigate radar.sqlite.copying first.');return 1
    print('Backing up existing Radar history from:',origin)
    src=sqlite3.connect(str(origin/'radar.sqlite'))
    dst=sqlite3.connect(str(temporary))
    try:
        src.backup(dst)
        if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Database integrity check failed')
    except Exception:
        dst.close();src.close();temporary.unlink(missing_ok=True);raise
    finally:
        try:dst.close();src.close()
        except Exception:pass
    for file in origin.iterdir():
        if file.is_file() and file.name not in ('radar.sqlite','radar.sqlite-wal','radar.sqlite-shm'):
            target=DATA/file.name
            if not target.exists():shutil.copy2(file,target)
    temporary.rename(DATA/'radar.sqlite')
    print('Copy completed. Original database is unchanged.')
    return 0
if __name__=='__main__':raise SystemExit(main())
