# 🗺️ API Guide - MapGL от 2ГИС

## 📦 Установка и настройка

### 1. Установка пакета
```bash
npm install @2gis/mapgl@^1.65.0
```

### 2. Получение API ключа
1. Зарегистрируйтесь на [dev.2gis.com](https://dev.2gis.com/)
2. Создайте новый проект
3. Получите API ключ для MapGL

### 3. Настройка переменных окружения
```bash
# .env.local
NEXT_PUBLIC_2GIS_API_KEY=ваш_ключ_здесь
```

## 🚀 Использование

### Базовый пример
```tsx
import { load } from '@2gis/mapgl'

function MyMap() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState(null)

  useEffect(() => {
    if (!mapContainer.current) return

    load().then((mapgl) => {
      const mapInstance = new mapgl.Map(mapContainer.current, {
        center: [37.6173, 55.7558], // Москва
        zoom: 11,
        key: process.env.NEXT_PUBLIC_2GIS_API_KEY,
        style: 'https://tilemaps.2gis.com/api/styles/v1/2gis/ru/light',
      })

      setMap(mapInstance)
    })

    return () => {
      if (map) {
        map.destroy()
      }
    }
  }, [])

  return <div ref={mapContainer} style={{ width: '100%', height: '400px' }} />
}
```

## 🎨 Стили карт

### Доступные стили
```javascript
const styles = {
  light: 'https://tilemaps.2gis.com/api/styles/v1/2gis/ru/light',
  dark: 'https://tilemaps.2gis.com/api/styles/v1/2gis/ru/dark',
  satellite: 'https://tilemaps.2gis.com/api/styles/v1/2gis/ru/satellite'
}
```

### Смена стиля
```javascript
map.setStyle(styles.dark)
```

## 🎯 События карты

### Основные события
```javascript
// Загрузка карты
map.on('load', () => {
  console.log('Карта загружена')
})

// Движение карты
map.on('move', () => {
  const center = map.getCenter()
  const zoom = map.getZoom()
  console.log('Центр:', center, 'Масштаб:', zoom)
})

// Клик по карте
map.on('click', (e) => {
  console.log('Клик:', e.lngLat)
})
```

## 🔧 Управление картой

### Методы навигации
```javascript
// Перемещение к точке
map.flyTo({
  center: [37.6173, 55.7558],
  zoom: 15,
  duration: 1000
})

// Установка масштаба
map.zoomTo(12)

// Получение текущего состояния
const center = map.getCenter()
const zoom = map.getZoom()
const bearing = map.getBearing()
const pitch = map.getPitch()
```

### Анимации
```javascript
// Плавное перемещение
map.flyTo({
  center: [37.6173, 55.7558],
  zoom: 15,
  duration: 2000,
  essential: true
})

// Мгновенное перемещение
map.jumpTo({
  center: [37.6173, 55.7558],
  zoom: 15
})
```

## 📍 Маркеры и слои

### Добавление маркера
```javascript
// Создание маркера
const marker = new mapgl.Marker({
  coordinates: [37.6173, 55.7558],
  map: map
})

// Удаление маркера
marker.destroy()
```

### Добавление слоя
```javascript
map.addSource('my-data', {
  type: 'geojson',
  data: {
    type: 'FeatureCollection',
    features: [...]
  }
})

map.addLayer({
  id: 'my-layer',
  type: 'circle',
  source: 'my-data',
  paint: {
    'circle-color': '#3b82f6',
    'circle-radius': 8
  }
})
```

## 🎛️ Элементы управления

### Встроенные контролы
```javascript
const map = new mapgl.Map(mapContainer, {
  // ... другие опции
  controls: {
    zoom: true,
    rotation: true,
    pitch: true
  }
})
```

### Кастомные контролы
```javascript
// Создание кастомного контрола
class CustomControl {
  onAdd(map) {
    this._map = map
    this._container = document.createElement('div')
    this._container.className = 'custom-control'
    this._container.innerHTML = '<button>Мой контрол</button>'
    return this._container
  }

  onRemove() {
    this._container.remove()
  }
}

map.addControl(new CustomControl())
```

## 🔍 Поиск и геокодирование

### Поиск адресов
```javascript
// Инициализация геокодера
const geocoder = new mapgl.Geocoder({
  apiKey: process.env.NEXT_PUBLIC_2GIS_API_KEY
})

// Поиск адреса
geocoder.geocode('Москва, Красная площадь', (results) => {
  if (results.length > 0) {
    const result = results[0]
    map.flyTo({
      center: result.coordinates,
      zoom: 15
    })
  }
})
```

## 📱 Адаптивность

### Responsive карта
```css
.map-container {
  width: 100%;
  height: 400px;
}

@media (max-width: 768px) {
  .map-container {
    height: 300px;
  }
}
```

### Обработка изменения размера
```javascript
// Автоматическое обновление размера
window.addEventListener('resize', () => {
  map.resize()
})
```

## 🚨 Обработка ошибок

### Проверка загрузки API
```javascript
load().then((mapgl) => {
  // API загружен успешно
  const map = new mapgl.Map(...)
}).catch((error) => {
  console.error('Ошибка загрузки MapGL:', error)
})
```

### Обработка ошибок карты
```javascript
map.on('error', (error) => {
  console.error('Ошибка карты:', error)
})
```

## 🎯 Лучшие практики

### 1. Очистка ресурсов
```javascript
useEffect(() => {
  return () => {
    if (map) {
      map.destroy()
    }
  }
}, [])
```

### 2. Оптимизация производительности
```javascript
// Дебаунс для событий движения
let timeoutId
map.on('move', () => {
  clearTimeout(timeoutId)
  timeoutId = setTimeout(() => {
    // Обработка движения
  }, 100)
})
```

### 3. Кэширование API
```javascript
// Загрузка API только один раз
let mapglPromise = null

function getMapGL() {
  if (!mapglPromise) {
    mapglPromise = load()
  }
  return mapglPromise
}
```

## 📚 Дополнительные ресурсы

- [Официальная документация 2ГИС](https://dev.2gis.com/)
- [Примеры использования](https://github.com/2gis/mapgl-examples)
- [API Reference](https://docs.2gis.com/ru/mapgl/overview)
