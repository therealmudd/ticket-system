# Ticket System Web App

Simple web app to generate tickets and scan them.

## Functionality

- Seller enters buyer's email and name and number of tickets
- Tickets are generated with reference number, date and QR code
- Tickets are then sent to the buyer via email, with one PDF per ticket
- Tickets are saved in database
- Tickets are scanned and verified when used
- Tickets are deleted from database when used

## Creating Multiple Tickets

The create form supports sending multiple tickets to the same buyer. The backend
generates one unique reference number per ticket, saves each ticket in Firestore,
and sends all generated ticket PDFs as attachments in one email.

The default maximum is 10 tickets per request. Override it with:

```powershell
$env:MAX_TICKETS_PER_REQUEST="20"
```

## Non-Production Testing

Use environment variables to keep local or staging tests away from production
ticket data and real buyer inboxes.

Start by copying `backend/.env.example` to `backend/.env`, then set your real
Firebase credential value:

```powershell
Copy-Item backend/.env.example backend/.env
```

Recommended local test settings:

```text
APP_ENV=local
EMAIL_MODE=console
TICKET_IMAGE=ticket2.png
```

When `APP_ENV` is anything other than `production`, Firestore collections are
automatically prefixed. For example, `APP_ENV=local` uses:

```text
local_tickets
local_daily_counters
```

This keeps test ticket creation and redemption separate from the production
`tickets` and `daily_counters` collections.

`EMAIL_MODE=console` still generates the ticket PDFs, but skips SMTP sending and
prints the intended recipient and references in the server logs.

When tickets are created outside production, the create response also includes an
email preview link. The frontend opens this link in a separate tab so you can
inspect the email body and generated PDF attachments without sending to a buyer.

Email previews are available only outside production:

```text
/email-preview?references=TKT26062026001,TKT26062026002
```

Preview attachment links are generated as:

```text
/email-preview/attachments/TKT26062026001
```

For a staging/preview deployment where you want to send emails only to yourself:

```text
APP_ENV=staging
EMAIL_MODE=smtp
EMAIL_REDIRECT_TO=your-test-address@example.com
```

The app also exposes a safe status endpoint:

```text
/health
```

It returns the active app environment, email mode, Firestore collection prefix,
and ticket image. It does not return secrets.

## Ticket QR Preview

Use `preview_ticket_qr.py` to test QR placement, size, colour, and output format
without starting the Flask app, sending emails, or writing to Firebase.

By default it uses `ticket2.png` and creates `ticket_qr_preview.png`:

```powershell
python preview_ticket_qr.py
```

Example with the current `ticket2.png` settings:

```powershell
python preview_ticket_qr.py --size 330 --y 480 --color "#ffffff"
```

Useful options:

```text
--ticket ticket2.png
--reference TKT24062026001
--output ticket_qr_preview.png
--x 520
--y 480
--size 330
--color "#ffffff"
--background transparent
--border 0
```

Set `x` or `y` only when you want to override the default centered position.

## Ticket Image Configuration

QR rendering settings are stored in `ticket_qr_config.json`. The backend chooses
the config by matching the ticket image filename.

Example:

```json
{
  "ticket2.png": {
    "x": null,
    "y": 480,
    "size": 330,
    "color": "#ffffff",
    "background": "transparent",
    "border": 0
  }
}
```

`x: null` means the QR code is centered horizontally. `y: null` means it is
centered vertically.

The backend uses `ticket2.png` by default. To use a different ticket image, set
the `TICKET_IMAGE` environment variable to a filename that exists in the project
root and has a matching entry in `ticket_qr_config.json`.

PowerShell example:

```powershell
$env:TICKET_IMAGE="ticket2.png"
python backend/app.py
```
