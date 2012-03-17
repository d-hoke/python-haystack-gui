#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
""" Win 7 heap structure - from LGPL metasm"""

__author__ = "Loic Jaquemet"
__copyright__ = "Copyright (C) 2012 Loic Jaquemet"
__license__ = "GPL"
__maintainer__ = "Loic Jaquemet"
__email__ = "loic.jaquemet+python@gmail.com"
__status__ = "Production"


''' insure ctypes basic types are subverted '''
from haystack import model
from haystack.config import Config

from haystack.model import is_valid_address,is_valid_address_value,getaddress,array2bytes,bytes2array
from haystack.model import LoadableMembers,RangeValue,NotNull,CString

from haystack.reverse.win32 import win7heap_generated as gen

import ctypes
import struct
import logging, sys

log=logging.getLogger('win7heap')

# ============== Internal type defs ==============

################ START copy generated classes ##########################

# copy generated classes (gen.*) to this module as wrapper
model.copyGeneratedClasses(gen, sys.modules[__name__])

# register all classes (gen.*, locally defines, and local duplicates) to haystack
# create plain old python object from ctypes.Structure's, to picke them
model.registerModule(sys.modules[__name__])

################ END   copy generated classes ##########################





############# Start expectedValues and methods overrides #################

## fix partial declaration
_HEAP_LOCK._fields_ = [
  ('voidme', ctypes.c_ubyte),
  ]

## make a match

_HEAP_SEGMENT.expectedValued = {
  'SegmentSignature':[0xffeeffee],
}
_HEAP_SEGMENT._listHead_ = [
  ('UCRSegmentList', _HEAP_SEGMENT),
  ]

_HEAP_SEGMENT._listMember_ = ['SegmentListEntry']



_HEAP.expectedValues = {
  'Signature':[0xeeffeeff],
}

# Setup list decorators
_HEAP_UCR_DESCRIPTOR._listMember_ = ['ListEntry']
_HEAP_UCR_DESCRIPTOR._listHead_ = [
  ('SegmentEntry', _HEAP_SEGMENT),
  ]

########## _HEAP
def _LIST_ENTRY_loadMembers(self, mappings, maxDepth):
  return True

_LIST_ENTRY.loadMembers = _LIST_ENTRY_loadMembers



########## _HEAP

def _HEAP_loadMembers(self, mappings, maxDepth):
  ''' '''
  part1 = loadListOfType(self, 'SegmentList', mappings, 
                    _HEAP_SEGMENT, 'SegmentListEntry', maxDepth )
  if not LoadableMembers.loadMembers(self, mappings, maxDepth):
    return False

  loadListPart2(self, 'SegmentList', part1)
  
  return True

#_HEAP.loadMembers = _HEAP_loadMembers

########## _HEAP_SEGMENT

def _HEAP_SEGMENT_loadMembers(self, mappings, maxDepth):
  ''' '''
  part1 = loadListOfType(self, 'UCRSegmentList', mappings,
                    _HEAP_UCR_DESCRIPTOR, 'ListEntry', maxDepth )
  if not LoadableMembers.loadMembers(self, mappings, maxDepth):
    return False
  loadListPart2(self, 'UCRSegmentList', part1)
  return True

#_HEAP_SEGMENT.loadMembers = _HEAP_SEGMENT_loadMembers

def _HEAP_SEGMENT_loadMembers(self, mappings, maxDepth):
  ''' '''
  part1 = loadListOfType(self, 'UCRSegmentList', mappings,
                    _HEAP_UCR_DESCRIPTOR, 'ListEntry', maxDepth )
  if not LoadableMembers.loadMembers(self, mappings, maxDepth):
    return False
  loadListPart2(self, 'UCRSegmentList', part1)
  return True

#_HEAP_SEGMENT.loadMembers = _HEAP_SEGMENT_loadMembers



###############
def _HEAP_UCR_DESCRIPTOR_loadMembers(self, mappings, maxDepth):

  part1 = loadListEntries(self, 'ListEntry', mappings, maxDepth )
  #segment1 = loadListOfType(self, 'SegmentEntry', mappings, 
  #                    _HEAP_SEGMENT, 'SegmentListEntry', maxDepth )
  
  if not LoadableMembers.loadMembers(self, mappings, maxDepth):
    return False

  loadListPart2(self, 'ListEntry', part1)
  #loadListPart2(self, 'SegmentEntry', segment1)
  
  # load segment list
  ## ? loadListEntries(self, 'SegmentEntry', mappings,  _HEAP_SEGMENT, maxDepth-1 )

  return True

    
#_HEAP_UCR_DESCRIPTOR.loadMembers = _HEAP_UCR_DESCRIPTOR_loadMembers

