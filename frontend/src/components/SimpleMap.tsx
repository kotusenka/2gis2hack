  'use client'

  import { useEffect, useRef } from 'react'
  import { load } from '@2gis/mapgl'
  import { Directions } from '@2gis/mapgl-directions'



  export default function SimpleMap() {
    const mapRef = useRef<HTMLDivElement>(null)
  const markersRef = useRef<Map<number, any>>(new Map())
  const busMarkerRef = useRef<any>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const lastCountRef = useRef<number | null>(null)
  const mapInstanceRef = useRef<any>(null)
  const currentIconRef = useRef<'default' | 'green' | 'yellow' | 'red'>('default')
  const trailingMarkerRef = useRef<any>(null)

  // Пути до иконок маркера (используем абсолютные URL, чтобы исключить /undefined)
  const ICONS = {
    default: 'https://docs.2gis.com/img/mapgl/marker.svg',
    green: (typeof window !== 'undefined' ? window.location.origin : '') + '/icons/green.svg',
    yellow: (typeof window !== 'undefined' ? window.location.origin : '') + '/icons/yellow.svg',
    red: (typeof window !== 'undefined' ? window.location.origin : '') + '/icons/red.svg',
  } as const

  // Размер иконки маркера (в пикселях)
  const MARKER_SIZE: [number, number] = [32, 32]

  // Предзагрузка иконок, чтобы избежать мига и 404 undefined
  const preloadIcons = () => {
    try {
      ;[ICONS.default, ICONS.green, ICONS.yellow, ICONS.red].forEach((url) => {
        const img = new Image()
        img.src = url
      })
    } catch {}
  }

  const applyLatestCountIfReady = () => {
    const count = lastCountRef.current
    if (count == null) return
    updateMarkerAppearance(count)
  }

  // Обновление подписи и иконки маркера по значению счётчика
  const updateMarkerAppearance = (count: number) => {
    const marker: any = busMarkerRef.current || markersRef.current.get(0)
    if (!marker) return
    // marker.setLabel({ text: `${count} чел.`, offset: [0, -10], color: '#111' }) // скрываем количество людей

    let nextIconKey: 'green' | 'yellow' | 'red' = 'green'
    if (count === 1) nextIconKey = 'yellow'
    else if (count >= 2) nextIconKey = 'red'

    if (currentIconRef.current !== nextIconKey) {
      const url = ICONS[nextIconKey]
      if (url && typeof marker.setIcon === 'function') {
        marker.setIcon({ icon: url, size: MARKER_SIZE } as any)
        currentIconRef.current = nextIconKey
      }
    }
  }

    useEffect(() => {
      if (!mapRef.current) return

      console.log('🧪 Простая карта: начинаем загрузку...')
      
      let cancelled = false
      load().then((mapglAPI) => {
        if (cancelled || !mapRef.current) return
        console.log('✅ Простая карта: API загружен')
        
        const map = new mapglAPI.Map(mapRef.current!, {
          center: [37.6208, 55.7539], // центр Москвы
          zoom: 13,
          key: '39d1fbf7-ca4d-4871-9f90-c3f3698ef3dc',
        })
        mapInstanceRef.current = map
        
        console.log('✅ Простая карта: создана', map)
        
        map.on('styleload', () => {
          console.log('🎉 Простая карта: загружена!')

          // Маршрут автобуса (массив координат [lng, lat])
          const route: [number, number][] = [
            [37.62372, 55.74965],
            [37.611929, 55.747856], //37.611929, 55.747856
         //   [37.61189, 55.74826],
         //   [37.61097, 55.74889],
            [37.6095, 55.74937],
            [37.60972, 55.75055],
            [37.61114, 55.75259],
            [37.61448, 55.75655],
            [37.6178, 55.75844],
            [37.62453, 55.75953],
            [37.62576, 55.7595],
            [37.62696, 55.75872],
            [37.63023, 55.7566],
            [37.63334, 55.75432],
            [37.63228, 55.7498],
            [37.62812, 55.74995],
            [37.62372, 55.74965], // Маршрут замыкается начальной точкой
        ];

        // Предзагрузим иконки до создания маркера
        preloadIcons()

        const marker = new mapglAPI.Marker(map, {
          coordinates: [37.62372, 55.74965],
          // По умолчанию считаем 0 → зелёный
          icon: ICONS.green,
          size: MARKER_SIZE,
          // стартуем без "полоски"
          // label: { text: `${0} чел.`, offset: [0, -10], color: '#111' } // скрываем количество людей
        });
        // Зелёный хвостовой маркер, едет позади без лейблов
        const trailingMarker = new mapglAPI.Marker(map, {
          coordinates: [37.62372, 55.74965],
          icon: ICONS.green,
          size: MARKER_SIZE,
        })
        trailingMarkerRef.current = trailingMarker
        // Рисуем маршрут цветной линией
        const routeLine = new mapglAPI.Polyline(map, {
          coordinates: route,
          color: '#1976d2',
          width: 6,
          opacity: 0.9
        } as any)
        // сохраняем маркер автобуса с id 0 и прямую ссылку
        markersRef.current.set(0, marker)
        busMarkerRef.current = marker
        // если уже пришли данные по WS — применим их сразу
        applyLatestCountIfReady()
      // Функция для интерполяции между двумя точками

  //     const directions = new Directions(map, {
  //       directionsApiKey: 'Ключ для Directions API',
  //   });
  //   directions.carRoute({
  //     points: [
  //         [55.27887, 25.21001],
  //         [55.30771, 25.20314],
  //     ],
  // });

function interpolateCoordinates(
  coord1: [number, number],
  coord2: [number, number],
  t: number
): [number, number] {
  return [
    coord1[0] + (coord2[0] - coord1[0]) * t,
    coord1[1] + (coord2[1] - coord1[1]) * t
  ]
}

function animateTravel(
  marker: any,
  route: [number, number][],
  durationPerSegment: number,
  perSegmentDuration?: (segmentIndex: number) => number
) {
  let segmentIndex = 0;
  

  function animateSegment(startTime: number) {
      const elapsedTime = performance.now() - startTime;
      const currentDuration = perSegmentDuration ? perSegmentDuration(segmentIndex) : durationPerSegment;
      const t = elapsedTime / currentDuration; // Процент завершения сегмента

      if (t < 1) {
          // Интерполяция координат
          const newCoords: [number, number] = interpolateCoordinates(
              route[segmentIndex],
              route[segmentIndex + 1],
              t,
          );
          marker.setCoordinates(newCoords);

          // Продолжение анимации текущего сегмента
          requestAnimationFrame(() => animateSegment(startTime));
      } else {
          // Переход к следующему сегменту
          segmentIndex++;
          if (segmentIndex < route.length - 1) {
              animateSegment(performance.now());
          } else {
              // Зацикливание маршрута
              segmentIndex = 0;
              animateSegment(performance.now());
          }
      }
  }

  // Начало анимации первого сегмента
  if (route.length > 1) {
      animateSegment(performance.now());
  }
}

// Вызов функции анимации
const BASE_SEGMENT_DURATION_MS = 20000;
const getSegmentDuration = (idx: number) => {
  // Ускоряем участок между 2-й и 3-й точками маршрута (индекс сегмента 1)
  if (idx === 1) return Math.max(3000, Math.floor(BASE_SEGMENT_DURATION_MS / 3));
  return BASE_SEGMENT_DURATION_MS;
};
animateTravel(marker, route, BASE_SEGMENT_DURATION_MS, getSegmentDuration);

// Хвостовой маркер стартует с задержкой, чтобы быть "сзади"
const TRAILING_DELAY_MS = 7000; // увеличиваем расстояние (задержку) хвоста
setTimeout(() => {
  try {
    if (trailingMarkerRef.current) {
      animateTravel(trailingMarkerRef.current, route, BASE_SEGMENT_DURATION_MS, getSegmentDuration)
    }
  } catch {}
}, TRAILING_DELAY_MS);


          map.setCenter(route[0])
          map.setZoom(14)
        })
        
        map.on('error', (err: any) => {
          console.error('❌ Простая карта: ошибка', err)
        })
        
      }).catch((err: any) => {
        console.error('❌ Простая карта: ошибка API', err)
      })

      // Чистка: уничтожаем карту при размонтировании, чтобы в dev не плодились инстансы
      return () => {
        cancelled = true
        try {
          if (mapInstanceRef.current) {
            mapInstanceRef.current.destroy()
            mapInstanceRef.current = null
          }
        } catch {}
      }
    }, [])

  // WebSocket: обновление подписи маркера в реальном времени (вне колбэков)
  useEffect(() => {
    const ws = new WebSocket('ws://192.168.195.57:8000/ws/aaa')
    wsRef.current = ws
    ws.onopen = () => {
      console.log('WebSocket connected')
    }
    ws.onmessage = (e) => {
      let nextCount: number | null = null
      try {
        const parsed = JSON.parse(e.data)
        console.log(parsed)
        if (parsed && typeof parsed.count === 'number') {
          nextCount = parsed.count
        }
      } catch (err) {
        const n = Number(e.data)
        if (!Number.isNaN(n)) nextCount = n
      }

      if (nextCount != null) {
        lastCountRef.current = nextCount
        applyLatestCountIfReady()
        // Обновим иконку/лейбл сразу
        updateMarkerAppearance(nextCount)
      }
    }
    ws.onclose = () => {
      console.log('WebSocket closed')
    }
    return () => {
      try { ws.close() } catch {}
      wsRef.current = null
    }
  }, [])

    return (
      <div className="w-full h-full">
        <div 
          ref={mapRef}
          className="w-full h-full"
          style={{ 
            width: '100%', 
            height: '100%'
          }}
        />
      </div>
    )
  }
