// Shown before demo visitors type anything, because demo data is visible to everyone
export function DemoNotice() {
  return (
    <p className="text-sm text-muted-foreground">
      Demo data is public. Do not enter personal or confidential information. Demo data is deleted after 7 days.
    </p>
  )
}