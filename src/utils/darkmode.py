# -- coding: utf-8 --
# @Time : 2024/03/31
# @Author : Tiger
# @File : darkmode.py
# @Software: vscode
import wx

try:
    from ObjectListView import ObjectListView
except ImportError:
    ObjectListView = False


# ----------------------------------------------------------------------
def get_widgets(parent):
    """
    Return a list of all the child widgets
    """
    items = [parent]
    for item in parent.GetChildren():
        items.append(item)
        if hasattr(item, "GetChildren"):
            for child in item.GetChildren():
                items.append(child)
    return items


# ----------------------------------------------------------------------
def dark_row_formatter(list_ctrl, dark=False):
    """
    Toggles the rows in a ListCtrl or ObjectListView widget.
    Based loosely on the following documentation:
    http://objectlistview.sourceforge.net/python/recipes.html#recipe-formatter
    and http://objectlistview.sourceforge.net/python/cellEditing.html
    """

    listItems = [list_ctrl.GetItem(i) for i in range(list_ctrl.GetItemCount())]
    for index, item in enumerate(listItems):
        if dark:
            if index % 2:
                item.SetBackgroundColour("Dark Grey")
            else:
                item.SetBackgroundColour("Light Grey")
        else:
            if index % 2:
                item.SetBackgroundColour("Light Blue")
            else:
                item.SetBackgroundColour("Yellow")
        list_ctrl.SetItem(item)


# ----------------------------------------------------------------------
def dark_mode(self, normalPanelColor):
    """
    Toggles dark mode
    """
    widgets = get_widgets(self)
    panel = widgets[0]
    if normalPanelColor == panel.GetBackgroundColour():
        dark_mode = True
    else:
        dark_mode = False
    for widget in widgets:
        if dark_mode:
            if isinstance(widget, ObjectListView) or isinstance(widget, wx.ListCtrl):
                dark_row_formatter(widget, dark=True)
            widget.SetBackgroundColour("Dark Grey")
            widget.SetForegroundColour("White")
        else:
            if isinstance(widget, ObjectListView) or isinstance(widget, wx.ListCtrl):
                dark_row_formatter(widget)
                widget.SetBackgroundColour("White")
                widget.SetForegroundColour("Black")
                continue
            widget.SetBackgroundColour(wx.NullColour)
            widget.SetForegroundColour("Black")
    self.Refresh()
    return dark_mode
