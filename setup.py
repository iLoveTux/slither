# Requirements:
#   prodict
import sys
from setuptools import setup

tests_require = ["nose>=1.0"]
if sys.version_info < (3,0):
    tests_require = ["nose>=1.0", "mock"]

setup(
    name="slither",
    version="0.1.0",
    author="Clifford Bressette",
    author_email="cliffbressette@gmail.com",
    description="software to increase computational utility",
    license="GPLv3",
    keywords="utility tools cli",
    url="http://github.com/ilovetux/slither",
    packages=['slither'],
    install_requires=["croniter"],
    entry_points={
        "console_scripts": [
            "sl-syslog=slither.syslog_server:main",
            "slyce=slither.slyce:main",
            "ginsu=slither.ginsu:cli",
            "slither=slither:main",
            "rextract=slither.rextract:rextract",
            "dsh=slither.dsh:main",
        ],
        "ginsu.plugin": [
            "python=slither.ginsu:python_plugin",
            "lambda=slither.ginsu:lambda_plugin",
            # "syslog=slither:syslog_server",
        ],
    },
    test_suite="nose.collector",
    tests_require=tests_require,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
)
