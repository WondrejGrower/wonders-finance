# Wonders Finance + Home

Osobní finanční přehled pro Wondreje a návrh domovské obrazovky notebooku s Omarchy.
Základ: **Maybe Finance**, archivovaný Rails ledger. Tento fork není spojený
s Maybe Finance Inc., není jí podporovaný ani schválený. Původní historie,
autorské údaje a [licence AGPLv3](LICENSE) zůstávají zachované.

## Otevřít návrh hubu

Bez instalace, účtu, serveru nebo připojení k bance:

```bash
xdg-open hub/index.html
```

V tmavém přírodním přehledu jsou klima pěstírny, Home Assistant Green,
Bitcoin Forest a vstup do osobních financí. Finance se otevírají samostatně;
ukázkový měsíc je nutné výslovně rozbalit. Klima a finanční údaje jsou syntetické.
Toto je interaktivní návrh, nikoli již propojený dashboard. Lokální soubory
neodesílají žádné požadavky; odkazy otevřou služby teprve na kliknutí.

## Mobil mimo domov

Požadavek je přístupný přehled také z telefonu v práci. Po skutečném nasazení
ho může obsluhovat stále zapnutý notebook přes soukromé připojení Tailscale;
prohlížeč v mobilu pak zobrazí webovou verzi. Notebook musí být online a neuspaný.
Současný návrh je pouze lokální soubor a vzdálený přístup ještě není nastavený.
Odkazy na `127.0.0.1` a `homeassistant.local` jsou pro notebook v domácí síti,
pro mobilní provoz je potřeba nastavit odpovídající privátní adresy služeb.
Podrobnosti jsou v [plánu](docs/WONDERS_PLAN.md#mobil-v-práci).

## Lokální analýza výpisu

Požadavky: Python **3.12+**, bez dalších balíčků. Spouštěj z kořene projektu.
První bezpečná zkouška na přiložených vymyšlených datech:

```bash
python3 companion/finance.py inspect companion/examples/kb-demo.csv
python3 companion/finance.py analyze companion/examples/kb-demo.csv --source kb --month 2026-10
```

Příkaz vypíše cestu k soukromému adresáři se `summary.json`, `report.md`
a `ledger-import.csv`. Výchozí umístění je
`${XDG_STATE_HOME:-~/.local/state}/wonders-finance/reports/`; oprávnění adresáře
jsou 700, souborů 600. Existující výstupy nepřepisujeme. Nikdy nepoužívej skutečné
výpisy jako testovací fixture ani je nepřidávej do veřejného repozitáře.

Vlastní CSV s hlavičkou z Komerční banky:

```bash
python3 companion/finance.py inspect /cesta/k/vypisu.csv
python3 companion/finance.py analyze /cesta/k/vypisu.csv --source kb --month 2026-10
```

Očekáváme sloupce datum, částka a měna. Volitelné: popis, kategorie, účet a druh.
Názvy lze vybrat pomocí `--date-column "Datum zaúčtování"` a obdobně
`--amount-column`, `--currency-column`, `--name-column`, `--account-column`,
`--category-column`, `--kind-column`. Přijímáme UTF-8 nebo Windows-1250,
středník/čárku/tabulátor, datum `DD.MM.RRRR` nebo `RRRR-MM-DD`. Odchozí platba
je záporná, příchozí kladná. Měny CZK/EUR/USD zůstávají oddělené.

Konkrétní výpis Wondrejovy KB ještě nebyl ověřený. Adaptér nepodporuje PDF,
bankovní API ani KB účetní CSV bez hlavičky. Při chybě tabulku odmítne; nevynechává
potichu neplatné řádky. Ukázková fixture neprokazuje kompatibilitu všech KB exportů.

Bez vlastního zařazení je druh platby jen odhad podle znaménka. Převod na vlastní
spoření, nákup investice a vratku označ pomocí sloupce `kind`/`Druh` nebo
`--rules /cesta/k/pravidlum.json`. [Ukázka pravidel](companion/examples/rules.example.json)
používá `contains`, `category` a volitelný `kind`: `income`, `expense`, `refund`,
`transfer`, `investment`. Použije se první odpovídající pravidlo.

Nástroj analyzuje jeden soubor, nevede databázi importů. Shodné řádky ponechává
a upozorní na ně. Úplnost výpisu a skutečné druhy plateb je nutné ověřit, než
začneme porovnávat měsíce nebo tvrdit, kolik lze ušetřit. Čistý pohyb peněz není
zůstatek účtu. Kandidát opakované platby není potvrzené předplatné.

## Bob v Codexu

Skill je v [skills/wonders-finance/SKILL.md](skills/wonders-finance/SKILL.md).
V této instalaci je dostupný přes uživatelský adresář `~/.agents/skills/`.
Pro přenos do jiného prostředí z tohoto projektu:

```bash
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/wonders-finance" ~/.agents/skills/wonders-finance
```

V Codexu pak například:

> $wonders-finance Bobe, vyhodnoť utrácení za říjen z výpisu /cesta/k/vypisu.csv.

> Bobe, které platby se opakují a co má smysl prověřit?

Výpočty běží lokálně bez sítě. Interpretace se skillem běží prostřednictvím
nastaveného modelu v Codexu, nejde o lokálně hostovaný AI model. Nástroj sám
Codex nespouští ani neposílá výpisy na internet. Není to samostatně běžící agent
na pozadí. Původní API chat v Rails aplikaci není potřeba pro tento postup zapínat.

## Most do ledgeru

`ledger-import.csv` má bankovní znaménka a datum `%Y-%m-%d`. V průvodci importem
vyber **kladné příjmy / inflows_positive**, desetinnou tečku a odpovídající sloupce.
Obsahuje celý vstupní soubor; měsíční filtr omezí pouze souhrn. Druh platby je
zachovaný v poznámce, nepáruje automaticky převody v ledgeru. Opakovaný ruční
import může vytvořit duplicity.

Zpět lze analyzovat `transactions.csv` z rodinného ZIP exportu ledgeru:

```bash
python3 companion/finance.py analyze /cesta/k/transactions.csv --source maybe-export
```

Tento export má opačná znaménka (kladná částka je výdaj); přepínač je převrátí.
CSV neexportuje vazby převodů ani jejich druh, proto je nutné je znovu ověřit
nebo použít pravidla. Nezaměňuj jej s `ledger-import.csv`.

## Samotná Rails aplikace

Původní požadavky: Ruby **3.4.4**, PostgreSQL a Redis; viz [upstream README](README.upstream.md).
Pro osobní instalaci je připravené `compose.wonders.yml`, které sestavuje **tento
fork**, ne archivovaný předpřipravený image. Poslouchá jen na `127.0.0.1:3000`.
Původní guide je historický podklad, zde používej nový compose.

```bash
python3 companion/setup_local.py
docker compose --env-file .env.wonders -f compose.wonders.yml config --quiet
docker compose --env-file .env.wonders -f compose.wonders.yml up -d --build
```

První příkaz vytvoří lokální náhodné klíče a heslo s oprávněním 600, nic nevypisuje.
Existující prostředí nemění. Je potřeba funkční oprávněný přístup k Dockeru.
V tomto sezení je přístup k Docker socketu odmítnutý, takže sestavení a běh Rails
**nebyly ověřeny**. Konfigurace systému, skupiny ani služby se neměnily.
Bankovní napojení, živá data hubu a chat přímo ve finančním UI zatím připojené nejsou.

## Ověření

Deterministické finanční chování:

```bash
python3 -m unittest discover -s companion -p 'test_*.py' -v
```

Prohlížečová kontrola: Node **22+**, Playwright **1.64.1**, systémové Chromium.
Playwright je výhradně vývojová pomůcka. Lze jej nainstalovat do dočasné složky:

```bash
npm install --prefix /tmp/wonders-hub-check --ignore-scripts --no-audit --no-fund playwright@1.64.1
PLAYWRIGHT_MODULE=/tmp/wonders-hub-check/node_modules/playwright node hub/browser.test.mjs
```

Test zkouší desktop, notebook, mobil, skrytí finanční ukázky, přepínání a dialogy;
kontroluje, že nevznikají externí požadavky ani horizontální přetékání. Náhledy
vznikají v ignorovaném `hub/previews/`. Rails testy zatím spuštěné nebyly.

Rozsah prvního kroku, omezení a další postup: [WONDERS_PLAN.md](docs/WONDERS_PLAN.md).
