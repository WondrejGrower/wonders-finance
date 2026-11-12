# Wonders Home + Wonders Finance

První základ pro Wondrejův notebook s Omarchy, 12. listopadu 2026.

## Rozdělení práce zařízení

Home Assistant Green má provozovat domácnost a automatizace. Notebook slouží
jako přehledový displej a běžné pracovní prostředí. Finanční aplikace a Codex
patří na notebook, případně později na samostatný server; první návrh s jejich
instalací do Green nepočítá.

Hub v `hub/` je lokální HTML návrh: domov, klima, vstup do Home Assistantu,
Bitcoin Forest a samostatná finanční stránka. Nezapisuje konfiguraci Omarchy,
nemění zámek ani playlist KioskChy, nevolá žádné externí služby. Čas je skutečný,
klimatické a finanční údaje jsou označené ukázky. Odkazy na Home Assistant
a Forest pouze otevřou jejich adresy na kliknutí; dostupnost neověřují.
Schování částek je vizuální výchozí stav, nikoli autentizace nebo zámek.

## Mobil v práci

Wondrej chce hub zobrazovat také mimo domov a notebook nechává běžet stále.
Pro finální provoz počítáme se soukromou webovou službou a připojením telefonu
přes Tailscale. Notebook musí mít připojení k internetu a nesmí být uspaný;
stačí vypnutý displej. Přístup z mobilu je součástí požadavků, nyní ještě
není nastavený ani otestovaný. Tailscale na notebooku není nainstalovaný.

Prototyp je už přizpůsobený mobilu. Současné odkazy na `homeassistant.local`
a `127.0.0.1` jsou pro domácí notebook: z telefonu mimo domov nefungují stejně.
Při skutečném nasazení je nahradíme adresami dosažitelnými přes privátní síť.
Home Assistant Green bude potřebovat vlastní přístup přes VPN nebo směrování
sítě; samotný VPN přístup na notebook ho automaticky nezpřístupní.

Pro finanční aplikaci použít Tailscale **Serve**, jehož přístup zůstává v tailnetu,
s pravidly pouze pro Wondrejova schválená zařízení a přihlášením do aplikace.
Účet a přihlášení telefonu/notebooku ještě zbývají. Tato fáze nemění router,
oprávnění Dockeru, uspávání ani žádné nastavení vzdáleného přístupu.

Zdroje: [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve),
[Tailscale quickstart](https://tailscale.com/docs/how-to/quickstart),
[vzdálený přístup k Home Assistantu](https://www.home-assistant.io/docs/configuration/remote/).

## Finanční tok

1. Wondrej stáhne CSV z Komerční banky.
2. `companion/finance.py` lokálně ověří tabulku, datum, znaménka a měny.
3. Vytvoří souhrny pro každý měsíc a měnu; převody a vratky vyžadují klasifikaci.
4. Codex se skillem `wonders-finance` přečte souhrn a vysvětlí utrácení v češtině.
5. Volitelný `ledger-import.csv` lze ručně nahrát do aplikace odvozené z Maybe.
6. Pro další analýzu lze použít také její rodinný export `transactions.csv`.

Tím vzniká použitelný souborový most do ledgeru; není to zatím vestavěný chat
ani automatická synchronizace databáze. Výpočty nevytváří jazykový model.
Při interpretaci přes Codex se použije jeho nastavený model; nejde o tvrzení,
že AI běží offline. Není potřeba zapínat původní OpenAI API chat v Rails aplikaci.

## Hotové v prvním kroku

- Vlastní GitHub fork `WondrejGrower/wonders-finance`, původní historie a AGPLv3.
- Přehled domova a finanční návrh s desktopovým a mobilním zobrazením.
- CSV s hlavičkou, UTF-8/Windows-1250, české částky a explicitní mapování sloupců.
- Oddělené měny CZK/EUR/USD a správná inverze znamének u exportu z ledgeru.
- Nezařazené položky, upozornění na stejné řádky, označené převody/investice/vratky.
- Kandidáti měsíčních plateb z alespoň tří měsíců, bez automatického rušení.
- Codex skill, lokální souhrny s oprávněním 600 v adresáři 700.

## Co vyžaduje skutečná data nebo další implementaci

- Ověřit konkrétní export z Wondrejovy KB/KB+. Ukázka je syntetická,
  není potvrzeným bankovním exportem. KB má i formát účetních dat bez hlavičky,
  který tento adaptér nepodporuje. Soukromý a podnikatelský export se mohou lišit.
- Spustit a ověřit Rails ledger. Docker je nainstalovaný, aktuální uživatel nemá
  oprávnění k jeho socketu. Nastavení oprávnění ani systémových služeb se neměnilo.
- Prověřit a průběžně aktualizovat závislosti archivovaného Rails projektu
  před dlouhodobým provozem se skutečnými finančními daty.
- Potvrdit kategorizaci, všechny vlastní účty, pravidelné příjmy a Wondrejovy cíle.
- Historie importů a deduplikace překrývajících se výpisů; nyní zpracovat jeden
  soudržný soubor a neopakovat ručně import do ledgeru bez kontroly.
- Propojit živý přehled financí do UI, případně řízené spuštění Codex analýzy.
- Připojit Green a skutečné klimatické hodnoty; teprve potom případný automatický
  start hubu nebo přidání do KioskChy.

## Zdroje rozhodnutí

- [Archivovaný upstream a pokyny pro forky](https://github.com/maybe-finance/maybe).
- [Znaménka a export ledgeru](../app/models/family/data_exporter.rb),
  [nastavení importu](../app/models/import/row.rb).
- [KB: formát účetního CSV, nikoli obecný retailový export](https://mojebanka.kb.cz/file/cs/format_CSV_KB.pdf).
- [KB+: možnosti PDF a CSV výpisů](https://www.kb.cz/cs/podpora/mobilni-aplikace/pruvodce-kb/co-dalsiho-kbplus-nabizi).
- [Official OpenAI documentation: lokální skills](https://learn.chatgpt.com/docs/build-skills).
