import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import (
    Expense,
    ReportError,
    format_by_month,
    parse_row,
    read_expenses,
    summary,
    totals_by_month,
)

ROW = {"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"}


def write_csv(text: str) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return Path(f.name)


class ParseRow(unittest.TestCase):
    def test_reads_a_row(self) -> None:
        self.assertEqual(parse_row(ROW, 2), Expense(date(2026, 10, 3), "Taxi", Decimal("12.50"), "USD"))

    def test_bad_date_names_the_line(self) -> None:
        with self.assertRaisesRegex(ReportError, "line 7"):
            parse_row({**ROW, "date": "03/10/2026"}, 7)

    def test_bad_amount(self) -> None:
        with self.assertRaises(ReportError):
            parse_row({**ROW, "amount": "twelve"}, 2)

    def test_bad_currency(self) -> None:
        with self.assertRaisesRegex(ReportError, "3-letter"):
            parse_row({**ROW, "currency": "dollars"}, 2)


class ReadAndSummarise(unittest.TestCase):
    def test_reads_a_file(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,12.50,USD\n2026-10-05,Lunch,9,EUR\n")
        self.assertEqual([e.currency for e in read_expenses(path)], ["USD", "EUR"])

    def test_error_line_counts_the_header(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,x,USD\n")
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(path)

    def test_summary(self) -> None:
        expenses = [parse_row(ROW, 2), parse_row({**ROW, "date": "2026-09-30"}, 3)]
        self.assertEqual(summary(expenses), "2 expenses from 2026-09-30 to 2026-10-03")

    def test_summary_of_nothing(self) -> None:
        self.assertEqual(summary([]), "No expenses.")


def exp(day: str, amount: str, cur: str = "USD") -> Expense:
    return Expense(date.fromisoformat(day), "x", Decimal(amount), cur)


class ByMonth(unittest.TestCase):
    def test_sums_same_month_and_currency(self) -> None:
        got = totals_by_month([exp("2026-10-01", "10.10"), exp("2026-10-20", "0.20")])
        self.assertEqual(got, {"2026-10": {"USD": Decimal("10.30")}})

    def test_separate_currencies(self) -> None:
        got = totals_by_month([exp("2026-10-01", "1"), exp("2026-10-02", "2", "EUR")])
        self.assertEqual(got["2026-10"], {"USD": Decimal("1"), "EUR": Decimal("2")})

    def test_month_keys(self) -> None:
        got = totals_by_month([exp("2026-09-30", "1"), exp("2026-10-01", "2")])
        self.assertEqual(sorted(got), ["2026-09", "2026-10"])

    def test_chronological_across_years(self) -> None:
        text = format_by_month([exp("2026-01-05", "1"), exp("2025-12-05", "2")])
        self.assertLess(text.index("2025-12"), text.index("2026-01"))

    def test_format_exact(self) -> None:
        text = format_by_month([exp("2026-10-01", "9", "EUR"), exp("2026-10-02", "12.50"), exp("2026-09-01", "3")])
        self.assertEqual(text, "2026-09\n  USD 3\n\n2026-10\n  EUR 9\n  USD 12.50")

    def test_format_of_nothing(self) -> None:
        self.assertEqual(format_by_month([]), "No expenses.")


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_by_month_flag_either_side(self) -> None:
        path = str(write_csv("date,description,amount,currency\n2026-10-03,Taxi,12.50,USD\n"))
        a, b = self.run_cli("--by-month", path), self.run_cli(path, "--by-month")
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(a.stdout, "2026-10\n  USD 12.50\n")
        self.assertEqual(a.stdout, b.stdout)

    def test_by_month_without_file_exits_2(self) -> None:
        self.assertEqual(self.run_cli("--by-month").returncode, 2)

    def test_by_month_bad_row_exits_1(self) -> None:
        path = str(write_csv("date,description,amount,currency\n2026-10-03,Taxi,x,USD\n"))
        out = self.run_cli("--by-month", path)
        self.assertEqual(out.returncode, 1)
        self.assertIn("line 2", out.stderr)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


if __name__ == "__main__":
    unittest.main()
