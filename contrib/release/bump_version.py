#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import with_statement

import errno
import os
import re
import sys
import subprocess

from contextlib import contextmanager
from tempfile import NamedTemporaryFile

rq = lambda s: s.strip("\"'")


def cmd(*args):
    return subprocess.Popen(args, stdout=subprocess.PIPE).communicate()[0]


@contextmanager
def no_enoent():
    try:
        yield
    except OSError, exc:
        if exc.errno != errno.ENOENT:
            raise

class StringVersion(object):

    def decode(self, s):
        text = ""
        major, minor, release = s.split(".")
        if not release.isdigit():
            pos = release.index(re.split("\d+", release)[1][0])
            release, text = release[:pos], release[pos:]
        return int(major), int(minor), int(release), text

    def encode(self, v):
        return ".".join(map(str, v[:3])) + v[3]
to_str = StringVersion().encode
from_str = StringVersion().decode


class TupleVersion(object):

    def decode(self, s):
        v = list(map(rq, s.split(", ")))
        return (tuple(map(int, v[0:3])) +
                tuple(["".join(v[3:])]))

    def encode(self, v):
        v = list(v)

        def quote(lit):
            if isinstance(lit, basestring):
                return '"%s"' % (lit, )
            return str(lit)

        if not v[-1]:
            v.pop()
        return ", ".join(map(quote, v))

class VersionFile(object):

    def __init__(self, filename):
        self.filename = filename

    def _as_orig(self, version):
        return self.wb % self.type.encode(version)

    def write(self, version):
        pattern = self.regex
        with no_enoent():
            with NamedTemporaryFile() as dest:
                with open(self.filename) as orig:
                    for line in orig:
                        if pattern.match(line):
                            dest.write(self._as_orig(version))
                        else:
                            dest.write(line)
                os.rename(dest.name, self.filename)

    def parse(self):
        pattern = self.regex
        with open(self.filename) as fh:
            for line in fh:
                m = pattern.match(line)
                if m:
                    return self.type.decode(m.groups()[0])

class PyVersion(VersionFile):
    regex = re.compile(r'^VERSION\s*=\s*\((.+?)\)')
    wb = "VERSION = (%s)\n"
    type = TupleVersion()

    def __init__(self, filename):
        self.filename = filename


class SphinxVersion(VersionFile):
    regex = re.compile(r'^:[Vv]ersion:\s*(.+?)$')
    wb = ':Version: %s\n'
    type = StringVersion()

    def __init__(self, filename):
        self.filename = filename


def bump(dist, docfile="README.rst", custom=None):
    distfile = os.path.join(dist, "__init__.py")
    files = [PyVersion(distfile), SphinxVersion(docfile)]

    versions = [v.parse() for v in files]
    current = list(reversed(sorted(versions)))[0]  # find highest

    if custom:
        next = from_str(custom)
    else:
        major, minor, release, text = current
        if text:
            raise Exception("Can't bump alpha releases")
        next = (major, minor, release + 1, text)

    print("Bump version from %s -> %s" % (to_str(current), to_str(next)))

    for v in files:
        print("  writing %r..." % (v.filename, ))
        v.write(next)

    print(cmd("git", "commit", "-m", "Bumps version to %s" % (to_str(next), ),
        *[f.filename for f in files]))
    print(cmd("git", "tag", "v%s" % (to_str(next), )))


def main(argv=sys.argv, docfile="README.rst", custom=None):
    if not len(argv) > 1:
        print("Usage: distdir [docfile] -- <custom version>")
        sys.exit(0)
    dist = argv[1]
    if "--" in argv:
        c = argv.index('--')
        custom = argv[c + 1]
        argv = argv[:c]
    try:
        docfile = argv[2]
    except IndexError:
        pass
    bump(dist, docfile, custom)




if __name__ == "__main__":
    main()
