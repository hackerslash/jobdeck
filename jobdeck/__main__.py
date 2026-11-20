import sys

from . import embed, pipeline, sync

cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
if cmd == "sync":
    sync.sync()
elif cmd == "build":
    pipeline.build()
elif cmd == "embed":
    embed.embed()
elif cmd == "update":  # what the background job does
    if sync.sync() or "--force" in sys.argv:
        pipeline.build()
    embed.embed()
elif cmd == "serve":
    import uvicorn
    uvicorn.run("jobdeck.api:app", host="127.0.0.1", port=int(sys.argv[2]) if len(sys.argv) > 2 else 8700)
else:
    sys.exit("usage: python -m jobdeck [sync|build|embed|update [--force]|serve [port]]")
