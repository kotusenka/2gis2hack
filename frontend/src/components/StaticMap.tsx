'use client'

import { useState } from 'react'

interface StaticMapProps {
  width?: string | number
  height?: string | number
  center?: [number, number]
  zoom?: number
  className?: string
}

export default function StaticMap({
  width = '100%',
  height = '400px',
  center = [37.6173, 55.7558],
  zoom = 11,
  className = ''
}: StaticMapProps) {
  const [imageError, setImageError] = useState(false)

  // Генерируем URL для статичной карты OpenStreetMap
  const mapUrl = `https://tile.openstreetmap.org/${zoom}/${Math.floor((center[0] + 180) / 360 * Math.pow(2, zoom))}/${Math.floor((1 - Math.log(Math.tan(center[1] * Math.PI / 180) + 1 / Math.cos(center[1] * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, zoom))}.png`

  if (imageError) {
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
          <p className="text-gray-500 text-sm">
            Не удалось загрузить карту.<br/>
            Проверьте интернет-соединение.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={`relative ${className}`} style={{ width, height }}>
      <img
        src={mapUrl}
        alt="Карта Москвы"
        className="w-full h-full object-cover rounded-lg"
        onError={() => setImageError(true)}
        style={{ width, height }}
      />
      <div className="absolute bottom-2 left-2 bg-white bg-opacity-90 rounded px-2 py-1 text-xs text-gray-600">
        Москва • Масштаб: {zoom}
      </div>
    </div>
  )
}
