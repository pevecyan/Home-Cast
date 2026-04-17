export function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
  const next = img.nextElementSibling as HTMLElement | null
  if (next?.classList.contains('img-fallback')) {
    next.style.display = 'flex'
  }
}
