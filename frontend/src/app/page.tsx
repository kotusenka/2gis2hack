import SimpleMap from '@/components/SimpleMap'

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-100">
      <div className="flex flex-col min-h-screen">
        <div className="flex-1">
          <div className="relative bg-white">
            <div className="h-screen">
              <SimpleMap />
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
