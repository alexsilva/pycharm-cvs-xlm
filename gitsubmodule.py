import sys

from gitpycharm import Project, Config

"""
Updates submodules of a project
"""

if __name__ == "__main__":
    config = Config(*sys.argv[1:])

    project_root = config.project_root

    print "Project update \"{}\"".format(project_root)
    project = Project(project_root, branch=config.project_branch)
    project.update()

    print "Loading submodules"
    project.load_submodules()

    for submodule in project:
        print "Submodule update \"{}\"".format(submodule.path)
        submodule.update()
