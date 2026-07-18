export function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
  const next = img.nextElementSibling as HTMLElement | null
  if (next?.classList.contains('img-fallback')) {
    next.style.display = 'flex'
  }
}

/** Return an <img> error handler that retries once with `fallback()` before
 *  giving up and showing the sibling placeholder (via `onImgError`). Use when a
 *  track thumbnail may 404 but a playlist/album cover can stand in for it. */
export function onImgErrorWithFallback(fallback: () => string | undefined | null) {
  return (e: Event) => {
    const img = e.target as HTMLImageElement
    const alt = fallback()
    // Only retry if we have a different, not-yet-tried cover.
    if (alt && img.src !== alt && !img.dataset.fallbackTried) {
      img.dataset.fallbackTried = '1'
      img.src = alt
      return
    }
    onImgError(e)
  }
}
