import sys

import os

from gitpycharm import Project

"""
Updates submodules of a project
"""

if __name__ == "__main__":
    projectdir = sys.argv[-1] if len(sys.argv) > 1 else os.getcwd()

    print "Project update \"{}\"".format(projectdir)
    project = Project(projectdir)
    project.update()

    print "Loading submodules"
    project.load_submodules()

    for submodule in project:
        print "Submodule update \"{}\"".format(submodule.path)
        submodule.update()
