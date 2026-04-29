// Smoke test for Supabase Realtime using the same JS client the dashboard uses.
// Run: node scripts/test-realtime.mjs
import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'node:fs'
import { randomUUID } from 'node:crypto'

const env = Object.fromEntries(
  readFileSync('.env', 'utf8').split('\n')
    .filter(l => l.includes('=') && !l.trim().startsWith('#'))
    .map(l => l.split('=').map(s => s.trim()).slice(0, 2).concat(l.split('=').slice(1).join('=')).slice(0, 2))
)

const url = env.SUPABASE_URL || env.VITE_SUPABASE_URL
const anon = env.SUPABASE_ANON_KEY || env.VITE_SUPABASE_ANON_KEY
const service = env.SUPABASE_SERVICE_KEY

if (!url || !anon || !service) {
  console.error('Missing env: SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_KEY')
  process.exit(2)
}
console.log('URL:', url)

const sub = createClient(url, anon)
const writer = createClient(url, service)

const events = []
const ch = sub
  .channel('test-rt-invoices')
  .on('postgres_changes', { event: '*', schema: 'public', table: 'invoices' }, p => {
    events.push(p.eventType)
    console.log(`  RT EVENT: ${p.eventType}`)
  })
  .subscribe(state => console.log(`  subscribe state: ${state}`))

await new Promise(r => setTimeout(r, 2500))

const id = randomUUID()
console.log('Inserting test row…')
const ins = await writer.from('invoices').insert({ id, status: 'pending' })
if (ins.error) console.error('insert error:', ins.error.message)

const upd = await writer.from('invoices').update({ status: 'extracting' }).eq('id', id)
if (upd.error) console.error('update error:', upd.error.message)

await new Promise(r => setTimeout(r, 4000))

await writer.from('invoices').delete().eq('id', id)
await sub.removeChannel(ch)

console.log(`\nEVENTS RECEIVED: ${events.length} -> [${events.join(', ')}]`)
console.log(events.length > 0
  ? 'REALTIME OK — publication membership active for invoices'
  : 'REALTIME NOT BROADCASTING — run schema.sql publication block in Supabase SQL editor')
process.exit(0)
