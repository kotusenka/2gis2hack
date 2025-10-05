'use client'

import { useCallback } from 'react'
import { useMap } from '@/context/MapContext'

export default function MapControls() {
  const [mapInstance] = useMap()

  const setInitialCenter = useCallback(() => {
    if (mapInstance) {
      mapInstance.setCenter([37.6173, 55.7558])
    }
  }, [mapInstance])

  const zoomIn = useCallback(() => {
    if (mapInstance) {
      const currentZoom = mapInstance.getZoom()
      mapInstance.zoomTo(currentZoom + 1, { duration: 300 })
    }
  }, [mapInstance])

  const zoomOut = useCallback(() => {
    if (mapInstance) {
      const currentZoom = mapInstance.getZoom()
      mapInstance.zoomTo(currentZoom - 1, { duration: 300 })
    }
  }, [mapInstance])

  const resetView = useCallback(() => {
    if (mapInstance) {
      mapInstance.flyTo({
        center: [37.6173, 55.7558],
        zoom: 11,
        duration: 1000
      })
    }
  }, [mapInstance])

  if (!mapInstance) {
    return null
  }

  return (
    <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
      <button
        onClick={setInitialCenter}
        className="bg-white hover:bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition-colors"
        title="Установить центр Москвы"
      >
        🏛️ Центр Москвы
      </button>
      
      <button
        onClick={zoomIn}
        className="bg-white hover:bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition-colors"
        title="Увеличить"
      >
        🔍+
      </button>
      
      <button
        onClick={zoomOut}
        className="bg-white hover:bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition-colors"
        title="Уменьшить"
      >
        🔍-
      </button>
      
      <button
        onClick={resetView}
        className="bg-white hover:bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition-colors"
        title="Сбросить вид"
      >
        🔄 Сброс
      </button>
    </div>
  )
}
