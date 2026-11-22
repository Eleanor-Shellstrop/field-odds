import type { Rarity, RarityStatus } from '@/api/client'

export const STATUS: Record<RarityStatus, { label: string; meaning: string }> = {
  being_seen: { label: 'Being seen', meaning: 'Several outings have reported it, and recently.' },
  single_report: { label: 'Single report', meaning: 'One outing has reported it so far.' },
  no_news: {
    label: 'No news',
    meaning: "Not enough birding has been submitted since the last report to say it's gone.",
  },
  no_new_reports: {
    label: 'No new reports',
    meaning: "It's gone quiet despite some birding. That doesn't prove anyone looked for it.",
  },
  probably_gone: {
    label: 'Probably gone',
    meaning: 'Reports stopped while enough birding went on that we would expect some.',
  },
}

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

// eBird times are already local, so they're formatted without any timezone conversion
export function when(local: string) {
  const at = new Date(local)
  const day = at.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  if (local.slice(11, 16) === '00:00') return day // checklist had no time
  return `${day}, ${at.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`
}

export function evidence(r: Rarity) {
  const parts = [`Last reported ${when(r.last_reported)}`]
  if (r.outings_today) parts.push(`${plural(r.outings_today, 'outing')} today`)
  else if (r.outings_yesterday) parts.push(`${plural(r.outings_yesterday, 'outing')} yesterday`)
  // With a single day of reports, the total would only repeat what's already there
  if (r.days_reported > 1 || parts.length === 1) {
    parts.push(`${plural(r.outings, 'outing')} over ${plural(r.days_reported, 'day')}`)
  }
  return parts.join(' · ')
}
