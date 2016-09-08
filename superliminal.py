#!/usr/bin/env python
import os, sys, site

base_path = os.path.dirname(os.path.realpath(__file__))
libs_dir = os.path.join(base_path, 'libs')
sys.path.insert(1, libs_dir)
site.addsitedir(libs_dir)

import superliminal.app

if __name__ == '__main__':
    superliminal.app.run(sys.argv[1:])
