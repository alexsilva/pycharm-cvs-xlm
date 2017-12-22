import re
import xml.etree.ElementTree as ET

import os
import sys
import ConfigParser
import subprocess
import io

# ---------------

if len(sys.argv) > 1:
    projectdir = sys.argv[-1]
else:
    projectdir = os.getcwd()

xmlfilepath = os.path.join(projectdir, ".idea", "vcs.xml")

# --------------

git_tool = os.environ.get('GIT_PATH', 'git')

vcs_name = 'git'
git_module_dir = '.git'
git_submodule_file = '.gitmodules'
git_submodules = []
git_submodule_config = []


for root, dirs, files in os.walk(projectdir):
    for dirname in dirs:
        dirpath = os.path.join(root, dirname)

    for filename in files:
        filepath = os.path.abspath(os.path.join(root, filename))
        if filename == git_module_dir:
            git_submodules.append(os.path.abspath(root))
        elif filename == git_submodule_file:
            git_submodule_config.append(filepath)

# -------------


class GitSubmodule(object):
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
                    'branch': cparser.get(sec, "branch", None),
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


submodules_config = []

for config in git_submodule_config:
    submodule = GitSubmodule(config)
    submodule.parser()

    submodules_config.append(submodule)

# -------------

tree = ET.parse(xmlfilepath)
project = tree.getroot()

environ_name = '$PROJECT_DIR$'

for component in project.iter('component'):

    pycharm_modules_config = []

    for mapping in component.iter('mapping'):
        vcs_type = mapping.attrib['vcs']
        if vcs_type and vcs_type.lower() == vcs_name:
            directory = mapping.attrib['directory']

            if directory.startswith(environ_name):
                directory = directory.replace(environ_name, projectdir)
                directory = os.path.abspath(directory)

            pycharm_modules_config.append(directory)

    for submodule_path in git_submodules:
        # already added
        if submodule_path in pycharm_modules_config:
            print "Already registered '{}'".format(submodule_path)
            continue
        print '-' * 20
        for submodule_config in submodules_config:
            config = submodule_config[submodule_path]
            # invalid path ?
            if config is None:
                continue
            print 'Module {}'.format(submodule_path)
            # noinspection PyBroadException
            try:
                print "Running {0:s} checkout".format(git_tool)
                subprocess.call([git_tool, 'checkout', config['branch']], cwd=submodule_path)
                print "Running {0:s} pull".format(git_tool)
                subprocess.call([git_tool, 'pull'], cwd=submodule_path)
            except Exception:
                pass
        pycharm_md_path = submodule_path.replace(projectdir, '$PROJECT_DIR$')
        print "Add to pycharm VCS ({})".format(pycharm_md_path)
        new_mapping = ET.SubElement(component, 'mapping', attrib={
            "directory": pycharm_md_path,
            "vcs":  "Git",
        })
        new_mapping.tail = "\n\t"

print 'Saving changes'
tree.write(xmlfilepath)
print 'Done.'
