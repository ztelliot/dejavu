from mutagen import File
import os
import re
import string


def information(file: str):
    album_name = song_singer = song_public = song_name = album_company = None
    try:
        song = File(file)
    except:
        return None
    try:
        song.tags.version
        if "TALB" in song:
            album_name = str(song["TALB"])
        if "TPE1" in song:
            song_singer = str(song["TPE1"])
        if "TIT2" in song:
            song_name = str(song["TIT2"])
        if "TDRC" in song:
            song_public = str(song["TDRC"])
        if "TPUB" in song:
            album_company = str(song["TPUB"])
    except:
        if "ALBUM" in song:
            album_name = song["ALBUM"][0]
        if "ARTISTS" in song:
            song_singer = song["ARTISTS"]
        elif "ARTIST" in song:
            song_singer = song["ARTIST"]
        if "DATE" in song:
            song_public = song["DATE"][0]
        elif "ORIGINALDATE" in song:
            song_public = song["ORIGINALDATE"][0]
        if "TITLE" in song:
            song_name = song["TITLE"][0]
        if "LABEL" in song:
            album_company = song["LABEL"][0]
    if isinstance(song_singer, list):
        song_singer = ", ".join(song_singer)
    if not song_name:
        name = os.path.splitext(file)[0]
        if "mqms" in name:
            raw = re.sub("\\[mqms.*?]", "", name)
            name = raw.split('-')
            if len(name) == 2:
                song_singer = name[0].strip()
                song_name = name[1].strip()
        elif name.split('-')[-1].isdigit():
            raw = name.rstrip(string.digits).replace("_", " ").strip('-')
            name = raw.split('-')
            if len(name) == 2:
                song_singer = name[1].strip()
                song_name = name[0].strip()
        else:
            raw = name
            name = raw.split('-')
            if len(name) >= 2:
                song_singer = name[0].strip()
                song_name = name[1].strip()
            else:
                song_name = name[0]
    try:
        length = int(song.info.length)
    except:
        length = None
    return song_name, album_company, length, song_singer, album_name, song_public
