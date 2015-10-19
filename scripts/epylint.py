#!/usr/bin/python

# sourced from:
# https://github.com/lopuhin/python-emacs-stuff/blob/master/epylint

import re
import sys

from subprocess import *

p = Popen("pylint -f parseable -r n "
          "--bad-functions=apply,input "
          "%s" % sys.argv[1],
          shell = True, stdout = PIPE).stdout

ignored_messages = [
    'Used * or ** magic',
    "Redefining built-in 'id'",
    'Class has no __init__ method',
    'Use super on an old style class', # pylint bug, I think
    'defined outside __init__', # Attibute blabla defined outside __init__ - I do it
    "Undefined variable 'patterns'",     # --------------------
    "Undefined variable 'url'",     # cause django recommends
    "Undefined variable 'include'", # from django.conf.urls.defaults import *
    "Redefining name '_' from outer scope",
    "Access to a protected member _meta of a client class",
    "(but some types could not be inferred)",
    ]

# FIXME - pylint --generated-members option not working
generated_members = \
    "is_valid,cleaned_data,fields,save,objects,_errors,id,app,at,document_id,"\
    "DoesNotExist,_meta,delay,get_logger,get_ancestors,get_descendants,instance,"\
    "assert_,assertEqual,assertFalse,assertTrue,errors,is_valid,save".split(',')

ignored_messages.extend(["has no '%s' member" % m for m in generated_members])


for line in p.readlines():
    match = re.search("\\[([WE])(, (.+?))?\\]", line)
    if match:
        kind = match.group(1)
        func = match.group(3)

        if kind == "W":
            msg = "Warning"
        else:
            msg = "Error"

        if func:
            line = re.sub("\\[([WE])(, (.+?))?\\]",
                          "%s (%s):" % (msg, func), line)
        else:
            line = re.sub("\\[([WE])?\\]", "%s:" % msg, line)

        if all(subs not in line for subs in ignored_messages):
            print line,

    p.close()