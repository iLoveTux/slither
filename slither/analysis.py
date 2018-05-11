import matplotlib.pyplot as plt
import time
import pandas as pd
import numpy as np
from IPython.display import display, HTML
from glob import iglob, glob
from lxml import etree
from datetime import datetime
import os

def get_provider(directory, host_segment, domain_segment, appliances, domain, status_provider, hour):
    t = time.time()
    t = datetime.fromtimestamp(t)
    # _glob is all the current data files for all appliances detailing status_provider in domain
    _glob = "/".join([directory, appliances, domain, "{}.log".format(status_provider)])
    rows = []
    print(directory)
    for filename in glob(_glob):
        host = filename.split(os.path.sep)[int(host_segment)]
        _domain = filename.split(os.path.sep)[int(domain_segment)]
        meta = {"host": host, "domain": _domain}
        with open(filename, "r") as fp:
            _rows = (etree.fromstring(line) for line in fp)
            __rows = (
                {datapoint.tag.split("}")[-1]: int(datapoint.text) if datapoint.text and datapoint.text.isdigit() else datapoint.text for datapoint in row.xpath(r"/{}/*".format(status_provider))}
                for row in _rows
            )
            for _row, __row in zip(_rows, __rows):
                __row.update(meta)
                __row["timestamp"] = pd.Timestamp(_row.attrib["timestamp"])
                print(__row)
                rows.append(__row)
    return pd.DataFrame(rows)


def plot(directory, provider, metric, title, appliances, domain, hour="%H"):
    plt.style.use(u'seaborn-whitegrid')
    plt.figure(figsize=(12,6))
    df = get_provider(directory, appliances, domain, provider, hour=hour)
    df.set_index("timestamp").groupby("host")[metric].plot(legend=True, title=title)
    return df

plt.style.use(u'seaborn-whitegrid')

# directory = os.path.join()
# host_segment = 6
# domain_segment = 7
def graph(directory, out_directory, host_segment, domain_segment, appliances="*", domain="*", hour="*", filename_prefix=""):
    now = time.time()
    now = datetime.fromtimestamp(now)

    filename_prefix = now.strftime(hour.replace("*", "")) + filename_prefix
    current_date = now.strftime("%Y%m%d")
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)

    title = "Established TCP Connections by host over time"
    df = get_provider(
        directory,
        host_segment,
        domain_segment,
        appliances,
        "default",
        "TCPSummary",
        hour=hour
    )
    df.to_csv(
        os.path.join(
            out_directory,
            "TCPSummary.csv"
        ),
        index=False
    )
    plt.figure(figsize=(12,6))
    df.set_index("timestamp").groupby("host")["established"].plot(legend=True, title=title)
    plt.savefig(
        os.path.join(
            out_directory,
            "EstablishedTCPConnections.svg"
        ),
        format="svg",
    )


    html = "<html>"
    html += '<head><meta http-equiv="refresh" content="60" ></head><body>'
    img_tmpl = '    <img src="{}" />'
    download_tmpl = '<a href="{0}">{0}</a><br />'
    html += "<h1>{}</h1>".format(filename_prefix)
    html += "<h2>Downloads</h2>"
    for filename in os.listdir(out_directory):
        if filename.endswith(".csv") and (filename_prefix in filename):
            html += download_tmpl.format(filename)
    html += "<h2>Graphs - for {}</h2>".format(filename_prefix)
    for filename in os.listdir(out_directory):
        if filename.endswith(".png") or filename.endswith(".svg"):
            html += img_tmpl.format(filename)
    html += "</body></html>"
    with open(os.path.join(out_directory, "index.html"), "w") as fp:
        fp.write(html)
