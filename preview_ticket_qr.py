import argparse
from pathlib import Path

from PIL import Image
import qrcode


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a local ticket preview with a QR code overlay."
    )
    parser.add_argument(
        "--ticket",
        default="ticket2.png",
        help="Path to the source ticket image.",
    )
    parser.add_argument(
        "--reference",
        default="TKT24062026001",
        help="Reference text encoded into the QR code.",
    )
    parser.add_argument(
        "--output",
        default="ticket_qr_preview.png",
        help="Output path. Use .png, .jpg, .jpeg, or .pdf.",
    )
    parser.add_argument(
        "--x",
        type=int,
        default=None,
        help="Left position for the QR code. Defaults to centered.",
    )
    parser.add_argument(
        "--y",
        type=int,
        default=None,
        help="Top position for the QR code. Defaults to centered.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=400,
        help="QR code size in pixels.",
    )
    parser.add_argument(
        "--color",
        default="#392d17",
        help="QR foreground color, for example '#392d17' or 'black'.",
    )
    parser.add_argument(
        "--background",
        default="transparent",
        choices=["transparent", "white"],
        help="QR background style.",
    )
    parser.add_argument(
        "--border",
        type=int,
        default=0,
        help="QR quiet-zone border size in modules.",
    )
    return parser.parse_args()


def make_qr(reference, size, color, background, border):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=border,
    )
    qr.add_data(reference)
    qr.make(fit=True)

    if background == "transparent":
        qr_image = qr.make_image(fill_color="black", back_color="white")
        mask = qr_image.convert("L").point(lambda pixel: 255 if pixel < 128 else 0)
        mask = mask.resize((size, size), Image.Resampling.NEAREST)

        qr_image = Image.new("RGBA", (mask.width, mask.height), color)
        qr_image.putalpha(mask)
    else:
        qr_image = qr.make_image(fill_color=color, back_color="white")
        qr_image = qr_image.convert("RGBA").resize((size, size), Image.Resampling.NEAREST)

    return qr_image


def save_preview(ticket, output_path):
    suffix = output_path.suffix.lower()

    if suffix == ".pdf":
        ticket.convert("RGB").save(output_path, format="PDF", resolution=100.0)
        return

    if suffix in {".jpg", ".jpeg"}:
        ticket.convert("RGB").save(output_path)
        return

    ticket.save(output_path)


def main():
    args = parse_args()
    ticket_path = Path(args.ticket)
    output_path = Path(args.output)

    ticket = Image.open(ticket_path).convert("RGBA")
    qr_image = make_qr(
        reference=args.reference,
        size=args.size,
        color=args.color,
        background=args.background,
        border=args.border,
    )

    x = args.x if args.x is not None else (ticket.width - args.size) // 2
    y = args.y if args.y is not None else (ticket.height - args.size) // 2

    ticket.paste(qr_image, (x, y), mask=qr_image)
    save_preview(ticket, output_path)

    print(f"Created {output_path}")
    print(f"Ticket: {ticket_path} ({ticket.width}x{ticket.height})")
    print(f"Reference: {args.reference}")
    print(f"QR: x={x}, y={y}, size={args.size}, color={args.color}")
    print(f"Background: {args.background}, border={args.border}")


if __name__ == "__main__":
    main()
