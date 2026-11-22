"""Read eBird's bar chart "Download Histogram Data" file.

The file is tab-separated: a "Sample Size:" row of complete-checklist counts, then one
row per taxon (common name only) with the share of those checklists reporting it. There
are 48 periods: each month is split into days 1-7, 8-14, 15-21 and 22 to the end.
"""

import re
from dataclasses import dataclass
from datetime import date

PERIODS = 48
_FILENAME = re.compile(r"ebird_(?P<region>.+?)__\d{4}_\d{4}_(?P<first>\d+)_(?P<last>\d+)_barchart")


@dataclass(frozen=True)
class Histogram:
    sample_sizes: list[int]
    frequencies: dict[str, list[float]]  # common name -> one value per period


def period_of(day: date) -> int:
    return (day.month - 1) * 4 + min((day.day - 1) // 7, 3)


def check_filename(filename: str, region: str) -> None:
    """The file's contents don't name their region, so the filename is the only safeguard."""
    match = _FILENAME.search(filename)
    if not match:
        raise ValueError(f"'{filename}' isn't an eBird bar chart filename; don't rename it")
    if match["region"] != region:
        raise ValueError(f"File is for {match['region']}, but REGION_CODE is {region}")
    if (match["first"], match["last"]) != ("1", "12"):
        raise ValueError("Download the bar chart for all months, January to December")


def parse_histogram(text: str) -> Histogram:
    sizes: list[int] = []
    frequencies: dict[str, list[float]] = {}
    for line in text.splitlines():
        name, *values = line.rstrip("\t").split("\t")
        if name.startswith("Sample Size"):
            if len(values) != PERIODS:
                raise ValueError(f"Expected {PERIODS} sample sizes, found {len(values)}")
            sizes = [round(float(v)) for v in values]
        elif sizes and name.strip():
            if len(values) != PERIODS:
                raise ValueError(f"Expected {PERIODS} values for '{name}', found {len(values)}")
            row = [float(v) for v in values]
            if not all(0 <= v <= 1 for v in row):
                raise ValueError(f"Frequency outside 0-1 for '{name}'")
            frequencies[name] = row
    if not frequencies:
        raise ValueError("No histogram data found")
    return Histogram(sizes, frequencies)
