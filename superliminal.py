#!/usr/bin/env python
import os
import sys

base_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(base_path, 'libs'))

import superliminal.app

if __name__ == '__main__':
    superliminal.app.run(sys.argv[1:])
