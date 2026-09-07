"""Translate text already materialized in a live Qt object tree."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDockWidget,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QWidget,
)

from insar_pilot.i18n import Translator


def retranslate_object_tree(root: QObject, source: Translator, target: Translator) -> None:
    """Replace exact catalog strings on existing widgets and actions in place.

    User-entered text and data-cell contents are deliberately excluded. Dynamic
    values are refreshed separately by their owning controllers.
    """

    translated = source.text_translator_to(target)

    objects = [root, *root.findChildren(QObject)]
    for obj in objects:
        _translate_common_text(obj, translated)
        if isinstance(obj, QMainWindow):
            obj.setWindowTitle(translated(obj.windowTitle()))
        if isinstance(obj, QDockWidget):
            obj.setWindowTitle(translated(obj.windowTitle()))
        if isinstance(obj, QMenu):
            obj.setTitle(translated(obj.title()))
        if isinstance(obj, QGroupBox):
            obj.setTitle(translated(obj.title()))
        if isinstance(obj, (QLabel, QAbstractButton)):
            obj.setText(translated(obj.text()))
        if isinstance(obj, (QLineEdit, QTextEdit, QPlainTextEdit)):
            obj.setPlaceholderText(translated(obj.placeholderText()))
        if isinstance(obj, QComboBox):
            for index in range(obj.count()):
                obj.setItemText(index, translated(obj.itemText(index)))
        if isinstance(obj, QTabWidget):
            for index in range(obj.count()):
                obj.setTabText(index, translated(obj.tabText(index)))
                obj.setTabToolTip(index, translated(obj.tabToolTip(index)))
        if isinstance(obj, QTableWidget):
            _translate_table_headers(obj, translated)
        if isinstance(obj, QTreeWidget):
            _translate_tree_headers(obj, translated)


def _translate_common_text(obj: QObject, translated: Callable[[str], str]) -> None:
    if isinstance(obj, QAction):
        obj.setText(translated(obj.text()))
        obj.setToolTip(translated(obj.toolTip()))
        obj.setStatusTip(translated(obj.statusTip()))
        obj.setWhatsThis(translated(obj.whatsThis()))
    if isinstance(obj, QWidget):
        obj.setToolTip(translated(obj.toolTip()))
        obj.setStatusTip(translated(obj.statusTip()))
        obj.setWhatsThis(translated(obj.whatsThis()))


def _translate_table_headers(table: QTableWidget, translated: Callable[[str], str]) -> None:
    for column in range(table.columnCount()):
        item = table.horizontalHeaderItem(column)
        if item is not None:
            item.setText(translated(item.text()))
    for row in range(table.rowCount()):
        item = table.verticalHeaderItem(row)
        if item is not None:
            item.setText(translated(item.text()))


def _translate_tree_headers(tree: QTreeWidget, translated: Callable[[str], str]) -> None:
    header = tree.headerItem()
    for column in range(tree.columnCount()):
        header.setText(column, translated(header.text(column)))
