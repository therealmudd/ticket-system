import os
import dotenv
import sys
import io
import smtplib
import json as json_module
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, json, render_template, request, send_file
from firebase_admin import firestore

from PIL import Image
import qrcode

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

dotenv.load_dotenv(PROJECT_ROOT / ".env")
dotenv.load_dotenv(BACKEND_DIR / ".env", override=True)

# Firebase
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.firebase_config import db

# SQLite
# import sqlite3
# db = sqlite3.connect('database/tickets.db', uri=True, check_same_thread=False)
# db.execute('CREATE TABLE IF NOT EXISTS tickets (reference_number TEXT, name TEXT, email TEXT, status TEXT)')

app = Flask(__name__, template_folder="../frontend")

APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
DEFAULT_COLLECTION_PREFIX = "" if APP_ENV == "production" else f"{APP_ENV}_"
FIRESTORE_COLLECTION_PREFIX = os.getenv(
    "FIRESTORE_COLLECTION_PREFIX", DEFAULT_COLLECTION_PREFIX
)
EMAIL_MODE = os.getenv("EMAIL_MODE", "smtp").strip().lower()
EMAIL_REDIRECT_TO = os.getenv("EMAIL_REDIRECT_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM", os.getenv("EMAIL", "m.antonio0294@gmail.com"))
TICKET_IMAGE = os.getenv("TICKET_IMAGE", "ticket2.png")
TICKET_QR_CONFIG_PATH = PROJECT_ROOT / "ticket_qr_config.json"
MAX_TICKETS_PER_REQUEST = int(os.getenv("MAX_TICKETS_PER_REQUEST", "10"))

DEFAULT_QR_CONFIG = {
    "x": None,
    "y": None,
    "size": 400,
    "color": "#392d17",
    "background": "transparent",
    "border": 0,
}


# Functions
def firestore_collection(name):
    return db.collection(f"{FIRESTORE_COLLECTION_PREFIX}{name}")


@firestore.transactional
def reserve_reference_numbers(transaction, counter_doc, quantity):
    counter_snapshot = counter_doc.get(transaction=transaction)
    current_count = counter_snapshot.to_dict().get("count", 0) if counter_snapshot.exists else 0
    new_count = current_count + quantity

    transaction.set(counter_doc, {"count": new_count})
    return current_count + 1, new_count


def generate_reference_numbers(quantity):
    today = datetime.now(ZoneInfo("Africa/Johannesburg")).strftime("%d%m%Y")
    counter_doc = firestore_collection("daily_counters").document(today)
    transaction = db.transaction()
    start_count, end_count = reserve_reference_numbers(
        transaction, counter_doc, quantity
    )

    return [f"TKT{today}{count:03d}" for count in range(start_count, end_count + 1)]


def save_to_database(name, email, reference_number):
    # Firbase
    ticket_data = {
        "timestamp": datetime.now(),
        "name": name,
        "email": email,
        "reference_number": reference_number,
        "status": "sold",
    }

    firestore_collection("tickets").add(ticket_data)

    # # SQLite
    # db.execute('INSERT INTO tickets (reference_number, name, email, status) VALUES (?, ?, ?, ?)', (reference_number, name, email, 'sold'))
    # db.commit()


def save_multiple_to_database(name, email, reference_numbers):
    batch = db.batch()
    timestamp = datetime.now()

    for reference_number in reference_numbers:
        ticket_data = {
            "timestamp": timestamp,
            "name": name,
            "email": email,
            "reference_number": reference_number,
            "status": "sold",
        }
        ticket_doc = firestore_collection("tickets").document()
        batch.set(ticket_doc, ticket_data)

    batch.commit()


def load_ticket_qr_config(ticket_image_name):
    if not TICKET_QR_CONFIG_PATH.exists():
        return DEFAULT_QR_CONFIG.copy()

    with TICKET_QR_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        configs = json_module.load(config_file)

    config = DEFAULT_QR_CONFIG.copy()
    config.update(configs.get(ticket_image_name, {}))
    return config


def get_ticket_from_database(reference_number):
    # Firebase
    doc_ref = firestore_collection("tickets").where(
        "reference_number", "==", reference_number
    )
    doc = doc_ref.stream()
    ticket = None
    for d in doc:
        ticket = d.to_dict()
    return ticket

    # SQLite
    # cursor = db.execute('SELECT * FROM tickets WHERE reference_number = ?', (reference_number,))
    # ticket = cursor.fetchone()
    # return ticket


def update_ticket_status_in_database(reference, status):
    firestore_collection("tickets").where("reference_number", "==", reference).get()[
        0
    ].reference.update({"status": status})


def redeem_ticket_from_database(reference):
    ticket = get_ticket_from_database(reference)
    if not ticket:
        return "ticket does not exist"
    if ticket.get("status") == "redeemed":
        return "ticket already redeemed"
    update_ticket_status_in_database(reference, "redeemed")
    return "ticket redeemed"


def get_all_tickets_from_database():
    # Firebase
    tickets_ref = firestore_collection("tickets")
    tickets_docs = tickets_ref.stream()

    tickets = [
        [
            doc.get("reference_number"),
            doc.get("name"),
            doc.get("email"),
            doc.get("status"),
            doc.to_dict().get("disabled", False),
        ]
        for doc in tickets_docs
    ]

    # SQLite
    # cursor = db.execute('SELECT * FROM tickets')
    # tickets = cursor.fetchall()

    # Sort tickets by date
    tickets.sort(
        key=lambda ticket: datetime.strptime(ticket[0][3:11], "%d%m%Y"), reverse=True
    )

    return tickets


def create_ticket_pdf(reference_number):
    ticket_path = PROJECT_ROOT / TICKET_IMAGE
    qr_config = load_ticket_qr_config(TICKET_IMAGE)

    # Load the ticket image
    ticket = Image.open(ticket_path).convert("RGBA")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=qr_config["border"],
    )
    qr.add_data(reference_number)
    qr.make(fit=True)

    size = qr_config["size"]
    if qr_config["background"] == "transparent":
        img = qr.make_image(fill_color="black", back_color="white")
        mask = img.convert("L").point(lambda pixel: 255 if pixel < 128 else 0)
        mask = mask.resize((size, size), Image.Resampling.NEAREST)

        img = Image.new("RGBA", (mask.width, mask.height), qr_config["color"])
        img.putalpha(mask)
    else:
        img = qr.make_image(fill_color=qr_config["color"], back_color="white")
        img = img.convert("RGBA").resize((size, size), Image.Resampling.NEAREST)

    x = qr_config["x"] if qr_config["x"] is not None else (ticket.width - size) // 2
    y = qr_config["y"] if qr_config["y"] is not None else (ticket.height - size) // 2

    # Paste the QR code onto the ticket
    ticket.paste(img, (x, y), mask=img)

    # Save to BytesIO
    pdf_bytes = io.BytesIO()
    ticket.convert("RGB").save(pdf_bytes, format="PDF", resolution=100.0)
    pdf_bytes.seek(0)
    return pdf_bytes


def send_email(name, email, reference_numbers):
    ticket_word = "ticket" if len(reference_numbers) == 1 else "tickets"
    reference_list = "".join(
        f"<li><strong>{reference_number}</strong></li>"
        for reference_number in reference_numbers
    )

    # Email content
    msg = MIMEMultipart()
    msg["Subject"] = f"Your {ticket_word} for the LT Annual Ball!"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_REDIRECT_TO or email
    if EMAIL_REDIRECT_TO:
        msg["X-Original-To"] = email

    location_link = "https://www.google.com/maps/dir//15+Mullins+Rd,+Malvern+East,+Germiston,+1401/@-26.1990207,28.0402136,12z/data=!4m8!4m7!1m0!1m5!1m1!1s0x1e9511e61722bd6f:0x3a607bc68bc577a3!2m2!1d28.1227225!2d-26.1990134?entry=ttu&g_ep=EgoyMDI1MDUyMS4wIKXMDSoASAFQAw%3D%3D"

    # HTML content
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="font-size: 24px; margin-bottom: 10px;">Your LT Annual Ball Ticket</h2>
            <p>Hi {name},</p>
            <p>Thank you for your purchase! We're excited to have you join us for the LT Annual Ball, happening on <strong>Saturday 28 June, 18:00 at <a href="{location_link}" target="_blank">15 Mullins Rd, Germiston</a>.</strong></p>
            <p>Please find attached your {ticket_word} for entry - either printed or on your phone.</p>
            <p>Your ticket reference number{"s are" if len(reference_numbers) > 1 else " is"}:</p>
            <ul>{reference_list}</ul>
            <p>We're looking forward to an unforgettable event!</p>
            <p>If you have any questions or need further assistance, feel free to reply to this email.</p>
            <p>Best regards,</p>
            <p><strong>Life Teen Blessed Sacrament</strong></p>
        </div>
    </body>
    </html>
    """

    # Attach HTML
    msg.attach(MIMEText(html, "html"))

    # Attach one PDF per ticket.
    for reference_number in reference_numbers:
        pdf_buffer = create_ticket_pdf(reference_number)
        attachment = MIMEApplication(pdf_buffer.read(), _subtype="pdf")
        attachment.add_header(
            "Content-Disposition", "attachment", filename=f"{reference_number}.pdf"
        )
        msg.attach(attachment)

    if EMAIL_MODE == "console":
        print(
            "EMAIL_MODE=console: skipped SMTP send. "
            f"to={msg['To']} references={', '.join(reference_numbers)}"
        )
        return

    # Connect to Gmail SMTP server
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(os.getenv("EMAIL"), os.getenv("EMAIL_PASSWORD"))
    server.send_message(msg)
    server.quit()


# Routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return {
        "app_env": APP_ENV,
        "email_mode": EMAIL_MODE,
        "firestore_collection_prefix": FIRESTORE_COLLECTION_PREFIX,
        "ticket_image": TICKET_IMAGE,
    }


@app.route("/qr/<reference>")
def qr(reference):
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(reference)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png")


@app.route("/create_ticket", methods=["POST"])
def generate():
    name = request.form["name"]
    email = request.form["email"]

    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        return {"error": "Quantity must be a number."}, 400

    if quantity < 1 or quantity > MAX_TICKETS_PER_REQUEST:
        return {
            "error": f"Quantity must be between 1 and {MAX_TICKETS_PER_REQUEST}."
        }, 400

    reference_numbers = generate_reference_numbers(quantity)

    save_multiple_to_database(name, email, reference_numbers)

    send_email(name, email, reference_numbers)

    return {"references": reference_numbers}


@app.route("/tickets")
def tickets():
    tickets = get_all_tickets_from_database()

    return json.dumps(tickets)


@app.route("/redeem-ticket/<reference>")
def redeem_ticket(reference):
    result = redeem_ticket_from_database(reference)

    return {"result": result}


if __name__ == "__main__":
    app.run(debug=True)
