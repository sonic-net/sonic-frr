import imp
import os

TEST_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Backup original function
_load_source = getattr(imp, 'load_source')

# Monkey patch
def load_source(name, pathname):
    if name == 'psuutil':
        return _load_source(name, TEST_DIR + '/plugins/psuutil.py')

# Replace the function with mocked one
imp.load_source = load_source
