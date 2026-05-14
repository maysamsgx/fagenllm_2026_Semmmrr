import { createClient } from '@supabase/supabase-js'

const supabaseUrl = (import.meta as any).env.VITE_SUPABASE_URL
const supabaseAnonKey = (import.meta as any).env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Missing Supabase environment variables for Realtime.')
}

// Architectural Decision: We explicitly disable auth session management here.
// Our system strictly relies on DB + Realtime capabilities, bypassing Supabase Auth.
// This defensive measure prevents the GoTrue client from crashing during initialization
// when attempting to access properties like `user.photoURL` on a null session object.
export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '', {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
    detectSessionInUrl: false,
  },
})
