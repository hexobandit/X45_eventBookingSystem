---
name: client-offer
description: Draft a Czech price quote for a prospective client of the course booking system, based on the internal price list. Use when asked for a nabídka, an offer, a quote, or a message to send a lead.
---

# Draft an offer for a lead

The template and the internal prices are in `docs/nabidka-paudent-whatsapp.md`.
Read it first and follow its structure. It is written to be pasted into
WhatsApp, so keep the formatting it uses.

## Rules

- **Czech, addressing the client as vy.** Plain language, no jargon. The reader
  is a lecturer or a clinic, not a developer.
- **Prices come from the internal list only.** Never invent a number and never
  publish prices on the marketing page. The page says the offer is on request;
  numbers appear in the message to the lead.
- **Two variants:** bank transfer with a QR code, and that plus card payment
  through Stripe. Say plainly that the gateway fee is Stripe's, not yours.
- **Name the running cost** for hosting, backups, monitoring and the monthly
  report, and the domain separately.
- **List what you need from the client** before work starts: courses, texts,
  photos, logo with the font name so the licence can be checked, and the domain
  decision.
- **Separate what exists today from what is built on order.** Reminders,
  certificates and discount codes are add-ons, not shipped features. Claiming
  otherwise creates a delivery problem.

## Structure

1. What the site does in both variants, as a short list.
2. Variant A with its price, variant B with its price, and a recommendation.
3. Running cost per month, domain per year.
4. What can be added later.
5. Timeline, tied to when the client delivers materials.
6. A second message listing the materials you need.

End with an internal checklist that is not sent, for anything to verify before
the work starts, such as the font licence of a supplied logo.

Offer the live demo as the closing line: it does more than any description.
