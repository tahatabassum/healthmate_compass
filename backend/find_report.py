from app.core.supabase import get_supabase_admin

sb = get_supabase_admin()
res = sb.table("report_values").select("*").limit(1).execute()
if res.data:
    print("report_values columns:", list(res.data[0].keys()))
else:
    print("report_values empty, cannot get keys from data")

rep = sb.table("reports").select("*").limit(1).execute()
if rep.data:
    print("reports columns:", list(rep.data[0].keys()))
