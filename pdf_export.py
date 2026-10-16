from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor


def text_pdf(title: str, content: str) -> bytes:
    if "SyllaKR" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("SyllaKR", str(Path(__file__).parent / "assets/NanumGothic-Regular.ttf")))
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, topMargin=42, bottomMargin=42, title=title, author="SyllaSync")
    style = ParagraphStyle("body", fontName="SyllaKR", fontSize=10, leading=17, wordWrap="CJK", textColor=HexColor("#183b3a"))
    heading = ParagraphStyle("title", parent=style, fontSize=21, leading=29, spaceAfter=18)
    story = [Paragraph(escape(title), heading)]
    for line in content.splitlines():
        story.append(Paragraph(escape(line), style) if line else Spacer(1, 10))
    doc.build(story)
    return buf.getvalue()
