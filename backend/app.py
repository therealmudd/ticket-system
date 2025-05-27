import os
import dotenv
import sys
import io
import uuid
import smtplib
from datetime import datetime

from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, json, render_template, request, send_file

from PIL import Image
import qrcode

dotenv.load_dotenv()

# Firebase
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.firebase_config import db

# SQLite
# import sqlite3
# db = sqlite3.connect('database/tickets.db', uri=True, check_same_thread=False)
# db.execute('CREATE TABLE IF NOT EXISTS tickets (reference_number TEXT, name TEXT, email TEXT, status TEXT)')

app = Flask(__name__, template_folder='../frontend')


# Functions
def generate_reference_number():
    today = datetime.now().strftime("%d%m%Y")
    counter_doc = db.collection("daily_counters").document(today)

    # Get or create the daily counter
    counter_snapshot = counter_doc.get()
    if counter_snapshot.exists:
        count = counter_snapshot.to_dict().get("count", 0) + 1
    else:
        count = 1

    # Update the counter in the DB
    counter_doc.set({"count": count})

    reference_number = f"TKT{today}{count:03d}"
    return reference_number


def save_to_database(name, email, reference_number):
    # Firbase
    ticket_data = {
        "timestamp": datetime.now(),
        "name": name,
        "email": email,
        "reference_number": reference_number,
        "status": "sold"
    }

    db.collection("tickets").add(ticket_data)

    # # SQLite
    # db.execute('INSERT INTO tickets (reference_number, name, email, status) VALUES (?, ?, ?, ?)', (reference_number, name, email, 'sold'))
    # db.commit()


def get_ticket_from_database(reference_number):
    # Firebase
    doc_ref = db.collection("tickets").where("reference_number", "==", reference_number)
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
    db.collection("tickets").where("reference_number", "==", reference).get()[0].reference.update({"status": status})


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
    tickets_ref = db.collection("tickets")
    tickets_docs = tickets_ref.stream()
    tickets = [[doc.get("reference_number"), doc.get("name"), doc.get("email"), doc.get("status")] for doc in tickets_docs]

    # SQLite
    # cursor = db.execute('SELECT * FROM tickets')
    # tickets = cursor.fetchall()

    return tickets


def create_ticket_pdf(reference_number):
    # Load the ticket image
    ticket = Image.open("ticket.png").convert("RGBA")

    qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=0,
        )
    qr.add_data(reference_number)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#392d17", back_color="white")
    img = img.resize((400, 400))

    # Convert to RGBA for transparency
    img = img.convert("RGBA")
    datas = img.getdata()

    new_data = []
    for item in datas:
        # If the pixel is white, make it transparent
        if item[0] == 255 and item[1] == 255 and item[2] == 255:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)

    img.putdata(new_data)

    # Paste the QR code onto the ticket
    ticket.paste(img, (ticket.width//2 - 400//2, ticket.height // 2 - 360//2), mask=img)  # offset from bottom-right

    # Save to BytesIO
    pdf_bytes = io.BytesIO()
    ticket.convert("RGB").save(pdf_bytes, format="PDF", resolution=100.0)
    pdf_bytes.seek(0)
    return pdf_bytes


def send_email(name, email, reference_number):
    # Email content
    msg = MIMEMultipart()
    msg["Subject"] = "Your ticket for the LT Annual Ball!"
    msg["From"] = "m.antonio0294@gmail.com"
    msg["To"] = email

    location_link = "https://www.google.com/maps/dir//15+Mullins+Rd,+Malvern+East,+Germiston,+1401/@-26.1990207,28.0402136,12z/data=!4m8!4m7!1m0!1m5!1m1!1s0x1e9511e61722bd6f:0x3a607bc68bc577a3!2m2!1d28.1227225!2d-26.1990134?entry=ttu&g_ep=EgoyMDI1MDUyMS4wIKXMDSoASAFQAw%3D%3D"

    # HTML content
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="font-size: 24px; margin-bottom: 10px;">Your LT Annual Ball Ticket</h2>
            <p>Hi {name},</p>
            <p>Thank you for your purchase! We're excited to have you join us for the LT Annual Ball, happening on <strong>Saturday 28 June, 18:00 at <a href="{location_link}" target="_blank">15 Mullins Rd, Germiston</a>.</strong></p>
            <p>Please find attached your ticket for entry - either printed or on your phone.</p>
            <p>Here's your ticket number: <strong>{reference_number}</strong></p>
            <p>We're looking forward to an unforgettable event!</p>
            <p>If you have any questions or need further assistance, feel free to reply to this email.</p>
            <p>Best regards,</p>
            <p><strong>Life Teen Blessed Sacrament</strong></p>
        </div>
    </body>
    </html>
    """

    # Attach HTML
    msg.attach(MIMEText(html, 'html'))

    # Attach the PDF
    pdf_buffer = create_ticket_pdf(reference_number)
    attachment = MIMEApplication(pdf_buffer.read(), _subtype='pdf')
    attachment.add_header('Content-Disposition', 'attachment', filename=f'{reference_number}.pdf')
    msg.attach(attachment)

    # Connect to Gmail SMTP server
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(os.getenv("EMAIL"), os.getenv("EMAIL_PASSWORD"))
    server.send_message(msg)
    server.quit()


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/qr/<reference>')
def qr(reference):
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(reference)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return send_file(buf, mimetype='image/png')


@app.route('/create_ticket', methods=['POST'])
def generate():
    name = request.form['name']
    email = request.form['email']
    reference_number = generate_reference_number()

    save_to_database(name, email, reference_number)

    send_email(name, email, reference_number)

    return {"reference": reference_number}


@app.route('/tickets')
def tickets():
    tickets = get_all_tickets_from_database()

    return json.dumps(tickets)


@app.route('/redeem-ticket/<reference>')
def redeem_ticket(reference):
    result = redeem_ticket_from_database(reference)

    return {"result": result}


if __name__ == '__main__':
    app.run(debug=True)
