#!/usr/bin/env python
import os, sys, site

base_path = os.path.dirname(os.path.realpath(__file__))
site.addsitedir(os.path.join(base_path, 'libs'))

import superliminal.app

if __name__ == '__main__':
    superliminal.app.run(sys.argv[1:])
