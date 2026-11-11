"""BM25 sparse vectors need Qdrant's IDF modifier; collections created without it scored every term alike."""
from qdrant_client import QdrantClient, models as qm

from research_copilot.storage.qdrant_client import create_or_upgrade_collection, ensure_sparse_idf

VOCAB = {"the": 1, "cat": 2, "zebra": 3, "dog": 4, "bird": 5}
DOCS = {1: "the the the the cat", 2: "the zebra", 3: "the dog", 4: "the bird"}


def _tf(text):
    counts = {}
    for word in text.split():
        counts[VOCAB[word]] = counts.get(VOCAB[word], 0) + 1.0
    ids = sorted(counts)
    return qm.SparseVector(indices=ids, values=[counts[i] for i in ids])


def _modifier(client, name):
    return client.get_collection(name).config.params.sparse_vectors["sparse"].modifier


def test_new_collections_get_idf():
    client = QdrantClient(location=":memory:")
    assert create_or_upgrade_collection(client, "c", dense_size=4, sparse_vector_name="sparse") is True
    assert _modifier(client, "c") == qm.Modifier.IDF


def test_existing_collection_is_upgraded_in_place_once():
    client = QdrantClient(location=":memory:")
    client.create_collection("old", vectors_config=qm.VectorParams(size=4, distance=qm.Distance.COSINE),
                             sparse_vectors_config={"sparse": qm.SparseVectorParams()})
    assert _modifier(client, "old") is None
    assert create_or_upgrade_collection(client, "old", dense_size=4, sparse_vector_name="sparse") is False
    assert _modifier(client, "old") == qm.Modifier.IDF
    assert ensure_sparse_idf(client, "old", "sparse") is False  # already done


def _top_hit(client, name):
    for pid, text in DOCS.items():
        client.upsert(name, [qm.PointStruct(id=pid, vector={"sparse": _tf(text)})])
    hits = client.query_points(name, query=_tf("the zebra"), using="sparse", limit=1).points
    return DOCS[hits[0].id]


def test_idf_lets_the_rare_term_win():
    client = QdrantClient(location=":memory:")
    client.create_collection("tf_only", vectors_config={},
                             sparse_vectors_config={"sparse": qm.SparseVectorParams()})
    client.create_collection("bm25", vectors_config={},
                             sparse_vectors_config={"sparse": qm.SparseVectorParams(modifier=qm.Modifier.IDF)})
    assert _top_hit(client, "tf_only") == "the the the the cat"  # frequent stop-word dominates
    assert _top_hit(client, "bm25") == "the zebra"  # rare, informative term wins
