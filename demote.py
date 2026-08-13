# -*- coding: utf-8 -*-
"""Native Kodi context item: Demote from Favorite."""
import sys
from favorites import demote

item = getattr(sys, "listitem", None)
demote(item)
