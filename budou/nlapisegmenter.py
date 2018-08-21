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

from .segmenter import Segmenter
from .cachefactory import load_cache
from .chunk import Chunk, ChunkList
import hashlib

DEPENDENT_LABEL = (
    'P', 'SNUM', 'PRT', 'AUX', 'SUFF', 'AUXPASS', 'RDROP', 'NUMBER', 'NUM',
    'PREF')

def memorize(func):
  def wrapper(self, *args, **kwargs):
    use_cache = kwargs.get('use_cache', True)
    if use_cache:
      cache = load_cache(self.cache_filename)
      original_key = ':'.join([
        self.__class__.__name__,
        func.__name__,
        '_'.join([str(a) for a in args]),
        '_'.join([str(w) for w in kwargs.values()])])
      cache_key = hashlib.md5(original_key.encode('utf-8')).hexdigest()
      cached_val = cache.get(cache_key)
      if cached_val:
        return cached_val
    val = func(self, *args, **kwargs)
    if use_cache: cache.set(cache_key, val)
    return val
  return wrapper

class NLAPISegmenter(Segmenter):

  supported_languages = {'ja', 'ko', 'zh', 'zh-TW', 'zh-CN', 'zh-HK'}

  def __init__(self, options={}):

    import google_auth_httplib2
    import googleapiclient.discovery

    if 'debug' in options and options['debug']:
      self.service = None
      return

    self.cache_filename = options.get(
        'cache_filename', '/tmp/budou-cache.pickle')

    scope = ['https://www.googleapis.com/auth/cloud-platform']
    if 'service_account' in options:
      try:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            options['service_account'])
        scoped_credentials = credentials.with_scopes(scope)
      except ImportError:
        print('''Failed to load google.oauth2.service_account module.
              If you are running this script in Google App Engine environment,
              please call `authenticate` method with empty argument to
              authenticate with default credentials.''')

    else:
      import google.auth
      scoped_credentials, project = google.auth.default(scope)
    authed_http = google_auth_httplib2.AuthorizedHttp(scoped_credentials)
    service = googleapiclient.discovery.build(
        'language', 'v1beta2', http=authed_http)
    self.service = service

  def segment(self, input_text, language=None, use_entity=False,
      use_cache=True):
    """Returns a chunk list by using Google Cloud Natural Language API.
    Args:
      input_text: String to parse. (str)
      language: A language code. 'ja' and 'ko' are supported. (str, optional)
      use_entity: Whether to use entities in Natural Language API response.
      (bool, optional)
    Returns:
      A chunk list. (ChunkList)
    """
    if language and not language in self.supported_languages:
      raise ValueError(
          'Language {} is not supported by NLAPI segmenter'.format(language))

    chunks, language = self._get_source_chunks(
        input_text, language=language, use_cache=use_cache)
    if use_entity:
      entities = self._get_entities(
          input_text, language=language, use_cache=use_cache)
      chunks = self._group_chunks_by_entities(chunks, entities)
    chunks.resolve_dependencies()
    return chunks

  def _get_source_chunks(self, input_text, language=None, use_cache=True):
    """Returns a chunk list retrieved from Syntax Analysis results.
    Args:
      input_text: Text to annotate. (str)
      language: Language of the text. 'ja' and 'ko' are supported.
          (str, optional)
    Returns:
      A chunk list. (ChunkList)
    """
    chunks = ChunkList()
    seek = 0
    result = self._get_annotations(
        input_text, language=language, use_cache=use_cache)
    tokens = result['tokens']
    language = result['language']
    for i, token in enumerate(tokens):
      word = token['text']['content']
      begin_offset = token['text']['beginOffset']
      label = token['dependencyEdge']['label']
      pos = token['partOfSpeech']['tag']
      if begin_offset > seek:
        chunks.append(Chunk.space())
        seek = begin_offset
      chunk = Chunk(word, pos, label)
      if chunk.label in DEPENDENT_LABEL:
        # Determining concatenating direction based on syntax dependency.
        chunk.dependency = i < token['dependencyEdge']['headTokenIndex']
      if chunk.is_punct():
        chunk.dependency = chunk.is_open_punct()
      chunks.append(chunk)
      seek += len(word)
    return chunks, language

  def _group_chunks_by_entities(self, chunks, entities):
    """Groups chunks by entities retrieved from NL API Entity Analysis.
    Args:
      chunks: The list of chunks to be processed. (ChunkList)
      entities: List of entities. (list of dict)
    Returns:
      A chunk list. (ChunkList)
    """
    for entity in entities:
      chunks_to_concat = chunks.get_overlaps(
          entity['beginOffset'], len(entity['content']))
      if not chunks_to_concat: continue
      new_chunk_word = u''.join([chunk.word for chunk in chunks_to_concat])
      new_chunk = Chunk(new_chunk_word)
      chunks.swap(chunks_to_concat, new_chunk)
    return chunks

  @memorize
  def _get_annotations(self, text, language='', use_cache=True,
      encoding='UTF32'):
    """Returns the list of annotations from the given text."""
    body = {
        'document': {
            'type': 'PLAIN_TEXT',
            'content': text,
        },
        'features': {
            'extract_syntax': True,
        },
        'encodingType': encoding,
    }
    if language: body['document']['language'] = language

    request = self.service.documents().annotateText(body=body)
    response = request.execute()
    tokens = response.get('tokens', [])
    language = response.get('language')

    return {'tokens': tokens, 'language': language}

  @memorize
  def _get_entities(self, text, language='', use_cache=True, encoding='UTF32'):
    """Returns the list of annotations from the given text."""
    body = {
        'document': {
            'type': 'PLAIN_TEXT',
            'content': text,
        },
        'encodingType': encoding,
    }
    if language: body['document']['language'] = language

    request = self.service.documents().analyzeEntities(body=body)
    response = request.execute()
    result = []
    for entity in response.get('entities', []):
      mentions = entity.get('mentions', [])
      if not mentions: continue
      entity_text = mentions[0]['text']
      offset = entity_text['beginOffset']
      for word in entity_text['content'].split():
        result.append({'content': word, 'beginOffset': offset})
        offset += len(word)
    return result

