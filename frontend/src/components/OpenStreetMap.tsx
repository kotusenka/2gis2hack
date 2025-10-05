'use client'

import { useEffect, useRef, useState } from 'react'

interface OpenStreetMapProps {
  center?: [number, number]
  zoom?: number
  width?: string | number
  height?: string | number
  className?: string
}

export default function OpenStreetMap({
  center = [37.6173, 55.7558],
  zoom = 11,
  width = '100%',
  height = '400px',
  className = ''
}: OpenStreetMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!mapRef.current) return

    console.log('🗺️ Загружаем OpenStreetMap...')
    
    // Создаем iframe с OpenStreetMap
    const iframe = document.createElement('iframe')
    iframe.src = `https://www.openstreetmap.org/export/embed.html?bbox=${center[0]-0.01},${center[1]-0.01},${center[0]+0.01},${center[1]+0.01}&layer=mapnik&marker=${center[1]},${center[0]}`
    iframe.width = '100%'
    iframe.height = '100%'
    iframe.frameBorder = '0'
    iframe.style.border = 'none'
    
    iframe.onload = () => {
      console.log('✅ OpenStreetMap загружен')
      setIsLoaded(true)
    }
    
    iframe.onerror = () => {
      console.error('❌ Ошибка загрузки OpenStreetMap')
      setError('Не удалось загрузить карту')
    }
    
    mapRef.current.appendChild(iframe)
    
    return () => {
      if (mapRef.current && iframe.parentNode) {
        iframe.parentNode.removeChild(iframe)
      }
    }
  }, [center])

  if (error) {
    return (
      <div 
        className={`flex items-center justify-center bg-gray-100 border-2 border-dashed border-gray-300 ${className}`}
        style={{ width, height }}
      >
        <div className="text-center p-6">
          <div className="text-gray-400 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-600 mb-2">Карта недоступна</h3>
          <p className="text-gray-500 text-sm">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`relative ${className}`} style={{ width, height }}>
      <div
        ref={mapRef}
        className="w-full h-full rounded-lg overflow-hidden"
        style={{ width, height }}
      />
      
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-sm text-gray-600">Загрузка карты...</p>
          </div>
        </div>
      )}
      
      {isLoaded && (
        <div className="absolute top-2 left-2 bg-white bg-opacity-90 rounded px-2 py-1 text-xs text-gray-600">
          OpenStreetMap • Москва
        </div>
      )}
    </div>
  )
}
