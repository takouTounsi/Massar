import os
import sys

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shared.application.startup_classifier import run_persona_tests

if __name__ == '__main__':
    ok = run_persona_tests()
    print('ALL_PASSED=', ok)
