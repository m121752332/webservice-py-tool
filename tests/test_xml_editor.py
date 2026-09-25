# -*- coding: utf-8 -*-
from src.ui.theme import DARK, LIGHT
from src.ui.xml_editor import XmlEditor


def formats_of(editor, block_number=0):
    block = editor.document().findBlockByNumber(block_number)
    return [
        (fmt.start, fmt.length, fmt.format.foreground().color().name().upper())
        for fmt in block.layout().formats()
    ]


def test_highlights_tag_attribute_and_value(qapp):
    editor = XmlEditor(LIGHT.xml)
    editor.setPlainText('<Field name="pmm01"/>')
    formats = formats_of(editor)
    assert (1, 5, LIGHT.xml.tag) in formats
    assert (7, 4, LIGHT.xml.attr_name) in formats
    assert (12, 7, LIGHT.xml.attr_value) in formats


def test_highlights_closing_tag(qapp):
    editor = XmlEditor(LIGHT.xml)
    editor.setPlainText("</Record>")
    assert (2, 6, LIGHT.xml.tag) in formats_of(editor)


def test_highlights_declaration_and_multiline_comment(qapp):
    editor = XmlEditor(LIGHT.xml)
    editor.setPlainText('<?xml version="1.0"?>\n<!-- a\nb -->\n<c/>')
    assert (0, 21, LIGHT.xml.declaration) in formats_of(editor, 0)
    assert (0, 6, LIGHT.xml.comment) in formats_of(editor, 1)
    assert (0, 5, LIGHT.xml.comment) in formats_of(editor, 2)
    assert (1, 1, LIGHT.xml.tag) in formats_of(editor, 3)


def test_set_colors_rehighlights(qapp):
    editor = XmlEditor(LIGHT.xml)
    editor.setPlainText("<a/>")
    editor.set_colors(DARK.xml)
    assert editor.colors == DARK.xml
    assert (1, 1, DARK.xml.tag) in formats_of(editor)


def test_read_only_flag(qapp):
    assert XmlEditor(LIGHT.xml, read_only=True).isReadOnly()
    assert not XmlEditor(LIGHT.xml).isReadOnly()


def test_uses_monospace_font(qapp):
    families = XmlEditor(LIGHT.xml).font().families()
    assert families[:2] == ["Cascadia Mono", "Consolas"]
