import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, read_expenses

ROWS = [
    ("2026-01-05", "Coffee", "12.50", "usd"),
    ("2026-02-10", "Taxi", "30", "COP"),
]
EXPECTED = [
    Expense(date(2026, 1, 5), "Coffee", Decimal("12.50"), "USD"),
    Expense(date(2026, 2, 10), "Taxi", Decimal("30"), "COP"),
]
KEYS = ("date", "description", "amount", "currency")


def csv_text(rows=ROWS):
    return "date,description,amount,currency\n" + "".join(",".join(r) + "\n" for r in rows)


def json_text(rows=ROWS):
    return json.dumps([dict(zip(KEYS, r)) for r in rows])


def xml_text(rows=ROWS):
    items = "".join(
        "<expense>" + "".join(f"<{k}>{v}</{k}>" for k, v in zip(KEYS, r)) + "</expense>"
        for r in rows
    )
    return f"<expenses>{items}</expenses>"


class FormatTests(unittest.TestCase):
    def read(self, name, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / name
            p.write_text(text, encoding="utf-8")
            return read_expenses(p)

    def test_csv_regression(self):
        self.assertEqual(self.read("a.csv", csv_text()), EXPECTED)

    def test_json(self):
        self.assertEqual(self.read("a.json", json_text()), EXPECTED)

    def test_json_number_amount(self):
        text = '[{"date":"2026-01-05","description":"x","amount":12.50,"currency":"usd"}]'
        self.assertEqual(self.read("a.json", text)[0].amount, Decimal("12.5"))

    def test_xml(self):
        self.assertEqual(self.read("a.xml", xml_text()), EXPECTED)

    def test_uppercase_extension(self):
        self.assertEqual(self.read("a.JSON", json_text()), EXPECTED)

    def test_same_result_everywhere(self):
        csv_r = self.read("a.csv", csv_text())
        self.assertEqual(self.read("a.json", json_text()), csv_r)
        self.assertEqual(self.read("a.xml", xml_text()), csv_r)

    def test_unknown_extension(self):
        with self.assertRaisesRegex(ReportError, "unsupported"):
            self.read("a.txt", "x")

    def test_excel_not_supported(self):
        with self.assertRaisesRegex(ReportError, "Excel"):
            self.read("a.xlsx", "x")

    def test_bad_record_names_position(self):
        bad = [("not-a-date", "x", "1", "USD")]
        with self.assertRaisesRegex(ReportError, "line 2"):
            self.read("a.json", json_text(bad))
        bad = [("2026-01-05", "x", "1", "US")]
        with self.assertRaisesRegex(ReportError, "line 2"):
            self.read("a.xml", xml_text(bad))

    def test_malformed_text(self):
        for name in ("a.json", "a.xml"):
            with self.assertRaises(ReportError):
                self.read(name, "{not valid")

    def test_json_top_level_not_list(self):
        with self.assertRaises(ReportError):
            self.read("a.json", '{"date": "2026-01-05"}')


if __name__ == "__main__":
    unittest.main()
