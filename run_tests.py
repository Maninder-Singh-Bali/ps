"""Run this checkout's tests, including with an isolated Windows Python runtime."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
if __name__=='__main__':
    import products
    if Path(products.__file__).resolve().parent!=ROOT:
        raise RuntimeError('Refusing to test a different checkout.')
    print('Testing checkout:',ROOT,flush=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=sys.argv[1] if len(sys.argv)>1 else 'test_*.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
