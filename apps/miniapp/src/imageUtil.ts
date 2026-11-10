// Phone photos are 3–10 MB; the API accepts up to 8 MB per file. Shrinking in the browser keeps uploads fast and
// well under the limit. PDFs and anything that cannot be decoded are sent untouched.
export const MAX_UPLOAD_BYTES = 8 * 1024 * 1024

export function fitWithin(w: number, h: number, max: number): { w: number; h: number } {
  const scale = Math.min(1, max / Math.max(w, h))
  return { w: Math.max(1, Math.round(w * scale)), h: Math.max(1, Math.round(h * scale)) }
}

export async function prepareImage(file: File, maxDim = 1600, quality = 0.85): Promise<File> {
  if (!file.type.startsWith('image/') || typeof createImageBitmap !== 'function') return file
  try {
    const bmp = await createImageBitmap(file)
    const { w, h } = fitWithin(bmp.width, bmp.height, maxDim)
    if (w === bmp.width && file.size < 1_500_000) return file // already small
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    canvas.getContext('2d')?.drawImage(bmp, 0, 0, w, h)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
    return blob && blob.size < file.size ? new File([blob], 'photo.jpg', { type: 'image/jpeg' }) : file
  } catch {
    return file
  }
}

export const tooLarge = (f: File): boolean => f.size > MAX_UPLOAD_BYTES
