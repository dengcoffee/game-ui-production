"""Install a new user-scoped skill without overwriting an existing installation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import os

SOURCE = Path(__file__).resolve().parents[1]/'skill/game-ui-production'
parser = argparse.ArgumentParser()
parser.add_argument('--destination', type=Path, default=Path.home()/'.agents/skills/game-ui-production')
parser.add_argument('--update',action='store_true')
parser.add_argument('--snapshot-limit',type=int,default=2)
parser.add_argument('--restore',type=Path)
args = parser.parse_args()
destination=args.destination.resolve()
if args.restore:
    recovery=args.restore.resolve()
    allowed=(destination.parent.parent/'skill-backups'/destination.name).resolve()
    if not recovery.is_relative_to(allowed) or recovery.parent!=allowed or not (recovery/'SKILL.md').is_file():
        parser.error('Restore must name this installation\'s recoverable snapshot')
    recovered_inventory={p.relative_to(recovery).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in recovery.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if hashlib.sha256(json.dumps(recovered_inventory,sort_keys=True).encode()).hexdigest()!=recovery.name:
        parser.error('Recovery snapshot changed')
    SOURCE=recovery
stage=destination.with_name(destination.name+'-installing')
if stage.exists():parser.error('Pending installation stage exists')
backup=None
if destination.exists():
    if not args.update:parser.error('Destination exists; use --update to preserve a recoverable snapshot')
    if not (destination/'SKILL.md').is_file():parser.error('Destination is not a skill folder')
    inventory={p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in destination.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    identity=hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()
    source_inventory={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in SOURCE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if inventory==source_inventory:
        print(json.dumps({'installed':str(destination),'verified':True,'already_current':True}))
        raise SystemExit(0)
    snapshots=destination.parent.parent/'skill-backups'/destination.name
    if snapshots.exists() and len(list(snapshots.iterdir()))>=args.snapshot_limit:
        parser.error('Snapshot budget exhausted; review backups before updating, none automatically deleted')
    backup=snapshots/identity
    if backup.exists():parser.error('Recovery snapshot already exists')
shutil.copytree(SOURCE, stage, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
for path in SOURCE.rglob('*'):
    if path.is_file() and '__pycache__' not in path.parts:
        target = stage/path.relative_to(SOURCE)
        assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(target.read_bytes()).digest()
if backup:
    backup.parent.mkdir(parents=True,exist_ok=True)
    os.replace(destination,backup)
try:os.replace(stage,destination)
except OSError:
    if backup:os.replace(backup,destination)
    raise
print(json.dumps({'installed': str(destination), 'verified': True,'backup':str(backup) if backup else None,'restored_from':str(args.restore) if args.restore else None}))
