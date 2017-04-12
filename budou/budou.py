# -*- coding: utf-8 -*-
#
# Copyright 2017 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Budou, an automatic CJK line break organizer."""

from . import api, cachefactory
import collections
from googleapiclient import discovery
import httplib2
from lxml import etree
from lxml import html
from oauth2client.client import GoogleCredentials
import oauth2client.service_account
import re
import six
import unicodedata

cache = cachefactory.load_cache()

Element = collections.namedtuple('Element', ['text', 'tag', 'source', 'index'])
"""HTML element object.

Attributes:
  text: Text of the element. (unicode)
  tag: Tag name of the element. (string)
  source: HTML source of the element. (string)
  index: Character-wise offset from the top of the sentence. (integer)
"""


class Chunk(object):
  """Chunk object. This represents a unit for word segmentation.

  Attributes:
    word: Surface word of the chunk. (unicode)
    pos: Part of speech. (string)
    label: Label information. (string)
    dependency: Dependency to neighbor words. None for no dependency, True for
    dependency to the following word, and False for the dependency to the
    previous word. (?boolean)
  """
  SPACE_POS = 'SPACE'
  HTML_POS = 'HTML'
  DEPENDENT_LABEL = (
      'P', 'SNUM', 'PRT', 'AUX', 'SUFF', 'MWV', 'AUXPASS', 'AUXVV', 'RDROP',
      'NUMBER', 'NUM')

  def __init__(self, word, pos=None, label=None, dependency=None):
    self.word = word
    self.pos = pos
    self.label = label
    self.dependency = dependency
    self._add_dependency_if_punct()

  def __repr__(self):
    return '<Chunk %s pos: %s, label: %s, dependency: %s>' % (
        self.word, self.pos, self.label, self.dependency)

  @classmethod
  def space(cls):
    """Creates space Chunk."""
    chunk = cls(u' ', cls.SPACE_POS)
    return chunk

  @classmethod
  def html(cls, html_code):
    """Creates HTML Chunk."""
    chunk = cls(html_code, cls.HTML_POS)
    return chunk

  def is_space(self):
    """Checks if this is space Chunk."""
    return self.pos == self.SPACE_POS

  def update_as_html(self, word):
    """Updates the chunk as HTML chunk with the given word."""
    self.word = word
    self.pos = self.HTML_POS

  def update_word(self, word):
    """Updates the word of the chunk."""
    self.word = word

  def serialize(self):
    """Returns serialized chunk data in dictionary."""
    return {
      'word': self.word,
      'pos': self.pos,
      'label': self.label,
      'dependency': self.dependency
    }

  def maybe_add_dependency(self, default_dependency_direction):
    """Adds dependency if any dependency is not assigned yet."""
    if self.dependency == None and self.label in self.DEPENDENT_LABEL:
      self.dependency = default_dependency_direction

  def _add_dependency_if_punct(self):
    """Adds dependency if the chunk is punctuation."""
    if self.pos == 'PUNCT':
      try:
        # Getting unicode category to determine the direction.
        # Concatenates to the following if it belongs to Ps or Pi category.
        # Ps: Punctuation, open (e.g. opening bracket characters)
        # Pi: Punctuation, initial quote (e.g. opening quotation mark)
        # Otherwise, concatenates to the previous word.
        # See also https://en.wikipedia.org/wiki/Unicode_character_property
        category = unicodedata.category(self.word)
        self.dependency = category in ('Ps', 'Pi')
      except:
        pass


class ChunkQueue(object):
  """Chunk queue object.

  Attributes:
    chunks: List of included chunks.
  """
  def __init__(self):
    self.chunks = []

  def add(self, chunk):
    """Adds a chunk to the chunk list."""
    self.chunks.append(chunk)

  def resolve_dependency(self):
    """Resolves chunk dependency by concatenating them."""
    self._concatenate_inner(True)
    self._concatenate_inner(False)

  def _concatenate_inner(self, direction):
    """Concatenates chunks based on each chunk's dependency.

    Args:
      direction: Direction of concatenation process.
    """
    result = []
    tmp_bucket = []
    chunks = self.chunks if direction else self.chunks[::-1]
    for chunk in chunks:
      if chunk.dependency == direction:
        tmp_bucket.append(chunk)
        continue
      tmp_bucket.append(chunk)
      if not direction: tmp_bucket = tmp_bucket[::-1]
      new_word = ''.join([tmp_chunk.word for tmp_chunk in tmp_bucket])
      chunk.update_word(new_word)
      result.append(chunk)
      tmp_bucket = []
    if tmp_bucket: result += tmp_bucket
    self.chunks = result if direction else result[::-1]

  def get_overlaps(self, offset, length):
    """Returns chunks overlapped with the given range.

    Args:
      offset: Begin offset of the range. (int)
      length: Length of the range. (int)

    Returns:
      List of Chunk.
    """
    # In case entity's offset points to a space just before the entity.
    if ''.join([chunk.word for chunk in self.chunks])[offset] == ' ':
      offset += 1
    index = 0
    result = []
    for chunk in self.chunks:
      if (offset < index + len(chunk.word) and index < offset + length):
        result.append(chunk)
      index += len(chunk.word)
    return result

  def swap(self, old_chunks, new_chunk):
    """Swaps old consecutive chunks with new chunk.

    Args:
      old_chunks: List of consecutive Chunks to be removed.
      new_chunk: Chunk to be inserted.
    """
    indexes = [self.chunks.index(chunk) for chunk in old_chunks]
    del self.chunks[indexes[0]:indexes[-1] + 1]
    self.chunks.insert(indexes[0], new_chunk)


class Budou(object):
  """A parser for CJK line break organizer.

  Attributes:
    service: A Resource object with methods for interacting with the service.
  """
  DEFAULT_CLASS_NAME = 'ww'

  def __init__(self, service):
    self.service = service

  @classmethod
  def authenticate(cls, json_path=None):
    """Authenticates user for Cloud Natural Language API and returns the parser.

    If the credential file path is not given, this tries to generate credentials
    from default settings.

    Args:
      json_path: A file path to a credential JSON file for a Google Cloud
      Project which Cloud Natural Language API is enabled (string, optional).

    Returns:
      Budou module.
    """
    if json_path:
      credentials = (
          oauth2client.service_account.ServiceAccountCredentials
          .from_json_keyfile_name(json_path))
    else:
      credentials = GoogleCredentials.get_application_default()
    scoped_credentials = credentials.create_scoped(
        ['https://www.googleapis.com/auth/cloud-platform'])
    http = httplib2.Http()
    scoped_credentials.authorize(http)
    service = discovery.build('language', 'v1beta1', http=http)
    return cls(service)

  def parse(self, source, attributes=None, use_cache=True, language='',
            use_entity=False, classname=None):
    """Parses input HTML code into word chunks and organized code.

    Args:
      source: HTML code to be processed (unicode).
      attributes: If a dictionary, then a map of name-value pairs for attributes
      of output SPAN tags. If a string, then this is the class name of output
      SPAN tags. If an array, the elements will be joined together as the class
      name of SPAN tags (dictionary|string, optional).
      use_cache: Whether to use cache (boolean, optional).
      language: A language used to parse text (string, optional).
      use_entity: Whether to use entities in Natural Language API response.
      Not that it doubles the number of requests to API, which may result in
      additional costs (boolean, optional).
      classname[deprecated]: A class name of output SPAN tags
      (string, optional).
      **This argument is deprecated. Please use attributes argument instead.**

    Returns:
      A dictionary with the list of word chunks and organized HTML code.
    """
    if use_cache:
      result_value = cache.get(source, language)
      if result_value: return result_value
    source = self._preprocess(source)
    dom = html.fragment_fromstring(source, create_parent='body')
    input_text = dom.text_content()

    if language == 'ko':
      # Korean has spaces between words, so this simply parses words by space
      # and wrap them as chunks.
      queue = self._get_chunks_per_space(input_text)
    else:
      queue = self._get_chunks_with_api(input_text, language, use_entity)
    elements = self._get_elements_list(dom)
    queue = self._migrate_html(queue, elements)
    attributes = self._get_attribute_dict(attributes, classname)
    html_code = self._spanize(queue, attributes)
    result_value = {
        'chunks': [chunk.serialize() for chunk in queue.chunks],
        'html_code': html_code
    }
    if use_cache:
      cache.set(source, language, result_value)
    return result_value

  def _get_chunks_per_space(self, input_text):
    """Returns a list of chunks by separating words by spaces.

    Args:
      input_text: String to parse.

    Returns:
      A list of Chunks.
    """
    queue = ChunkQueue()
    words = input_text.split()
    for i, word in enumerate(words):
      queue.add(Chunk(word))
      if i < len(words) - 1:  # Add no space after the last word.
        queue.add(Chunk.space())
    return queue

  def _get_chunks_with_api(self, input_text, language, use_entity):
    """Returns a list of chunks by using Natural Language API.

    Args:
      input_text: String to parse.
      language: A language used to parse text (string, optional).
      use_entity: Whether to use entities in Natural Language API response
      (boolean, optional).

    Returns:
      A list of Chunks.
    """
    queue = self._get_source_chunks(input_text, language)
    if use_entity:
      entities = api.get_entities(self.service, input_text, language)
      queue = self._group_chunks_by_entities(queue, entities)
    queue.resolve_dependency()
    return queue

  def _get_attribute_dict(self, attributes, classname=None):
    """Returns a dictionary of attribute name-value pairs.

    Args:
      attributes: If a dictionary, then a map of name-value pairs for attributes
      of output SPAN tags. If a string, then this is the class name of output
      SPAN tags (dictionary|string).
      classname: Optional class name (string, optional).

    Returns:
      A dictionary.
    """
    if attributes and isinstance(attributes, six.string_types):
      return {
          'class': attributes
      }
    if not attributes:
      attributes = {}
    if not classname:
      classname = self.DEFAULT_CLASS_NAME
    attributes.setdefault('class', classname)
    return attributes

  def _preprocess(self, source):
    """Removes unnecessary break lines and whitespaces.

    Args:
      source: HTML code to be processed (unicode).

    Returns:
      Preprocessed HTML code (unicode).
    """
    source = source.replace(u'\n', u'').strip()
    source = re.sub(r'<br\s*\/?\s*>', u' ', source, re.I)
    source = re.sub(r'\s\s+', u' ', source)
    return source

  def _get_source_chunks(self, input_text, language=''):
    """Returns the words chunks.

    Args:
      input_text: An input text to annotate (unicode).
      language: A language used to parse text (string).

    Returns:
      A list of word chunk objects (list).
    """
    queue = ChunkQueue()
    sentence_length = 0
    tokens = api.get_annotations(self.service, input_text, language)
    for token in tokens:
      word = token['text']['content']
      begin_offset = token['text']['beginOffset']
      label = token['dependencyEdge']['label']
      pos = token['partOfSpeech']['tag']
      if begin_offset > sentence_length:
        queue.add(Chunk.space())
        sentence_length = begin_offset
      chunk = Chunk(word, pos, label)
      # Determining default concatenating direction based on syntax dependency.
      chunk.maybe_add_dependency(
          tokens.index(token) < token['dependencyEdge']['headTokenIndex'])
      queue.add(chunk)
      sentence_length += len(word)
    return queue

  def _migrate_html(self, queue, elements):
    """Migrates HTML elements to the word chunks by bracketing each element.

    Args:
      queue: The list of word chunks to be processed.
      elements: List of Element.

    Returns:
      A list of processed word chunks.
    """
    for element in elements:
      concat_chunks = queue.get_overlaps(element.index, len(element.text))
      if not concat_chunks: continue
      new_chunk_word = u''.join([chunk.word for chunk in concat_chunks])
      new_chunk_word = new_chunk_word.replace(element.text, element.source)
      new_chunk = Chunk.html(new_chunk_word)
      queue.swap(concat_chunks, new_chunk)
    return queue

  def _group_chunks_by_entities(self, queue, entities):
    """Groups chunks by entities retrieved from NL API.

    Args:
      queue: ChunkQueue.
      entities: List of entities.
    """
    for entity in entities:
      concat_chunks = queue.get_overlaps(
          entity['beginOffset'], len(entity['content']))
      if not concat_chunks: continue
      new_chunk_word = u''.join([chunk.word for chunk in concat_chunks])
      new_chunk = Chunk(new_chunk_word)
      queue.swap(concat_chunks, new_chunk)
    return queue

  def _get_elements_list(self, dom):
    """Digs DOM to the first depth and returns the list of elements.

    Args:
      dom: DOM to access the given HTML source.

    Returns:
      A list of elements.
    """
    elements = []
    index = 0
    if dom.text:
      index += len(dom.text)
    for element in dom:
      text = etree.tostring(
          element, with_tail=False, method='text',
          encoding='utf8').decode('utf8')
      source = etree.tostring(
          element, with_tail=False, encoding='utf8').decode('utf8')
      elements.append(Element(text, element.tag, source, index))
      index += len(text)
      if element.tail: index += len(element.tail)
    return elements

  def _spanize(self, queue, attributes):
    """Returns concatenated HTML code with SPAN tag.

    Args:
      queue: The list of word chunks.
      attributes: If a dictionary, then a map of name-value pairs for attributes
      of output SPAN tags. If a string, then this is the class name of output
      SPAN tags. If an array, the elements will be joined together as the
      class name of SPAN tags.

    Returns:
      The organized HTML code.
    """
    result = []
    for chunk in queue.chunks:
      if chunk.is_space():
        result.append(chunk.word)
      else:
        attribute_str = ' '.join(
            '%s="%s"' % (k, v) for k, v in sorted(attributes.items()))
        result.append('<span %s>%s</span>' % (attribute_str, chunk.word))
    return ''.join(result)
