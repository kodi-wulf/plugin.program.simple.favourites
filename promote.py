# -*- coding: utf-8 -*-
"""Native Kodi context item: Promote to Favorite."""
import sys
from favorites import promote

item = getattr(sys, "listitem", None)
promote(item)
