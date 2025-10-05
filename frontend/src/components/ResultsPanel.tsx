'use client'

interface ResultItem {
  id: string
  title: string
  subtitle?: string
  distance?: string
}

const mock: ResultItem[] = [
  { id: '1', title: 'Остановка: Площадь Революции', subtitle: 'Автобусы: 158, 904', distance: '120 м' },
  { id: '2', title: 'Кофейня рядом', subtitle: 'Открыто до 23:00', distance: '250 м' },
  { id: '3', title: 'Аптека', subtitle: 'Круглосуточно', distance: '300 м' },
]

export default function ResultsPanel() {
  return (
    <aside className="w-80 bg-white border-l border-gray-200 h-full flex flex-col">
      <div className="p-3 border-b border-gray-100 text-sm text-gray-600">Найденные места</div>
      <div className="flex-1 overflow-y-auto">
        <ul className="divide-y divide-gray-100">
          {mock.map((r) => (
            <li key={r.id} className="p-3 hover:bg-gray-50 cursor-pointer">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-gray-900">{r.title}</div>
                {r.distance && <div className="text-xs text-gray-500">{r.distance}</div>}
              </div>
              {r.subtitle && <div className="text-xs text-gray-600 mt-0.5">{r.subtitle}</div>}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  )
}


