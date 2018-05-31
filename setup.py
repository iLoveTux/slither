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
            "sl-syslog=slither.plugins.syslog_server:main",
            "slyce=slither.slyce:main",
            "slither=slither:main",
        ],
        "slither.plugin": [
            "tictok=slither.plugins:tick_tock",
            "files=slither.plugins:watch_directory",
            "automan=slither.plugins:automan",
            # "syslog=slither:syslog_server",
        ]
    },
    test_suite="nose.collector",
    tests_require=tests_require,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
)
