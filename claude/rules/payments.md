---
description: Payments lessons learned on a live web game (Razorpay, RevenueCat, Dodo) from 2026-08 to 2026-09, every one measured live. Rules and the failures behind them. Loads when billing, checkout, subscription, pricing or webhook files are touched. Read it before any payments work in any project, even before touching files.
paths:
  - "**/billing/**"
  - "**/payments/**"
  - "**/payment/**"
  - "**/checkout/**"
  - "**/webhooks/**"
  - "**/*razorpay*"
  - "**/*revenuecat*"
  - "**/*dodo*"
  - "**/*subscription*"
  - "**/*pricing*"
  - "**/payments-lessons.md"
---

# Payments (learned on a live web game 2026-08-11 to 08-19; applies to every project)

Rules only. Full forensics, failure codes and pricing maths:
`~/projects/a live web game/docs/payments-lessons.md`.

**1. An anonymous charge gets declined.** Amount and currency alone, with no customer object, name
or email, gave **11% success on international cards** against the gateway's published 70%. A real
customer object, `prefill.name` / `prefill.email` and a gateway-collected billing address (AVS is
most of how a foreign issuer scores it) took it to **83%**. Never force `readonly` prefill: the name
on the card may differ from the account. Two habits that made it findable and are cheap everywhere:
**persist the raw webhook payload** (it killed the wrong theory in one query), and **compare against
the vendor's published baseline before blaming the vendor**. Also: gateway pricing is not the
sticker, so all-in cost can make a merchant-of-record comparable rather than a premium.

**2. One live subscription per person, and only the DATABASE can promise it.** A read-then-write
check loses the race: two clicks 400ms apart both read "nothing pending" and both create. One player
got four subscription objects, two active, and was **charged twice** out of five paying customers.
- A **partial unique index** (`unique (user_id, provider) where status='pending'`) is the only real
  fix. Test it by firing ~12 inserts at once; a sequential test passes against the broken code.
- **Record the provider's id the moment it exists**, or a crash before the webhook orphans a live
  billing object nobody can see.
- **The button is half the bug.** `rzp.open()` returns immediately, so a `finally` re-enables it
  underneath the open sheet. Only the gateway's own `modal.ondismiss` may re-enable it.
- **Do not trust the gateway to deduplicate.** Razorpay's subscription list refuses a `customer_id`
  filter, and `fail_existing: 0` still minted two customers for one email.

**3. An event that names the PAYMENT does not name the PERSON.** Razorpay writes `notes` only on the
objects you create, the subscription and the order, never on the payment. So a handler reading the
payer from `payload.<entity>.notes` does nothing at all on `payment.captured`, `payment.failed` and
`order.paid`. Measured live: **16/16, 15/15 and 20/20 did nothing.** The whole billing system ran on
`subscription.charged` alone, a player paid $9.99 and stayed on Free, and **no payment-failure email
had ever been sent** in the product's life. Recover the person via `payment.invoice_id` -> invoice ->
`subscription_id` -> your own checkout table, and **never by the payer's email** (three card emails
on that account differ from the login email). Empty `notes` arrives as `[]`, an ARRAY, so
`notes.user_id` is `undefined` rather than an error: it fails silently forever.
**Test every event type separately; green on one proves nothing about the others.**

**4. An uncollected first payment never starts the subscription.** Left `authorized`, the
subscription stays `created` with `auth_attempts: 0`, `subscription.charged` never fires, and
capturing it later **takes the money without activating anything**. Uncaptured authorisations
auto-refund after **3 days**. So subscribe to `payment.authorized` and capture from the webhook,
grant on `subscription.activated` as well as `.charged`, and **reconcile daily against the
PROVIDER**, your own tables cannot show a customer they have no row for.

> The 2026-08-19 case was a confirmed gateway OUTAGE, and that is the trap. Their incident caused
> the stuck capture, but **once it was captured by hand the events arrived correctly and our handler
> still did nothing**. A gateway will have incidents; "it was their fault" is the reason to check
> your own side, not to skip it.

**5. "Delete my account" should ANONYMISE, not destroy.** A cascade from `auth.users` took a paying
player's 29 turns, the owner's world and the owner's characters, leaving three ownerless "broken" / "boring"
feedback rows; it also took the owner's billing row, so the owner's live subscription kept charging the owner invisibly.
Apple 5.1.1(v), GDPR Art. 17 and India's DPDP all require the deletion, but GDPR Recital 26 puts
genuinely anonymous data outside the regulation entirely. So drop the FK from `profiles` to
`auth.users`, give every child key `ON UPDATE CASCADE`, **rotate the user id to a fresh uuid**, then
delete the auth row. Rotating the id is the part that matters: the old one sits in the provider's
notes next to the email, so keeping it is pseudonymisation, which is still personal data. Cancel the
subscription on the way out and disclose in the UI what is kept.

**6. Read your own dunning copy before it can send.** The card-refused email was unreachable for the
product's whole life; when it could finally send, it turned out to be written for a renewal, and
**every real failure had been somebody's FIRST payment**. It told people who had never subscribed
that their account "stays Storyteller for a few days". Branch the copy, and put the gateway's real
decline reasons in it rather than billing boilerplate.

**7. BEFORE ASKING A PROVIDER TO ENABLE SOMETHING, CHECK WHETHER IT IS A FLAG IN YOUR OWN
CHECKOUT.** Learned the embarrassing way on 2026-09-03: a support email was drafted asking Razorpay
to "switch on In-Session Retries", and it was never theirs to switch. `retry: { enabled: true }` is
a Standard Checkout option, its web default is **false**, and it had never been sent since the day
the integration was written. Their published figures are a 3-4% lift on international card success
and ~40% fewer failed attempts, and it cost one line. `max_count` is Android/iOS only and does
nothing on web.

**What actually is the provider's to enable**, on this account: **non-3DS processing** (dashboard
request, risk-team decision, shifts all chargeback liability to you, and the dashboard refuses a
second request within 30 days), **chargeback protection** (~1% on international cards, the right
pairing for non-3DS), and **AVS**. What is NOT: retries, and anything else living in checkout
options.

**AVS IS A COMPLEMENT TO 3DS, NEVER A SUBSTITUTE**, and the instinct that non-3DS makes it
unnecessary is backwards: removing authentication removes the liability shift too, so fraud signals
matter more, not less. Razorpay's AVS is US/UK/CA cards only, needs zero code, and is a support
request. But it can **decline on mismatch**, so it is a trade rather than a free win. On a live web game it
was declined on the numbers: **zero chargebacks in the product's life**, so it would guard against
something that has never happened while risking real declines. Revisit only if disputes appear.

**NETWORK TOKENISATION DOES NOT APPLY TO A 100%-INTERNATIONAL CUSTOMER BASE.** RBI tokenisation
covers cards issued in India; Razorpay's own docs say international card reports still show the full
name and number. The "4.4% approval lift" is not available here. Do not ask for it.

**A DECLINE CODE WITH A 100% LOSS RATE IS NOT THE SAME AS A COMMON ONE.** Over 45 days, 29 people
tried and 22 paid. `card_not_enrolled` ("3dsecure is not enabled for the card") was only the third
most FREQUENT reason at 5 failures, and the only one where **every single person was lost** -- two
of them retried the identical card because the raw provider string told them nothing. Rank decline
reasons by customers lost, never by count. And never show a customer the provider's raw
description: it is written for a developer reading a dashboard.

**IN-SESSION RETRIES CHANGE WHAT THE FAILURE HANDLER MAY DO.** With retries on, a decline leaves the
sheet OPEN. Releasing the buy button there re-enables it underneath a live payment sheet, which is
the exact bug that once gave one player two subscriptions and a double charge. Hold `busy` through
the failure, hold the explanation too, and release both on `ondismiss` -- with a long backstop timer
so a sheet that never fires ondismiss cannot strand the button.

**A SUBSCRIPTION IS A COUNT, AND THE PROVIDER WILL NOT LET IT BE PERPETUAL.** Razorpay requires
`total_count` on create and refuses the request without it: no null, no zero, no "until cancelled".
Whatever number goes in is the number of times that customer will EVER be charged. Ours was 12
monthly and **1 annual**, against Terms that said both "auto-renew until cancelled", so every
monthly subscriber would have stopped being billed after a year, silently, one at a time, about
eleven months after anyone would think to look. **If a provider makes you state a term, state one
longer than the business.** And a term lives on the object AT THE PROVIDER, so a code change never
reaches the people who already subscribed; they need a migration script
(`PATCH /subscriptions/{id}` with `remaining_count`).

**"FINISHED" IS NOT "CANCELLED", AND THE DIFFERENCE IS SOMEBODY'S MONEY.** `subscription.completed`
means every invoice has now been raised; `subscription.cancelled` means the customer ended it. Only
the second is a reason to revoke. Finished means no MORE money is coming, not that the money
already taken has stopped buying anything. Sharing one branch between them, plus `total_count: 1`
on annual (the first charge COMPLETES the subscription), put a real GBP 59.99 customer on Free one
second after paying -- and only the arrival order of two webhooks put it back:

    19:00:37 subscription.completed -> free   19:00:38 activated -> back   19:00:39 charged -> back

**A RULE THAT DEPENDS ON WHICH WEBHOOK ARRIVES LAST IS NOT A RULE.** Events are delivered and
retried independently, so decide from the one field that cannot be raced: the provider's own
paid-until date on the event. Same payload, same answer, however late and however often redelivered.

**"WILL MORE MONEY ARRIVE" AND "IS THERE PAID-FOR TIME LEFT" ARE DIFFERENT QUESTIONS,** and every
reconcile written here asked only the first. A completed subscription owes the customer its whole
final period; a cancelled one owes them to the end of the cycle. Gate on `paid_count > 0` as well
as the date, because an ABANDONED checkout also carries a future end date and owes nothing (150 of
187 objects on the a live web game account are exactly that shape).

**A HALTED SUBSCRIPTION'S CURRENT PERIOD IS THE ONE IT FAILED TO COLLECT (a live web game, 27 Sep 2026).**
Razorpay opens the next cycle and THEN charges it; after the retries fail it moves the subscription
to `halted` and keeps reporting that uncollected cycle as `current_start` / `current_end`, with
`paid_count` unchanged. So on a halted object `current_end` is not paid-for time. Five people who
had paid once and been refused the next month were moved to Free by the halted webhook, then given
Pro back **every morning** by the reconcile, which read "paid_count 1, current_end next month" as
time still owed. **Never trust a provider's period end on a subscription it has stopped
collecting: read the status first, and end paid time at `current_start` for halted.** `pending`
keeps its grace (the provider is still retrying). And a safety net that GRANTS on a field must be
able to TAKE BACK on the same field, or a wrong grant renews itself daily. Applies to every product
on Razorpay, RevenueCat or any provider that separates "period" from "paid".

**ASK THE MANDATE HOW LONG A TERM, NOT THE API.** Razorpay's ceiling is 100 years, measured live:
`total_count` 1200 monthly / 100 yearly accepted, 1201 / 101 return *"Exceeds the maximum
total_count ... allowed for the given period and interval"*. **The API accepting it says nothing
about what the payer's bank will approve.** A UPI token's expiry IS the subscription's end date, so
`total_count` sets how long a mandate the customer is asked to authorise in their own banking app,
and NPCI caps that at 30 years from the start date (NPCI/UPI/OC-123/2021-2022; 40 under the Dec 2023
master circular). A 100-year mandate is refused at the one moment you cannot see or retry. **Thirty
years is the answer**; the difference between 30 and 100 has no customer in it. Card mandates are
unaffected either way -- a card token expires with the CARD (measured: 2026-10 through 2034-09 on
the live ones), which is also its own coming wave of failed renewals to expect and not misdiagnose.

**A UPI OR EMANDATE SUBSCRIPTION CANNOT BE UPDATED AT ALL** (`"subscriptions cannot be updated when
payment mode is upi"`), and domestic cards can only have their OFFER changed. That is correct rather
than an obstacle: the bank agreed an end date at approval and nothing sent to the gateway changes
it. **Read every write back** -- status, next charge date, current period, paid count, plan and
notes all asserted unchanged -- because the only acceptable version of a billing migration is one
that moves no date, charges nobody, and alters no price.

**A PLAN CHANGE ON A LIVE SUBSCRIPTION IS `PATCH /subscriptions/{id}` WITH `schedule_change_at:
"cycle_end"`, AND A PERIOD CHANGE NEEDS `remaining_count` (a live web game, 30 Sep 2026).** Measured in
test mode: monthly to yearly without `remaining_count` is refused with *"remaining_count should be
present to update to new plan which has different period"*; send the term the new plan's checkout
would get (30 yearly cycles), never a smaller number that ends the subscription early. Read it
back with `GET /subscriptions/{id}/retrieve_scheduled_changes`, which returns the object carrying
the PENDING values (`plan_id` = the new plan, `has_scheduled_changes: true`, `change_scheduled_at`
= `current_end`) and answers **400 "No Pending update for this subscription"** when nothing is
scheduled, so a null from a GET helper means "nothing pending", not "down". The live object keeps
its old `plan_id` until cycle end. `POST .../cancel_scheduled_changes` undoes it and is harmless
when nothing is pending. Razorpay accepts a scheduled plan change on a subscription already set to
cancel at cycle end, so withdraw the change before cancelling rather than leaving both to race.
**The tier must then be read from `plan_id`, never from `notes.tier`:** notes are written once at
creation and the update API cannot change them.

**RAZORPAY TEST MODE IS A SEPARATE WORLD, AND THE KEYS ARE ACCOUNT-WIDE.** One test key pair
serves every project on the account (`RAZORPAY_TEST_KEY_ID` / `_SECRET`, filed for a live web game, see
`rules/secrets-map.md`); it has its OWN plans (create them with the test keys, the live plan ids
do not exist there), and a secret is shown once at generation, so an unfiled test key is a
regenerate, not a lookup. To get an ACTIVE test subscription: create it WITHOUT `customer_id` (a
subscription created with one has no hosted page: *"Hosted page is not available"*), open its
`short_url` in **playwright-cli** (the Chrome extension cannot see inside the checkout iframe and
its screenshots freeze on that page), and know the checkout's traps: the contact step rejects the
dummy numbers 9999999999 and 9876543210 as "not a valid mobile number" but takes 9123456789; the
card step wants a name and an email too; the international subscription test card is
`5104 0155 5555 5558`, any future expiry, any CVV; the mock bank page has a **Success** button,
and the subscription reads `active` with `payment_method: "card"` a few seconds later. Cancel
every test subscription when done.
