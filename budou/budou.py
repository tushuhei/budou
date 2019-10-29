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

"""Budou: an automatic organizer tool for beautiful line breaking in CJK

Usage:
  budou <source> [--segmenter=<seg>] [--language=<lang>] [--classname=<class>] [--inline-style]
  budou -h | --help
  budou -v | --version

Options:
  -h --help                   Show this screen.

  -v --version                Show version.

  --segmenter=<segmenter>     Segmenter to use [default: nlapi].

  --language=<language>       Language the source in.

  --classname=<classname>     Class name for output SPAN tags. Use
                              comma-separated value to specify multiple classes.

  --inline-style              Put display:inline-block in inline style
                              attributes of output SPAN tags.
"""

from __future__ import print_function

import sys
import warnings
from docopt import docopt
from .parser import get_parser
from .__version__ import __version__

AVAILABLE_SEGMENTERS = {'nlapi', 'mecab'}

def main():
  """Budou main method for the command line tool.
  """
  args = docopt(__doc__)
  if args['--version']:
    print(__version__)
    sys.exit()

  result = parse(
      args['<source>'],
      segmenter=args['--segmenter'],
      language=args['--language'],
      classname=args['--classname'],
      inline_style=args['--inline-style'],
      )
  print(result['html_code'])
  sys.exit()

def parse(source, segmenter='nlapi', language=None, max_length=None,
          classname=None, attributes=None, inline_style=False, **kwargs):
  """Parses input source.

  Args:
    source (:obj:`str`): Input source to process.
    segmenter (:obj:`str`, optional): Segmenter to use [default: nlapi].
    language (:obj:`str`, optional): Language code.
    max_length (:obj:`int`, optional): Maximum length of a chunk.
    classname (:obj:`str`, optional): Class name of output SPAN tags.
    attributes (:obj:`dict`, optional): Attributes for output SPAN tags.
    inline_style (:obj:`bool`, optional): Put display:inline-block in inline
                                          style attribute.

  Returns:
    Results in a dict. :code:`chunks` holds a list of chunks
    (:obj:`budou.chunk.ChunkList`) and :code:`html_code` holds the output HTML
    code.
  """
  parser = get_parser(segmenter, **kwargs)
  return parser.parse(
      source, language=language, max_length=max_length, classname=classname,
      attributes=attributes, inline_style=inline_style)

def authenticate(json_path=None):
  """Gets a Natural Language API parser by authenticating the API.

  **This method is deprecated.** Please use :obj:`budou.get_parser` to obtain a
  parser instead.

  Args:
    json_path (:obj:`str`, optional): The file path to the service account's
        credentials.

  Returns:
    Parser. (:obj:`budou.parser.NLAPIParser`)

  """
  msg = ('budou.authentication() is deprecated. '
         'Please use budou.get_parser() to obtain a parser instead.')
  warnings.warn(msg, DeprecationWarning)
  parser = get_parser('nlapi', credentials_path=json_path)
  return parser

if __name__ == '__main__':
  main()
