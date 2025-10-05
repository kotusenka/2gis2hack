'use client'

import SimpleMap from '@/components/SimpleMap'
import OpenStreetMap from '@/components/OpenStreetMap'

export default function TestPage() {

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Тестовая страница MapGL</h1>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-lg p-4">
            <h2 className="text-xl font-semibold mb-2">MapGL (2ГИС):</h2>
            <p className="text-gray-600 mb-4">Красная рамка показывает границы контейнера</p>
            <SimpleMap />
          </div>
          
          <div className="bg-white rounded-lg p-4">
            <h2 className="text-xl font-semibold mb-2">OpenStreetMap:</h2>
            <p className="text-gray-600 mb-4">Альтернативная карта без внешних зависимостей</p>
            <OpenStreetMap height="384px" />
          </div>
        </div>
        
        <div className="mt-6 bg-blue-50 p-4 rounded-lg">
          <h3 className="font-semibold mb-2">Откройте консоль разработчика (F12) для просмотра логов</h3>
          <p className="text-sm text-gray-600">
            Если карта не видна, проверьте консоль на ошибки. Красная рамка должна показывать границы контейнера.
          </p>
        </div>
      </div>
    </div>
  )
}
