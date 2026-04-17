import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('../views/SearchView.vue'),
    },
    {
      path: '/artist/:browseId',
      name: 'artist',
      component: () => import('../views/ArtistView.vue'),
    },
    {
      path: '/playlist/:playlistId',
      name: 'playlist',
      component: () => import('../views/PlaylistView.vue'),
    },
    {
      path: '/album/:browseId',
      name: 'album',
      component: () => import('../views/AlbumView.vue'),
    },
    {
      path: '/radio',
      name: 'radio',
      component: () => import('../views/RadioView.vue'),
    },
    {
      path: '/playlists',
      name: 'playlists',
      component: () => import('../views/SavedPlaylistsView.vue'),
    },
    {
      path: '/playlists/:id/edit',
      name: 'edit-playlist',
      component: () => import('../views/EditPlaylistView.vue'),
    },
  ],
})

export default router
