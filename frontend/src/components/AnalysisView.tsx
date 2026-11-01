import { Section } from '@/components/Section'
import { SimilarIncidents } from '@/components/SimilarIncidents'
import { StatusBadge } from '@/components/StatusBadge'
import type { AnalysisRecord } from '@/lib/api'
import { timeAgo } from '@/lib/labels'

// Model and user text is plain text: pre-wrap keeps its line breaks, break-words keeps long words inside the page
const TEXT = 'whitespace-pre-wrap break-words'

// A pending analysis in full, so the reviewer has everything needed to decide
export function AnalysisView({ record }: { record: AnalysisRecord }) {
  const { probable_cause, suggested_steps, evidence } = record.analysis

  return (
    <div className="space-y-5">
      <Section title="Probable cause">
        <p className={TEXT}>{probable_cause}</p>
      </Section>
      {suggested_steps.length > 0 && (
        <Section title="Suggested steps">
          <ol className="list-decimal space-y-1 pl-5">
            {suggested_steps.map((step, index) => (
              <li key={index} className={TEXT}>
                {step}
              </li>
            ))}
          </ol>
        </Section>
      )}
      <SimilarIncidents items={record.similar_incidents} />
      {evidence.length > 0 && (
        <Section title="Evidence">
          <ul className="list-disc space-y-1 pl-5">
            {evidence.map((sentence, index) => (
              <li key={index} className={`${TEXT} text-sm text-muted-foreground`}>
                {sentence}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}

// A decided analysis in short: the outcome, the cause, who decided and when, and their comment
export function DecidedResult({ record }: { record: AnalysisRecord }) {
  return (
    <div className="space-y-3">
      <StatusBadge status={record.status} />
      <p className={TEXT}>{record.analysis.probable_cause}</p>
      <p className="text-sm text-muted-foreground">
        Decided by {record.decided_by ?? 'unknown'}
        {record.reviewed_at ? ` ${timeAgo(record.reviewed_at)}` : ''}
      </p>
      {record.reviewer_comment && <p className={`${TEXT} text-sm`}>{record.reviewer_comment}</p>}
    </div>
  )
}