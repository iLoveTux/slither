import re
import sys
import click
import logging
from pathlib import Path
from glob import glob
from lxml import etree

logging.basicConfig(stream=sys.stdout, level=20, format="%(message)s")

def handle_file(path, columns, patterns, content_type):
    log = logging.getLogger(__name__)
    with path.open("r") as fin:
        for line in fin:
            if content_type == "xml":
                line = etree.fromstring(line)
                log.info(",".join(";".join(map(str, line.xpath(pattern))) for pattern in patterns))
            elif content_type == "text":
                log.info(",".join(";".join(pattern.findall(line)) for pattern in patterns))

@click.command()
@click.argument("src", type=click.Path())
@click.option("--columns", "-c", multiple=True)
@click.option("--xml", "content_type", flag_value="xml")
@click.option("--text", "content_type", flag_value="text", default=True)
def main(src, columns, content_type):
    log = logging.getLogger(__name__)
    _columns, _patterns = [], []
    for column in columns:
        _column, _pattern = column.split(":", 1)
        _columns.append(_column)
        if content_type == "text":
            _patterns.append(re.compile(_pattern))
        else:
            _patterns.append(_pattern)
    log.info(",".join(_columns))
    for path in glob(src):
        path = Path(path)
        if path.is_file():
            handle_file(path, _columns, _patterns, content_type)
        elif path.is_dir():
            handle_dir(path, columns, content_type)
