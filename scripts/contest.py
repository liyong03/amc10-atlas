"""Which contest a script works on. Every script takes it as its first argument (default amc10):
    python3 scripts/merge_labels.py amc8
Data lives in data/<contest>/, the site in docs/ (AMC 10) or docs/amc8/ (AMC 8)."""
import os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
CONTESTS = {
    'amc10': {'name': 'AMC 10', 'wiki': 'AMC_10', 'docs': 'docs', 'first_year': 2000},
    'amc8': {'name': 'AMC 8', 'wiki': 'AMC_8', 'docs': 'docs/amc8', 'first_year': 1999},
}
KEY = next((a for a in sys.argv[1:] if a in CONTESTS), 'amc10')
C = CONTESTS[KEY]


def D(*a):
    """Path inside data/<contest>/."""
    return os.path.join(ROOT, 'data', KEY, *a)


def DOCS(*a):
    """Path inside this contest's site folder."""
    return os.path.join(ROOT, C['docs'], *a)
