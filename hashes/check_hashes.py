#!/usr/bin/env python3
"""Checks this package. Needs only Python 3. Run from anywhere:  python3 hashes/check_hashes.py

1. Every file listed in SHA256SUMS has the listed SHA-256, and no file is missing or extra.
2. The eight files that the report's Reproducibility table names have the fingerprints (first 16 characters of SHA-256) recorded there.
The exit code is 0 if everything matches, 1 otherwise."""
import hashlib, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

bad = 0
listed = {}
with open(os.path.join(ROOT, 'SHA256SUMS'), encoding='utf-8') as f:
    for line in f:
        line = line.rstrip('\n')
        if not line: continue
        digest, rel = line.split('  ', 1)
        listed[rel] = digest

on_disk = set()
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d != '__pycache__' and d != '.git']
    for name in fn:
        rel = os.path.relpath(os.path.join(dp, name), ROOT).replace(os.sep, '/')
        if rel != 'SHA256SUMS': on_disk.add(rel)

for rel in sorted(listed):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        print('MISSING', rel); bad += 1
    elif sha(path) != listed[rel]:
        print('CHANGED', rel); bad += 1
for rel in sorted(on_disk - set(listed)):
    print('EXTRA  ', rel); bad += 1
print('SHA256SUMS: %d files listed, %d problems' % (len(listed), bad))

# fingerprints named in the report's Reproducibility table (first 16 hex characters)
named = [
    ('guide/SILEX-0-GRAMMAR.md', 'fd8640fcec49787e'),
    ('protocol/ANALYSIS_PLAN.md', '25e27eeac34a1f4a'),
    ('tools/aggregate.py', '0c2ec37a4cfee7b6'),
    ('protocol/JUDGING_PROCEDURE.md', 'bf56e21fe4f0a6b4'),
    ('tools/score_f.py', 'fe01189f2c43d6d4'),
    ('tools/make_strict_copy_f.py', '4c2da5a40c99c415'),
    ('tools/phrase_judge_f.py', '7fff8c2c82adef89'),
    ('tools/fill_scoring_xlsx.py', 'dfdc0e6f79592b2a'),
]
bad2 = 0
for rel, want in named:
    path = os.path.join(ROOT, rel)
    got = sha(path)[:16] if os.path.exists(path) else 'missing'
    ok = got == want
    bad2 += 0 if ok else 1
    print('%-4s %-34s %s%s' % ('OK' if ok else 'FAIL', rel, got, '' if ok else '  (report says %s)' % want))
print('report fingerprints: %d of %d match' % (len(named) - bad2, len(named)))
sys.exit(1 if (bad or bad2) else 0)
