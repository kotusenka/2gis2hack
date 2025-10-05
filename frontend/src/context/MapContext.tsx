'use client'

import React, { createContext, useContext, useState } from 'react'

// Создаем Context для доступа к карте из других компонентов
// Согласно документации 2ГИС: https://docs.2gis.com/ru/mapgl/start/react
const MapContext = createContext<[any, (map: any) => void]>([undefined, () => {}])

export const MapProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mapInstance, setMapInstance] = useState<any>()

  return (
    <MapContext.Provider value={[mapInstance, setMapInstance]}>
      {children}
    </MapContext.Provider>
  )
}

export const useMap = () => {
  const [mapInstance, setMapInstance] = useContext(MapContext)
  return [mapInstance, setMapInstance] as const
}
