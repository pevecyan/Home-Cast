import pychromecast
from pychromecast import quick_play
from uuid import UUID

#chromecasts, browser = pychromecast.get_listed_chromecasts(
#     known_hosts=["192.168.1.23"]
#)

cc = pychromecast.get_chromecast_from_host(
    ("192.168.1.23", None, None, None, None)
)
cc.wait()

cc.media_controller.play_media

cc.set_volume(0.1)
cc.quit_app()

app_name = "default_media_receiver"
app_data = {
    "media_id": "http://mp3.rtvslo.si/val202"
}
quick_play.quick_play(cc, app_name, app_data)


print("OK")