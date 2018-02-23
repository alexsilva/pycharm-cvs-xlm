import sys

from gitpycharm import Project

"""
Updates submodules of a project
"""

if __name__ == "__main__":
    projectdir = sys.argv[-1]

    print "Project update \"{}\"".format(projectdir)
    project = Project(projectdir)
    project.update()

    print "Loading submodules"
    project.load_submodules()

    for submodule in project:
        print "Submodule update \"{}\"".format(submodule.path)
        submodule.update()
