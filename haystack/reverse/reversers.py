#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Loic Jaquemet loic.jaquemet+python@gmail.com
#

__author__ = "Loic Jaquemet loic.jaquemet+python@gmail.com"

import argparse
import logging
import numpy
import os
import pickle
import shelve
import sys
import time

from haystack.config import Config
from haystack.utils import Dummy
from haystack import memory_dumper

import structure
import fieldtypes
import utils

log = logging.getLogger('reversers')


class ReverserContext():
  #dummy
  def __init__(self, mappings, heap):
    self.mappings = mappings
    # meta
    self.dumpname = mappings.name
    self.heap = heap
    self._init()
    return
    
  def _init(self):
    self.heapPathname= self.heap.pathname
    self.base = self.heap.start
    self.size = len(self.heap)
    # content
    self.structures = { } 
    self.structures_addresses = numpy.array([],int)
    self.lastReversedStructureAddr = self.base # save our last state

    self.pointersMeta = Dummy()
    self.typesMeta = Dummy()
    
    self.resolved = False # True if all fields have been checked
    self.pointerResolved = False # True if all pointer fields have been checked

    self.parsed = set()
    return
  
  @classmethod
  def cacheLoad(cls, mappings):
    print mappings.name
    dumpname = os.path.normpath(mappings.name)
    context_cache = Config.getCacheFilename(Config.CACHE_CONTEXT, dumpname)
    log.info('\t [-] cacheLoad my context')
    return pickle.load(file(context_cache,'r'))
    #if not os.access(context_cache,os.F_OK):
    #  raise IOError('file not found') 
    #d = shelve.open(context_cache)
    #me = d['context']
    #d.close()
    #return me
    
  
  def save(self):
    # we only need dumpfilename to reload mappings, addresses to reload cached structures
    context_cache = Config.getCacheFilename(Config.CACHE_CONTEXT, self.dumpname)
    pickle.dump(self, file(context_cache,'w'))
    #d = shelve.open(context_cache)
    #d['context'] = self
    #d.close()
  
  def __getstate__(self):
    d = self.__dict__.copy()
    del d['mappings']
    del d['heap']
    del d['structures']
    del d['structures_addresses']
    #d['dumpname'] = os.path.normpath(self.dumpname )
    #d['heapPathname']= self.heap.pathname
    #d['structures_addresses'] = self.structures_addresses
    #d['lastReversedStructureAddr'] = self.lastReversedStructureAddr
    return d

  def __setstate__(self, d):
    self.__dict__ = d
    self.mappings = memory_dumper.load( file(self.dumpname), lazy=True)  
    self.heap = self.mappings.getMmap(d['heapPathname'])
    self.structures = { } 
    self.structures_addresses = numpy.array([],int)
    #self._init()
    #self.structures_addresses = d['structures_addresses'] # load from int_array its quicker
    #self.lastReversedStructureAddr = d['lastReversedStructureAddr']
    #load structures from cache
    #self.structures = dict([ (vaddr,s) for vaddr,s in structure.cacheLoadAllLazy(self.dumpname,self.structures_addresses)])
    #self.structures = {}
    #self.parsed = d['parsed']

    return
  

''' 
Inherits this class when you are delivering a controller that target structure-based elements and :
  * check consistency between structures,
  * aggregate structures based on a heuristic,
'''
class StructureOrientedReverser():
  '''
    Apply heuristics on context.heap
  '''
  def __init__(self):
    self.cacheFilenames=[]
    #self.cacheDict
  
  ''' Improve the reversing process
  '''
  def reverse(self, ctx, cacheEnabled=True):
    if cacheEnabled:
      ctx,skip = self._getCache(ctx)
    try:
      if skip:
        log.info('[+] skipping %s - cached results'%(str(self)))
      else:
        # call the heuristic
        self._reverse(ctx)
    finally:
      if cacheEnabled:
        self._putCache(ctx)
    return ctx
  
  ''' Subclass implementation of the reversing process '''
  def _reverse(self, ctx):
    raise NotImplementedError

  def _getCache(self, ctx):
    ''' define cache read on your input/output data '''
    # you should check timestamp against cache
    if str(self) in ctx.parsed :
      print 'getcache',str(self),'True'
      return ctx, True
    print 'getcache',str(self),'False'
    return ctx, False

  def _putCache(self, ctx):
    ''' define cache write on your output data '''
    t0 = time.time()
    log.info('\t[-] please wait while I am saving our %d structs'%(len(ctx.structures)))
    # save context with cache
    ctx.save()
    tl = time.time()
    # dump all structures
    for i,s in enumerate(ctx.structures.values()):
      s.save()
      if time.time()-tl > 30: #i>0 and i%10000 == 0:
        tl = time.time()
        log.info('\t\t - %2.2f secondes to go '%( (len(ctx.structures)-i)*((tl-t0)/i) ) )
    # save mem2py headers file
    save_headers(ctx)
    tf = time.time()
    log.info('\t[.] saved in %2.2f secs'%(tf-t0))
    return 
  
  def __str__(self):
    return '<%s>'%(self.__class__.__name__)
  
'''
  Looks at pointers values to build basic structures boundaries.
'''
class PointerReverser(StructureOrientedReverser):



  ''' 
  slice the mapping in several structures delimited per pointer-boundaries
  
  '''
  def _reverse(self, context):
    log.info('[+] Reversing pointers in %s'%(context.heap))
    
    # TODO move that in context
    if len(context.structures_addresses) == 0:
      ptr_values, ptr_offsets, aligned_ptr, not_aligned_ptr = utils.getHeapPointers(context.dumpname, context.mappings)
      context.structures_addresses = aligned_ptr
    else:
      aligned_ptr = context.structures_addresses

    # make structure lengths from interval between pointers
    lengths = self.makeLengths(context.heap, aligned_ptr)
    
    # this is the list of build anon struct. it will grow towards aligned_ptr...
    # tis is the optimised key list of structCache
    #context.structures_addresses = numpy.array([],int)
    log.info('[+] Fetching cached structures list')
    context.structures = dict([ (vaddr,s) for vaddr,s in structure.cacheLoadAllLazy(context) ])
    log.info('[+] Fetched %d cached structures from disk'%( len(context.structures) ))
    ## we really should be lazyloading structs..
    t0 = time.time()
    tl = t0
    loaded = 0
    fromcache = len(context.structures)
    todo = set(aligned_ptr) - set(context.structures.keys())
    # build structs from pointers boundaries. and creates pointer fields if possible.
    log.info('[+] Adding new raw structures from pointers boundaries')
    for i, ptr_value in enumerate(todo):
      #if ptr_value not in caches:
      loaded+=1
      size = lengths[i]
      # save the ref/struct type
      context.structures[ ptr_value ] = structure.makeStructure(context, ptr_value, size)
      context.structures_addresses = numpy.append(context.structures_addresses, ptr_value)
      context.structures[ ptr_value ].save()
      #else:
      #  #log.info('loaded %x from cache'%(ptr_value))
      #  fromcache+=1
      #  pass
      if time.time()-tl > 30: #i>0 and i%10000 == 0:
        save_headers(context)
        tl = time.time()
        log.info('%2.2f secondes to go (b:%d/c:%d)'%( (len(todo)-i)*((tl-t0)/i), loaded, fromcache ) )
    log.info('[+] Extracted %d structures in %2.2f (b:%d/c:%d)'%(loaded+ fromcache, time.time()-t0),loaded, fromcache )
    
    context.parsed.add(str(self))
    return



  def makeLengths(self, heap, aligned):
    lengths=[(aligned[i+1]-aligned[i]) for i in range(len(aligned)-1)]    
    lengths.append(heap.end-aligned[-1]) # add tail
    return lengths




class FieldReverser(StructureOrientedReverser):
  def _reverse(self, context):

    log.info('[+] FieldReverser: decoding fields')
    t0 = time.time()
    tl = t0
    done = 0
    print context.structures
    for ptr_value,anon in context.structures.items():
      anon.decodeFields()
      print anon.toString()
      done+=1
      if time.time()-tl > 30: #i>0 and i%10000 == 0:
        tl = time.time()
        log.info('%2.2f secondes to go '%( (len(aligned_ptr)-done)*((tl-t0)/done) ) )
    
    log.info('[+] FieldReverser: finished %d structures in %2.2f'%(done, time.time()-t0) )
    context.parsed.add(str(self))
    return


def save_headers(context):
  ''' structs_addrs is sorted '''
  fout = file(Config.getCacheFilename(Config.CACHE_GENERATED_PY_HEADERS_VALUES, context.dumpname),'w')
  towrite = []
  for vaddr,anon in context.structures.items():
    towrite.append(anon.toString())
    if len(towrite) >= 10000:
      fout.write('\n'.join(towrite) )
      towrite = []
  fout.write('\n'.join(towrite) )
  fout.close()
  return

def search(opts):
  #
  mappings = memory_dumper.load( opts.dumpfile, lazy=True)  
  try:
    try:
      context = ReverserContext.cacheLoad(mappings)
    except IOError,e:
      context = ReverserContext(mappings, mappings.getHeap())  
    ptrRev = PointerReverser()
    context = ptrRev.reverse(context)
    # we have enriched context
    fr = FieldReverser()
    context = fr.reverse(context)
    ##libRev = KnowStructReverser('libQt')
    ##context = libRev.reverse(context)
    # we have more enriched context
    # etc
  except KeyboardInterrupt,e:
    #except IOError,e:
    log.warning(e)
    log.info('[+] %d structs extracted'%(  len(context.structures)) )
    raise e
    pass
  pass
  
def argparser():
  rootparser = argparse.ArgumentParser(prog='haystack-reversers', description='Do a iterative pointer search to find structure.')
  rootparser.add_argument('--debug', action='store_true', help='Debug mode on.')
  rootparser.add_argument('dumpfile', type=argparse.FileType('rb'), action='store', help='Source memory dump by haystack.')
  rootparser.set_defaults(func=search)  
  return rootparser

def main(argv):
  parser = argparser()
  opts = parser.parse_args(argv)

  level=logging.INFO
  if opts.debug :
    level=logging.DEBUG
  #ad16c58
  flog = os.path.sep.join([Config.cacheDir,'log'])
  logging.basicConfig(level=level, filename=flog, filemode='w')
  
  #logging.getLogger('haystack').setLevel(logging.INFO)
  #logging.getLogger('dumper').setLevel(logging.INFO)
  #logging.getLogger('structure').setLevel(logging.INFO)
  #logging.getLogger('field').setLevel(logging.INFO)
  #logging.getLogger('progressive').setLevel(logging.INFO)
  logging.getLogger('reversers').addHandler(logging.StreamHandler(stream=sys.stdout))

  log.info('[+] output log to %s'% flog)

  opts.func(opts)


if __name__ == '__main__':
  main(sys.argv[1:])