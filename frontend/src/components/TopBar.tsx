import { useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { signOut, type Me } from '@/lib/api'

export function TopBar({ me }: { me: Me }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  async function handleSignOut() {
    // Leave even if the call fails; the sign-in page is the right place either way
    await signOut().catch(() => undefined)
    await navigate('/login')
    queryClient.clear()
  }

  return (
    <header className="border-b">
      <div className="mx-auto flex h-14 max-w-3xl items-center gap-3 px-4">
        <Link to="/" className="font-semibold">
          Fixwright
        </Link>
        {me.role === 'demo' && <Badge variant="secondary">Demo</Badge>}
        <Button
          variant="ghost"
          size="icon"
          aria-label="Sign out"
          title="Sign out"
          className="ml-auto"
          onClick={handleSignOut}
        >
          <LogOut />
        </Button>
      </div>
    </header>
  )
}