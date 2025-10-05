'use client'

import { useEffect, useState } from 'react'
import { load } from '@2gis/mapgl'
import MapWrapper from './MapWrapper'
import { useMap } from '@/context/MapContext'

interface MapGLProps {
  center?: [number, number]
  zoom?: number
  apiKey?: string
  onMapLoad?: (map: any) => void
  onMapError?: (error: string) => void
}

export default function MapGL({
  center = [37.6173, 55.7558],
  zoom = 11,
  apiKey,
  onMapLoad,
  onMapError
}: MapGLProps) {
  const [isLoaded, setIsLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [, setMapInstance] = useMap()

  useEffect(() => {
    let map: any = null

    // Проверяем, что контейнер существует
    const container = document.getElementById('map-container')
    console.log('📦 Контейнер карты:', container ? 'НАЙДЕН' : 'НЕ НАЙДЕН', container)

    // Загрузка MapGL API согласно документации
    console.log('🔄 Начинаем загрузку MapGL API...')
    load().then((mapglAPI) => {
      console.log('✅ MapGL API загружен успешно:', mapglAPI)
      
      // Проверяем API ключ
      const key = apiKey || process.env.NEXT_PUBLIC_2GIS_API_KEY
      console.log('🔑 API ключ:', key ? `${key.substring(0, 8)}...` : 'НЕ НАЙДЕН')
      
      if (!key || key === 'YOUR_2GIS_API_KEY') {
        const errorMsg = 'API ключ не настроен. Создайте файл .env.local с NEXT_PUBLIC_2GIS_API_KEY'
        console.error('❌', errorMsg)
        setError(errorMsg)
        onMapError?.(errorMsg)
        return
      }

      try {
        console.log('🗺️ Инициализируем карту с параметрами:', { center, zoom, key: key.substring(0, 8) + '...' })
        
        // Инициализация карты согласно документации 2ГИС
        map = new mapglAPI.Map('map-container', {
          center: center,
          zoom: zoom,
          key: key,
          // Убираем внешние стили, используем встроенные
        })
        
        console.log('✅ Карта создана:', map)

        // Обработчики событий
        map.on('load', () => {
          console.log('🎉 Карта загружена успешно!')
          
          // Принудительно обновляем размер карты
          setTimeout(() => {
            map.resize()
            console.log('📏 Размер карты обновлен')
          }, 100)
          
          setIsLoaded(true)
          setError(null)
          setMapInstance(map) // Сохраняем ссылку на карту в Context
          onMapLoad?.(map)
        })

        map.on('error', (err: any) => {
          console.error('❌ Ошибка карты:', err)
          const errorMsg = `Ошибка карты: ${err.message || 'Неизвестная ошибка'}`
          setError(errorMsg)
          onMapError?.(errorMsg)
        })

      } catch (initError: any) {
        console.error('❌ Ошибка инициализации карты:', initError)
        const errorMsg = `Ошибка инициализации карты: ${initError.message || 'Неизвестная ошибка'}`
        setError(errorMsg)
        onMapError?.(errorMsg)
      }
    }).catch((err: any) => {
      console.error('❌ Ошибка загрузки MapGL:', err)
      const errorMsg = `Ошибка загрузки MapGL: ${err.message || 'Проверьте интернет-соединение'}`
      setError(errorMsg)
      onMapError?.(errorMsg)
    })

    // Удаляем карту при размонтировании компонента (согласно документации)
    return () => {
      if (map) {
        map.destroy()
      }
    }
  }, [center, zoom, apiKey, onMapLoad, onMapError])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <MapWrapper />
      
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
