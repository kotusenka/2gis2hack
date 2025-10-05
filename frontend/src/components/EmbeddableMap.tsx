'use client'

import { useEffect, useRef, useState } from 'react'
import { load } from '@2gis/mapgl'

interface EmbeddableMapProps {
  width?: string | number
  height?: string | number
  zoom?: number
  center?: [number, number]
  showInfo?: boolean
  style?: 'light' | 'dark' | 'satellite'
  className?: string
}

export default function EmbeddableMap({
  width = '100%',
  height = '400px',
  zoom = 11,
  center = [37.6173, 55.7558],
  showInfo = false,
  style = 'light',
  className = ''
}: EmbeddableMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapInstance = useRef<any>(null)
  const [isLoaded, setIsLoaded] = useState(false)

  const styleUrls = {
    light: 'https://tilemaps.2gis.com/api/styles/v1/2gis/ru/light',
    dark: 'https://tilemaps.2gis.com/api/styles/v1/2gis/ru/dark',
    satellite: 'https://tilemaps.2gis.com/api/styles/v1/2gis/ru/satellite'
  }

  useEffect(() => {
    if (!mapContainer.current) return

    // Загрузка MapGL API
    load().then((mapgl) => {
      const map = new mapgl.Map(mapContainer.current, {
        center: center,
        zoom: zoom,
        key: process.env.NEXT_PUBLIC_2GIS_API_KEY || 'YOUR_2GIS_API_KEY',
        
      )

      mapInstance.current = map

      map.on('load', () => {
        setIsLoaded(true)
      })
    })

    return () => {
      if (mapInstance.current) {
        mapInstance.current.destroy()
      }
    }
  }, [center, zoom, style])

  return (
    <div className={`relative ${className}`}>
      <div
        ref={mapContainer}
        className="w-full h-full rounded-lg overflow-hidden shadow-lg"
        style={{ width, height }}
      />
      
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-sm text-gray-600">Загрузка...</p>
          </div>
        </div>
      )}

      {isLoaded && showInfo && (
        <div className="absolute top-2 left-2 bg-white bg-opacity-90 rounded px-2 py-1 text-xs text-gray-600">
          Москва • Масштаб: {zoom}
        </div>
      )}
    </div>
  )
}
