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
let queueItems = [];
let currentItemId = null;
let progressInterval = null;
let currentRepeatMode = cast.framework.messages.RepeatMode.OFF;

// Notification state
let stateBeforeNotification = {
  itemId: null,
  time: null,
  queue: [],
  active: false,
  state: null,
};

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

  if (queueItems.length > 0) {
    const idx = queueItems.findIndex(i => i.itemId === currentItemId);
    trackPosition.textContent = idx >= 0 ? `${idx + 1} / ${queueItems.length}` : '';
  }
}

function syncQueueItems() {
  const items = playerManager.getQueueManager().getItems();
  if (items && items.length > 0) {
    queueItems = items;
  }
  console.log('[homecast] queue items synced:', queueItems);
}

function startProgressTimer() {
  if (progressInterval) clearInterval(progressInterval);
  progressInterval = setInterval(() => {
    const cur = playerManager.getCurrentTimeSec() || 0;
    const mediaInfo = playerManager.getMediaInformation();
    const dur = (mediaInfo && mediaInfo.duration) || 0;
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

function broadcastState() {
  const senders = context.getSenders();
  if (!senders.length) return;
  const msg = {
    type: 'STATE',
    queue: playerManager.getQueueManager().getItems() || [],
    currentItemId,
    repeatMode: currentRepeatMode,
  };
  senders.forEach(sender => context.sendCustomMessage(NAMESPACE, sender.id, msg));
}

// --- CAF event hooks ---

playerManager.addEventListener('MEDIA_STATUS', event => {
  const status = event.mediaStatus;
  if (!status) return;

  const state = status.playerState;

  if (status.repeatMode != null) {
    currentRepeatMode = status.repeatMode;
  }

  if (state === cast.framework.messages.PlayerState.PLAYING ||
      state === cast.framework.messages.PlayerState.BUFFERING ||
      state === cast.framework.messages.PlayerState.PAUSED) {
    syncQueueItems();
    appEl.classList.remove('hidden');
    showScreen('playing');
    updateTrackInfo(status);
    if (state === cast.framework.messages.PlayerState.PLAYING) {
      startProgressTimer();
    } else {
      stopProgressTimer();
    }
    broadcastState();
  } else if (state === cast.framework.messages.PlayerState.IDLE) {
    stopProgressTimer();
    const reason = status.idleReason;
    if (reason === cast.framework.messages.IdleReason.FINISHED ||
        reason === cast.framework.messages.IdleReason.CANCELLED ||
        reason === cast.framework.messages.IdleReason.ERROR) {
      if (!stateBeforeNotification.active) {
        appEl.classList.remove('hidden');
        showScreen('idle');
        queueItems = [];
        currentItemId = null;
        broadcastState();
      }
    }
  }
});


// --- Custom message handler ---

context.addCustomMessageListener(NAMESPACE, event => {
  const msg = event.data;
  console.log('[homecast] message received:', JSON.stringify(msg));
  if (!msg || !msg.type) return;

  switch (msg.type) {
    case 'SET_REPEAT': {
      const modeMap = {
        'off': cast.framework.messages.RepeatMode.REPEAT_OFF,
        'all': cast.framework.messages.RepeatMode.REPEAT_ALL,
        'one': cast.framework.messages.RepeatMode.REPEAT_SINGLE,
      };
      const mode = modeMap[msg.mode] || cast.framework.messages.RepeatMode.REPEAT_OFF;
      currentRepeatMode = mode;
      if (queueItems.length > 0) {
        const reloadRequest = new cast.framework.messages.LoadRequestData();
        reloadRequest.queueData = new cast.framework.messages.QueueData();
        reloadRequest.queueData.items = queueItems.map(i => {
          const qi = new cast.framework.messages.QueueItem();
          qi.media = i.media;
          return qi;
        });
        reloadRequest.queueData.startIndex = queueItems.findIndex(i => i.itemId === currentItemId);
        reloadRequest.queueData.repeatMode = mode;
        reloadRequest.currentTime = playerManager.getCurrentTimeSec() || 0;
        reloadRequest.autoplay = playerManager.getPlayerState() === cast.framework.messages.PlayerState.PLAYING;
        playerManager.load(reloadRequest);
      }
      break;
    }

    case 'SKIP_TO_ITEM': {
      const idx = msg.index;
      if (typeof idx !== 'number' || queueItems.length === 0) break;
      const target = queueItems[idx];
      if (!target) break;
      const skipRequest = new cast.framework.messages.LoadRequestData();
      skipRequest.queueData = new cast.framework.messages.QueueData();
      skipRequest.queueData.items = queueItems.map(i => {
        const qi = new cast.framework.messages.QueueItem();
        qi.media = i.media;
        return qi;
      });
      skipRequest.queueData.startIndex = idx;
      skipRequest.queueData.repeatMode = currentRepeatMode;
      skipRequest.currentTime = 0;
      skipRequest.autoplay = true;
      playerManager.load(skipRequest);
      break;
    }

    case 'RELOAD_QUEUE': {
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
      if (msg.repeatMode != null) {
        const modeMap = {
          'OFF': cast.framework.messages.RepeatMode.REPEAT_OFF,
          'ALL': cast.framework.messages.RepeatMode.REPEAT_ALL,
          'SINGLE': cast.framework.messages.RepeatMode.REPEAT_SINGLE,
        };
        currentRepeatMode = modeMap[msg.repeatMode] ?? cast.framework.messages.RepeatMode.REPEAT_OFF;
      }
      loadRequest.queueData.repeatMode = currentRepeatMode;
      loadRequest.autoplay = true;
      playerManager.load(loadRequest);
      break;
    }

    case 'NOTIFICATION': {
      if (!msg.url) break;
      stateBeforeNotification.active = true;
      stateBeforeNotification.itemId = currentItemId;
      stateBeforeNotification.time = playerManager.getCurrentTimeSec() || null;
      stateBeforeNotification.queue = queueItems.slice();
      stateBeforeNotification.state = playerManager.getPlayerState();

      playerManager.pause();

      const notifRequest = new cast.framework.messages.LoadRequestData();
      const notifMedia = new cast.framework.messages.MediaInformation();
      notifMedia.contentId = msg.url;
      notifMedia.contentType = msg.mediaType || 'audio/mp3';
      notifMedia.streamType = cast.framework.messages.StreamType.BUFFERED;
      notifRequest.media = notifMedia;
      notifRequest.autoplay = true;

      const onNotifStatus = (evt) => {
        const s = evt.mediaStatus;
        if (!s) return;
        if (s.playerState === cast.framework.messages.PlayerState.IDLE &&
            (s.idleReason === cast.framework.messages.IdleReason.FINISHED ||
             s.idleReason === cast.framework.messages.IdleReason.ERROR ||
             s.idleReason === cast.framework.messages.IdleReason.CANCELLED)) {
          playerManager.removeEventListener('MEDIA_STATUS', onNotifStatus);
          stateBeforeNotification.active = false;
          _resumeAfterNotification();
        }
      };
      playerManager.addEventListener('MEDIA_STATUS', onNotifStatus);
      playerManager.load(notifRequest);
      break;
    }

    case 'GET_STATE': {
      broadcastState();
      break;
    }

    case 'PING':
      context.sendCustomMessage(NAMESPACE, event.senderId, { type: 'PONG' });
      break;
  }
});

function _resumeAfterNotification() {
  const { itemId, time, queue } = stateBeforeNotification;
  if (itemId == null || queue.length === 0) return;
  const startIndex = queue.findIndex(i => i.itemId === itemId);
  const resumeRequest = new cast.framework.messages.LoadRequestData();
  resumeRequest.queueData = new cast.framework.messages.QueueData();
  resumeRequest.queueData.items = queue.map(i => {
    const qi = new cast.framework.messages.QueueItem();
    qi.media = i.media;
    return qi;
  });
  resumeRequest.queueData.startIndex = startIndex >= 0 ? startIndex : 0;
  resumeRequest.queueData.repeatMode = currentRepeatMode;
  resumeRequest.currentTime = time || 0;
  resumeRequest.autoplay = stateBeforeNotification.state === cast.framework.messages.PlayerState.PLAYING;
  playerManager.load(resumeRequest);
  stateBeforeNotification = { itemId: null, time: null, queue: [], active: false, state: null };
}


// --- Start ---
context.start({
  disableIdleTimeout: false,
  playbackConfig: new cast.framework.PlaybackConfig(),
});
