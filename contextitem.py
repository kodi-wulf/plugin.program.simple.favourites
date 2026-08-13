# -*- coding: utf-8 -*-
"""Kodi context-menu entry for promoting the currently selected item."""

import sys

import xbmcgui

from favorites import promote


def main():
    item = getattr(sys, "listitem", None)
    if item is None:
        xbmcgui.Dialog().notification("Simple Favourites", "Kein Kodi-Element verfügbar", xbmcgui.NOTIFICATION_WARNING)
        return
    promote(item)


if __name__ == "__main__":
    main()
