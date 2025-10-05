  'use client'

  import { useEffect, useRef } from 'react'
  import { load } from '@2gis/mapgl'
  import { Directions } from '@2gis/mapgl-directions'



  export default function SimpleMap() {
    const mapRef = useRef<HTMLDivElement>(null)
  const markersRef = useRef<Map<number, any>>(new Map())
  const busMarkerRef = useRef<any>(null)

    useEffect(() => {
      if (!mapRef.current) return

      console.log('🧪 Простая карта: начинаем загрузку...')
      
      load().then((mapglAPI) => {
        console.log('✅ Простая карта: API загружен')
        
        const map = new mapglAPI.Map(mapRef.current!, {
          center: [37.6208, 55.7539], // центр Москвы
          zoom: 13,
          key: '39d1fbf7-ca4d-4871-9f90-c3f3698ef3dc',
        })
        
        console.log('✅ Простая карта: создана', map)
        
        map.on('styleload', () => {
          console.log('🎉 Простая карта: загружена!')

          // Маршрут автобуса (массив координат [lng, lat])
          const route = [
            [37.62372, 55.74965],
            [37.61306, 55.74789],
            [37.61189, 55.74826],
            [37.61097, 55.74889],
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

        const marker = new mapglAPI.Marker(map, {
          coordinates: [37.62372, 55.74965],
          icon: 'https://docs.2gis.com/img/mapgl/marker.svg',
          // стартуем без "полоски"
          label: { text: `${0} чел.`, offset: [0, -10], color: '#111' }
        });
        // сохраняем маркер автобуса с id 0 и прямую ссылку
        markersRef.current.set(0, marker)
        busMarkerRef.current = marker
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

function interpolateCoordinates(coord1, coord2, t) {
  return [coord1[0] + (coord2[0] - coord1[0]) * t, coord1[1] + (coord2[1] - coord1[1]) * t];
}

function animateTravel(marker, route, durationPerSegment) {
  let segmentIndex = 0;
  

  function animateSegment(startTime) {
      const elapsedTime = performance.now() - startTime;
      const t = elapsedTime / durationPerSegment; // Процент завершения сегмента

      if (t < 1) {
          // Интерполяция координат
          const newCoords = interpolateCoordinates(
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
const durationPerSegment = 20000;
animateTravel(marker, route, durationPerSegment);


          map.setCenter(route[0][0], route[0][1])
          map.setZoom(14)
        })
        
        map.on('error', (err: any) => {
          console.error('❌ Простая карта: ошибка', err)
        })
        
      }).catch((err: any) => {
        console.error('❌ Простая карта: ошибка API', err)
      })
    }, [])

  // WebSocket: обновление подписи маркера в реальном времени (вне колбэков)
  useEffect(() => {
    const ws = new WebSocket('ws://192.168.195.57:8000/ws/aaa')
    ws.onopen = () => {
      console.log('WebSocket connected')
    }
    ws.onmessage = (e) => {
      try {
        const { count } = JSON.parse(e.data)
        console.log(count)
        console.log(busMarkerRef.current)
        console.log(markersRef.current.get(0))
        const m = busMarkerRef.current || markersRef.current.get(0)
        if (m && typeof count === 'number') {
          console.log('setLabe', count)
          // m.SetIcon({url: '/icons/red.svg', size: [32, 32]})
          m.setLabel({ text: `${count} чел.`, offset: [0, -10], color: '#111' })
          console.log("setLabel")
        }
      } catch {}
    }
    return () => ws.close()
  }, [])

    return (
      <div className="w-full h-96 border-2 border-red-500 bg-gray-100">
        <div 
          ref={mapRef}
          className="w-full h-full"
          style={{ 
            width: '100%', 
            height: '100%',
            minHeight: '384px' // 24rem = 384px
          }}
        />
      </div>
    )
  }
