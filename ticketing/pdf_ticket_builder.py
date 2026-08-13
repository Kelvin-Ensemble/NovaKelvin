import io
import os
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth

# ---- brand tokens (match the email/site) ----
TEAL      = HexColor("#008888")
TEAL_DARK = HexColor("#006666")
INK       = HexColor("#111827")   # gray-900
BODY      = HexColor("#4b5563")   # gray-600
MUTED     = HexColor("#9ca3af")   # gray-400
PANEL     = HexColor("#f9fafb")   # gray-50
HAIRLINE  = HexColor("#e5e7eb")   # gray-200
PERF      = HexColor("#cbd5d5")
HEAD_SUB  = HexColor("#cceaea")

# ---- fonts ----
# Built-in Helvetica can't render diacritics (Dvořák, Janáček...). Register a
# TrueType font if we can find one, else fall back to Helvetica.
FONT, FONT_BOLD, FONT_MONO = "Helvetica", "Helvetica-Bold", "Courier-Bold"


def _register_fonts():
    global FONT, FONT_BOLD, FONT_MONO
    cands = {
        "TicketSans": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ],
        "TicketSans-Bold": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ],
        "TicketMono": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            r"C:\Windows\Fonts\consolab.ttf",
        ],
    }
    found = {}
    for name, paths in cands.items():
        for p in paths:
            if os.path.exists(p):
                try:
                    pdfmetrics.registerFont(TTFont(name, p))
                    found[name] = True
                except Exception:
                    pass
                break
    if found.get("TicketSans") and found.get("TicketSans-Bold"):
        FONT, FONT_BOLD = "TicketSans", "TicketSans-Bold"
    if found.get("TicketMono"):
        FONT_MONO = "TicketMono"


_register_fonts()

# ---- geometry (points; 1pt = 1/72in) ----
W        = 560          # ticket width
PAD      = 32
INNER    = W - 2 * PAD
GUTTER   = 34           # padding between the Attendee/Ticket/Order columns
HEADER_H = 80
QR_SIZE  = 112
STUB_PAD = 24
RADIUS   = 0            # square corners

TITLE_S  = 20
LINE_GAP = 6
VAL_SIZE = 13           # fixed field-value size (wrap instead of shrink)
VAL_TOP  = 26           # first value baseline below the column top
VAL_LEAD = 17           # leading between wrapped value lines


def _tracked(c, text, x, y, font, size, tracking, color, right=None):
    """Draw letter-spaced text (Canvas has no setCharSpace; text objects do)."""
    w = stringWidth(text, font, size) + tracking * max(len(text) - 1, 0)
    if right is not None:
        x = right - w
    t = c.beginText(x, y)
    t.setFont(font, size)
    t.setCharSpace(tracking)
    t.setFillColor(color)
    t.textOut(text)
    c.drawText(t)


def _ellipsize(text, font, size, maxw):
    """Trim text to fit maxw at a fixed size, adding an ellipsis if needed."""
    text = str(text)
    if stringWidth(text, font, size) <= maxw:
        return text
    ell = "\u2026"
    while text and stringWidth(text + ell, font, size) > maxw:
        text = text[:-1]
    return text + ell if text else ell


def _wrap_value(text, font, size, maxw):
    """Wrap a value onto as many lines as needed at a fixed size (keeps the size).
    Any single unbreakable line still gets ellipsized so it can't overflow."""
    lines = simpleSplit(str(text), font, size, maxw) or [""]
    return [_ellipsize(ln, font, size, maxw) for ln in lines]


def _fields(shared, row):
    """Lay out the Attendee / Ticket / Order columns. Returns (cols, block_height)
    where cols = [(label, [lines], x)] and every value is wrapped, not shrunk."""
    order_w = 56                                   # ORDER is tiny (<= 3 digits)
    rest = INNER - order_w - 2 * GUTTER
    att_w, tkt_w = rest * 0.52, rest * 0.48
    x0 = PAD
    x1 = x0 + att_w + GUTTER
    x2 = x1 + tkt_w + GUTTER
    specs = [
        ("ATTENDEE", row.get("attendee") or "Guest", x0, att_w),
        ("TICKET",   row.get("ticket_type") or "",   x1, tkt_w),
        ("ORDER",    shared["order_number"],          x2, order_w),
    ]
    cols, max_lines = [], 1
    for label, value, cx, w in specs:
        lines = _wrap_value(value, FONT_BOLD, VAL_SIZE, w)
        max_lines = max(max_lines, len(lines))
        cols.append((label, lines, cx))
    block_h = VAL_TOP + (max_lines - 1) * VAL_LEAD + 4
    return cols, block_h


def _qr_image(data: str) -> ImageReader:
    qr = qrcode.QRCode(box_size=10, border=1,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    im = qr.make_image(fill_color="#111827", back_color="white").convert("RGB")
    return ImageReader(im)


def _title_lines(title: str):
    return simpleSplit(title, FONT_BOLD, TITLE_S, INNER)


def _page_height(shared, row) -> float:
    """Page height that snugly fits one ticket's content (including wrapped fields)."""
    title_h = len(_title_lines(shared["concert_title"])) * (TITLE_S + LINE_GAP)
    venue_h = 18 if shared.get("venue") else 0
    _, fields_h = _fields(shared, row)
    body_h = 26 + title_h + 20 + venue_h + 24 + fields_h + 26
    stub_h = STUB_PAD * 2 + QR_SIZE
    return HEADER_H + body_h + stub_h


def _draw_ticket(c: canvas.Canvas, H: float, shared: dict, row: dict):
    c.saveState()
    clip = c.beginPath()
    clip.roundRect(0.5, 0.5, W - 1, H - 1, RADIUS)
    c.clipPath(clip, stroke=0, fill=0)

    c.setFillColor(white)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # ---- header: teal gradient, clipped to header rect ----
    hy = H - HEADER_H
    c.saveState()
    hclip = c.beginPath()
    hclip.rect(0, hy, W, HEADER_H)
    c.clipPath(hclip, stroke=0, fill=0)
    c.linearGradient(0, hy, W, hy + HEADER_H, [TEAL, TEAL_DARK], [0, 1], extend=True)
    c.restoreState()

    logo = shared.get("logo")
    if logo is not None:
        iw, ih = logo.getSize()
        lh = 46.0
        lw = lh * iw / ih
        max_w = W - PAD - 170          # keep clear of the E-TICKET / ADMIT ONE block
        if lw > max_w:
            lh *= max_w / lw
            lw = max_w
        c.drawImage(logo, PAD, hy + (HEADER_H - lh) / 2.0, lw, lh,
                    preserveAspectRatio=True, mask="auto")
    else:
        c.setFillColor(white)
        c.setFont(FONT_BOLD, 25)
        c.drawString(PAD, hy + HEADER_H - 37, "Kelvin")
        _tracked(c, "SYMPHONY ORCHESTRA", PAD + 1, hy + HEADER_H - 52, FONT_BOLD, 8, 3.5, HEAD_SUB)
    _tracked(c, "E-TICKET", 0, hy + HEADER_H - 32, FONT_BOLD, 8, 2, HEAD_SUB, right=W - PAD)
    _tracked(c, "ADMIT ONE", 0, hy + HEADER_H - 49, FONT_BOLD, 13, 1, white, right=W - PAD)

    # ---- body ----
    y = hy - 26
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, TITLE_S)
    for line in _title_lines(shared["concert_title"]):
        c.drawString(PAD, y - TITLE_S, line)
        y -= (TITLE_S + LINE_GAP)

    y -= 6
    c.setFillColor(BODY)
    c.setFont(FONT, 11)
    when = shared["concert_date"]
    if shared.get("concert_time"):
        when += "   \u2022   " + shared["concert_time"]
    c.drawString(PAD, y - 11, when)
    y -= 20
    if shared.get("venue"):
        c.drawString(PAD, y - 11, shared["venue"])
        y -= 18

    # fields: Attendee / Ticket / Order — fixed size, wrapped over multiple lines
    y -= 20
    cols, _ = _fields(shared, row)
    for label, lines, cx in cols:
        _tracked(c, label, cx, y - 8, FONT_BOLD, 8, 0.8, TEAL)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, VAL_SIZE)
        yy = y - VAL_TOP
        for ln in lines:
            c.drawString(cx, yy, ln)
            yy -= VAL_LEAD

    # ---- perforation ----
    perf_y = STUB_PAD * 2 + QR_SIZE
    c.setStrokeColor(PERF)
    c.setLineWidth(1)
    c.setDash(3, 3)
    c.line(PAD, perf_y, W - PAD, perf_y)
    c.setDash()

    # ---- stub ----
    c.setFillColor(PANEL)
    c.rect(0, 0, W, perf_y, fill=1, stroke=0)

    c.drawImage(row["qr"], PAD, STUB_PAD, QR_SIZE, QR_SIZE,
                preserveAspectRatio=True, mask="auto")

    tx = PAD + QR_SIZE + 22
    tw = W - PAD - tx
    ty = STUB_PAD + QR_SIZE - 6
    c.setFillColor(BODY)
    c.setFont(FONT, 10)
    for line in simpleSplit("Scan this QR code at the door to check in.", FONT, 10, tw):
        c.drawString(tx, ty - 10, line)
        ty -= 14
    ty -= 8
    _tracked(c, "TICKET REFERENCE", tx, ty - 8, FONT_BOLD, 8, 0.8, TEAL)
    c.setFillColor(INK)
    c.setFont(FONT_MONO, 16)
    c.drawString(tx, ty - 26, row.get("ticket_id") or "")

    c.restoreState()

    c.setStrokeColor(HAIRLINE)
    c.setLineWidth(1)
    c.roundRect(0.5, 0.5, W - 1, H - 1, RADIUS, stroke=1, fill=0)


def render_tickets_pdf(shared: dict, rows: list) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, _page_height(shared, rows[0]) if rows else 400))
    for row in rows:
        H = _page_height(shared, row)
        c.setPageSize((W, H))
        _draw_ticket(c, H, shared, row)
        c.showPage()
    c.save()
    return buf.getvalue()


def _load_logo():
    """Load the header logo from staticfiles. Returns an ImageReader, or None to
    fall back to the text wordmark. Swap in a URL/path here if you prefer."""
    try:
        from django.contrib.staticfiles import finders
        path = finders.find("img/header/logo.png")
        return ImageReader(path) if path else None
    except Exception:
        return None


def build_ticket_pdf(order) -> bytes:
    """Django entry point: pull fields off the order and render all its tickets to PDF bytes."""
    tickets = order.tickets.select_related("ticket_type", "for_concert").all()
    concert = next((t.for_concert for t in tickets if t.for_concert), None)

    shared = {
        "logo": _load_logo(),
        "order_number": f"#{order.id}",
        "concert_title": concert.concert_name if concert else "",
        "concert_date": (
            f"{concert.concert_date.strftime('%A')} {concert.concert_date.day} "
            f"{concert.concert_date.strftime('%B %Y')}"
        ) if concert else "",
        "concert_time": concert.concert_time.strftime("%I:%M %p").lstrip("0") if concert else "",
        "venue": concert.concert_location if concert else "",
    }
    rows = [{
        "attendee": (t.name or order.customer_name or "").strip(),
        "ticket_type": t.ticket_type.ticket_label if t.ticket_type else "",
        "ticket_id": t.ticket_ID or "",
        # encode the raw reference; swap for a verify URL to make a phone-camera scan useful:
        # "qr": _qr_image(f"https://kelvin-symphony.co.uk/verify/{t.ticket_ID}"),
        "qr": _qr_image(t.ticket_ID or ""),
    } for t in tickets]

    return render_tickets_pdf(shared, rows)


if __name__ == "__main__":
    shared = {
        "order_number": "#35",
        "concert_title": "An Evening of Romantic Symphonies",
        "concert_date": "Sunday 30 November 2025",
        "concert_time": "7:30 PM",
        "venue": "Bute Hall, University of Glasgow",
    }
    rows = [
        {"attendee": "Yuki Suterno", "ticket_type": "Standard Seating",
         "ticket_id": "aB3kZ9qLmN7xR2pW", "qr": _qr_image("aB3kZ9qLmN7xR2pW")},
    ]
    open("ticket_preview.pdf", "wb").write(render_tickets_pdf(shared, rows))
    print("ok")