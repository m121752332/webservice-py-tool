# -*- coding: utf-8 -*-
"""
XML 編輯器：等寬字型 + 語法上色（顏色跟著主題）
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QPlainTextEdit

from src.ui.theme import XmlColors

EDITOR_FONT_FAMILIES = ["Cascadia Mono", "Consolas"]
EDITOR_FONT_SIZE = 10
_IN_COMMENT = 1


def _char_format(color: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    return fmt


class XmlHighlighter(QSyntaxHighlighter):
    _TAG = QRegularExpression(r"</?([A-Za-z_][\w.:-]*)")
    _ATTRIBUTE = QRegularExpression(r"([A-Za-z_][\w.:-]*)\s*=\s*(\"[^\"]*\"|'[^']*')")
    _DECLARATION = QRegularExpression(r"<\?.*?\?>")

    def __init__(self, document, colors: XmlColors):
        super().__init__(document)
        self._colors = colors
        self._formats = self._build_formats(colors)

    @property
    def colors(self) -> XmlColors:
        return self._colors

    def set_colors(self, colors: XmlColors) -> None:
        self._colors = colors
        self._formats = self._build_formats(colors)
        self.rehighlight()

    @staticmethod
    def _build_formats(colors: XmlColors) -> dict[str, QTextCharFormat]:
        return {
            "tag": _char_format(colors.tag),
            "attr_name": _char_format(colors.attr_name),
            "attr_value": _char_format(colors.attr_value),
            "comment": _char_format(colors.comment),
            "declaration": _char_format(colors.declaration),
        }

    def highlightBlock(self, text: str) -> None:
        # 後套用的會覆蓋先套用的：宣告蓋過屬性，註解蓋過全部
        self._apply(self._TAG, text, {1: "tag"})
        self._apply(self._ATTRIBUTE, text, {1: "attr_name", 2: "attr_value"})
        self._apply(self._DECLARATION, text, {0: "declaration"})
        self._highlight_comments(text)

    def _apply(self, pattern: QRegularExpression, text: str, groups: dict[int, str]) -> None:
        matches = pattern.globalMatch(text)
        while matches.hasNext():
            match = matches.next()
            for group, key in groups.items():
                self.setFormat(match.capturedStart(group), match.capturedLength(group), self._formats[key])

    def _highlight_comments(self, text: str) -> None:
        self.setCurrentBlockState(0)
        start = 0 if self.previousBlockState() == _IN_COMMENT else text.find("<!--")
        while start >= 0:
            end = text.find("-->", start)
            if end < 0:
                self.setCurrentBlockState(_IN_COMMENT)
                length = len(text) - start
            else:
                length = end - start + 3
            self.setFormat(start, length, self._formats["comment"])
            start = text.find("<!--", start + length)


class XmlEditor(QPlainTextEdit):
    def __init__(self, colors: XmlColors, read_only: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("XmlEditor")
        font = QFont()
        font.setFamilies(EDITOR_FONT_FAMILIES)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(EDITOR_FONT_SIZE)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setReadOnly(read_only)
        self._highlighter = XmlHighlighter(self.document(), colors)

    @property
    def colors(self) -> XmlColors:
        return self._highlighter.colors

    def set_colors(self, colors: XmlColors) -> None:
        self._highlighter.set_colors(colors)
