from ytmusicapi import YTMusic

yt = YTMusic()
playlist = yt.search("Mi2", filter="artists")

artist = yt.get_artist(playlist[0]["browseId"])

album = yt.get_playlist('OLAK5uy_nSRlaF2SAFBFtjZ-6yktyuE1WjdtbOLUg')

print(playlist)