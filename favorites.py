# -*- coding: utf-8 -*-
"""Simple Favourites - editable, persistent media shortcuts for Kodi."""

import json
import os
import sys
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON_ID = "plugin.program.simple.favourites"
VERSION = "0.1.33~alpha7"
FAVORITE_PROPERTY = "SimpleFavourites.IsFavorite"
FAVORITE_ID_PROPERTY = "SimpleFavourites.FavoriteId"
ADDON = xbmcaddon.Addon(ADDON_ID)
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
ROOT = "special://profile/addon_data/%s/" % ADDON_ID
STORE = ROOT + "favorites.json"

CATEGORIES = (
    ("movies", "Filme", "special://home/addons/%s/resources/img/movies.png" % ADDON_ID),
    ("series", "Serien", "special://home/addons/%s/resources/img/popular.png" % ADDON_ID),
    ("music", "Musik", "special://home/addons/%s/resources/img/music.png" % ADDON_ID),
    ("tvserver", "TV-Sender", "special://home/addons/%s/resources/img/tv.png" % ADDON_ID),
)


def _ensure_root():
    xbmcvfs.mkdirs(ROOT)


def _atomic_write(data):
    _ensure_root()
    tmp = STORE + ".tmp"
    f = xbmcvfs.File(tmp, "w")
    f.write(json.dumps(data, ensure_ascii=False, indent=2))
    f.close()
    if xbmcvfs.exists(STORE):
        xbmcvfs.delete(STORE)
    xbmcvfs.rename(tmp, STORE)


def _default_store():
    return {"schema": 2, "version": VERSION, "folders": {
        key: {"id": key, "name": name, "parent": None, "builtin": True}
        for key, name, _ in CATEGORIES
    }, "items": []}


def _load():
    _ensure_root()
    if not xbmcvfs.exists(STORE):
        data = _default_store()
        _atomic_write(data)
        return data
    try:
        f = xbmcvfs.File(STORE, "r")
        data = json.loads(f.read())
        f.close()
        if not isinstance(data, dict):
            raise ValueError("invalid store")
        data.setdefault("schema", 2)
        data.setdefault("folders", {})
        data.setdefault("items", [])
        changed = False
        for key, name, _ in CATEGORIES:
            if key not in data["folders"]:
                data["folders"][key] = {"id": key, "name": name, "parent": None, "builtin": True}
                changed = True
        data["schema"] = 2
        if changed:
            _atomic_write(data)
        return data
    except Exception as exc:
        xbmc.log("Simple Favourites: store read failed: %s" % exc, xbmc.LOGERROR)
        return _default_store()


def _save(data):
    data["version"] = VERSION
    _atomic_write(data)


def _folder_children(data, parent):
    return [f for f in data["folders"].values() if f.get("parent") == parent]


def _items_for(data, folder):
    return [i for i in data["items"] if i.get("folder") == folder]


def _new_id(prefix):
    return "%s-%d-%d" % (prefix, int(time.time() * 1000), os.getpid())


def _category_for_item(item):
    dbtype = (item.get("dbtype") or "").lower()
    mimetype = (item.get("mimetype") or "").lower()
    path = (item.get("target") or "").lower()
    if dbtype == "movie" or "/movie" in path:
        return "movies"
    if dbtype in ("tvshow", "season", "episode") or "tvshow" in path:
        return "series"
    if dbtype in ("song", "album", "artist") or mimetype.startswith("audio/"):
        return "music"
    if path.startswith("pvr://") or dbtype in ("channel", "recording"):
        return "tvserver"
    return None


def _selected_target(item):
    target = item.getPath() or item.getProperty("path") or ""
    if not target.startswith(("plugin://", "pvr://", "http://", "https://", "smb://", "nfs://", "file://")):
        target = item.getProperty("originalpath") or item.getProperty("OriginalPath") or target
    return target


def _find_favorite(data, target):
    """Stable recognition: target URL is the identity of a shortcut."""
    if not target:
        return None
    for item in data["items"]:
        if item.get("target") == target:
            return item
    return None


def is_favorite(target):
    return _find_favorite(_load(), target) is not None


def _all_folder_choices(data, exclude=None):
    """Return every editable directory, with its full logical path."""
    folders = data["folders"]
    children = {}
    for folder in folders.values():
        children.setdefault(folder.get("parent"), []).append(folder)

    result = []

    def walk(parent, prefix):
        for folder in sorted(children.get(parent, []), key=lambda x: x.get("name", "").casefold()):
            if folder["id"] != exclude:
                path = "%s / %s" % (prefix, folder["name"]) if prefix else folder["name"]
                result.append((folder["id"], path))
                walk(folder["id"], path)

    walk(None, "")
    return result


def _choose_destination(data, suggested=None):
    """After promotion, always ask where the shortcut should be stored."""
    choices = _all_folder_choices(data)
    if not choices:
        return None
    labels = [label for _, label in choices]
    preselect = next((n for n, (folder_id, _) in enumerate(choices) if folder_id == suggested), 0)
    selected = xbmcgui.Dialog().select("Favorit ablegen in", labels, preselect=preselect)
    if selected < 0:
        return None
    return choices[selected][0]


def promote(item=None):
    item = item or getattr(sys, "listitem", None)
    if item is None:
        return
    target = _selected_target(item)
    if not target:
        xbmcgui.Dialog().notification("Simple Favourites", "Kein gültiges Ziel gefunden", xbmcgui.NOTIFICATION_WARNING)
        return

    data = _load()
    existing = _find_favorite(data, target)
    if existing:
        # No duplicate and, importantly, no silent update anymore.
        xbmcgui.Dialog().notification("Simple Favourites", "Bereits als Favorit gespeichert", xbmcgui.NOTIFICATION_INFO)
        return

    suggested = _category_for_item({
        "dbtype": item.getProperty("dbtype"),
        "mimetype": item.getProperty("mimetype"),
        "target": target,
    })
    folder_id = _choose_destination(data, suggested)
    if not folder_id:
        return

    title = item.getLabel() or "Favorit"
    favorite_id = _new_id("fav")
    data["items"].append({
        "id": favorite_id,
        "folder": folder_id,
        "label": title,
        "target": target,
        "thumbnail": item.getArt("thumb") or item.getArt("poster") or "",
        "fanart": item.getArt("fanart") or "",
        "is_folder": bool(item.isFolder()),
        "dbtype": item.getProperty("dbtype") or "",
        "mimetype": item.getProperty("mimetype") or "",
        "created": int(time.time()),
    })
    _save(data)
    xbmcgui.Dialog().notification("Simple Favourites", "%s zu Favoriten hinzugefügt" % title)
    xbmc.executebuiltin("Container.Refresh")


def demote(item=None):
    """Remove the exact source target from Simple Favourites."""
    item = item or getattr(sys, "listitem", None)
    if item is None:
        return
    target = _selected_target(item)
    data = _load()
    existing = _find_favorite(data, target)
    if not existing:
        xbmcgui.Dialog().notification("Simple Favourites", "Kein Favorit für dieses Element gefunden", xbmcgui.NOTIFICATION_INFO)
        return
    title = existing.get("label", item.getLabel() or "Favorit")
    if not xbmcgui.Dialog().yesno("Favorit entfernen", "Soll '%s' aus den Favoriten entfernt werden?" % title):
        return
    data["items"] = [i for i in data["items"] if i.get("id") != existing.get("id")]
    _save(data)
    xbmcgui.Dialog().notification("Simple Favourites", "%s aus Favoriten entfernt" % title)
    xbmc.executebuiltin("Container.Refresh")


def annotate_item(item, favorite=None):
    """Set an explicit marker on items rendered by Simple Favourites."""
    if favorite is None:
        favorite = _find_favorite(_load(), _selected_target(item))
    if favorite:
        item.setProperty(FAVORITE_PROPERTY, "true")
        item.setProperty(FAVORITE_ID_PROPERTY, favorite.get("id", ""))
    else:
        item.setProperty(FAVORITE_PROPERTY, "false")
        item.clearProperty(FAVORITE_ID_PROPERTY)


def _add_item(label, target, thumb="", fanart="", is_folder=False, context=None, favorite=None):
    li = xbmcgui.ListItem(label=label)
    if thumb:
        li.setArt({"thumb": thumb, "icon": thumb})
    if fanart:
        li.setArt({"fanart": fanart})
    li.setProperty("IsPlayable", "false" if is_folder else "true")
    annotate_item(li, favorite)
    if context:
        li.addContextMenuItems(context, replaceItems=False)
    xbmcplugin.addDirectoryItem(HANDLE, target, li, is_folder)


def _plugin_url(action, **params):
    query = urllib.parse.urlencode({"action": action, **params})
    return "plugin://%s/?%s" % (ADDON_ID, query)


def _run(url):
    return "RunPlugin(%s)" % url


def _refresh():
    xbmc.executebuiltin("Container.Refresh")


def _prompt_name(title, default=""):
    return xbmcgui.Dialog().input(title, default, type=xbmcgui.INPUT_ALPHANUM)


def _folder_context(folder):
    result = []
    if not folder.get("builtin"):
        result += [("Ordner umbenennen", _run(_plugin_url("rename_folder", folder=folder["id"]))),
                   ("Ordner löschen", _run(_plugin_url("delete_folder", folder=folder["id"]))) ]
    result.append(("Unterordner erstellen", _run(_plugin_url("new_folder", parent=folder["id"]))))
    return result


def _item_context(item):
    return [("Favorit entfernen", _run(_plugin_url("remove_item", item=item["id"]))),
            ("Favorit umbenennen", _run(_plugin_url("rename_item", item=item["id"]))),
            ("Verschieben", _run(_plugin_url("move_item", item=item["id"])))]


def root():
    data = _load()
    for key, name, icon in CATEGORIES:
        _add_item(name, _plugin_url("folder", folder=key), icon, is_folder=True,
                  context=_folder_context(data["folders"][key]))
    xbmcplugin.setContent(HANDLE, "files")
    xbmcplugin.endOfDirectory(HANDLE)


def folder(folder_id):
    data = _load()
    if folder_id not in data["folders"]:
        root()
        return
    for child in sorted(_folder_children(data, folder_id), key=lambda x: x.get("name", "").casefold()):
        _add_item(child["name"], _plugin_url("folder", folder=child["id"]), child.get("thumbnail", ""),
                  child.get("fanart", ""), True, _folder_context(child))
    for item in sorted(_items_for(data, folder_id), key=lambda x: x.get("label", "").casefold()):
        _add_item(item.get("label", "Favorit"), item.get("target", ""), item.get("thumbnail", ""),
                  item.get("fanart", ""), bool(item.get("is_folder")), _item_context(item), item)
    _add_item("+ Unterordner erstellen", _plugin_url("new_folder", parent=folder_id),
              "special://home/addons/%s/resources/img/folder.png" % ADDON_ID)
    xbmcplugin.setContent(HANDLE, "files")
    xbmcplugin.endOfDirectory(HANDLE)


def new_folder(parent):
    data = _load()
    if parent not in data["folders"]:
        return
    name = _prompt_name("Neuer Favoriten-Unterordner")
    if not name:
        return
    if any(f.get("parent") == parent and f.get("name", "").casefold() == name.casefold() for f in data["folders"].values()):
        xbmcgui.Dialog().notification("Simple Favourites", "Ordner existiert bereits", xbmcgui.NOTIFICATION_WARNING)
        return
    folder_id = _new_id("folder")
    data["folders"][folder_id] = {"id": folder_id, "name": name, "parent": parent, "builtin": False}
    _save(data)
    _refresh()


def delete_folder(folder_id):
    data = _load()
    folder = data["folders"].get(folder_id)
    if not folder or folder.get("builtin"):
        return
    if not xbmcgui.Dialog().yesno("Ordner löschen", "Ordner und seine Favoriten löschen?", "", folder.get("name", "")):
        return
    doomed = {folder_id}
    changed = True
    while changed:
        changed = False
        for f in data["folders"].values():
            if f.get("parent") in doomed and f["id"] not in doomed:
                doomed.add(f["id"])
                changed = True
    data["folders"] = {k: v for k, v in data["folders"].items() if k not in doomed}
    data["items"] = [i for i in data["items"] if i.get("folder") not in doomed]
    _save(data)
    _refresh()


def rename_folder(folder_id):
    data = _load()
    folder = data["folders"].get(folder_id)
    if not folder or folder.get("builtin"):
        return
    name = _prompt_name("Ordner umbenennen", folder.get("name", ""))
    if name:
        folder["name"] = name
        _save(data)
        _refresh()


def remove_item(item_id):
    data = _load()
    data["items"] = [i for i in data["items"] if i.get("id") != item_id]
    _save(data)
    _refresh()


def rename_item(item_id):
    data = _load()
    item = next((i for i in data["items"] if i.get("id") == item_id), None)
    if not item:
        return
    name = _prompt_name("Favorit umbenennen", item.get("label", ""))
    if name:
        item["label"] = name
        _save(data)
        _refresh()


def move_item(item_id):
    data = _load()
    item = next((i for i in data["items"] if i.get("id") == item_id), None)
    if not item:
        return
    folders = _all_folder_choices(data)
    idx = xbmcgui.Dialog().select("Favorit verschieben", [f[1] for f in folders])
    if idx >= 0:
        item["folder"] = folders[idx][0]
        _save(data)
        _refresh()


def dispatch():
    if len(sys.argv) < 3 or not sys.argv[2]:
        root()
        return
    raw = sys.argv[2][1:] if sys.argv[2].startswith("?") else sys.argv[2]
    query = urllib.parse.parse_qs(raw)
    action = query.get("action", [""])[0]
    if action == "folder":
        folder(query.get("folder", [""])[0])
    elif action == "new_folder":
        new_folder(query.get("parent", [""])[0])
    elif action == "delete_folder":
        delete_folder(query.get("folder", [""])[0])
    elif action == "rename_folder":
        rename_folder(query.get("folder", [""])[0])
    elif action == "remove_item":
        remove_item(query.get("item", [""])[0])
    elif action == "rename_item":
        rename_item(query.get("item", [""])[0])
    elif action == "move_item":
        move_item(query.get("item", [""])[0])
    else:
        root()


if __name__ == "__main__":
    dispatch()
