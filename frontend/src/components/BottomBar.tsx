'use client'

export default function BottomBar() {
  return (
    <div className="h-10 bg-white border-t border-gray-200 flex items-center justify-between px-4 text-xs text-gray-600">
      <div className="flex items-center gap-3">
        <span>Данные: 2ГИС</span>
        <a className="hover:underline" href="https://2gis.ru" target="_blank" rel="noreferrer">Справка</a>
        <a className="hover:underline" href="#">Лицензия</a>
      </div>
      <div className="text-gray-400">v0.1</div>
    </div>
  )
}


