import SimpleMap from '@/components/SimpleMap'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Карта Москвы
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Интерактивная карта Москвы с использованием MapGL от 2ГИС
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
          <div className="h-[384px]">
            <SimpleMap />
          </div>
        </div>


        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl p-6 shadow-lg">
            <h3 className="text-lg font-semibold mb-3 text-gray-800">
              🗺️ Интерактивность
            </h3>
            <p className="text-gray-600">
              Полнофункциональная карта с возможностью масштабирования, 
              поворота и наклона
            </p>
          </div>
          
          <div className="bg-white rounded-xl p-6 shadow-lg">
            <h3 className="text-lg font-semibold mb-3 text-gray-800">
              🚀 Производительность
            </h3>
            <p className="text-gray-600">
              Оптимизированная карта с быстрой загрузкой и плавной анимацией
            </p>
          </div>
          
          <div className="bg-white rounded-xl p-6 shadow-lg">
            <h3 className="text-lg font-semibold mb-3 text-gray-800">
              📱 Адаптивность
            </h3>
            <p className="text-gray-600">
              Отлично работает на всех устройствах - от мобильных до десктопов
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
