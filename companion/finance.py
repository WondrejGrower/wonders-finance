#!/usr/bin/env python3
"""Local, deterministic CSV preparation for Wonders Finance. No network access."""

import argparse
import csv
import io
import json
import os
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


class ImportError(ValueError):
    pass


def normalized(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", value)
                            if not unicodedata.combining(c)).lower().split())


ALIASES = {
    "date": ["date", "datum", "datum zaúčtování", "datum provedení", "datum transakce"],
    "amount": ["amount", "částka", "objem", "zaúčtovaná částka"],
    "name": ["name", "název", "popis", "popis transakce", "název protiúčtu", "název obchodníka"],
    "currency": ["currency", "měna", "měna účtu"],
    "category": ["category", "kategorie"],
    "account": ["account", "account_name", "účet", "číslo účtu"],
    "kind": ["kind", "druh"],
}
KINDS = {"income", "expense", "transfer", "investment", "refund"}


def money(value):
    """Strict two-decimal currencies; accepts Czech and English grouping."""
    value = re.sub(r"[\s\u00a0\u202f]", "", value).replace("−", "-")
    if len(value) > 32 or not re.fullmatch(r"[+-]?\d[\d.,]*", value):
        raise ImportError("Neplatná částka; očekávám číslo bez měnové značky.")
    if "," in value and "." in value:
        decimal = "," if value.rfind(",") > value.rfind(".") else "."
        grouping = "." if decimal == "," else ","
        left, right = value.rsplit(decimal, 1)
        if not re.fullmatch(r"[+-]?\d{1,3}(?:" + re.escape(grouping) + r"\d{3})+", left):
            raise ImportError("Neplatné oddělovače tisíců.")
        value = left.replace(grouping, "") + "." + right
    else:
        value = value.replace(",", ".")
    try:
        result = Decimal(value)
        if not result.is_finite() or result != result.quantize(Decimal("0.01")):
            raise InvalidOperation
        return result
    except InvalidOperation:
        raise ImportError("Částka musí mít nejvýše dvě desetinná místa.") from None


def parsed_date(value):
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d. %m. %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    raise ImportError("Datum musí mít formát RRRR-MM-DD nebo DD.MM.RRRR.")


def read_table(path):
    if Path(path).stat().st_size > 30_000_000:
        raise ImportError("Soubor přesahuje 30 MB; rozděl export na kratší období.")
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1250")
    try:
        dialect = csv.Sniffer().sniff(text[:16000], delimiters=";,\t")
        rows = list(csv.reader(io.StringIO(text), dialect=dialect, strict=True))
    except csv.Error:
        raise ImportError("Nerozpoznané CSV; očekávám tabulku s hlavičkou.") from None
    # Excel's optional separator directive is not a transaction.
    if rows and rows[0] and rows[0][0].lower().startswith("sep="):
        rows = rows[1:]
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise ImportError("Soubor je prázdný.")
    headers = [cell.strip() for cell in rows[0]]
    if len({normalized(h) for h in headers}) != len(headers):
        raise ImportError("Hlavička obsahuje duplicitní názvy sloupců.")
    return headers, rows[1:]


def load_rules(path):
    if not path:
        return []
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rules, list):
        raise ImportError("Pravidla musí být JSON seznam.")
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("contains"), str) or not rule["contains"].strip():
            raise ImportError("Pravidlo musí obsahovat neprázdné contains.")
        if rule.get("kind") and rule["kind"] not in KINDS:
            raise ImportError("Neznámý druh transakce v pravidlech.")
        if "category" in rule and not isinstance(rule["category"], str):
            raise ImportError("Kategorie pravidla musí být text.")
    return rules


def transactions(path, source, mapping=None, rules=None):
    headers, rows = read_table(path)
    mapping = mapping or {}
    columns = {}
    for field, aliases in ALIASES.items():
        wanted = [normalized(mapping[field])] if field in mapping else [normalized(a) for a in aliases]
        matches = [i for i, header in enumerate(headers) if normalized(header) in wanted]
        if len(matches) > 1:
            raise ImportError(f"Více sloupců pro {field}; vyber jej pomocí --{field}-column.")
        if field in mapping and not matches:
            raise ImportError(f"Zadaný sloupec pro {field} chybí.")
        if matches:
            columns[field] = matches[0]
    if not {"date", "amount", "currency"} <= columns.keys():
        raise ImportError("Chybí datum, částka nebo měna. Použij CSV s hlavičkou a případně --date-column, --amount-column, --currency-column. KB účetní CSV bez hlavičky zatím nepodporujeme.")
    result = []
    for line, row in enumerate(rows, start=2):
        if len(row) != len(headers):
            raise ImportError(f"Řádek {line}: počet polí neodpovídá hlavičce; nic nebylo importováno.")
        values = {field: row[index].strip() for field, index in columns.items()}
        try:
            amount = money(values["amount"])
            if source == "maybe-export":
                amount = -amount  # Entry.amount: positive is an expense in upstream Rails.
            currency = values["currency"].upper()
            if currency not in {"CZK", "EUR", "USD"}:
                raise ImportError("Podporované měny jsou CZK, EUR a USD; jiné nepřepočítávám.")
            tx = {"date": parsed_date(values["date"]), "amount": amount, "currency": currency,
                  "name": values.get("name", ""), "account": values.get("account", ""),
                  "category": values.get("category") or "Nezařazené",
                  "kind": values.get("kind") or ("income" if amount > 0 else "expense"),
                  "kind_confirmed": bool(values.get("kind"))}
            for rule in rules or []:
                if normalized(rule["contains"]) in normalized(tx["name"]):
                    tx["category"] = rule.get("category", tx["category"])
                    if rule.get("kind"):
                        tx["kind"] = rule["kind"]
                        tx["kind_confirmed"] = True
                    break
            if tx["kind"] not in KINDS:
                raise ImportError("Druh musí být income, expense, transfer, investment nebo refund.")
            if (tx["kind"] in {"income", "refund"} and amount < 0) or (tx["kind"] == "expense" and amount > 0):
                raise ImportError("Znaménko částky neodpovídá druhu transakce.")
            result.append(tx)
        except ImportError as error:
            raise ImportError(f"Řádek {line}: {error}") from None
    if not result:
        raise ImportError("Soubor neobsahuje transakce.")
    return result


def summarize(txs, month=None):
    selected = [tx for tx in txs if not month or tx["date"].startswith(month)]
    if not selected:
        raise ImportError("Pro zvolené období nejsou žádné transakce.")
    groups = defaultdict(list)
    for tx in selected:
        groups[(tx["date"][:7], tx["currency"])].append(tx)
    periods = []
    for (period, currency), items in sorted(groups.items()):
        def total(kind):
            return sum((tx["amount"] for tx in items if tx["kind"] == kind), Decimal(0))
        categories = defaultdict(lambda: Decimal(0))
        for tx in items:
            if tx["kind"] == "expense":
                categories[tx["category"]] -= tx["amount"]
        periods.append({"month": period, "currency": currency, "transactions": len(items),
                        "income": f"{total('income'):.2f}", "expenses_before_refunds": f"{-total('expense'):.2f}",
                        "refunds": f"{total('refund'):.2f}",
                        "expenses_after_refunds": f"{-total('expense') - total('refund'):.2f}",
                        "net_cash_movement": f"{sum((t['amount'] for t in items), Decimal(0)):.2f}",
                        "transfer_net": f"{total('transfer'):.2f}", "investment_net": f"{total('investment'):.2f}",
                        "categories": {k: f"{v:.2f}" for k, v in sorted(categories.items(), key=lambda p: -p[1])}})
    # Keep identical rows: two equal card charges can both be legitimate.
    fingerprints = Counter((t["date"], str(t["amount"]), t["currency"], t["name"], t["account"]) for t in selected)
    # Monthly recurring candidates need 3 distinct months and 20–40 day gaps.
    # Multiple purchases in any month disqualify the candidate. This is not a subscription detector.
    recurring = defaultdict(list)
    for tx in txs:
        if tx["kind"] == "expense" and tx["name"]:
            recurring[(normalized(tx["name"]), tx["account"], tx["currency"])].append(tx)
    candidates = []
    for items in recurring.values():
        items.sort(key=lambda t: t["date"])
        amounts = [-t["amount"] for t in items]
        dates = [date.fromisoformat(t["date"]) for t in items]
        if (len(items) >= 3 and len({d.strftime('%Y-%m') for d in dates}) == len(items)
                and all(20 <= (b - a).days <= 40 for a, b in zip(dates, dates[1:]))
                and min(amounts) > 0 and max(amounts) <= min(amounts) * Decimal("1.05")):
            candidates.append({"reference": f"R{len(candidates)+1}", "currency": items[0]["currency"],
                               "category": items[-1]["category"], "occurrences": len(items),
                               "last_amount": f"{amounts[-1]:.2f}", "last_date": dates[-1].isoformat(),
                               "status": "candidate_needs_confirmation"})
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_range": {"from": min(t["date"] for t in txs), "to": max(t["date"] for t in txs)},
            "selected_month": month, "coverage": "unverified_statement_completeness",
            "classification": "provisional_until_transfers_and_refunds_reviewed",
            "uncategorized_rows": sum(t["category"] == "Nezařazené" for t in selected),
            "unconfirmed_kind_rows": sum(not t["kind_confirmed"] for t in selected),
            "identical_rows_to_review": sum(n-1 for n in fingerprints.values() if n > 1),
            "periods": periods, "recurring_candidates_from_full_file": candidates,
            "notes": ["Čistý pohyb není zůstatek ani výše úspor.",
                      "Měny se nesčítají. Převody, investice a vratky je třeba označit.",
                      "Shodné řádky zůstaly započítané; ověř případné duplicity.",
                      "Kandidáti opakovaných plateb nejsou potvrzená předplatná."]}


def report_markdown(report):
    lines = ["# Finanční podklad pro Boba", "", "Souhrn importovaných dat; úplnost výpisu zatím není ověřená.",
             "Částky a kategorie jsou podklad, nikoli automatické doporučení.", ""]
    for period in report["periods"]:
        lines.extend([f"## {period['month']} · {period['currency']}", "",
                      f"Příchozí platby označené jako příjem: {period['income']}",
                      f"Výdaje před vratkami: {period['expenses_before_refunds']}",
                      f"Označené vratky: {period['refunds']}",
                      f"Čistý pohyb peněz: {period['net_cash_movement']}", "", "Kategorie výdajů:", ""])
        lines.extend(f"- {key}: {value}" for key, value in period["categories"].items())
        lines.append("")
    lines.extend(["## Před doporučením ověřit", "",
                  f"- Nezařazené řádky: {report['uncategorized_rows']}",
                  f"- Nepotvrzený druh transakce: {report['unconfirmed_kind_rows']}",
                  f"- Shodné řádky k prověření: {report['identical_rows_to_review']}",
                  "- Úplnost výpisu, převody mezi vlastními účty a případné vratky.", ""])
    lines.extend(f"- {note}" for note in report["notes"])
    return "\n".join(lines) + "\n"


def safe_cell(value):
    # Export is intended for the ledger and spreadsheet previews, never formulas.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def ledger_csv(txs):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["date", "amount", "name", "currency", "category", "account", "kind", "notes"])
    for tx in txs:
        writer.writerow([tx["date"], f"{tx['amount']:.2f}", safe_cell(tx["name"]), tx["currency"],
                         safe_cell(tx["category"]), safe_cell(tx["account"]), tx["kind"], f"kind={tx['kind']}"])
    return output.getvalue()


def private_write(path, content):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists():
        raise ImportError("Výstup už existuje; zvol nový adresář. Existující soubory nepřepisuji.")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
        stream.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Vypíše pouze názvy sloupců, nikoli transakce.")
    inspect.add_argument("csv", type=Path)
    analyze = sub.add_parser("analyze", help="Vytvoří lokální podklady pro Codex a import do účetní aplikace.")
    analyze.add_argument("csv", type=Path)
    analyze.add_argument("--source", choices=["kb", "generic", "maybe-export"], required=True)
    analyze.add_argument("--month", help="RRRR-MM; bez volby všechny měsíce samostatně.")
    analyze.add_argument("--rules", type=Path)
    analyze.add_argument("--output-dir", type=Path)
    for field in ALIASES:
        analyze.add_argument(f"--{field}-column")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            print(json.dumps({"columns": read_table(args.csv)[0]}, ensure_ascii=False, indent=2))
            return
        if args.month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", args.month):
            raise ImportError("Měsíc musí mít formát RRRR-MM.")
        mapping = {field: getattr(args, f"{field}_column") for field in ALIASES
                   if getattr(args, f"{field}_column")}
        txs = transactions(args.csv, args.source, mapping, load_rules(args.rules))
        report = summarize(txs, args.month)
        if args.output_dir:
            output = args.output_dir.expanduser()
            output.mkdir(mode=0o700, parents=True, exist_ok=True)
            if any(output.iterdir()):
                raise ImportError("Výstupní adresář musí být prázdný; existující data neměním.")
            output.chmod(0o700)
        else:
            base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "wonders-finance/reports"
            base.mkdir(mode=0o700, parents=True, exist_ok=True)
            output = Path(tempfile.mkdtemp(prefix="report-", dir=base))
        private_write(output / "summary.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        private_write(output / "report.md", report_markdown(report))
        private_write(output / "ledger-import.csv", ledger_csv(txs))
        print(f"Hotovo. Lokální podklady: {output}")
        print("ledger-import.csv obsahuje celý soubor; filtr měsíce se vztahuje jen na souhrn.")
    except (ImportError, OSError, UnicodeError, json.JSONDecodeError) as error:
        parser.exit(2, f"Import se nezdařil: {error}\n")


if __name__ == "__main__":
    main()
