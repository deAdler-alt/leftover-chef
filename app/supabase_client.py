import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

