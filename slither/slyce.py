import re
import csv
import sys
import click
import logging
import pkg_resources
import multiprocessing
from pathlib import Path
from glob import glob
from lxml import etree
from collections import defaultdict

logging.basicConfig(stream=sys.stdout, level=20, format="%(message)s")

def xml(line):
    line = etree.fromstring(line)
    out_dict = {}
    for node in line.xpath("//*"):
        if node.text:
            key = ".".join(reversed([n.tag for n in node.iterancestors()])) + "." + node.tag
            # print(key)
            yield (key, node.text)
        for k, v in node.attrib.items():
            key = ".".join(reversed([n.tag for n in node.iterancestors()]))
            key = key + "." + node.tag + "@" + k if key else node.tag + "@" + k
            # print(key)
            yield (key, v)

def regex(regexp):
    def inner(line):
        return regexp.findall(line)
    return inner

def handle_file(path, pipeline, fieldnames):
    log = logging.getLogger(__name__)
    if path is sys.stdin:
        for line in path:
            for step in pipeline["preprocess"]:
                line = step(line)
            out_dict = {}
            for step in pipeline["pipeline"]:
                out_dict.update(
                    dict(list(step(line)))
                )
            if any(fieldname in out_dict for fieldname in fieldnames):
                print(",".join(out_dict.get(fieldname) for fieldname in fieldnames))
    else:
        with path.open("r") as fin:
            for line in fin:
                for step in pipeline["preprocess"]:
                    line = step(line)
                out_dict = defaultdict(list)
                for step in pipeline["pipeline"]:
                    for k, v in step(line):
                        out_dict[k].append(v)
                if any(fieldname in out_dict for fieldname in fieldnames):
                    print(",".join(" ".join(out_dict.get(fieldname)) for fieldname in fieldnames))

def _get_plugins(group: str="slyce.plugin"):
    """Retrieve the items registered with setuptools
    entry_points for the given group (defaults to
    slither.plugin group).

    TODO: Whitelist/blacklist for plugins
    """
    plugins = {}
    for ep in pkg_resources.iter_entry_points(group=group):
        plugins.update({ep.name: ep.load()})
    return plugins

def _import(module, func):
    """Perform the equivalent of from $module import $func
    """
    module = __import__(
        module, globals(), locals(), [func], 0
    )
    return getattr(module, func)

@click.command()
@click.argument("src", type=click.Path())
@click.option("--preprocesses", "-p", multiple=True)
@click.option("--extractions", "-x", multiple=True)
@click.option("--fieldnames", "-f", multiple=True)
def main(src, preprocesses, extractions, fieldnames):
    plugins = _get_plugins()
    pipeline = {
        "preprocess": [],
        "pipeline": [],
    }
    for preprocess in preprocesses:
        func = _import(*preprocess.split(":"))
        pipeline["preprocess"].append(func)
    for extraction in extractions:
        pipeline["pipeline"].append(
            _import(*extraction.split(":"))
        )
    print(",".join(fieldnames))
    if src == "-":
        handle_file(sys.stdin, pipeline, fieldnames)
    else:
        for path in glob(src):
            path = Path(path)
            if path.is_file():
                handle_file(path, pipeline, fieldnames)
            elif path.is_dir():
                raise ValueError("Only filenames and glob patterns are allowed, not directories.")
