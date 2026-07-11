import { createClient } from '@supabase/supabase-js'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

// New Supabase projects issue a publishable key (sb_publishable_...); older ones
// an anon key. Either works as the browser client key.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseKey =
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseKey) {
  throw new Error(
    'Missing Supabase config: set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY in frontend/.env, then restart the dev server.',
  )
}

export const supabase = createClient(supabaseUrl, supabaseKey)

/** fetch against the API with the current Supabase access token attached. */
export async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(`${API_BASE}${path}`, { ...init, headers })
}
