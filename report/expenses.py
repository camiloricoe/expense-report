"""Read expenses from a CSV file (date,description,amount,currency) and summarise them."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class Expense:
    day: date
    description: str
    amount: Decimal
    currency: str


class ReportError(ValueError):
    """A row the report cannot use; the message names its line in the file."""


def parse_row(row: dict[str, str], line: int) -> Expense:
    try:
        day = date.fromisoformat(row["date"].strip())
        amount = Decimal(row["amount"].strip())
    except (KeyError, AttributeError, ValueError, InvalidOperation) as exc:
        raise ReportError(f"line {line}: cannot read date or amount ({exc})") from exc
    currency = (row.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ReportError(f"line {line}: currency must be a 3-letter code, got {currency!r}")
    return Expense(day, (row.get("description") or "").strip(), amount, currency)


def _read_csv(path: Path) -> list[Expense]:
    with path.open(newline="", encoding="utf-8") as f:
        return [parse_row(row, n) for n, row in enumerate(csv.DictReader(f), start=2)]


def _read_json(path: Path) -> list[Expense]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ReportError(f"invalid JSON ({exc})") from exc
    if not isinstance(data, list):
        raise ReportError("JSON must be a list of expense objects")
    rows = []
    for n, item in enumerate(data, start=2):
        if not isinstance(item, dict):
            raise ReportError(f"line {n}: expense must be an object")
        rows.append(parse_row({k: "" if v is None else str(v) for k, v in item.items()}, n))
    return rows


def _read_xml(path: Path) -> list[Expense]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ReportError(f"invalid XML ({exc})") from exc
    return [
        parse_row({c.tag: c.text or "" for c in item}, n)
        for n, item in enumerate(root.findall("expense"), start=2)
    ]


def _read_excel(path: Path) -> list[Expense]:
    raise ReportError("Excel files are not supported yet")


_READERS = {
    ".csv": _read_csv,
    ".json": _read_json,
    ".xml": _read_xml,
    ".xlsx": _read_excel,
    ".xls": _read_excel,
}


def read_expenses(path: Path) -> list[Expense]:
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        raise ReportError(f"unsupported file format {path.suffix!r}")
    return reader(path)


def summary(expenses: list[Expense]) -> str:
    if not expenses:
        return "No expenses."
    days = sorted(e.day for e in expenses)
    return f"{len(expenses)} expenses from {days[0].isoformat()} to {days[-1].isoformat()}"
