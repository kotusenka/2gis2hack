'use client'

const items = [
  { emoji: '🍔', label: 'Поесть' },
  { emoji: '🛍️', label: 'Покупки' },
  { emoji: '💊', label: 'Аптеки' },
  { emoji: '🛠️', label: 'Услуги' },
  { emoji: '🏥', label: 'Медицина' },
  { emoji: '🚗', label: 'Авто' },
  { emoji: '🎓', label: 'Учёба' },
  { emoji: '🏋️', label: 'Спорт' },
]

export default function LeftSidebar() {
  return (
    <aside className="w-56 bg-white border-r border-gray-200 h-full overflow-y-auto">
      <div className="p-3 text-xs text-gray-500">Рубрики</div>
      <ul className="px-2 pb-4 space-y-1">
        {items.map((it) => (
          <li key={it.label}>
            <button className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded hover:bg-gray-50 text-gray-700">
              <span className="text-lg" aria-hidden>{it.emoji}</span>
              <span>{it.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}


