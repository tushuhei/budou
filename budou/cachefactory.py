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

"""Budou cache factory class."""
from abc import ABCMeta, abstractmethod
import hashlib
import six
import pickle
import os


def load_cache(filename):
  try:
    return AppEngineMemcache()
  except:
    return PickleCache(filename)


@six.add_metaclass(ABCMeta)
class BudouCache(object):

  @abstractmethod
  def get(self, key):
    pass

  @abstractmethod
  def set(self, key, val):
    pass


class PickleCache(BudouCache):

  def __init__(self, filename):
    self.filename = filename

  def get(self, key):
    if not os.path.exists(self.filename): return None
    with open(self.filename, 'rb') as f:
      try:
        cache_pickle = pickle.load(f)
      except EOFError:
        cache_pickle = {}
      return cache_pickle.get(key, None)

  def set(self, key, val):
    with open(self.filename, 'w+b') as f:
      try:
        cache_pickle = pickle.load(f)
      except EOFError:
        cache_pickle = {}
      cache_pickle[key] = val
      f.seek(0)
      pickle.dump(cache_pickle, f)


class AppEngineMemcache(BudouCache):

  def __init__(self):
    from google.appengine.api import memcache
    self.memcache = memcache

  def get(self, key):
    return self.memcache.get(key, None)

  def set(self, key, value):
    self.memcache.set(key, val)
