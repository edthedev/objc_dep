#!/usr/bin/python

# Nicolas Seriot
#   with updates for Python by Edward Delaporte
# https://github.com/edthedev/objc_dep/

"""

Input: path of a Python project module path

Output: import dependencies Graphviz format

Usage: 
    objc_dep.py [--language=<language>] [--ignore=<folder>...] [--exclude=<module>...] <project_path>

Output should be piped into a .dot file.
The .dot file can be opened with Graphviz or OmniGraffle.

- red arrows: .pch imports
- blue arrows: two ways imports

Graphviz examples:
    dot output.dot -o output.jpg -Tjpg; eog output.jpg
    dot output.dot -Kfdp -o output.jpg -Tjpg; eog output.jpg

Options:
    -h --help               Show this help.
    -i --ignore=<folder>    List of folder names to ignore. 
    -x --exclude=<regex>    list of modules to skip.
"""

from docopt import docopt
import sys
import os
from sets import Set
import re
from os.path import basename

# C#
regex_imports = [re.compile("^#(import|include) \"(?P<filename>\S*)\.h")]
EXTENSIONS = ['.h', '.hpp', '.m', '.mm', '.c', '.cc', '.cpp']

# Python
regex_imports = [
        re.compile("^from (?P<module>[\S\.]*) import (?P<target>\S*)"),
        re.compile("^import (?P<module>[\S\.]*)"),
        ]
EXTENSIONS = ['.py']

# In python, we need to prepend the current working directory to generate paths.
project_root = os.curdir

def gen_filenames_imported_in_file(path, excludes):
    # print "# Opening " + path
    results = []
    for line in open(path):
        for regex_import in regex_imports:
            result = re.search(regex_import, line)
            if result:
                results = results + [result]

    for result in results:
        # modules = result.group('module').split(',')
        module = result.group('module')
        skip = False
        for exclude in excludes:
            if exclude in module:
                # print "# Excluding " + module + "(" + exclude + ")"
                skip = True
        if skip:
            continue
        yield module

def module_from_filename(ignore_path, root, dirs, filename):
    base = root.replace(ignore_path, '')
    module_path = []
    module_path.append(base)
    module_path = module_path + dirs
    module_path.append(filename)
    full_module_path = '/'.join(module_path)
    # print full_module_path
    return full_module_path.replace('.py', '').replace('/', '.')

def dependencies_in_project(project_path, ext, excludes, ignore):
    d = {}
   
    path = project_path
    for root, dirs, files in os.walk(path):
        for i in ignore:
            if i in dirs:
                dirs.remove(i)

        objc_files = (f for f in files if f.endswith(ext))

        for f in objc_files:
            filename = os.path.splitext(f)[0]
            module_full = module_from_filename(project_path, root, dirs, f)
            for exclude in excludes:
                if exclude in module_full:
                    print "# EX " + exclude + " - " + module_full
                    continue
            
            if module_full not in d:
                d[module_full] = Set()
            
            path = os.path.join(root, f)
            
            for imported_filename in gen_filenames_imported_in_file(path, excludes):
               #  , regex_exclude):
                if imported_filename != filename and '+' not in imported_filename:
                    d[module_full].add(imported_filename)
                else:
                    print "# Technicality excluded " + filename

    return d

def dependencies_in_project_with_file_extensions(project_path, exts, exclude, ignore):

    d = {}
    
    for ext in exts:
        d2 = dependencies_in_project(project_path, ext, exclude, ignore)
        for (k, v) in d2.iteritems():
            if not k in d:
                d[k] = Set()
            d[k] = d[k].union(v)

    return d

def two_ways_dependencies(d):

    two_ways = Set()

    # d is {'a1':[b1, b2], 'a2':[b1, b3, b4], ...}

    for a, l in d.iteritems():
        for b in l:
            if b in d and a in d[b]:
                if (a, b) in two_ways or (b, a) in two_ways:
                    continue
                if a != b:
                    two_ways.add((a, b))
                    
    return two_ways

def category_files(d):
    d2 = {}
    l = []
    
    for k, v in d.iteritems():
        if not v and '+' in k:
            l.append(k)
        else:
            d2[k] = v

    return l, d2

def referenced_classes_from_dict(d):
    d2 = {}

    for k, deps in d.iteritems():
        for x in deps:
            d2.setdefault(x, Set())
            d2[x].add(k)
    
    return d2
    
def print_frequencies_chart(d):
    
    lengths = map(lambda x:len(x), d.itervalues())
    if not lengths: return
    max_length = max(lengths)
    
    for i in range(0, max_length+1):
        s = "%2d | %s\n" % (i, '*'*lengths.count(i))
        sys.stderr.write(s)

    sys.stderr.write("\n")
    
    l = [Set() for i in range(max_length+1)]
    for k, v in d.iteritems():
        l[len(v)].add(k)

    for i in range(0, max_length+1):
        s = "%2d | %s\n" % (i, ", ".join(sorted(list(l[i]))))
        sys.stderr.write(s)
        
def dependencies_in_dot_format(project_path, exclude, ignore):

    d = dependencies_in_project_with_file_extensions(project_path, EXTENSIONS, exclude, ignore)

    two_ways_set = two_ways_dependencies(d)

    category_list, d = category_files(d)

    # pch_set = dependencies_in_project(path, '.pch', exclude, ignore)

    #
    
    sys.stderr.write("# number of imports\n\n")
    print_frequencies_chart(d)
    
    sys.stderr.write("\n# times the class is imported\n\n")
    d2 = referenced_classes_from_dict(d)    
    print_frequencies_chart(d2)
        
    #

    l = []
    l.append("digraph G {")
    l.append("\tnode [shape=box];")

    for k, deps in d.iteritems():
        if deps:
            deps.discard(k)
        
        if len(deps) == 0:
            l.append("\t\"%s\" -> {};" % (k))
        
        for k2 in deps:
	        if not ((k, k2) in two_ways_set or (k2, k) in two_ways_set):
	            l.append("\t\"%s\" -> \"%s\";" % (k, k2))

    l.append("\t")
    # for (k, v) in pch_set.iteritems():
    #     l.append("\t\"%s\" [color=red];" % k)
    #     for x in v:
    #         l.append("\t\"%s\" -> \"%s\" [color=red];" % (k, x))
    
    l.append("\t")
    l.append("\tedge [color=blue, dir=both];")

    for (k, k2) in two_ways_set:
        l.append("\t\"%s\" -> \"%s\";" % (k, k2))
    
    if category_list:
        l.append("\t")
        l.append("\tedge [color=black];")
        l.append("\tnode [shape=plaintext];")
        l.append("\t\"Categories\" [label=\"%s\"];" % "\\n".join(category_list))

    if ignore:
        l.append("\t")
        l.append("\tnode [shape=box, color=blue];")
        l.append("\t\"Ignored\" [label=\"%s\"];" % "\\n".join(ignore))

    l.append("}\n")
    return '\n'.join(l)

def main():
# Parse all arguments out of the module doc string.
    args = docopt(__doc__, version='1.0')

    print "# Graph generated from source code at " + args['<project_path>']
    if args['--exclude']:
        print "# Modules excluded: " + ' '.join(args['--exclude']) 
    print dependencies_in_dot_format(
            args['<project_path>'], 
            args['--exclude'],
            args['--ignore'],
            )
  
if __name__=='__main__':
    main()
