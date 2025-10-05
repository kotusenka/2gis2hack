'use client'

import React from 'react'

// MapWrapper компонент с React.memo для избежания повторного рендеринга
// Согласно документации 2ГИС: https://docs.2gis.com/ru/mapgl/start/react
const MapWrapper = React.memo(
  () => {
    return (
      <div 
        id="map-container" 
        style={{ 
          width: '100%', 
          height: '100%',
          minHeight: '400px', // Минимальная высота
          position: 'relative' // Важно для позиционирования
        }}
      />
    )
  },
  () => true, // Всегда возвращаем true для избежания повторного рендеринга
)

MapWrapper.displayName = 'MapWrapper'

export default MapWrapper
