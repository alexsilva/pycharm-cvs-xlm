import re
import xml.etree.ElementTree as ET

import os
import sys
import ConfigParser
import subprocess
import io


class VCS(object):
    """Stores information about version control"""
    tool = os.environ.get('VCS_PATH', 'git')
    name = 'git'

    @classmethod
    def execute(cls, pargs, *args, **kwargs):
        kwargs.setdefault('env', os.environ.copy())
        return subprocess.call([cls.tool] + list(pargs), *args, **kwargs)


class GitSMConfig(object):
    """Analyzes files of type .gitmodules """

    def __init__(self, filepath):
        self.filepath = filepath
        self.modules = []

    def parser(self):
        cparser = ConfigParser.ConfigParser()

        with open(self.filepath) as _:
            content = []
            for line in _.readlines():
                content.append(re.sub(r"^[\s\t]+", "", line))

            cparser.readfp(io.BytesIO("".join(content)))

            for sec in cparser.sections():
                self.modules.append({
                    'path': os.path.normpath(cparser.get(sec, "path", None)),
                    'url': cparser.get(sec, "url", None),
                    'branch': cparser.get(sec, "branch", "master"),
                })
        return cparser

    def __getitem__(self, path):
        """Find the settings for a sub-module for the given path"""
        for module in self:
            if path.endswith(module['path']):
                return module
        return None

    def __iter__(self):
        return iter(self.modules)


class Submodule(object):
    """Represents an object of type submodule"""

    def __init__(self, fullpath, config):
        self.fullpath = fullpath
        self.config = config

    @property
    def path(self):
        return self.config['path']

    def update(self):
        VCS.execute(['checkout', self.config['branch']],
                    cwd=self.fullpath)

    def __str__(self):
        return str(self.config)


class Project(object):
    """A project containing submodules"""
    git_module_dir = '.git'
    git_submodule_filename = '.gitmodules'
    update_extra_args = [
        '--init',
        '--recursive',
        '--merge'
    ]

    def __init__(self, project_root, branch=None):
        self.project_root = project_root
        self.branch = branch
        self.submodule_configs = {}
        self.submodules = []

    def update(self):
        args = ['pull']
        if self.branch is not None:
            args.append(self.branch)
        VCS.execute(args, cwd=self.project_root)
        VCS.execute(['submodule', 'update'] + self.update_extra_args,
                    cwd=self.project_root)

    def submodule_register(self, sm_path):
        for git_module_path in self.submodule_configs:
            sm_config = self.submodule_configs[git_module_path][sm_path]
            if sm_config is not None:
                sm = Submodule(sm_path, sm_config)
                self.submodules.append(sm)
                break

    def __iter__(self):
        return iter(self.submodules)

    def load_submodules(self):
        for root, dirs, files in os.walk(self.project_root):
            for filename in files:
                if filename == self.git_module_dir:
                    self.submodule_register(os.path.abspath(root))

                elif filename == self.git_submodule_filename:
                    filepath = os.path.abspath(os.path.join(root, filename))

                    sm_config = GitSMConfig(filepath)
                    sm_config.parser()

                    self.submodule_configs[filepath] = sm_config


class Pycharm(object):
    """Pycharm configuration object"""
    env_project_dir = '$PROJECT_DIR$'
    filename = "vcs.xml"
    config_dir = ".idea"
    root_item_name = 'component'

    def __init__(self, project):
        self.project_root = project.project_root
        self.xml_filepath = os.path.join(self.project_root,
                                         self.config_dir,
                                         self.filename)
        self.tree = ET.parse(self.xml_filepath)
        self.tree_root = self.tree.getroot()
        self.project = project

    def update(self):
        config = []
        for component in self.tree_root.iter(self.root_item_name):
            for mapping in component.iter('mapping'):
                vcs_type = mapping.attrib['vcs']
                if vcs_type and vcs_type.lower() == VCS.name:
                    directory = mapping.attrib['directory']

                    if directory.startswith(self.env_project_dir):
                        directory = directory.replace(self.env_project_dir,
                                                      self.project_root)
                        directory = os.path.abspath(directory)

                    config.append(directory)

            for submodule in self.project:
                submodule_path = submodule.fullpath
                # check if you have already registered with pycharm
                if submodule_path in config:
                    print "Skip \"{}\" already registered".format(submodule_path)
                    continue

                submodule_relpath = submodule_path.replace(self.project_root,
                                                           self.env_project_dir)
                print "Pycharm add ({})".format(submodule_relpath)
                new_mapping = ET.SubElement(component, 'mapping', attrib={
                    "directory": submodule_relpath,
                    "vcs": VCS.name.capitalize(),
                })
                new_mapping.tail = "\n\t"

        print 'Saving changes'
        self.tree.write(self.xml_filepath)
        print 'Done'


class Config(object):
    def __init__(self, *args):
        self._cache_config = {}
        self.args = args

    @property
    def project_root(self):
        value = self._cache_config.get('project_root')
        if value is None:
            value = self.args[1] if len(self.args) > 1 else os.getcwd()
        return value


if __name__ == "__main__":

    config = Config(*sys.argv)

    project_root = config.project_root

    print "Project update \"{}\"".format(project_root)
    project = Project(project_root)
    project.update()

    print "Loading submodules"
    project.load_submodules()

    for submodule in project:
        print "Submodule update \"{}\"".format(submodule.path)
        submodule.update()

    print "Pycharm update"
    pycharm = Pycharm(project)
    pycharm.update()
