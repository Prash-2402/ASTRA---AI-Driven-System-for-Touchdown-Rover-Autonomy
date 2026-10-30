import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import './MarsScrollSection.css'

const TOTAL_FRAMES = 301
const FRAME_PATH = (idx: number) => {
  const pad = (idx + 1).toString().padStart(4, '0')
  return `/mars_frames/frame_${pad}.jpg`
}

interface MarsScrollSectionProps {
  onEnterApp?: () => void
}

export const MarsScrollSection: React.FC<MarsScrollSectionProps> = ({ onEnterApp }) => {
  const navigate = useNavigate()
  const trackRef = useRef<HTMLElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  // Cache for loaded images
  const imageCache = useRef<Map<number, HTMLImageElement>>(new Map())
  const loadingQueue = useRef<Set<number>>(new Set())
  const lastDrawnFrame = useRef<number>(-1)
  const isInitialFrameLoaded = useRef(false)

  // Current normalized scroll progress [0, 1]
  const [progress, setProgress] = useState(0)
  const [firstFrameReady, setFirstFrameReady] = useState(false)
  const [reducedMotion, setReducedMotion] = useState(false)

  // Helper to load a single frame
  const loadFrame = useCallback((index: number, priority = false): Promise<HTMLImageElement | null> => {
    if (index < 0 || index >= TOTAL_FRAMES) return Promise.resolve(null)
    if (imageCache.current.has(index)) {
      return Promise.resolve(imageCache.current.get(index)!)
    }
    if (loadingQueue.current.has(index)) {
      return Promise.resolve(null)
    }

    loadingQueue.current.add(index)
    return new Promise((resolve) => {
      const img = new Image()
      img.src = FRAME_PATH(index)
      img.onload = () => {
        imageCache.current.set(index, img)
        loadingQueue.current.delete(index)
        resolve(img)
      }
      img.onerror = () => {
        loadingQueue.current.delete(index)
        resolve(null)
      }
    })
  }, [])

  // Draw a frame to canvas preserving aspect ratio (1920x1080)
  const renderFrame = useCallback((index: number) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return

    // Find requested frame or closest loaded frame
    let imgToDraw: HTMLImageElement | undefined = imageCache.current.get(index)
    let actualIndex = index

    if (!imgToDraw || !imgToDraw.complete || imgToDraw.naturalWidth === 0) {
      // Find nearest loaded frame to avoid ANY blank canvas or flickering
      let minDiff = Infinity
      imageCache.current.forEach((cachedImg, k) => {
        if (cachedImg.complete && cachedImg.naturalWidth > 0) {
          const diff = Math.abs(k - index)
          if (diff < minDiff) {
            minDiff = diff
            imgToDraw = cachedImg
            actualIndex = k
          }
        }
      })
    }

    if (!imgToDraw || !imgToDraw.complete || imgToDraw.naturalWidth === 0) {
      return
    }

    // Canvas dimensions
    const cWidth = canvas.width
    const cHeight = canvas.height

    // 1920x1080 original aspect ratio
    const imgAspect = 1920 / 1080
    const canvasAspect = cWidth / cHeight

    let drawW = cWidth
    let drawH = cHeight
    let offsetX = 0
    let offsetY = 0

    // Cover style scaling: preserve aspect ratio, fill canvas, zero distortion
    if (canvasAspect > imgAspect) {
      drawW = cWidth
      drawH = cWidth / imgAspect
      offsetX = 0
      offsetY = (cHeight - drawH) / 2
    } else {
      drawH = cHeight
      drawW = cHeight * imgAspect
      offsetX = (cWidth - drawW) / 2
      offsetY = 0
    }

    ctx.drawImage(imgToDraw, offsetX, offsetY, drawW, drawH)
    lastDrawnFrame.current = actualIndex
  }, [])

  // Check prefers-reduced-motion
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReducedMotion(media.matches)
    const listener = (e: MediaQueryListEvent) => setReducedMotion(e.matches)
    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [])

  // Step 1: Immediately load frame 0
  useEffect(() => {
    loadFrame(0, true).then((img) => {
      if (img) {
        setFirstFrameReady(true)
        isInitialFrameLoaded.current = true
        renderFrame(0)
      }
    })
  }, [loadFrame, renderFrame])

  // Step 2: Progressive preloading around scroll position
  useEffect(() => {
    if (!firstFrameReady) return

    // Immediately queue the initial buffer (frames 1 to 20)
    for (let i = 1; i <= 20; i++) {
      loadFrame(i)
    }

    // Progressively load keyframes (every 5th frame) across the whole sequence
    let idleIdx = 25
    const keyframeTimer = setInterval(() => {
      if (idleIdx >= TOTAL_FRAMES) {
        clearInterval(keyframeTimer)
        // Fill all gaps in background
        fillRemainingFrames()
        return
      }
      for (let k = 0; k < 4 && idleIdx < TOTAL_FRAMES; k++, idleIdx += 5) {
        loadFrame(idleIdx)
      }
    }, 40)

    const fillRemainingFrames = () => {
      let gapIdx = 0
      const gapTimer = setInterval(() => {
        if (gapIdx >= TOTAL_FRAMES) {
          clearInterval(gapTimer)
          return
        }
        for (let j = 0; j < 3 && gapIdx < TOTAL_FRAMES; j++, gapIdx++) {
          if (!imageCache.current.has(gapIdx)) {
            loadFrame(gapIdx)
          }
        }
      }, 50)
    }

    return () => clearInterval(keyframeTimer)
  }, [firstFrameReady, loadFrame])

  // Resize handler with High-DPI support
  const handleResize = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const w = window.innerWidth
    const h = window.innerHeight

    canvas.width = Math.round(w * dpr)
    canvas.height = Math.round(h * dpr)
    canvas.style.width = `${w}px`
    canvas.style.height = `${h}px`

    // Re-draw current frame
    if (lastDrawnFrame.current >= 0) {
      renderFrame(lastDrawnFrame.current)
    } else {
      renderFrame(0)
    }
  }, [renderFrame])

  useEffect(() => {
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [handleResize])

  // Scroll listener mapping section scroll range to frameIndex [0, 300]
  useEffect(() => {
    if (reducedMotion) return

    let rafId: number
    const onScroll = () => {
      cancelAnimationFrame(rafId)
      rafId = requestAnimationFrame(() => {
        const track = trackRef.current
        if (!track) return

        const scrollY = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0
        const rect = track.getBoundingClientRect()
        const sectionStart = rect.top + scrollY
        const sectionHeight = track.offsetHeight
        const viewportHeight = window.innerHeight
        const scrollDistance = sectionHeight - viewportHeight

        if (scrollDistance <= 0) return

        // Compute normalized local progress clamped strictly [0, 1]
        const p = Math.max(0, Math.min(1, (scrollY - sectionStart) / scrollDistance))
        setProgress(p)

        const targetFrame = Math.round(p * (TOTAL_FRAMES - 1))

        // Preload immediate window around target frame
        for (let offset = -4; offset <= 8; offset++) {
          const idx = targetFrame + offset
          if (idx >= 0 && idx < TOTAL_FRAMES && !imageCache.current.has(idx)) {
            loadFrame(idx, true)
          }
        }

        renderFrame(targetFrame)
      })
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    // Initial run
    onScroll()

    return () => {
      window.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(rafId)
    }
  }, [loadFrame, renderFrame, reducedMotion])

  // Fade out hero content gradually as user scrolls into the planetary reveal
  const textOpacity = reducedMotion ? 1 : Math.max(0, 1 - progress * 2.4)
  const textTranslateY = reducedMotion ? 0 : -(progress * 60)
  const isTextInteractive = textOpacity > 0.15

  const handleLaunch = () => {
    if (onEnterApp) onEnterApp()
    else navigate('/app')
  }

  return (
    <section
      ref={trackRef}
      className={`mars-scroll-section mars-scroll-track ${reducedMotion ? 'reduced-motion' : ''}`}
      id="overview"
    >
      {/* Pinned Sticky Viewport Container */}
      <div className="mars-sticky-viewport mars-sticky-container">
        {/* Frame Canvas */}
        <canvas ref={canvasRef} className="mars-frame-canvas" />

        {/* Cinematic Vignette & Ambient Darkness Overlays */}
        <div className="mars-ambient-vignette" />
        <div className="mars-scanline-overlay" />

        {/* Hero Content Staggered Overlay */}
        <div
          className="hero-content-layer"
          style={{
            opacity: textOpacity,
            transform: `translateY(${textTranslateY}px)`,
            pointerEvents: isTextInteractive ? 'auto' : 'none',
          }}
        >
          <div className="hero-content">
            <div className="hero-eyebrow">
              <span className="eyebrow-dot" />
              AUTONOMOUS PLANETARY INTELLIGENCE
            </div>
            <h1 className="hero-headline">
              Beyond Simulation.<br />
              <em>Toward Autonomous</em><br />
              Exploration.
            </h1>
            <p className="hero-description">
              ASTRA is an integrated planetary autonomy research platform combining
              physics-based touchdown simulation, intelligent rover navigation,
              reinforcement learning, and adaptive decision-making in a unified
              simulation environment.
            </p>
            <div className="hero-actions">
              <button className="btn-secondary-hero" onClick={handleLaunch}>
                Enter Mission Control
              </button>
            </div>
            <div className="hero-metrics">
              <div className="hero-metric">
                <span className="metric-label">Platform</span>
                <span className="metric-value">Physics-Based EDL</span>
              </div>
              <div className="hero-metric-divider" />
              <div className="hero-metric">
                <span className="metric-label">Controllers</span>
                <span className="metric-value">PID · MPC · PPO</span>
              </div>
              <div className="hero-metric-divider" />
              <div className="hero-metric">
                <span className="metric-label">Navigation</span>
                <span className="metric-value">EKF Fault-Aware</span>
              </div>
            </div>
          </div>
        </div>


      </div>
    </section>
  )
}

export default MarsScrollSection
