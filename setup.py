from setuptools import setup

setup(
    name='pychnarm-vcs-xml',
    py_modules=[
        'gitpycharm',
        "gitsubmodule"
    ],
    version='3.0',
    url='https://github.com/alexsilva/pycharm-cvs-xlm',
    license='MIT',
    author='alex',
    author_email='alex@fabricadigital.com.br',
    description='Search for git submodules in the project and add them to the vcs.xml file from a pycharm (.idea) configuration directory.'
)
