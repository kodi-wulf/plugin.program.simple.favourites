# -*- coding: utf-8 -*-
"""Native Kodi context-item actions for Simple Favourites."""

import sys

import xbmcgui

from favorites import demote, is_favorite, promote, _selected_target


def main():
    item = getattr(sys, "listitem", None)
    if item is None:
        xbmcgui.Dialog().notification("Simple Favourites", "Kein Kodi-Element verfügbar", xbmcgui.NOTIFICATION_WARNING)
        return

    # The two native Kodi context entries are intentionally backed by the same
    # identity check. External providers such as xStream do not expose our
    # custom ListItem properties, so the exact original target URL is the
    # authoritative identity. The action itself therefore remains reliable
    # outside the Simple Favourites directory as well.
    target = _selected_target(item)
    if is_favorite(target):
        demote(item)
    else:
        promote(item)


if __name__ == "__main__":
    main()
