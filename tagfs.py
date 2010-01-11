#!/usr/bin/env python

import os, stat, errno, sys, xattr
import fuse
from fuse import Fuse
from traceback import format_exc

fuse.fuse_python_api = (0, 2)
spool_dir = os.getenv("HOME") + "/video" # hack

def print_(s): print s

# any generic func?
def filelist(dir):
  for node in os.listdir(dir):
    fname = "%s/%s" % ( dir , node )
    if stat.S_ISDIR( os.stat(fname).st_mode ):
      for ret in filelist(fname):
        yield ret
    else:
      yield fname



def xattr_tags(path):
  return map(
      lambda attr: attr.replace("user.", ""),
      xattr.listxattr(path)
  )

# make plugins?
def path_tags(rpath):
  path = fixpath(rpath)

  spath = path.split("/")

  if len(spath) == 1:
    return ('root',)

  return spath[:1]

# make some class?
def fixpath(rpath):
  path = rpath[len(spool_dir)+1:]
  fname = path.split("/")[-1]

  print 'fixpath', rpath
  fullpath[fname] = rpath
  return path


def filltags(rpath):

  path = fixpath(rpath)

  tags = [ 'all' ]
  tags += path_tags(rpath)
  tags += xattr_tags(rpath)

  print path, tags

  for tag in tags:
    if tag not in backend:
      backend[tag] = []

    backend[tag].append( rpath )

backend = { }
fullpath = {} # hack, lol
map(filltags,  filelist( spool_dir ) )
#sys.exit(0)


class MyStat(fuse.Stat):
  def __init__(self):
    self.st_mode = 0
    self.st_ino = 0
    self.st_dev = 0
    self.st_nlink = 0
    self.st_uid = 0
    self.st_gid = 0
    self.st_size = 0
    self.st_atime = 0
    self.st_mtime = 0
    self.st_ctime = 0


def dir():
    st = MyStat()
    st.st_mode = stat.S_IFDIR | 0755
    st.st_nlink = 2

    return st

def link():
    st = MyStat()
    st.st_mode = stat.S_IFLNK | 0644
    st.st_nlink = 1
    st.st_size = 0

    return st

def tagged(tags):

  print 'tagged', tags

  # ugly
  if not tags:
    return []

  # ugly
  if tags[0] not in backend:
    return []

  print tags

  ret = list(backend[tags[0]])

  for tag in tags[1:]:
    for el in list(ret):
      if el not in backend[tag]:
        ret.remove(el)

  return ret


class TagFS(Fuse):


  def getattr(self, path):
    split = path.split('/')
    fname = split[-1]

    print 'getattr', split


    if path == '/' or fname in backend:
      print 'dir', path
      return dir()

    # zsh is buggy crap
    if fname not in fullpath:
      return -errno.ENOENT

    tags, fname = split[1:-1], split[-1]

    print 'link', tags, fname

    for tag in tags:
      if fullpath[fname] not in backend[tag]:
        print 'DAMM!', path, tag, tags
        return -errno.ENOENT
      
    return link()

  def readdir(self, path, offset):
    split = path.split('/')[1:]
    print 'read dir', split , path

    for r in  ('.', '..',):
      yield fuse.Direntry(r)

    if split[-1] != 'all': #HACK!
      for tag in backend.keys():
        if tag in split:
          continue

        yield fuse.Direntry(tag)

    for f in tagged(split):
      fname = f.split("/")[-1]
      yield fuse.Direntry( fname )

    print 'read dir', split 

  def readlink(self, path):
    print 'readlink', path

    path = path.split("/")
    fname = path[-1]

    return fullpath[fname]

  def symlink(self, frm, to):
    print 'symlink', frm, to

    tags = to.split("/")[1:-1] # hmmm
    fname = frm.split("/")[-1]
    full = fullpath[fname]

    for tag in tags:
      if full not in backend[tag]:
        backend[tag].append(full)

      try:
        xa = "user.%s" % tag
        print 'set xa', full, xa

        xattr.setxattr(full, xa, "1")
      except:
        print 'xattr fuckup', format_exc()

    return 0

  def unlink(self, path):
    print 'unlink', path
    tags = path.split("/")[1:-1] # hmmm
    fname = path.split("/")[-1]
    full = fullpath[fname]

    print tags
    xalist = xattr.listxattr(full)

    for tag in tags:
      xa = "user.%s" % tag

      if xa in xalist:
        xattr.removexattr(full, xa)

      if full in backend[tag]:
        backend[tag].remove(full)

    return 0

  def mkdir(self, path, mode):
    print 'mkdir', path, mode
    tag = path[1:]
    print tag

    if tag in backend:
      raise IoError()

    backend[tag] = []

    return 0

  def open(self, path, flags):
    return -errno.ENOENT

  def read(self, path, size, offset):
    return -errno.ENOENT

usage="tag files system"
server = TagFS(version="%prog " + fuse.__version__,
    usage=usage,
    dash_s_do='setsingle',
    fetch_mp=True
)

server.parse(errex=1)
server.main()

