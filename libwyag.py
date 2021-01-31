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
                raise Exception("Unsupported repositoryformatversion %s" % vers)

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

    assert(check_git_dir(repo, "branches", mkdir=True))
    assert(check_git_dir(repo, "objects", mkdir=True))
    assert(check_git_dir(repo, "refs", "tags", mkdir=True))
    assert(check_git_dir(repo, "refs", "heads", mkdir=True))

    # .git/description
    with open(git_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

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

argparser = argparse.ArgumentParser(description="The git simulation program")
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository")
argsp.add_argument("path",
                   metavar="directory",
                   nargs="?",
                   default=".",
                   help="Where to create the repository")

def cmd_init(args):
    repo_create(args.path)

def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)

    if args.command == "init":
        cmd_init(args)
