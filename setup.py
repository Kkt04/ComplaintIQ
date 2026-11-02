from setuptools import find_packages, setup

setup(
    name="complaintiq",
    version="1.0.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
)
