/** TA-083: health checks detect an interrupted stream without inferring intent. */
export type CameraHealth = 'active' | 'interrupted' | 'no_image'

export class CameraHealthMonitor {
  private previousTime: number | null = null
  private stalledSince: number | null = null
  private blackSince: number | null = null

  check(now: number, videoTime: number, trackState: string, meanBrightness: number | null): CameraHealth {
    if (trackState !== 'live') return 'interrupted'
    if (!Number.isFinite(videoTime)) return 'no_image'
    if (this.previousTime !== null && videoTime <= this.previousTime) {
      this.stalledSince ??= now
    } else {
      this.stalledSince = null
    }
    this.previousTime = videoTime
    if (meanBrightness !== null && meanBrightness < 7) {
      this.blackSince ??= now
    } else {
      this.blackSince = null
    }
    if (this.stalledSince !== null && now - this.stalledSince >= 4000) return 'no_image'
    if (this.blackSince !== null && now - this.blackSince >= 4000) return 'no_image'
    return 'active'
  }
}

/** Sample a tiny in-memory canvas. Never saves or transmits this diagnostic image. */
export function meanVideoBrightness(video: HTMLVideoElement): number | null {
  if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) return null
  const canvas = document.createElement('canvas')
  canvas.width = 16
  canvas.height = 12
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return null
  try {
    ctx.drawImage(video, 0, 0, 16, 12)
    const pixels = ctx.getImageData(0, 0, 16, 12).data
    let sum = 0
    for (let p = 0; p < pixels.length; p += 4) sum += (pixels[p] + pixels[p + 1] + pixels[p + 2]) / 3
    return sum / (pixels.length / 4)
  } catch { return null }
}
