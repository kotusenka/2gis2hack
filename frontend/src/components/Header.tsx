'use client'

import { useState } from 'react'

export default function Header() {
  const [query, setQuery] = useState('')

  return (
    <header className="w-full h-14 bg-white border-b border-gray-200 flex items-center px-4 gap-4">
      <div className="text-emerald-600 font-bold tracking-wide">2ГИС</div>
      <div className="flex-1 max-w-3xl">
        <div className="relative">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск: адрес, место, категория"
            className="w-full h-10 rounded-md border border-gray-300 pl-10 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
          <span className="absolute left-3 top-2.5 text-gray-400">🔎</span>
          <button className="absolute right-2 top-1.5 text-xs bg-emerald-600 text-white rounded px-2 py-1">Найти</button>
        </div>
      </div>
      <nav className="hidden md:flex items-center gap-3 text-sm text-gray-600">
        <button className="hover:text-gray-900">Вход</button>
        <button className="hover:text-gray-900">Добавить место</button>
      </nav>
    </header>
  )
}


