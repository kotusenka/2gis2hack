'use client'

import { useEffect, useRef, useState } from 'react'
import { load } from '@2gis/mapgl'

interface MoscowMapProps {
  width?: string | number
  height?: string | number
  embeddable?: boolean
  showControls?: boolean
  initialZoom?: number
  center?: [number, number]
}

export default function MoscowMap({
  width = '100%',
  height = '600px',
  embeddable = false,
  showControls = true,
  initialZoom = 11,
  center = [37.6173, 55.7558] // Координаты центра Москвы
}: MoscowMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<any>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mapInfo, setMapInfo] = useState({
    zoom: initialZoom,
    center: center,
    bearing: 0,
    pitch: 0
  })

  useEffect(() => {
    if (!mapContainer.current) return

    // Загрузка MapGL API с таймаутом
    const loadTimeout = setTimeout(() => {
      setError('Таймаут загрузки MapGL. Проверьте интернет-соединение.')
    }, 10000) // 10 секунд таймаут

    load().then((mapgl) => {
      clearTimeout(loadTimeout)
      
      // Проверяем API ключ
      const apiKey = process.env.NEXT_PUBLIC_2GIS_API_KEY
      if (!apiKey || apiKey === 'YOUR_2GIS_API_KEY') {
        setError('API ключ не настроен. Создайте файл .env.local с NEXT_PUBLIC_2GIS_API_KEY')
        return
      }

      try {
        // Инициализация карты (исправлено согласно документации)
        const map = new mapgl.Map(mapContainer.current, {
          center: center,
          zoom: initialZoom,
          key: apiKey
        })

        mapInstance.current = map

        // Обработчики событий карты
        map.on('load', () => {
          setIsLoaded(true)
          setError(null)
        })

        map.on('error', (err) => {
          console.error('MapGL Error:', err)
          setError(`Ошибка карты: ${err.message || 'Неизвестная ошибка'}`)
        })

        map.on('move', () => {
          const center = map.getCenter()
          const zoom = map.getZoom()
          setMapInfo({
            zoom: Math.round(zoom * 10) / 10,
            center: [center.lng, center.lat],
            bearing: map.getBearing(),
            pitch: map.getPitch()
          })
        })
      } catch (initError) {
        console.error('MapGL Init Error:', initError)
        setError(`Ошибка инициализации карты: ${initError.message || 'Неизвестная ошибка'}`)
      }
    }).catch((err) => {
      clearTimeout(loadTimeout)
      console.error('MapGL Load Error:', err)
      setError(`Ошибка загрузки MapGL: ${err.message || 'Проверьте интернет-соединение'}`)
    })

    // Очистка при размонтировании
    return () => {
      if (mapInstance.current) {
        mapInstance.current.destroy()
      }
    }
  }, [])

  const handleZoomIn = () => {
    if (mapInstance.current) {
      const currentZoom = mapInstance.current.getZoom()
      mapInstance.current.zoomTo(currentZoom + 1, { duration: 300 })
    }
  }

  const handleZoomOut = () => {
    if (mapInstance.current) {
      const currentZoom = mapInstance.current.getZoom()
      mapInstance.current.zoomTo(currentZoom - 1, { duration: 300 })
    }
  }

  const handleResetView = () => {
    if (mapInstance.current) {
      mapInstance.current.flyTo({
        center: center,
        zoom: initialZoom,
        duration: 1000
      })
    }
  }

  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      mapContainer.current?.requestFullscreen()
    } else {
      document.exitFullscreen()
    }
  }

  return (
    <div className="relative w-full h-full">
      <div
        ref={mapContainer}
        className="mapgl-container"
        style={{ width, height }}
      />
      
      {showControls && (
        <div className="mapgl-controls">
          <button
            onClick={handleZoomIn}
            className="mapgl-control-button"
            title="Увеличить"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>
          
          <button
            onClick={handleZoomOut}
            className="mapgl-control-button"
            title="Уменьшить"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>
          
          <button
            onClick={handleResetView}
            className="mapgl-control-button"
            title="Сбросить вид"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path>
              <path d="M21 3v5h-5"></path>
              <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path>
              <path d="M3 21v-5h5"></path>
            </svg>
          </button>
          
          <button
            onClick={handleToggleFullscreen}
            className="mapgl-control-button"
            title="Полный экран"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
            </svg>
          </button>
        </div>
      )}

      {isLoaded && (
        <div className="mapgl-info-panel">
          <h3 className="font-semibold text-lg mb-2">Карта Москвы</h3>
          <div className="space-y-1 text-sm text-gray-600">
            <p><strong>Масштаб:</strong> {mapInfo.zoom}</p>
            <p><strong>Центр:</strong> {mapInfo.center[0].toFixed(4)}, {mapInfo.center[1].toFixed(4)}</p>
            <p><strong>Поворот:</strong> {mapInfo.bearing.toFixed(1)}°</p>
            <p><strong>Наклон:</strong> {mapInfo.pitch.toFixed(1)}°</p>
          </div>
        </div>
      )}

      {!isLoaded && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Загрузка карты...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-red-50">
          <div className="text-center max-w-md mx-auto p-6">
            <div className="text-red-500 mb-4">
              <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-red-800 mb-2">Ошибка загрузки карты</h3>
            <p className="text-red-600 mb-4">{error}</p>
            <div className="bg-red-100 border border-red-300 rounded-lg p-4 text-left">
              <h4 className="font-semibold text-red-800 mb-2">Как исправить:</h4>
              <ol className="text-sm text-red-700 space-y-1">
                <li>1. Получите API ключ на <a href="https://dev.2gis.com/" target="_blank" rel="noopener noreferrer" className="underline">dev.2gis.com</a></li>
                <li>2. Создайте файл <code className="bg-red-200 px-1 rounded">.env.local</code></li>
                <li>3. Добавьте: <code className="bg-red-200 px-1 rounded">NEXT_PUBLIC_2GIS_API_KEY=ваш_ключ</code></li>
                <li>4. Перезапустите сервер</li>
              </ol>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
