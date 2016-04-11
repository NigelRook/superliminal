import sys, os, site
base_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(base_path, '..'))
site.addsitedir(os.path.join(base_path, '../libs'))
