---
description: Inbound email on Resend, and webhooks in general, learned on a live web game and a course site 2026-08-15. Account-wide webhooks, bodies that must be fetched, bare-domain URLs, Razorpay PUT semantics. Loads when inbound, email, mail, Resend or webhook files are touched. Read it on day one of any new site.
paths:
  - "**/inbound/**"
  - "**/*inbound*"
  - "**/email/**"
  - "**/emails/**"
  - "**/*resend*"
  - "**/*mail*"
  - "**/webhooks/**"
---

# Inbound email, and webhooks in general (learned on a live web game + a course site, 2026-08-15)

Every site here publishes support@, privacy@, safety@ and hello@. All of them run on ONE Resend
account. Three things about that were wrong on every site at once, and each failed SILENTLY, which
is why they need to be checked on day one of any new site rather than discovered later.

**1. A RESEND WEBHOOK IS ACCOUNT-WIDE, NOT DOMAIN-SCOPED.** Verified against the API and confirmed
in Resend's docs: creating a webhook takes exactly two fields, `endpoint` and `events`. There is no
`domain_id`. So EVERY `email.received` on the account fires EVERY `email.received` webhook on it,
correctly signed. Measured: one message to `support@example.com` produced forwards from BOTH
a live web game and a course site. Resend's own guidance is to "intelligently route based on the `to` field".
So **every `/api/inbound` must filter on its own domain and ignore the rest** --
`OWNED_DOMAIN = "<thissite>.com"`, match on `received_for` first, then `to`, then `cc`, and ack 200
without forwarding when nothing matches. Prefer `received_for`: a message can arrive via BCC or an
alias and never name us in To or Cc, and matching on To alone drops exactly those.

**2. THE WEBHOOK DOES NOT CARRY THE MESSAGE.** Resend: "Webhooks do not include the email body,
headers, or attachments, only their metadata." Reading `data.text` / `data.html` off the event
yields nothing, so the forward arrives with the right sender, the right subject, working Reply-To
and a blank body. It looks like it works. Fetch the body with
`GET https://api.resend.com/emails/receiving/{data.email_id}`, and note the HTML part comes back as
a **data: URI** (`html_format: "data_uri"`), so it must be base64/percent decoded or the operator is
mailed the literal string `data:text/html;base64,…`. (`resend@4` has no `emails.receiving`; the
SDK helper `emails.receiving.forward()` exists only on newer majors and does not let you set
Reply-To, which is the whole point of forwarding. Call the REST endpoint.)

**3. EVERY WEBHOOK URL MUST BE THE BARE DOMAIN.** `www.` 308-redirects, and senders differ on
whether they follow that on POST. Measured: **Svix (Resend) does NOT follow it**: a live web game's
inbound forwarder never ran for two days and mail only arrived because a course site's site happened to
pick it up. **Razorpay DOES follow it.** Never rely on which; use the apex.

**Razorpay's webhook update is `PUT`, not `PATCH`, and it is a FULL REPLACE.** A PUT carrying only
`url` cleared all six event subscriptions on the live payment webhook. `events` must be an OBJECT
MAP (`{"payment.captured": true}`); an array is read as indices and 400s with
`Invalid event name/names: 1, 2, 3, 4, 5`. Always read the webhook back after writing it.

**The general rule: a published address that bounces, or forwards an empty message, is worse than
no address at all**, because it reads as a working channel to the sender and to App Review. When
adding inbound mail to any new site, check all four: apex MX record exists, webhook on the bare
domain, domain filter present, and **send a real test message and open it**: delivery is not
proof, only the body is.
