import SimpleMap from '@/components/SimpleMap'
import Header from '@/components/Header'
import LeftSidebar from '@/components/LeftSidebar'
import ResultsPanel from '@/components/ResultsPanel'
import BottomBar from '@/components/BottomBar'

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-100">
      <div className="flex flex-col min-h-screen">
        <Header />
        <div className="flex-1 grid grid-cols-[14rem_1fr_20rem] grid-rows-[1fr_auto]">
          <LeftSidebar />
          <div className="relative bg-white border-x border-gray-200">
            <div className="h-[calc(100vh-3.5rem-2.5rem)]">
              <SimpleMap />
            </div>
          </div>
          <ResultsPanel />
          <div className="col-span-3">
            <BottomBar />
          </div>
        </div>
      </div>
    </main>
  )
}
