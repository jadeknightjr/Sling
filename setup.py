import os

from setuptools import find_packages, setup

setup(
    name="Sling",
    version="1.0",
    packages=find_packages(where="src", exclude=("test",)),
    package_dir={"": "src"},
)
