"""ESC/POS receipt + tag generation for Epson thermal printers.

Two outputs are produced for every workshop intake:

* **Innleveringskvittering** – the customer copy with order number, contact
  data, item summary and a QR linking back to the job-status page.
* **Verksteds-lapp** – the bag tag attached to the physical item, prominent
  customer name, contents/description and the same QR for quick lookup.

Both are returned as raw ESC/POS byte streams that can be piped directly to a
TM-series Epson (USB / network / Bluetooth). Rendered by hand to keep the
dependency surface small and avoid native build issues on Windows.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Iterable, Optional

import qrcode
from PIL import Image

from .models import Job, PrinterConfig

# --- ESC/POS primitives ------------------------------------------------------
ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"
LF = b"\n"
CUT = GS + b"V" + b"\x42\x00"     # partial cut, feed
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
UNDER_ON = ESC + b"-\x01"
UNDER_OFF = ESC + b"-\x00"
SIZE_NORMAL = GS + b"!\x00"
SIZE_DOUBLE_H = GS + b"!\x01"
SIZE_DOUBLE_W = GS + b"!\x10"
SIZE_DOUBLE = GS + b"!\x11"      # double width AND height
CHARSET_NORWAY = ESC + b"R\x09"  # international charset = Norway (æøå)
CODEPAGE_PC865 = ESC + b"t\x05"  # PC865 Nordic (æ=0x91 ø=0x9B å=0x86 etc.)


def _enc(text: str) -> bytes:
    """Encode to PC865 (Nordic). Falls back to ascii-replace for safety."""
    try:
        return text.encode("cp865")
    except UnicodeEncodeError:
        return text.encode("ascii", "replace")


@dataclass
class _Buf:
    out: bytearray

    def write(self, b: bytes) -> None:
        self.out.extend(b)

    def text(self, s: str, end: bytes = LF) -> None:
        self.out.extend(_enc(s))
        if end:
            self.out.extend(end)


# --- Raster image (QR / bitmap) ---------------------------------------------
def _raster_image(img: Image.Image, max_dots: int) -> bytes:
    """Render a 1-bpp PIL image as ESC/POS GS v 0 raster bit image."""
    if img.mode != "1":
        img = img.convert("L").point(lambda v: 0 if v < 160 else 255, "1")
    if img.width > max_dots:
        ratio = max_dots / img.width
        img = img.resize((max_dots, int(img.height * ratio)))
    # ensure width multiple of 8
    pad_w = (8 - img.width % 8) % 8
    if pad_w:
        new = Image.new("1", (img.width + pad_w, img.height), 1)  # white pad
        new.paste(img, (0, 0))
        img = new
    width_bytes = img.width // 8
    raster = bytearray()
    pixels = img.load()
    for y in range(img.height):
        for xb in range(width_bytes):
            byte = 0
            for bit in range(8):
                if pixels[xb * 8 + bit, y] == 0:  # black
                    byte |= 1 << (7 - bit)
            raster.append(byte)
    header = GS + b"v0\x00" + bytes([width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
                                     img.height & 0xFF, (img.height >> 8) & 0xFF])
    return bytes(header + raster)


def _qr_image(payload: str, box_size: int = 6, border: int = 2) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=box_size, border=border)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").get_image()


# --- Helpers -----------------------------------------------------------------
def _line(buf: _Buf, char: str = "-", width_chars: int = 42) -> None:
    buf.text(char * width_chars)


def _kv(buf: _Buf, key: str, value: str, width_chars: int = 42) -> None:
    if value is None:
        value = ""
    line = f"{key}: {value}"
    if len(line) > width_chars:
        buf.text(f"{key}:")
        # word-wrap value
        words, cur = value.split(), ""
        for w in words:
            if len(cur) + len(w) + 1 > width_chars:
                buf.text(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            buf.text(cur)
    else:
        buf.text(line)


def _money(amount) -> str:
    if amount is None:
        return "—"
    try:
        return f"kr {float(amount):,.2f}".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return str(amount)


def _qr_payload(job: Job, cfg: Optional[PrinterConfig]) -> str:
    if cfg and cfg.receipt_url_template:
        return cfg.receipt_url_template.format(token=job.qr_token or "", id=job.id,
                                               number=job.job_number or "",
                                               code=job.pickup_code or "")
    return f"GVK|{job.job_number}|{job.pickup_code or ''}|{job.qr_token or ''}"


def _width_chars(cfg: Optional[PrinterConfig]) -> int:
    if cfg and cfg.paper_width_mm and cfg.paper_width_mm <= 58:
        return 32
    return 42


# --- Public renderers --------------------------------------------------------
def render_receipt(job: Job, cfg: Optional[PrinterConfig]) -> bytes:
    width_chars = _width_chars(cfg)
    dots = (cfg.dots_per_line if cfg and cfg.dots_per_line else 576)
    qr_dots = min(dots - 40, 320)

    buf = _Buf(bytearray())
    buf.write(INIT + CHARSET_NORWAY + CODEPAGE_PC865 + ALIGN_CENTER + SIZE_DOUBLE + BOLD_ON)
    buf.text((cfg.header_line1 if cfg and cfg.header_line1 else "GULLSMED VERKSTED").upper())
    buf.write(SIZE_NORMAL + BOLD_OFF)
    if cfg and cfg.header_line2:
        buf.text(cfg.header_line2)
    if cfg and cfg.header_line3:
        buf.text(cfg.header_line3)
    buf.write(LF + ALIGN_LEFT)
    _line(buf, "=", width_chars)
    buf.write(ALIGN_CENTER + BOLD_ON + SIZE_DOUBLE_H)
    buf.text("INNLEVERINGSKVITTERING")
    buf.write(SIZE_NORMAL + BOLD_OFF + ALIGN_LEFT)
    _line(buf, "=", width_chars)

    buf.write(BOLD_ON)
    buf.text(f"Ordrenr: {job.job_number}")
    buf.write(BOLD_OFF)
    if job.pickup_code:
        buf.text(f"Hentekode: {job.pickup_code}")
    buf.text(f"Dato: {job.created_at.strftime('%d.%m.%Y %H:%M') if job.created_at else ''}")
    if job.estimated_completion:
        buf.text(f"Estimert ferdig: {job.estimated_completion.strftime('%d.%m.%Y')}")

    _line(buf, "-", width_chars)
    buf.write(BOLD_ON); buf.text("KUNDE"); buf.write(BOLD_OFF)
    if job.customer:
        buf.text(job.customer.name)
        if job.customer.phone:
            buf.text(job.customer.phone)
        if job.customer.email:
            buf.text(job.customer.email)
    else:
        buf.text("Walk-in")

    _line(buf, "-", width_chars)
    buf.write(BOLD_ON); buf.text("ARBEID"); buf.write(BOLD_OFF)
    type_map = {"repair": "Reparasjon", "design": "Design", "sale": "Salg", "other": "Annet"}
    buf.text(f"Type: {type_map.get(getattr(job.job_type, 'value', str(job.job_type)), str(job.job_type))}")
    if job.metal_type:
        _kv(buf, "Metall", job.metal_type, width_chars)
    if job.gemstones:
        _kv(buf, "Stener", job.gemstones, width_chars)
    if job.estimated_weight_g is not None:
        buf.text(f"Vekt:    {job.estimated_weight_g} g")
    if job.description:
        buf.text("")
        _kv(buf, "Beskrivelse", job.description, width_chars)
    if job.condition_notes:
        buf.text("")
        _kv(buf, "Tilstand", job.condition_notes, width_chars)

    _line(buf, "-", width_chars)
    buf.write(BOLD_ON + SIZE_DOUBLE_H)
    buf.text(f"Estimat: {_money(job.estimated_price)}")
    buf.write(SIZE_NORMAL + BOLD_OFF)
    buf.text("(Endelig pris kan avvike etter inspeksjon.)")

    if not cfg or cfg.print_qr_on_receipt:
        _line(buf, "-", width_chars)
        buf.write(ALIGN_CENTER)
        buf.write(_raster_image(_qr_image(_qr_payload(job, cfg), box_size=6), qr_dots))
        buf.write(LF + ALIGN_LEFT)
        buf.write(ALIGN_CENTER)
        buf.text("Skann for status")
        buf.write(ALIGN_LEFT)

    _line(buf, "-", width_chars)
    buf.text("Vennligst ta vare på denne kvitteringen.")
    buf.text("Den må fremvises ved henting.")
    buf.write(LF + ALIGN_CENTER)
    if cfg and cfg.footer_line:
        buf.text(cfg.footer_line)
    buf.write(ALIGN_LEFT + LF + LF + LF)
    if not cfg or cfg.cut_paper:
        buf.write(CUT)
    return bytes(buf.out)


def render_tag(job: Job, cfg: Optional[PrinterConfig]) -> bytes:
    """Bag tag attached to the physical item."""
    width_chars = _width_chars(cfg)
    dots = (cfg.dots_per_line if cfg and cfg.dots_per_line else 576)
    qr_dots = min(dots - 40, 280)

    buf = _Buf(bytearray())
    buf.write(INIT + CHARSET_NORWAY + CODEPAGE_PC865)
    buf.write(ALIGN_CENTER + BOLD_ON + SIZE_DOUBLE)
    buf.text(f"#{job.job_number}")
    buf.write(SIZE_NORMAL + BOLD_OFF)
    if job.pickup_code:
        buf.text(f"Hent: {job.pickup_code}")
    buf.write(LF)

    buf.write(_raster_image(_qr_image(_qr_payload(job, cfg), box_size=6), qr_dots))
    buf.write(LF + ALIGN_LEFT)
    _line(buf, "=", width_chars)

    buf.write(BOLD_ON); buf.text("KUNDE"); buf.write(BOLD_OFF)
    if job.customer:
        buf.write(SIZE_DOUBLE_H); buf.text(job.customer.name); buf.write(SIZE_NORMAL)
        if job.customer.phone:
            buf.text(job.customer.phone)
    else:
        buf.text("Walk-in")

    _line(buf, "-", width_chars)
    buf.write(BOLD_ON); buf.text("INNHOLD"); buf.write(BOLD_OFF)
    if job.metal_type:
        _kv(buf, "Metall", job.metal_type, width_chars)
    if job.gemstones:
        _kv(buf, "Stener", job.gemstones, width_chars)
    if job.estimated_weight_g is not None:
        buf.text(f"Vekt: {job.estimated_weight_g} g")

    if job.description:
        _line(buf, "-", width_chars)
        buf.write(BOLD_ON); buf.text("BESKRIVELSE"); buf.write(BOLD_OFF)
        _kv(buf, "", job.description, width_chars)
        # _kv prints "" prefix line, replace by writing description directly:
    if job.condition_notes:
        _line(buf, "-", width_chars)
        buf.write(BOLD_ON); buf.text("TILSTAND"); buf.write(BOLD_OFF)
        _kv(buf, "", job.condition_notes, width_chars)

    _line(buf, "=", width_chars)
    buf.text(f"Mottatt: {job.created_at.strftime('%d.%m.%Y %H:%M') if job.created_at else ''}")
    if job.location:
        buf.text(f"Lokasjon: {job.location.label}")
    buf.write(LF + LF + LF)
    if not cfg or cfg.cut_paper:
        buf.write(CUT)
    return bytes(buf.out)


# --- HTML preview (browser-based printing fallback) -------------------------
def _qr_data_uri(payload: str) -> str:
    img = _qr_image(payload, box_size=8, border=2)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    import base64
    return "data:image/png;base64," + base64.b64encode(bio.getvalue()).decode("ascii")


_HTML_BASE = """<!doctype html>
<html lang="nb"><head><meta charset="utf-8"/>
<title>{title}</title>
<style>
  @page {{ size: {width_mm}mm auto; margin: 3mm; }}
  html, body {{ width: {width_mm}mm; margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #000; }}
  body {{ padding: 4mm; font-size: 11pt; }}
  h1 {{ font-size: 18pt; margin: 0 0 2mm 0; text-align: center; letter-spacing: 0.5px; }}
  h2 {{ font-size: 12pt; margin: 4mm 0 1mm 0; border-bottom: 1px solid #000; padding-bottom: 1mm; }}
  .center {{ text-align: center; }}
  .big {{ font-size: 16pt; font-weight: 700; }}
  .xl  {{ font-size: 22pt; font-weight: 800; }}
  .muted {{ color: #444; font-size: 9pt; }}
  .row  {{ display: flex; justify-content: space-between; gap: 4mm; }}
  .qr   {{ display: block; margin: 3mm auto; width: 60mm; height: 60mm; }}
  .sep  {{ border-top: 1px dashed #555; margin: 3mm 0; }}
  .estimate {{ text-align: center; font-size: 16pt; font-weight: 800; padding: 2mm 0; border: 1px solid #000; }}
  pre  {{ white-space: pre-wrap; font: inherit; margin: 0; }}
</style>
</head><body>
{body}
<script>{script}</script>
</body></html>"""


def render_receipt_html(job: Job, cfg: Optional[PrinterConfig], auto_print: bool = True) -> str:
    width_mm = cfg.paper_width_mm if cfg and cfg.paper_width_mm else 80
    qr = _qr_data_uri(_qr_payload(job, cfg))
    type_map = {"repair": "Reparasjon", "design": "Design", "sale": "Salg", "other": "Annet"}
    jt = type_map.get(getattr(job.job_type, "value", str(job.job_type)), str(job.job_type))
    parts = []
    parts.append(f"<h1>{(cfg.header_line1 if cfg and cfg.header_line1 else 'Gullsmed Verksted').upper()}</h1>")
    if cfg and cfg.header_line2:
        parts.append(f"<div class='center muted'>{cfg.header_line2}</div>")
    if cfg and cfg.header_line3:
        parts.append(f"<div class='center muted'>{cfg.header_line3}</div>")
    parts.append("<div class='sep'></div>")
    parts.append("<h2 class='center'>Innleveringskvittering</h2>")
    parts.append(f"<div class='row'><div><b>Ordrenr</b><br><span class='big'>{job.job_number}</span></div>"
                 f"<div style='text-align:right'><b>Hentekode</b><br><span class='big'>{job.pickup_code or '—'}</span></div></div>")
    parts.append(f"<div class='muted'>Dato: {job.created_at.strftime('%d.%m.%Y %H:%M') if job.created_at else ''}</div>")
    if job.estimated_completion:
        parts.append(f"<div class='muted'>Estimert ferdig: {job.estimated_completion.strftime('%d.%m.%Y')}</div>")

    parts.append("<h2>Kunde</h2>")
    if job.customer:
        parts.append(f"<div class='big'>{job.customer.name}</div>")
        if job.customer.phone: parts.append(f"<div>{job.customer.phone}</div>")
        if job.customer.email: parts.append(f"<div class='muted'>{job.customer.email}</div>")
    else:
        parts.append("<div>Walk-in</div>")

    parts.append("<h2>Arbeid</h2>")
    parts.append(f"<div><b>Type:</b> {jt}</div>")
    if job.metal_type: parts.append(f"<div><b>Metall:</b> {job.metal_type}</div>")
    if job.gemstones:  parts.append(f"<div><b>Stener:</b> {job.gemstones}</div>")
    if job.estimated_weight_g is not None: parts.append(f"<div><b>Vekt:</b> {job.estimated_weight_g} g</div>")
    if job.description: parts.append(f"<div style='margin-top:2mm'><b>Beskrivelse:</b><br><pre>{_esc(job.description)}</pre></div>")
    if job.condition_notes: parts.append(f"<div style='margin-top:2mm'><b>Tilstand:</b><br><pre>{_esc(job.condition_notes)}</pre></div>")

    parts.append(f"<div class='estimate'>Estimat: {_money(job.estimated_price)}</div>")
    parts.append("<div class='muted center'>Endelig pris kan avvike etter inspeksjon.</div>")

    if not cfg or cfg.print_qr_on_receipt:
        parts.append(f"<img class='qr' src='{qr}' alt='QR'/>")
        parts.append("<div class='center muted'>Skann for status</div>")

    parts.append("<div class='sep'></div>")
    parts.append("<div class='center'>Vennligst ta vare på denne kvitteringen.<br>Må fremvises ved henting.</div>")
    if cfg and cfg.footer_line:
        parts.append(f"<div class='center muted' style='margin-top:3mm'>{cfg.footer_line}</div>")

    body = "\n".join(parts)
    script = "window.onload=function(){setTimeout(function(){window.print()},250)};" if auto_print else ""
    return _HTML_BASE.format(title=f"Kvittering {job.job_number}", width_mm=width_mm, body=body, script=script)


def render_tag_html(job: Job, cfg: Optional[PrinterConfig], auto_print: bool = True) -> str:
    width_mm = cfg.paper_width_mm if cfg and cfg.paper_width_mm else 80
    qr = _qr_data_uri(_qr_payload(job, cfg))
    parts = []
    parts.append(f"<div class='center xl'>#{job.job_number}</div>")
    if job.pickup_code:
        parts.append(f"<div class='center'>Hent: <b>{job.pickup_code}</b></div>")
    parts.append(f"<img class='qr' src='{qr}' alt='QR'/>")
    parts.append("<div class='sep'></div>")
    parts.append("<h2>Kunde</h2>")
    if job.customer:
        parts.append(f"<div class='big'>{job.customer.name}</div>")
        if job.customer.phone: parts.append(f"<div>{job.customer.phone}</div>")
    else:
        parts.append("<div>Walk-in</div>")
    parts.append("<h2>Innhold</h2>")
    if job.metal_type: parts.append(f"<div><b>Metall:</b> {job.metal_type}</div>")
    if job.gemstones:  parts.append(f"<div><b>Stener:</b> {job.gemstones}</div>")
    if job.estimated_weight_g is not None: parts.append(f"<div><b>Vekt:</b> {job.estimated_weight_g} g</div>")
    if job.description:
        parts.append("<h2>Beskrivelse</h2>")
        parts.append(f"<pre>{_esc(job.description)}</pre>")
    if job.condition_notes:
        parts.append("<h2>Tilstand</h2>")
        parts.append(f"<pre>{_esc(job.condition_notes)}</pre>")
    parts.append("<div class='sep'></div>")
    if job.created_at:
        parts.append(f"<div class='muted'>Mottatt: {job.created_at.strftime('%d.%m.%Y %H:%M')}</div>")
    if job.location:
        parts.append(f"<div class='muted'>Lokasjon: {job.location.label}</div>")
    body = "\n".join(parts)
    script = "window.onload=function(){setTimeout(function(){window.print()},250)};" if auto_print else ""
    return _HTML_BASE.format(title=f"Lapp {job.job_number}", width_mm=width_mm, body=body, script=script)


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
