import { IncidentList } from '@/components/IncidentList'
import { NewIncidentDialog } from '@/components/NewIncidentDialog'
import { PendingCards } from '@/components/PendingCards'
import { useMe } from '@/components/RequireSession'

export function HomePage() {
  const me = useMe()

  return (
    <div className="space-y-8">
      <PendingCards />
      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Incidents</h2>
          <NewIncidentDialog role={me.role} />
        </div>
        <IncidentList />
      </section>
    </div>
  )
}