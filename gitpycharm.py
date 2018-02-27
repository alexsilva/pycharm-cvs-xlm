import argparse
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
        return cls.call(subprocess.call, pargs, *args, **kwargs)

    @classmethod
    def execute_output(cls, pargs, *args, **kwargs):
        return cls.call(subprocess.check_output, pargs, *args, **kwargs)

    @classmethod
    def call(cls, subprocess_func, pargs, *args, **kwargs):
        kwargs.setdefault('env', os.environ.copy())
        return subprocess_func([cls.tool] + list(pargs), *args, **kwargs)


class GitSMState(object):
    regex_hash = re.compile("\d+\s\w+\s(?P<hash>[^\s]+)")
    regex_branch = re.compile("\*\s(?P<branch>[^\s]+)", re.DOTALL|re.MULTILINE)

    def __init__(self, project_root):
        self.project_root = project_root

    def get(self, sm_path):
        data = VCS.execute_output(["branch"], cwd=self.project_root)
        options = self.regex_branch.findall(data)
        if len(options) > 0:
            branch = options[0]
        else:
            branch = "master"
            print "* \"{}\" using branch default \"{}\"".format(sm_path, branch)
        data = VCS.execute_output(["ls-tree", branch,  sm_path],
                                  cwd=self.project_root)
        match = self.regex_hash.match(data)
        return match.groupdict()["hash"]


class GitSMConfig(object):
    """Analyzes files of type .gitmodules """

    def __init__(self, filepath):
        self.filepath = filepath
        self.modules = []

    def parser(self):
        sm_state = GitSMState(os.path.dirname(self.filepath))

        config_parser = ConfigParser.ConfigParser()

        with open(self.filepath) as _:
            content = []
            for line in _.readlines():
                content.append(re.sub(r"^[\s\t]+", "", line))

            config_parser.readfp(io.BytesIO("".join(content)))

            for sec in config_parser.sections():
                path = config_parser.get(sec, "path", None)
                if path is None:
                    continue

                sm_hash = sm_state.get(path)

                self.modules.append({
                    'path': os.path.normpath(path),
                    'url': config_parser.get(sec, "url", None),
                    'branch': config_parser.get(sec, "branch", "master"),
                    'hash': sm_hash
                })
        return config_parser

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

    def __init__(self, fullpath, config, **options):
        self.fullpath = fullpath
        self.config = config
        self.options = options

    @property
    def path(self):
        return self.config['path']

    def update(self):
        VCS.execute(['checkout', self.config['branch']],
                    cwd=self.fullpath)
        # Force the last state registered in the project.
        VCS.execute(['reset', "--" + self.options['sm_reset'], self.config['hash']],
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

    def __init__(self, project_root, branch=None, **options):
        self.project_root = project_root
        self.branch = branch
        self.submodule_configs = {}
        self.submodules = []
        self.options = options

    def update(self):
        args = ['pull']
        if self.branch is not None:
            args.extend(["origin", self.branch])
        VCS.execute(args, cwd=self.project_root)
        VCS.execute(['submodule', 'update'] + self.update_extra_args,
                    cwd=self.project_root)

    def submodule_register(self, sm_path):
        for git_module_path in self.submodule_configs:
            sm_config = self.submodule_configs[git_module_path][sm_path]
            if sm_config is not None:
                sm = Submodule(sm_path, sm_config, **self.options)
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
        parser = self.add_arguments()
        self.options = parser.parse_args(args)

    @staticmethod
    def add_arguments():
        parser = argparse.ArgumentParser(description='Project arguments')
        parser.add_argument("-p", "--path", default=os.getcwd())
        parser.add_argument("-b", "--branch", default=None)
        parser.add_argument("-s", "--sm-reset", default="soft")
        return parser

    @property
    def project_root(self):
        return self.options.path

    @property
    def project_branch(self):
        return self.options.branch


if __name__ == "__main__":

    config = Config(*sys.argv[1:])

    project_root = config.project_root

    options = vars(config.options)

    print "Project update \"{}\"".format(project_root)
    project = Project(project_root, **options)
    project.update()

    print "Loading submodules"
    project.load_submodules()

    for submodule in project:
        print "Submodule update \"{}\"".format(submodule.path)
        submodule.update()

    print "Pycharm update"
    pycharm = Pycharm(project)
    pycharm.update()
