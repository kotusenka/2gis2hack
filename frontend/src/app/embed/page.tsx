import EmbeddableMap from '@/components/EmbeddableMap'

export default function EmbedPage() {
  return (
    <main className="min-h-screen bg-gray-50 py-8">
      <div className="container mx-auto px-4">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-4">
            Встраиваемые карты
          </h1>
          <p className="text-lg text-gray-600">
            Примеры использования карт в различных размерах и стилях
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
          {/* Большая карта */}
          <div className="bg-white rounded-xl p-6 shadow-lg">
            <h3 className="text-xl font-semibold mb-4">Большая карта</h3>
            <EmbeddableMap 
              height="400px"
              zoom={12}
              showInfo={true}
              style="light"
            />
          </div>

          {/* Маленькая карта */}
          <div className="bg-white rounded-xl p-6 shadow-lg">
            <h3 className="text-xl font-semibold mb-4">Компактная карта</h3>
            <EmbeddableMap 
              height="300px"
              zoom={10}
              showInfo={true}
              style="dark"
            />
          </div>
        </div>

        {/* Сетка карт */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <div className="bg-white rounded-xl p-4 shadow-lg">
            <h4 className="font-semibold mb-3">Светлая тема</h4>
            <EmbeddableMap 
              height="250px"
              zoom={13}
              style="light"
            />
          </div>

          <div className="bg-white rounded-xl p-4 shadow-lg">
            <h4 className="font-semibold mb-3">Темная тема</h4>
            <EmbeddableMap 
              height="250px"
              zoom={13}
              style="dark"
            />
          </div>

          <div className="bg-white rounded-xl p-4 shadow-lg">
            <h4 className="font-semibold mb-3">Спутник</h4>
            <EmbeddableMap 
              height="250px"
              zoom={13}
              style="satellite"
            />
          </div>
        </div>

        {/* Код для встраивания */}
        <div className="bg-gray-900 rounded-xl p-6 text-white">
          <h3 className="text-xl font-semibold mb-4">Код для встраивания</h3>
          <pre className="bg-gray-800 rounded-lg p-4 overflow-x-auto text-sm">
            <code>{`// React компонент
import EmbeddableMap from './components/EmbeddableMap'

function MyPage() {
  return (
    <EmbeddableMap 
      height="400px"
      zoom={12}
      center={[37.6173, 55.7558]}
      style="light"
      showInfo={true}
    />
  )
}`}
            </code>
          </pre>
        </div>
      </div>
    </main>
  )
}
