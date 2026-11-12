import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from finance import ImportError, ledger_csv, money, summarize, transactions
from setup_local import setup


class FinanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def table(self, content, encoding="utf-8"):
        path = self.root / "input.csv"
        path.write_bytes(content.encode(encoding))
        return path

    def test_czech_and_english_money_exact_to_cents(self):
        for value in ("1 234,56", "1\u00a0234,56", "1.234,56", "1,234.56", "1234.56"):
            self.assertEqual(money(value), Decimal("1234.56"))
        self.assertEqual(money("−0,01"), Decimal("-0.01"))
        for value in ("NaN", "1,234", "1.2.3", "12 CZK", "1e5", "1,23.45"):
            with self.subTest(value=value), self.assertRaises(ImportError):
                money(value)

    def test_windows_1250_and_maybe_signs(self):
        source = self.table("Datum zaúčtování;Částka;Měna;Popis\n01.10.2026;-120,50;CZK;Nákup\n", "cp1250")
        bank = transactions(source, "kb")
        self.assertEqual(bank[0]["amount"], Decimal("-120.50"))
        source = self.table("date,amount,currency,name,account_name\n2026-10-01,120.50,CZK,Nákup,Checking\n")
        ledger = transactions(source, "maybe-export")
        self.assertEqual(ledger[0]["amount"], bank[0]["amount"])
        self.assertEqual(ledger[0]["kind"], "expense")

    def test_transfers_refunds_currencies_and_month_filter(self):
        source = self.table("date;amount;currency;kind;category\n2026-10-01;10000;CZK;income;Práce\n2026-10-02;-1000;CZK;expense;Jídlo\n2026-10-03;200;CZK;refund;Jídlo\n2026-10-04;-5000;CZK;transfer;Převod\n2026-10-05;-10;EUR;expense;Jídlo\n2026-09-05;-999;CZK;expense;Jídlo\n")
        report = summarize(transactions(source, "kb"), "2026-10")
        czk, eur = report["periods"]
        self.assertEqual(czk["expenses_after_refunds"], "800.00")
        self.assertEqual(czk["net_cash_movement"], "4200.00")
        self.assertEqual(czk["transfer_net"], "-5000.00")
        self.assertEqual(czk["categories"], {"Jídlo": "1000.00"})
        self.assertEqual(eur["expenses_after_refunds"], "10.00")
        self.assertEqual(report["source_range"]["from"], "2026-09-05")

    def test_identical_legitimate_purchases_are_retained(self):
        source = self.table("date;amount;currency;name\n2026-10-01;-20;CZK;Coffee\n2026-10-01;-20;CZK;Coffee\n")
        report = summarize(transactions(source, "kb"))
        self.assertEqual(report["periods"][0]["expenses_before_refunds"], "40.00")
        self.assertEqual(report["identical_rows_to_review"], 1)

    def test_recurring_three_months_and_names_omitted(self):
        source = self.table("date;amount;currency;name\n2026-08-05;-199;CZK;PRIVATE MERCHANT\n2026-09-05;-199;CZK;PRIVATE MERCHANT\n2026-10-05;-199;CZK;PRIVATE MERCHANT\n")
        report = summarize(transactions(source, "kb"), "2026-10")
        self.assertEqual(len(report["recurring_candidates_from_full_file"]), 1)
        self.assertNotIn("PRIVATE MERCHANT", json.dumps(report))

    def test_bad_rows_fail_instead_of_partial_import(self):
        for content in ("date;amount;currency\n2026-10-01;-10;CZK\n2026-10-02;bad;CZK\n",
                        "date;amount;currency\n2026-10-01;-10;CZK\n2026-10-02;-20\n",
                        "date;amount;currency\n2026-10-01;-10;BTC\n",
                        "date;amount;currency;kind\n2026-10-01;10;CZK;expense\n"):
            with self.subTest(content=content), self.assertRaises(ImportError):
                transactions(self.table(content), "kb")

    def test_ambiguous_mapping_requires_explicit_choice(self):
        source = self.table("Datum;Datum zaúčtování;Částka;Měna\n01.10.2026;02.10.2026;-10;CZK\n")
        with self.assertRaises(ImportError):
            transactions(source, "kb")
        self.assertEqual(transactions(source, "kb", {"date": "Datum zaúčtování"})[0]["date"], "2026-10-02")

    def test_rules_classify_transfers_without_affecting_other_rows(self):
        source = self.table("date;amount;currency;name\n2026-10-01;-1000;CZK;MOJE SPOŘENÍ\n2026-10-02;-20;CZK;Nákup\n")
        txs = transactions(source, "kb", rules=[{"contains": "moje sporeni", "kind": "transfer", "category": "Vlastní"}])
        self.assertEqual(txs[0]["kind"], "transfer")
        self.assertTrue(txs[0]["kind_confirmed"])
        self.assertEqual(summarize(txs)["periods"][0]["expenses_before_refunds"], "20.00")

    def test_import_bridge_keeps_bank_sign_and_escapes_formulas(self):
        source = self.table('date;amount;currency;name\n2026-10-01;-10;CZK;"=1+1"\n')
        rendered = ledger_csv(transactions(source, "kb"))
        self.assertIn("-10.00", rendered)
        self.assertIn("'=1+1", rendered)

    def test_private_output_no_overwrite_and_no_stdout_amounts(self):
        source = self.table("date;amount;currency;name\n2026-10-01;-12345.67;CZK;PRIVATE NAME\n")
        script = Path(__file__).with_name("finance.py")
        output = self.root / "report"
        cmd = [sys.executable, str(script), "analyze", str(source), "--source", "kb", "--output-dir", str(output)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertNotIn("PRIVATE NAME", result.stdout)
        self.assertNotIn("12345.67", result.stdout)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        for file in output.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("PRIVATE NAME", (output / "summary.json").read_text())
        before = (output / "summary.json").read_bytes()
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((output / "summary.json").read_bytes(), before)

    def test_synthetic_demo_totals(self):
        txs = transactions(Path(__file__).parent / "examples/kb-demo.csv", "kb")
        period = summarize(txs, "2026-10")["periods"][0]
        self.assertEqual(period["expenses_after_refunds"], "16569.50")
        self.assertEqual(period["net_cash_movement"], "20430.50")

    def test_bridge_round_trip_preserves_signs_and_transaction_kinds(self):
        txs = transactions(Path(__file__).parent / "examples/kb-demo.csv", "kb")
        before = summarize(txs, "2026-10")["periods"]
        path = self.root / "bridge.csv"
        path.write_text(ledger_csv(txs), encoding="utf-8")
        self.assertEqual(summarize(transactions(path, "generic"), "2026-10")["periods"], before)

    def test_local_setup_secrets_are_private_and_existing_file_preserved(self):
        self.assertTrue(setup(self.root))
        output = self.root / ".env.wonders"
        original = output.read_bytes()
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(output.read_text().splitlines()), 2)
        self.assertFalse(setup(self.root))
        self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
