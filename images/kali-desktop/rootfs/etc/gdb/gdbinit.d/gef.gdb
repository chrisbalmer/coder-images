# Loads GEF (Kali's gef package) into every gdb session. For plain gdb, for example in a script
# where GEF's context display is noise, set GEF_DISABLE=1: GEF_DISABLE=1 gdb -batch -x run.gdb
python
import os
if os.environ.get("GEF_DISABLE", "") in ("", "0") and os.path.isfile("/usr/share/gdb/gef.py"):
    gdb.execute("source /usr/share/gdb/gef.py")
end
