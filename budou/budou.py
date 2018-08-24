# -*- coding: utf-8 -*-
#
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Budou

Usage:
  budou <source> [--segmenter=<seg>] [--language=<lang>] [--classname=<class>]
  budou -h | --help
  budou -v | --version

Options:
  -h --help                   Show this screen.

  -v --version                Show version.

  --segmenter=<segmenter>     Segmenter to use [default: nlapi].

  --language=<language>       Language the source in.

  --classname=<classname>     Class name for output SPAN tags.
                              Use comma-separated value to specify multiple
                              classes.
"""

from __future__ import print_function

import sys
from docopt import docopt
from .parser import NLAPIParser, MecabParser
from .__version__ import __version__

def main():
  args = docopt(__doc__)
  if args['--version']:
    print(__version__)
    sys.exit()

  result = parse(
      args['<source>'],
      segmenter=args['--segmenter'],
      language=args['--language'],
      classname=args['--classname'])
  print(result['html_code'])
  sys.exit()

def parse(source, segmenter='nlapi', language=None, classname=None,
          options=None):
  parser = get_parser(segmenter, options=options)
  return parser.parse(source, language=language, classname=classname)

def authenticate(json_path=None):
  options = {'service_account': json_path}
  parser = NLAPIParser(options)
  return parser

def get_parser(segmenter, options=None):
  parser = None
  if segmenter == 'nlapi':
    parser = NLAPIParser(options=options)
  elif segmenter == 'mecab':
    parser = MecabParser(options=options)
  return parser

if __name__ == '__main__':
  main()
