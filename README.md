# Ticket System Web App

Simple web app to generate tickets and scan them.

## Functionality

- Seller enters buyer's email and name and number of tickets
- Tickets are generated with reference number, date and QR code
- Tickets are then sent to the buyer via email
- Tickets are saved in database
- Tickets are scanned and verified when used
- Tickets are deleted from database when used

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
