import { useEffect } from 'react'
import { supabase } from './supabase'

export function useRealtime(table: string, callback: () => void) {
  useEffect(() => {
    // Listen for any INSERT, UPDATE, or DELETE on the specified table
    const channel = supabase
      .channel(`db-changes-${table}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table },
        () => {
          console.log(`Realtime update received for ${table}`)
          callback()
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [table, callback])
}
