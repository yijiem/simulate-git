import argparse
import collections
import configparser
import hashlib
import os
import re
import sys
import zlib


class GitRepository(object):
    """ A git repository """
    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, '.git')

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception("Not a git repository %s" % path)

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = git_file(self, 'config')
        if cf and os.path.exists(cf):
            self.conf.read(cf)
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception("Unsupported repositoryformatversion %s" %
                                vers)


def git_path(repo, *path):
    """ Compute a path under repo's gitdir """
    return os.path.join(repo.gitdir, *path)


def check_git_dir(repo, *path, mkdir=False):
    """ Check or mkdir *path if absent and if mkdir=True """
    path = git_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception("Not a directory %s" % path)

    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None


def git_file(repo, *path, mkdir=False):
    """ Same as git_path, but create dirname(*path) if absent. For example,
        git_file(r, "refs", "remotes", "origin", "HEAD", mkdir=True) will
        create .git/refs/remotes/origin/ if mkdir=True """
    if check_git_dir(repo, *path[:-1], mkdir=mkdir):
        return git_path(repo, *path)


def repo_default_config():
    config = configparser.ConfigParser()

    config.add_section("core")
    config.set("core", "repositoryformatversion", "0")
    config.set("core", "filemode", "false")
    config.set("core", "bare", "false")
    return config


def repo_create(path):
    """ Create a new repository at path """
    repo = GitRepository(path, force=True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception("%s is not a directory" % repo.worktree)
        if os.listdir(repo.worktree):
            raise Exception("%s is not empty" % repo.worktree)
    else:
        os.makedirs(repo.worktree)

    assert (check_git_dir(repo, "branches", mkdir=True))
    assert (check_git_dir(repo, "objects", mkdir=True))
    assert (check_git_dir(repo, "refs", "tags", mkdir=True))
    assert (check_git_dir(repo, "refs", "heads", mkdir=True))

    # .git/description
    with open(git_file(repo, "description"), "w") as f:
        f.write(
            "Unnamed repository; edit this file 'description' to name the repository.\n"
        )

    # .git/HEAD
    with open(git_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    # .git/config
    with open(git_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo


def repo_search(path=".", required=True):
    path = os.path.realpath(path)
    if os.path.exists(os.path.join(path, ".git")):
        return GitRepository(path)

    parent = os.path.realpath(os.path.join(path, ".."))
    if parent == path:
        # Bottom case
        # os.path.join("/", "..") == "/"
        if required:
            raise Exception("No git repository found")
        else:
            return None

    return repo_search(parent, required)


class GitObject(object):
    repo = None

    def __init__(self, repo, data=None):
        self.repo = repo
        if data != None:
            self.deserialize(data)

    def serialize(self):
        raise Exception("Unimplemented")

    def deserialize(self, data):
        raise Exception("Unimplemented")


class GitBlob(GitObject):
    fmt = b'blob'

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data


def object_read(repo, sha):
    """ Read object sha from git repo. Return a GitObject whose exact type
        depends on the object. """
    # e.g. .git/objects/e6/73d1b7eaa0aa01b5bc2442d570a765bdaae751
    path = git_file(repo, "objects", sha[0:2], sha[2:])
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

    # object file format, <type>\x20<size>\x00<content> e.g.
    #   |commit 1086.tree|
    #   | 29ff16c9c14e265|
    #   |2b22f8b78bb08a5a|
    p1 = raw.find(b' ')
    fmt = raw[0:p1]
    p2 = raw.find(b'\x00', p1)
    size = int(raw[p1 + 1:p2].decode('ascii'))
    if size != len(raw) - p2 - 1:
        raise Exception("Malformed object {0}: bad length".format(sha))

    if fmt == b'commit':
        c = GitCommit
    elif fmt == b'tree':
        c = GitTree
    elif fmt == b'tag':
        c = GitTag
    elif fmt == b'blob':
        c = GitBlob
    else:
        raise Exception("Unknown type %s for object %s".format(
            fmt.decode('ascii'), sha))

    # Call the constructor and return the object
    return c(repo, raw[p2 + 1:])


def object_write(obj, actually_write=True):
    # Serialize object data
    data = obj.serialize()
    # Add header
    content = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(content).hexdigest()

    if actually_write:
        path = git_file(obj.repo, "objects", sha[0:2], sha[2:], mkdir=True)
        with open(path, "wb") as f:
            f.write(zlib.compress(content))

    return sha


def object_search(repo, name, fmt=None, follow=True):
    return name


argparser = argparse.ArgumentParser(description="The git simulation program")
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True
# subparsers
# init
argsp = argsubparsers.add_parser("init",
                                 help="Initialize a new, empty repository")
argsp.add_argument("path",
                   metavar="directory",
                   nargs="?",
                   default=".",
                   help="Where to create the repository")
# cat-file
argsp = argsubparsers.add_parser("cat-file",
                                 help="Provide content of repository object")
argsp.add_argument("type",
                   metavar="type",
                   choices=["blob", "commit", "tag", "tree"],
                   help="Specify the type")
argsp.add_argument("object",
                   metavar="object",
                   help="Object hash of the object")


def cmd_init(args):
    repo_create(args.path)


def cmd_cat_file(args):
    repo = repo_search()

    obj = object_read(repo, object_search(repo, args.object,
                                          args.type.encode()))
    sys.stdout.buffer.write(obj.serialize())


def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)

    if args.command == "init":
        cmd_init(args)
    elif args.command == "cat-file":
        cmd_cat_file(args)
