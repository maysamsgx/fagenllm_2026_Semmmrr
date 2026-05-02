import { useEffect, useRef } from 'react'
import Hls from 'hls.js'

const HLS_SRC = 'https://stream.mux.com/tLkHO1qZoaaQOUeVWo8hEBeGQfySP02EPS02BmnNFyXys.m3u8'

export default function VideoBackground() {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    if (Hls.isSupported()) {
      const hls = new Hls({ autoStartLoad: true })
      hls.loadSource(HLS_SRC)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => { video.play().catch(() => {}) })
      return () => { hls.destroy() }
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = HLS_SRC
      video.play().catch(() => {})
    }
  }, [])

  return (
    <video
      ref={videoRef}
      autoPlay
      loop
      muted
      playsInline
      className="absolute inset-0 w-full h-full object-cover"
      style={{ zIndex: 0 }}
    />
  )
}
