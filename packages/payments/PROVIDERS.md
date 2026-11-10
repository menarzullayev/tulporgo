# Payment providers (decision 44)

Prices come only from decision 10 (Asosiy 29 000 / Pro 59 000 / Biznes 99 000 so'm per month, no multi-month
discount). While `settings.free_period_until` is in the future checkout is refused (`409 free_period`) and `/obuna`
offers nothing to pay. Everything runs in sandbox/test mode by default; live keys only after a merchant contract.

| Provider | Module | Spec |
|---|---|---|
| P2P card | `providers/p2p.py` | internal flow (decisions 11, 44) |
| Telegram Stars | `providers/stars.py` | https://core.telegram.org/bots/payments-stars , https://core.telegram.org/bots/api#sendinvoice , https://core.telegram.org/bots/api#createinvoicelink , https://core.telegram.org/bots/api#botsubscriptionupdated |
| Click | `providers/click.py` | https://docs.click.uz/click-api-request/ (SHOP API: Prepare / Complete, `sign_string` MD5) and https://docs.click.uz/ (pay URL `https://my.click.uz/services/pay`) |
| Payme | `providers/payme.py` | https://developer.help.paycom.uz/ (Merchant API protocol and methods), sandbox https://test.paycom.uz |
| Other | `providers/other.py` | documented stub: one subclass of `GatewayProvider` per gateway |

Note on verification: the vendor documentation sites are JavaScript apps that could not be rendered by the
automated fetch used while building this; the implementation follows the published protocols (parameters, signature
formulas, error codes, states) as recorded above and in the module docstrings. Before going live, run each
provider's official sandbox/test console (Click merchant test, Payme "Sandbox" test suite) against
`/api/payments/click/*` and `/api/payments/payme` and compare — this is the open item for the merchant contract.

## Endpoints (mounted at `/api/payments`)
- `POST /checkout` — Mini App auth (`Authorization: tma <initData>`); body `{plan, months, provider, recurring?}`;
  the amount is computed server-side. Returns `{payment_id, provider, amount, currency, start}`.
- `GET /providers` — configured providers and the free-period flag.
- `POST /click/prepare`, `POST /click/complete` — form-encoded (JSON accepted); reply `{error, error_note, ...}`.
- `POST /payme` — JSON-RPC, `Authorization: Basic base64("Paycom:" + payme_key)`; always HTTP 200 with a JSON-RPC
  envelope. Account field: `payment_id`; amounts in tiyin.

## Click (SHOP API)
`sign_string = md5(click_trans_id + service_id + SECRET + merchant_trans_id [+ merchant_prepare_id] + amount +
action + sign_time)`; `merchant_trans_id` = our `Payment.id`. Errors: 0 ok, -1 sign, -2 amount, -3 action,
-4 already paid, -5 order not found, -6 transaction not found, -7 update failed, -8 bad request, -9 cancelled.
Complete is idempotent (a replay answers -4 and changes nothing). Click-reported failure (`error < 0`) cancels.

## Payme (Merchant API)
Methods: CheckPerformTransaction, CreateTransaction, PerformTransaction, CancelTransaction, CheckTransaction,
GetStatement. States 1 / 2 / -1 / -2; 12 h timeout (reason 4). Errors: -32504 auth, -32700/-32600/-32601 protocol,
-31001 amount, -31003 transaction not found, -31008 cannot perform, -31050 order not found, -31099 order busy/closed.
Cancel after perform = refund: the subscription days are taken back and the payment becomes `refunded`.
Transaction state lives in `Payment.payload["payme"]` (no schema change). Fiscal-receipt `detail` (IKPU codes) is not
emitted yet — needed only if the merchant's cash desk requires online receipts.

## Telegram Stars
Invoice payload `pay:<payment_id>`, currency `XTR`, `provider_token ""`. `pre_checkout_query` is answered after
checking payment exists, is pending, belongs to the user and the amount matches. `successful_payment` marks paid with
`telegram_payment_charge_id` (replay-safe). Monthly auto-renewal: `createInvoiceLink` with
`subscription_period=2592000` (one-month plans only); each renewal arrives as a recurring `successful_payment` and
creates a new Payment row. `BotSubscriptionUpdated` (`router.subscription`) records canceled/active/failed and tells
the driver. `stars_rate_uzs` (165) must be confirmed by the owner before live Stars.

## Telegram Stars rules (bot commands)
`/terms` (link `TERMS_URL` in `tulporgo_payments/__init__.py`), `/paysupport` (next message is forwarded to admins with
the user last payment ids; admins answer by replying to it, routed by the `[support:<tg_id>]` tag), and `/refund <id>`
(admin only: `refundStarPayment`, payment -> `refunded`, subscription shortened by the paid period, never below now).
Every purchase goes through a terms screen with one explicit confirm button (`pay:tc:`) before any invoice/link/payment.

## Adding a gateway
See the docstring of `providers/other.py`.
