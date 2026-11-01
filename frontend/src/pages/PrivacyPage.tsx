import type { ReactNode } from 'react'
import { Link } from 'react-router'

const ISSUES = 'https://github.com/ozcivitcagkan/Fixwright-Enterprise-AI-Reliability-Integration-Platform/issues'

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="font-semibold">{title}</h2>
      <div className="space-y-2 text-sm text-muted-foreground">{children}</div>
    </section>
  )
}

// Public on purpose: people should be able to read this before they sign in
export function PrivacyPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 px-4 py-10">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold">Privacy</h1>
        <p className="text-muted-foreground">
          Fixwright is a portfolio project with a public demo. This page explains what happens to the data you enter.
        </p>
      </div>

      <Part title="What is processed">
        <p>Incident IDs and descriptions, the analyses created for them, and the comments you add to decisions.</p>
        <p>
          One cookie, <code>fixwright_session</code>. It only records whether you use the demo or an API key, and it
          expires after 8 hours or when you sign out.
        </p>
        <p>IP addresses, which the hosting provider records in its access logs.</p>
      </Part>

      <Part title="Why">
        <p>To run the demo: store incidents, analyze them and show the results to the people using it.</p>
      </Part>

      <Part title="Where">
        <p>The app and its database run on Render and Neon in Frankfurt, Germany.</p>
        <p>
          To analyze an incident and find similar ones, its text is sent to Anthropic (Claude) and Voyage AI, both based
          in the United States. Anthropic does not train models on data sent through its API, and Fixwright has opted
          out of Voyage AI storing this data or using it for training.
        </p>
      </Part>

      <Part title="How long">
        <p>Incidents, analyses and comments created in the demo are deleted after 7 days.</p>
      </Part>

      <Part title="Cookies and tracking">
        <p>
          The session cookie is the only cookie and is needed to sign in, so there is no consent banner. There is no
          analytics, tracking or advertising.
        </p>
      </Part>

      <Part title="Contact">
        <p>
          Questions about this notice:{' '}
          <a href={ISSUES} rel="noreferrer" className="text-foreground underline underline-offset-4">
            GitHub issues
          </a>
          . Please do not post personal information there.
        </p>
      </Part>

      <Link to="/login" className="inline-block text-sm underline underline-offset-4">
        Back to sign in
      </Link>
    </main>
  )
}