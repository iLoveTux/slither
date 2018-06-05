import os
import re
import pkg_resources
from collections import defaultdict
from urllib.parse import urlparse, parse_qsl
from functools import partial, reduce
import atexit
from textwrap import dedent
import sys
import logging
from lxml import etree
from pathlib import Path
from glob import glob
import click

logging.basicConfig(
    stream=sys.stdout,
    level=20,
    format="%(message)s"
)

def python_plugin(obj):
    module = obj.netloc
    func = obj.path.lstrip("/").replace("/", ".").split(";")[0]
    func = _import(module, func)
    kwargs = dict(parse_qsl(obj.query, keep_blank_values=True))
    if "_args" in kwargs:
        args = kwargs.pop("_args")
        if isinstance(args, str):
            args = [args]
    else:
        args = []
    ret = partial(func, *args, **kwargs)
    return ret

def lambda_plugin(obj):
    expression = obj.netloc
    return lambda x: eval(expression)

def _map_handle_file(path, maps):
    for line in path:
        output = line
        for func in maps:
            output = func(output)
        yield output

def map_handle_file(path, maps):
    log = logging.getLogger(__name__)
    if path is sys.stdin:
        for line in _map_handle_file(path, maps):
            yield line
    else:
        with path.open("r") as fin:
            for line in _map_handle_file(fin, maps):
                yield line

def _filter_handle_file(path, logical_operator, filters):
    for line in path:
        if logical_operator(f(line) for f in filters):
            yield line

def filter_handle_file(path, logical_operator, filters):
    if path is sys.stdin:
        for line in _filter_handle_file(path, logical_operator, filters):
            yield line
    else:
        with path.open("r") as fin:
            for line in _filter_handle_file(fin, logical_operator, filters):
                yield line

def _reduce_handle_file(path, reducer):
    return reduce(reducer, path)

def reduce_handle_file(path, reducer):
    if path is sys.stdin:
        return _reduce_handle_file(path, reducer)
    else:
        with path.open("r") as fin:
            return _reduce_handle_file(fin, reducer)

def _get_plugins(group: str="ginsu.plugin"):
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


cli = click.Group()

@cli.command("map")
@click.argument("src", type=click.Path())
@click.option("--maps", "-m", multiple=True)
def _map(src, maps):
    log = logging.getLogger("ginsu.map")
    plugins = _get_plugins()
    _maps = []
    for map in maps:
        obj = urlparse(map)
        getter = obj.scheme
        if getter in plugins:
            getter = plugins[getter]
        else:
            raise ValueError("Cannot find plugin {}".format(getter))
        _maps.append(getter(obj))
    if src == "-":
        for line in map_handle_file(sys.stdin, _maps):
            log.info(str(line))
    else:
        for path in glob(src):
            path = Path(path)
            if path.is_file():
                for line in map_handle_file(path, _maps):
                    log.info(str(line))
            elif path.is_dir():
                raise ValueError("Only filenames and glob patterns are allowed, not directories.")

@cli.command("filter")
@click.argument("src", type=click.Path())
@click.option("--filters", "-f", multiple=True)
@click.option("--and", "logical_operator", flag_value=all, default=True)
@click.option("--or", "logical_operator", flag_value=any)
def _filter(src, filters, logical_operator):
    log = logging.getLogger("ginsu.map")
    plugins = _get_plugins()
    _filters = []
    for f in filters:
        obj = urlparse(f)
        getter = obj.scheme
        if getter in plugins:
            getter = plugins[getter]
        else:
            raise ValueError("Cannot find plugin {}".format(getter))
        _filters.append(getter(obj))
    if src == "-":
        for line in filter_handle_file(sys.stdin, logical_operator, _filters):
            log.info(line.strip())
    else:
        for path in glob(src):
            path = Path(path)
            if path.is_file():
                for line in filter_handle_file(path, logical_operator, _filters):
                    log.info(line.strip())
            elif path.is_dir():
                raise ValueError("Only filenames and glob patterns are allowed, not directories.")

@cli.command("reduce")
@click.argument("src", type=click.Path())
@click.option("--reducer", "-r")
def _reduce(src, reducer):
    log = logging.getLogger("ginsu.map")
    plugins = _get_plugins()
    obj = urlparse(reducer)
    getter = obj.scheme
    if getter in plugins:
        getter = plugins[getter]
    else:
        raise ValueError("Cannot find plugin {}".format(getter))
    reducer = getter(obj)
    if src == "-":
        log.info(str(reduce_handle_file(sys.stdin, reducer)))
    else:
        for path in glob(src):
            path = Path(path)
            if path.is_file():
                log.info(str(reduce_handle_file(path, reducer)))
            elif path.is_dir():
                raise ValueError("Only filenames and glob patterns are allowed, not directories.")

pattern_action = re.compile(r"(.*?)\{(.+?)^\}", re.UNICODE|re.DOTALL|re.MULTILINE)
def parse_script(script):
    ret = defaultdict(list)
    if os.path.isfile(script):
        with open(script, "r") as fin:
            script = fin.read()
    script = dedent(script)
    for test, action in pattern_action.findall(script):
        if not test:
            test = "True"
        ret[test.strip()].append(dedent(action))
    return ret

@cli.command("do")
@click.argument("script", type=str, default='True{print(LINE)}')
@click.argument("src", nargs=-1, type=click.Path())
def do(script, src):
    actions = parse_script(script)
    if "BEGIN" in actions:
        for action in actions.pop("BEGIN"):
            exec(dedent(action), globals(), locals())
    if "END" in actions:
        for action in actions.pop("END"):
            atexit.register(exec, dedent(action), globals(), locals())
    if "BEGINLINE" in actions:
        begin_line = actions.pop("BEGINLINE")
    else:
        begin_line = []
    if "ENDLINE" in actions:
        end_line = actions.pop("ENDLINE")
    else:
        end_line = []
    for item in src:
        if item == "-":
            for LINE in sys.stdin:
                for test in actions:
                    if begin_line:
                        for action in begin_line:
                            exec(action, globals(), locals())
                    if eval(test, globals(), locals()):
                        for action in actions[test]:
                            exec(action, globals(), locals())
                    if end_line:
                        for action in end_line:
                            exec(action, globals(), locals())
        else:
            for filename in glob(item):
                with open(filename, "r") as fin:
                    for LINE in fin:
                        if begin_line:
                            for action in begin_line:
                                exec(action, globals(), locals())
                        for test in actions:
                            if eval(test, globals(), locals()):
                                for action in actions[test]:
                                    exec(action, globals(), locals())
                        if end_line:
                            for action in end_line:
                                print(action)
                                exec(action, globals(), locals())
