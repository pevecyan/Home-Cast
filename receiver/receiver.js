'use strict';

const NAMESPACE = 'urn:x-cast:io.1home.homecast';

const context = cast.framework.CastReceiverContext.getInstance();
const playerManager = context.getPlayerManager();

// --- UI elements ---
const appEl = document.getElementById('app');
const idleScreen = document.getElementById('idle-screen');
const playingScreen = document.getElementById('playing-screen');
const albumArt = document.getElementById('album-art');
const albumArtPlaceholder = document.getElementById('album-art-placeholder');
const trackTitle = document.getElementById('track-title');
const trackArtist = document.getElementById('track-artist');
const trackAlbum = document.getElementById('track-album');
const progressFill = document.getElementById('progress-fill');
const timeCurrent = document.getElementById('time-current');
const timeTotal = document.getElementById('time-total');
const trackPosition = document.getElementById('track-position');
const queueList = document.getElementById('queue-list');

// --- State ---
let queueItems = [];       // MediaQueueItem array as loaded
let currentItemId = null;
let progressInterval = null;

// Notification state
let notifSavedItemId = null;
let notifSavedTime = null;
let notifActive = false;

// --- Helpers ---

function formatTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function showScreen(name) {
  idleScreen.classList.toggle('hidden', name !== 'idle');
  playingScreen.classList.toggle('hidden', name !== 'playing');
}

function setAlbumArt(url) {
  if (url) {
    albumArt.src = url;
    albumArt.classList.remove('hidden');
    albumArtPlaceholder.classList.add('hidden');
  } else {
    albumArt.classList.add('hidden');
    albumArtPlaceholder.classList.remove('hidden');
  }
}

function renderQueue(items, currentId) {
  queueList.innerHTML = '';
  items.forEach((item, idx) => {
    const meta = item.media && item.media.metadata;
    const title = (meta && meta.title) || 'Unknown';
    const artist = (meta && meta.artist) || '';
    const isCurrent = item.itemId === currentId;

    const row = document.createElement('div');
    row.className = 'queue-item' + (isCurrent ? ' queue-item--current' : '');

    const num = document.createElement('span');
    num.className = 'queue-item-num';
    num.textContent = idx + 1;

    const info = document.createElement('div');
    info.className = 'queue-item-info';

    const t = document.createElement('div');
    t.className = 'queue-item-title';
    t.textContent = title;

    const a = document.createElement('div');
    a.className = 'queue-item-artist';
    a.textContent = artist;

    info.appendChild(t);
    info.appendChild(a);
    row.appendChild(num);
    row.appendChild(info);
    queueList.appendChild(row);

    if (isCurrent) {
      // scroll current item into view after render
      setTimeout(() => row.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 50);
    }
  });
}

function updateTrackInfo(mediaStatus) {
  if (!mediaStatus || !mediaStatus.media) return;
  const meta = mediaStatus.media.metadata || {};
  trackTitle.textContent = meta.title || '';
  trackArtist.textContent = meta.artist || '';
  trackAlbum.textContent = meta.albumName || '';

  const images = meta.images || [];
  setAlbumArt(images.length > 0 ? images[0].url : null);

  currentItemId = mediaStatus.currentItemId;
  renderQueue(queueItems, currentItemId);

  // track position label e.g. "3 / 12"
  if (queueItems.length > 0) {
    const idx = queueItems.findIndex(i => i.itemId === currentItemId);
    trackPosition.textContent = idx >= 0 ? `${idx + 1} / ${queueItems.length}` : '';
  }
}

function startProgressTimer() {
  if (progressInterval) clearInterval(progressInterval);
  progressInterval = setInterval(() => {
    const status = playerManager.getPlayerData();
    if (!status) return;
    const cur = status.currentTime || 0;
    const dur = (status.media && status.media.duration) || 0;
    timeCurrent.textContent = formatTime(cur);
    timeTotal.textContent = formatTime(dur);
    progressFill.style.width = dur > 0 ? `${(cur / dur) * 100}%` : '0%';
  }, 500);
}

function stopProgressTimer() {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
}

// --- CAF event hooks ---

playerManager.addEventListener(cast.framework.events.EventType.MEDIA_STATUS, event => {
  const status = event.mediaStatus;
  if (!status) return;

  const state = status.playerState;

  if (state === cast.framework.messages.PlayerState.PLAYING ||
      state === cast.framework.messages.PlayerState.BUFFERING ||
      state === cast.framework.messages.PlayerState.PAUSED) {
    appEl.classList.remove('hidden');
    showScreen('playing');
    updateTrackInfo(status);
    if (state === cast.framework.messages.PlayerState.PLAYING) {
      startProgressTimer();
    } else {
      stopProgressTimer();
    }
  } else if (state === cast.framework.messages.PlayerState.IDLE) {
    stopProgressTimer();
    const reason = status.idleReason;
    if (reason === cast.framework.messages.IdleReason.FINISHED ||
        reason === cast.framework.messages.IdleReason.CANCELLED ||
        reason === cast.framework.messages.IdleReason.ERROR) {
      // Only go idle if not mid-notification
      if (!notifActive) {
        appEl.classList.remove('hidden');
        showScreen('idle');
        queueItems = [];
        currentItemId = null;
      }
    }
  }
});

// Capture queue items when a LOAD completes
playerManager.addEventListener(cast.framework.events.EventType.PLAYER_LOAD_COMPLETE, () => {
  const mediaInfo = playerManager.getMediaInformation();
  if (mediaInfo && mediaInfo.queueData && mediaInfo.queueData.items) {
    queueItems = mediaInfo.queueData.items;
  }
});

// Update current item highlight when track changes within the queue
playerManager.addEventListener(cast.framework.events.EventType.QUEUE_ITEM_ENDED, () => {
  const status = playerManager.getPlayerData();
  if (status) {
    currentItemId = status.currentItemId;
    renderQueue(queueItems, currentItemId);
    const idx = queueItems.findIndex(i => i.itemId === currentItemId);
    trackPosition.textContent = idx >= 0 ? `${idx + 1} / ${queueItems.length}` : '';
  }
});

// --- Custom message handler ---

context.addCustomMessageListener(NAMESPACE, event => {
  const msg = event.data;
  if (!msg || !msg.type) return;

  switch (msg.type) {
    case 'SET_REPEAT': {
      const modeMap = {
        'off': cast.framework.messages.RepeatMode.OFF,
        'all': cast.framework.messages.RepeatMode.ALL,
        'one': cast.framework.messages.RepeatMode.SINGLE,
      };
      const mode = modeMap[msg.mode] || cast.framework.messages.RepeatMode.OFF;
      playerManager.setRepeatMode(mode);
      break;
    }

    case 'RELOAD_QUEUE': {
      // Sent by Python when shuffle is toggled — replaces the queue with re-ordered items
      // msg.items: array of { url, mediaType, metadata, itemId }
      // msg.startIndex: index in the new items array to start from
      if (!msg.items || msg.items.length === 0) break;
      const loadRequest = new cast.framework.messages.LoadRequestData();
      loadRequest.queueData = new cast.framework.messages.QueueData();
      loadRequest.queueData.items = msg.items.map(i => {
        const qi = new cast.framework.messages.QueueItem();
        qi.media = new cast.framework.messages.MediaInformation();
        qi.media.contentId = i.url;
        qi.media.contentType = i.mediaType || 'audio/mpeg';
        qi.media.streamType = cast.framework.messages.StreamType.BUFFERED;
        qi.media.metadata = i.metadata || {};
        return qi;
      });
      loadRequest.queueData.startIndex = msg.startIndex || 0;
      loadRequest.queueData.repeatMode = playerManager.getRepeatMode();
      playerManager.load(loadRequest);
      break;
    }

    case 'NOTIFICATION': {
      if (!msg.url) break;
      notifActive = true;
      const playerData = playerManager.getPlayerData();
      notifSavedItemId = playerData ? playerData.currentItemId : null;
      notifSavedTime = playerData ? playerData.currentTime : null;

      playerManager.pause();

      // Play the notification as a one-shot media item
      const notifRequest = new cast.framework.messages.LoadRequestData();
      const notifMedia = new cast.framework.messages.MediaInformation();
      notifMedia.contentId = msg.url;
      notifMedia.contentType = msg.mediaType || 'audio/mp3';
      notifMedia.streamType = cast.framework.messages.StreamType.BUFFERED;
      notifRequest.media = notifMedia;
      notifRequest.autoplay = true;

      // Listen for notif end then restore queue
      const onNotifStatus = (evt) => {
        const s = evt.mediaStatus;
        if (!s) return;
        if (s.playerState === cast.framework.messages.PlayerState.IDLE &&
            (s.idleReason === cast.framework.messages.IdleReason.FINISHED ||
             s.idleReason === cast.framework.messages.IdleReason.ERROR ||
             s.idleReason === cast.framework.messages.IdleReason.CANCELLED)) {
          playerManager.removeEventListener(cast.framework.events.EventType.MEDIA_STATUS, onNotifStatus);
          notifActive = false;
          _resumeAfterNotification();
        }
      };
      playerManager.addEventListener(cast.framework.events.EventType.MEDIA_STATUS, onNotifStatus);
      playerManager.load(notifRequest);
      break;
    }

    case 'PING':
      context.sendCustomMessage(NAMESPACE, event.senderId, { type: 'PONG' });
      break;
  }
});

function _resumeAfterNotification() {
  if (notifSavedItemId == null || queueItems.length === 0) return;
  const jumpRequest = new cast.framework.messages.QueueJumpRequest();
  jumpRequest.currentItemId = notifSavedItemId;
  jumpRequest.currentTime = notifSavedTime || 0;
  playerManager.queueJumpToItem(notifSavedItemId, notifSavedTime || 0);
  notifSavedItemId = null;
  notifSavedTime = null;
}

// Broadcast queue state to Python backend on every track change
playerManager.addEventListener(cast.framework.events.EventType.QUEUE_ITEM_ENDED, () => {
  _broadcastQueueState();
});
playerManager.addEventListener(cast.framework.events.EventType.PLAYER_LOAD_COMPLETE, () => {
  _broadcastQueueState();
});

function _broadcastQueueState() {
  const playerData = playerManager.getPlayerData();
  const curId = playerData ? playerData.currentItemId : null;
  const idx = queueItems.findIndex(i => i.itemId === curId);
  context.sendCustomMessage(NAMESPACE, undefined, {
    type: 'QUEUE_STATE',
    currentIndex: idx,
    currentItemId: curId,
    itemIds: queueItems.map(i => i.itemId),
  });
}

// --- Start ---
context.start({
  disableIdleTimeout: false,
  playbackConfig: new cast.framework.PlaybackConfig(),
});
