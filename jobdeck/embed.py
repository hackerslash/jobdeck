"""Embed jobs whose content_hash has no vector yet. Vectors live in `emb` and survive rebuilds."""
import sys
import time

import pyarrow as pa

from . import config, db

DIM = 384
SEQ = 256  # title/role/skills lead the text; 256 vs 384 tokens: cosine 0.993, 1.8x faster
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge: prefix queries, not documents

_model = None


def model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer
        mps = torch.backends.mps.is_available()
        _model = SentenceTransformer(config.load()["embedding_model"], device="mps" if mps else "cpu")
        _model.max_seq_length = SEQ
        if mps:
            _model = _model.half()
    return _model


def encode(texts: list[str]):
    return model().encode(texts, batch_size=128, normalize_embeddings=True, convert_to_numpy=True).astype("float32")


def embed(log=lambda m: print(m, file=sys.stderr)) -> int:
    c = db.cur()
    name = config.load()["embedding_model"]
    c.execute(f"CREATE TABLE IF NOT EXISTS emb (hash VARCHAR PRIMARY KEY, v FLOAT[{DIM}])")
    c.execute("CREATE TABLE IF NOT EXISTS meta (k VARCHAR PRIMARY KEY, v VARCHAR)")
    if (c.execute("SELECT v FROM meta WHERE k = 'embedding_model'").fetchone() or [name])[0] != name:
        log("embedding model changed: dropping cached vectors")
        c.execute("DELETE FROM emb")
    c.execute("INSERT OR REPLACE INTO meta VALUES ('embedding_model', ?)", [name])
    c.execute("DELETE FROM emb WHERE hash NOT IN (SELECT content_hash FROM jobs)")
    todo = c.execute("""SELECT content_hash, any_value(embed_text) FROM jobs
                        WHERE content_hash NOT IN (SELECT hash FROM emb) GROUP BY 1""").fetchall()
    if not todo:
        log("embeddings up to date")
        return 0
    log(f"embedding {len(todo):,} jobs")
    t0, done, step = time.time(), 0, 4096
    for i in range(0, len(todo), step):
        chunk = todo[i:i + step]
        vecs = encode([t for _, t in chunk])
        tbl = pa.table({"hash": [h for h, _ in chunk],
                        "v": pa.FixedSizeListArray.from_arrays(pa.array(vecs.ravel(), pa.float32()), DIM)})
        c.register("batch", tbl)
        c.execute("INSERT OR REPLACE INTO emb SELECT hash, v::FLOAT[384] FROM batch")
        c.unregister("batch")
        done += len(chunk)
        log(f"  {done:,}/{len(todo):,} ({done / (time.time() - t0):.0f}/s)")
    return done


if __name__ == "__main__":
    embed()
