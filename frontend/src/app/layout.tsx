import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Карта Москвы - MapGL',
  description: 'Интерактивная карта Москвы с использованием MapGL от 2ГИС',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <body className="antialiased">
        {children}
      </body>
    </html>
  )
}
