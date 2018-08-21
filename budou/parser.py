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

from abc import ABCMeta, abstractmethod
import six
import re
import html5lib
from xml.etree import ElementTree as ET
from .mecabsegmenter import MecabSegmenter
from .nlapisegmenter import NLAPISegmenter

DEFAULT_CLASS_NAME = 'chunk'

@six.add_metaclass(ABCMeta)
class Parser(object):

  def __init__(self, options=None):
    self.options = options

  def parse(self, source, attributes={}, language=None, max_length=None,
      classname=None):
    attributes = parse_attributes(attributes, classname)
    source = preprocess(source)
    chunks = self.segmenter.segment(source, language)
    html_code = chunks.html_serialize(attributes, max_length=max_length)
    return {
        'chunks': chunks,
        'html_code': html_code,
    }


class NLAPIParser(Parser):

  def __init__(self, options=None):
    super(NLAPIParser, self).__init__(options)
    self.segmenter = NLAPISegmenter()


class MecabParser(Parser):

  def __init__(self, options=None):
    super(MecabParser, self).__init__(options)
    self.segmenter = MecabSegmenter()


def parse_attributes(attributes={}, classname=None):
  attributes.setdefault('class', DEFAULT_CLASS_NAME)
  # If `classname` is specified, it overwrites `class` property in `attributes`.
  if classname: attributes['class'] = classname
  return attributes

def preprocess(source):
  """Removes unnecessary break lines and white spaces.
  Args:
    source: HTML code to be processed. (str)
  Returns:
    Preprocessed HTML code. (str)
  """
  doc = html5lib.parseFragment(source)
  source = ET.tostring(doc, encoding='utf-8', method='text').decode('utf-8')
  source = source.replace(u'\n', u'').strip()
  source = re.sub(r'\s\s+', u' ', source)
  return source
