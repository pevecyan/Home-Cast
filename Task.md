# Local music player

We have this local control app, that can control local audio devices (chromecast, sonos).
I would like to extend this app with controller for local music and UI

# Requirements for local music controller
- We should use YTMusic api to search for songs, artists or playlist
- There should be an endpoint to play song or playlist which will start playing music on speaker provided in request data (slug & type)
- We should get list of songs, create m3u file, download with yt-dlp (at least first) song and send m3u file to speaker. 
- Inside m3u file we should specify url to songs that we will also serve (probably by id), song name, cover photo etc.
- We should cache this files for some time (set by constant) and delete after that
- If we try to get specific song and it is not cached yet, try to fetch it
- We will have list of persisted playlist that are played more often

# Requirements for UI
We should create ui for this whole app with Vue3 and Vite
we should be able:
- Control all the speakers and show states
  - volume
  - play/pause
  - next/prev
  - stop
  - ...
- Search for artist, playlist, songs
- Play songs, playlist on speakers
- It should be mobile friendly and easy to use
- It should use some nice UI framework, to look similar to apple or Google home apps


# Requirements general
- split UI and app into two separate folders
- create dockerfile that will spin up nginx that will host ui and proxy request to app
- we will need config.yaml to specify some settings, like hostname of a server for frontend calls

