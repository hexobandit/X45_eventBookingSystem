# Cenová nabídka — školicí web Paudent (WhatsApp)

> Zpráva je připravená ke zkopírování do WhatsApp (formátování `*tučně*`
> WhatsApp umí). Klidně ji rozděl na dvě zprávy v místě oddělovače.

---

## Zpráva 1 — nabídka

Dobrý den, posílám slíbenou orientační nabídku k webu pro školení, jak jsme se bavili 9. 9.

*Co web umí v obou variantách:*
- prezentace kurzů (termíny, program, lektor, ceny)
- registrace účastníků s potvrzením e-mailem
- automatické hlídání kapacity kurzu + čekací listina
- administrace: přehled přihlášek, plateb, e-maily účastníkům, export
- provoz na vlastní doméně, HTTPS, zálohy

*Varianta A — platba převodem (QR):* 45 000 Kč
Po potvrzení registrace přijde účastníkovi e-mail s platebními údaji a QR kódem pro bankovní aplikaci. Platbu potvrzujete jedním klikem v administraci, systém pak sám pošle potvrzení a drží kapacitu.

*Varianta B — platební brána (karta online):* 53 000 Kč
Vše z varianty A + účastník může zaplatit kartou ihned při registraci (Stripe). Platba se potvrdí sama, místo se rezervuje okamžitě, bez ruční práce. Brána si účtuje ~1,5–2,5 % z transakce (poplatek Stripe, ne můj).

Doporučuji variantu B — proces je pak plně automatický a působí profesionálně, převod s QR zůstává jako druhá možnost pro ty, kdo kartou platit nechtějí.

*Provoz:* hosting + údržba + denní zálohy + monitoring dostupnosti a měsíční report (návštěvnost, registrace, tržby) — cca 800–1 200 Kč/měsíc, doména ~300 Kč/rok.

*Co se dá přikoupit později (funguje to už u podobného řešení):*
- automatické připomínky účastníkům před kurzem (den/týden předem)
- čekací listina s automatickou nabídkou uvolněného místa
- sběr kontaktů pro marketing (souhlasy GDPR) + hromadné e-maily účastníkům
- kontaktní/poptávkový formulář s antispamem
- vícejazyčnost (EN verze pro zahraniční lékaře)
- certifikáty o absolvování kurzu (PDF automaticky e-mailem)
- slevové kódy / early-bird ceny

*Termín:* při dodání podkladů do konce září zvládneme spuštění v říjnu / začátkem listopadu.

---

## Zpráva 2 — co od Vás budu potřebovat

Abychom mohli začít, poprosím o tyto podklady:

1. *Kurzy* — názvy, termíny, kapacita, ceny, anotace/program, informace o lektorovi
2. *Texty webu* — pár vět o Vás / o klinice, kontakty, fakturační údaje (IČO, číslo účtu pro platby)
3. *Fotky* — z ordinace/školení, portrét; stačí co máte, zbytek dořešíme
4. *Logo* — soubor loga a hlavně *název použitého fontu*, ať prověřím licenci pro komerční užití (u rychle generovaných log bývá font jen pro osobní použití — lepší zjistit teď než po spuštění)
5. *Doména* — rozhodnutí, jestli školení pojedou na subdoméně (skoleni.paudent.cz — rychlejší, zdarma) nebo na nové doméně (čistší oddělení pacienti × lékaři). Pošlu doporučení, až budu vědět, jak chcete značku dál rozvíjet. Případně přístup ke správě domény paudent.cz.

Jakmile budu mít podklady 1–2, můžu začít stavět strukturu webu a průběžně doplňovat zbytek. Dejte vědět, která varianta Vám dává smysl, a pošlu harmonogram po týdnech. Díky!

---

## Interní checklist (neposílat)

- [ ] Po obdržení loga prověřit licenci fontu (komerční užití)
- [ ] Připravit doporučení subdoména vs. nová doména
- [ ] Po volbě varianty poslat harmonogram po týdnech (cíl: spuštění říjen / začátek listopadu)
- [ ] Založit projekt (repo, VM site, DB) po odsouhlasení nabídky
