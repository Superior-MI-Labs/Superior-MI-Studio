"""Native Qt syntax colors. Decorative only; no language semantics here."""
from __future__ import annotations
import keyword
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class PythonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        def fmt(color, bold=False):
            style=QTextCharFormat();style.setForeground(QColor(color))
            if bold:style.setFontWeight(QFont.Weight.DemiBold)
            return style
        words='|'.join(keyword.kwlist)
        self.rules=[
            (QRegularExpression(r'\b(?:'+words+r')\b'),fmt('#77b8f7',True)),
            (QRegularExpression(r'\b[0-9]+(?:\.[0-9]+)?\b'),fmt('#eac17b')),
            (QRegularExpression(r'"(?:[^"\\]|\\.)*"|\x27(?:[^\x27\\]|\\.)*\x27'),fmt('#b5d996')),
            (QRegularExpression(r'#[^\n]*'),fmt('#758ba3')),
        ]

    def highlightBlock(self,text):
        for pattern,style in self.rules:
            matches=pattern.globalMatch(text)
            while matches.hasNext():
                m=matches.next()
                self.setFormat(m.capturedStart(),m.capturedLength(),style)
