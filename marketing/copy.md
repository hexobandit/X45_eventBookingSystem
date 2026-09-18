# Marketingová stránka — texty (návrh v1)

Jazyk: čeština. Cena se na stránce neuvádí — vždy jen „nezávazná nabídka".
Doména: **romansolutions.cz** (značka Roman Solutions), demo na **demo.romansolutions.cz**.
V textu `{BRAND}` = Roman Solutions, `{DEMO_URL}` = https://demo.romansolutions.cz (lokálně http://127.0.0.1:5000).

Pořadí sekcí = pořadí na stránce. Texty jsou psané tak, aby se daly vložit
do HTML rovnou; nadpisy H1/H2 označené.

---

## 1. Hero

**Eyebrow:** Web + rezervace + platby pro pořadatele kurzů

**H1:** Web pro vaše kurzy, který sám vybírá přihlášky, hlídá kapacitu a inkasuje platby.

**Podtitul:** Pro lektory, ordinace a školicí firmy, které pořádají několik kurzů ročně a dnes to řeší přes e‑mail, Excel a bankovní výpis.

**CTA primární:** Vyzkoušet demo → `{DEMO_URL}`
**CTA sekundární:** Nezávazně poptat → `#poptavka`

**Mikro-text pod tlačítky:** Vlastní doména. Bez provize z přihlášky. Platby přímo na váš účet.

---

## 2. Problém (poznáte se?)

**H2:** Přihlášky v e‑mailu, seznam v Excelu, platby ve výpisu.

Tři odstavce / tři karty:

- **„Je ještě místo?"** — Odpovídáte na to samé desetkrát týdně. Mezitím se dva lidé přihlásí na poslední místo a jeden z nich se to dozví až od vás.
- **Kdo zaplatil a kdo ne** — Procházíte výpis, hledáte jména a částky, pak to přepisujete do tabulky. Před kurzem stejně voláte těm, co nezaplatili.
- **Potvrzení, připomínky, informace k místu** — Každému zvlášť, ručně, večer po ordinaci. Když se termín posune, píšete všem znovu.

**Uzavírací věta:** Nic z toho není vaše práce. Vaše práce je učit.

---

## 3. Jak to funguje

**H2:** Tři kroky, žádná ruční práce.

1. **Účastník se přihlásí** na stránce kurzu — vidí program, lektora, cenu a kolik míst zbývá. Když je plno, zapíše se na čekací listinu.
2. **Přijde mu potvrzení a platební údaje** — e‑mail s QR kódem pro bankovní aplikaci a variabilním symbolem, nebo platba kartou rovnou při přihlášce.
3. **Vy vidíte zaplaceno** — v administraci máte seznam účastníků, stav plateb, export pro účetní a jedno tlačítko na připomínku před kurzem.

(Ke každému kroku screenshot z dema: stránka kurzu / e‑mail s QR / seznam registrací.)

---

## 4. Co všechno umí

**H2:** Víc než přihlašovací formulář.

Pět karet:

**Prodejní stránky kurzů**
Obsah, program, lektoři, fotky, co se účastník naučí. Marketingový web, ne jen formulář. Upravujete sami ve vizuálním editoru.

**Rezervace míst**
Kapacita se hlídá sama, i když se dva lidé přihlásí ve stejnou vteřinu. Čekací listina, časované otevření prodeje s odpočtem, možnost napojit externí registraci partnera.

**Platby**
Karta (Stripe) i převod s QR kódem — český QR platba v Kč i evropský SEPA v eurech. Párování přes variabilní symbol, přehled zaplaceno / nezaplaceno, platby chodí přímo na váš účet.

**Komunikace**
Automatické potvrzení přihlášky, platební údaje, připomínka před kurzem, potvrzení platby. Hromadné zprávy všem účastníkům kurzu. Každý odeslaný e‑mail je dohledatelný v logu.

**Administrace účastníků**
Export do Excelu / CSV / PDF, fakturační údaje, poznámky, audit kdo co změnil. Smazané registrace končí v archivu s důvodem — GDPR bez tabulek bokem.

---

## 5. Proč ne Eventbrite, SimplyBook nebo Reservio

**H2:** Platformy jsou skvělé na jednorázové akce. Tohle je pro lidi, kteří učí opakovaně.

Srovnávací tabulka (řádky = kritérium, sloupce = {BRAND} / platformy pro prodej vstupenek / rezervační SaaS):

| | {BRAND} | Eventbrite a podobné | SimplyBook, Reservio |
|---|---|---|---|
| Provize z každé přihlášky | žádná | ano, z každé vstupenky | měsíční licence podle funkcí |
| Vlastní doména a vzhled | ano, celý web je váš | stránka na jejich doméně | omezeně, jejich šablony |
| Platba převodem s QR a VS | ano | ne | většinou ne |
| Platby chodí | přímo na váš účet | přes platformu, výplata později | podle tarifu |
| Čekací listina, časované otevření | ano | částečně | částečně |
| Data účastníků | u vás, v EU | u platformy | u platformy |
| Přizpůsobení na míru | ano, je to váš web | ne | ne |

> Před zveřejněním ověřit aktuální poplatky a funkce konkurence. Nepsat konkrétní procenta, pokud nejsou z jejich ceníku k danému datu.

**Poznámka pod tabulkou:** Pokud pořádáte jednu akci ročně pro tisíc lidí, vezměte Eventbrite. Pokud učíte pravidelně desítky lidí a chcete, aby web pracoval za vás, čtěte dál.

---

## 6. Reference

**H2:** Běží to v praxi.

**Varianta A (po souhlasu klienta):**
ANTERIOR — kurzy estetické stomatologie pro lékaře z celé Evropy. Přihlášky, čekací listina, platby v korunách i eurech, e‑maily s QR kódem. Web, který jsme postavili, se stal jejich hlavním prodejním kanálem. → anteriorcourses.com

**Varianta B (anonymní, dokud není souhlas):**
Vzdělávací kurzy pro zubní lékaře — desítky účastníků ročně z několika zemí, platby v Kč i eurech, čekací listina, kompletní e‑mailová komunikace bez ruční práce. Referenci rádi sdělíme osobně.

---

## 7. Jak spolupráce probíhá

**H2:** Od první schůzky ke spuštění za 4–6 týdnů.

**Dvě varianty webu:**

- **Platba převodem s QR** — účastník po potvrzení dostane e‑mail s platebními údaji a QR kódem. Platbu potvrdíte jedním klikem v administraci, systém pošle potvrzení a drží místo.
- **Platba kartou online + převod** — vše z první varianty a navíc platba kartou rovnou při přihlášce (Stripe). Platba se potvrdí sama, místo se rezervuje okamžitě. Bránu si účtuje Stripe, ne my.

**Provoz:** hosting na vlastní doméně, HTTPS, denní zálohy, monitoring dostupnosti, aktualizace a měsíční report (návštěvnost, registrace, tržby). Jedna měsíční částka, žádné překvapení.

**Co od vás budeme potřebovat:**
1. Kurzy — názvy, termíny, kapacita, ceny, anotace, informace o lektorech
2. Texty — pár vět o vás, kontakty, fakturační údaje a číslo účtu pro platby
3. Fotky — z kurzů nebo z praxe; co máte, zbytek dořešíme
4. Logo — a název použitého fontu, ať prověříme licenci
5. Doména — stávající, subdoména nebo nová; poradíme

**CTA:** Poptat nezávaznou nabídku → `#poptavka`

---

## 8. Co se dá přikoupit

**H2:** Rozšíření, když je budete potřebovat.

Dvě skupiny — poctivě oddělit, co existuje a co se staví na objednávku:

**Hotové, zapíná se:**
- platba kartou (Stripe)
- SEPA platby v eurech pro zahraniční účastníky
- externí registrace u partnera (odkaz místo formuláře)
- sběr kontaktů pro marketing se souhlasem GDPR + hromadné e‑maily

**Na objednávku:**
- automatické připomínky před kurzem (den / týden předem, bez klikání)
- čekací listina s automatickou nabídkou uvolněného místa
- certifikáty o absolvování (PDF automaticky e‑mailem)
- slevové kódy a early‑bird ceny
- anglická verze webu pro zahraniční účastníky
- napojení na fakturační systém

---

## 9. Časté otázky

**Komu patří web a data?**
Vám. Web běží na vaší doméně, data účastníků jsou ve vaší databázi na serveru v EU. Když skončíte, dostanete zálohu a kód.

**Můžu si sám měnit texty a přidávat kurzy?**
Ano. Kurzy, program, lektory, fotky a ceny upravujete ve vizuálním editoru v administraci. Žádné školení není potřeba — ukážeme vám to na první schůzce po spuštění.

**Co když nechci platby kartou?**
Nemusíte. Převod s QR kódem stačí většině pořadatelů. Kartu jde zapnout kdykoli později.

**Jak dlouho to trvá?**
Při dodání podkladů do dvou týdnů od schůzky obvykle spouštíme za 4–6 týdnů.

**Co se stane, když přestanu platit provoz?**
Web běží do konce zaplaceného období, pak vám předáme zálohu dat a kód. Nic vám nedržíme jako rukojmí.

**Je to GDPR v pořádku?**
Ano. Souhlasy se ukládají s datem, smazané registrace jdou do archivu s důvodem, každý e‑mail je zalogovaný. Zásady zpracování dodáme jako součást webu.

**Zvládne to nápor, když otevřu prodej?**
Kapacita se hlídá na úrovni databáze — dva lidé nikdy nedostanou stejné poslední místo. Otevření prodeje můžete načasovat a účastníci vidí odpočet.

---

## 10. O mně

**H2:** Kdo to staví.

Jméno, jedna fotka, jeden odstavec (doplní autor):

Stavím weby a interní systémy pro malé firmy {N} let. Tenhle systém vznikl, protože jsem viděl, jak lektoři tráví večery přepisováním přihlášek z e‑mailu do tabulky. První verze běží v ostrém provozu od {rok} a každý další web z ní čerpá. Ozvěte se, pošlu vám demo s vašimi kurzy.

IČO a sídlo v patičce.

---

## 11. Poptávka (`#poptavka`)

**H2:** Pošlete mi, co učíte. Vrátím vám nabídku.

Tři přímé kontakty, žádný formulář:
- WhatsApp → `https://wa.me/{TEL}?text=Dobrý%20den,%20mám%20zájem%20o%20web%20pro%20kurzy`
- E‑mail → `mailto:{EMAIL}?subject=Web%20pro%20kurzy`
- Telefon → `{TEL}`

**Text:** Stačí dvě věty: co učíte a kolikrát ročně. Ozvu se do dvou pracovních dnů.

---

## 12. Patička

{BRAND} · {Jméno} · IČO {IČO} · {Město}
Odkazy: Demo · Zásady zpracování osobních údajů · Kontakt

---

## SEO

- **Title:** Web a rezervační systém pro kurzy a workshopy | {BRAND}
- **Meta description:** Web pro vaše kurzy, který sám vybírá přihlášky, hlídá kapacitu a inkasuje platby. Vlastní doména, bez provize, platby přímo na váš účet. Pro lektory, ordinace a školicí firmy.
- **Klíčové fráze:** rezervační systém pro kurzy, registrace na kurz online platba, web pro školení a workshopy, prodej vstupenek bez provize, QR platba kurz
- **OG obrázek:** 1200×630, H1 věta + screenshot stránky kurzu
- **JSON‑LD:** `Service` (název, popis, poskytovatel) + `Organization`
