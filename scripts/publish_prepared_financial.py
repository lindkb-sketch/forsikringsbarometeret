#!/usr/bin/env python3
"""Transfer audited finance files from an unlocked validation job to a locked publisher.

Only the short publish job shares the Pages lock with stock updates. Independent
stock and approved broker-commentary commits during PDF import are preserved. Any intervening code or finance change
blocks publishing, rather than overwriting newer observations.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 'prepared-financial'
# Outputs formerly staged by the finance job. Stock quotes are NEVER included.
FILES = (
    'data/live.json',
    'data/financial_audit.json',
    'data/verified_financial_feed.json',
    'data/financial_observations.json',
    'data/geographic_import_status.json',
    'data/quarterly_editorial.json',
    'data/quarterly_insights.json',
    'data/strategic_market.json',
    'data/official_news.json',
    'data/newsweb_notices.json',
    'data/report_candidates.json',
    'data/report_coverage.json',
    'data/prior_year_growth_coverage.json',
    'data/profitability_coverage.json',
    'data/publication_provenance.json',
    'data/investor_readiness.json',
    'data/frende_fremtind_candidates.json',
    'data/frende_skade_reports.json',
    'data/frende_skade_financials.json',
    'data/all_financial_source_evidence.json',
)
REQUIRED = {'data/verified_financial_feed.json', 'data/financial_observations.json',
            'data/financial_audit.json', 'data/live.json'}
ALLOWED_INTERVENING = {'data/stock_prices.json', 'data/broker_commentary.json'}


def git(*args: str, root: Path = ROOT) -> str:
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root: Path = ROOT) -> dict:
    root = Path(root)
    stage = root / STAGE
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    copied = {}
    for rel in FILES:
        source = root / rel
        if not source.is_file():
            if rel in REQUIRED:
                raise ValueError(f'Missing validated financial output: {rel}')
            continue
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied[rel] = sha256(target)
    manifest = {'base_sha': git('rev-parse', 'HEAD', root=root), 'files': copied}
    (stage / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(f'FINANCIAL_PREPARED {len(copied)} files at {manifest["base_sha"][:12]}', flush=True)
    return manifest


def verify_snapshot(root: Path = ROOT) -> dict:
    stage = Path(root) / STAGE
    manifest = json.loads((stage / 'manifest.json').read_text(encoding='utf-8'))
    base = manifest.get('base_sha')
    files = manifest.get('files')
    if not isinstance(base, str) or len(base) != 40 or any(c not in '0123456789abcdef' for c in base):
        raise ValueError('Invalid source commit in financial artifact')
    if not isinstance(files, dict) or not REQUIRED.issubset(files) or any(f not in FILES for f in files):
        raise ValueError('Unrecognized or incomplete financial artifact')
    for rel, expected in files.items():
        if not isinstance(expected, str) or sha256(stage / rel) != expected:
            raise ValueError(f'Financial artifact integrity mismatch: {rel}')
    return manifest


def publish(root: Path = ROOT) -> None:
    root = Path(root)
    manifest = verify_snapshot(root)
    base = manifest['base_sha']
    # GITHUB_SHA belongs to the real workflow checkout, not to temporary
    # Git repositories supplied explicitly by isolated unit tests.
    expected_base = os.environ.get('GITHUB_SHA') if root.resolve() == ROOT.resolve() else None
    if expected_base and base != expected_base:
        raise ValueError('Financial artifact does not match this workflow run')
    git('fetch', '--quiet', 'origin', 'main', root=root)
    current = git('rev-parse', 'origin/main', root=root)
    if git('rev-parse', 'HEAD', root=root) != current:
        raise ValueError('main advanced since publisher checkout; retry with a fresh snapshot')
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', base, current], cwd=root)
    if ancestor.returncode != 0:
        raise ValueError('Validated financial source is not an ancestor of current main')
    changed = set(git('diff', '--name-only', base, current, root=root).splitlines())
    unsafe = changed - ALLOWED_INTERVENING
    if unsafe:
        raise ValueError('main changed outside stock prices during financial validation: ' + ', '.join(sorted(unsafe)))
    if changed:
        print('FINANCIAL_PUBLISH_REBASE stock/broker commentary changes retained', flush=True)
    for rel in manifest['files']:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / STAGE / rel, dest)
    git('add', '--', *manifest['files'].keys(), root=root)
    diff_status = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=root).returncode
    if diff_status == 0:
        print('FINANCIAL_PUBLISH_NOOP generated finance already current', flush=True)
        return
    if diff_status != 1:
        raise ValueError('Unable to inspect staged finance changes')
    git('config', 'user.name', 'github-actions[bot]', root=root)
    git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com', root=root)
    git('commit', '-m', 'Update verified financial feed and report calendar', root=root)
    # A manual commit racing this operation makes push fail safely. Stock
    # publishers cannot race while this job holds the shared Pages lock.
    git('push', 'origin', 'HEAD:main', root=root)
    print('FINANCIAL_PUBLISH_OK generated finance published, stock prices preserved', flush=True)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ('prepare', 'publish'):
        raise SystemExit('Usage: publish_prepared_financial.py prepare|publish')
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        publish()


if __name__ == '__main__':
    main()
