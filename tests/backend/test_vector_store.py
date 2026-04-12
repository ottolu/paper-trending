import pytest
from backend.core.vector_store import VectorStore

@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_dir=str(tmp_path / "chroma"))

def test_store_initialization(store):
    assert store is not None

def test_get_or_create_collection(store):
    collection = store.get_or_create_collection("paper_embeddings_v1")
    assert collection is not None
    assert collection.name == "paper_embeddings_v1"

def test_add_embeddings(store):
    store.get_or_create_collection("test_collection")
    store.add(collection_name="test_collection", ids=["p1", "p2"], embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], metadatas=[{"paper_id": "p1"}, {"paper_id": "p2"}])
    result = store.get("test_collection", ids=["p1"])
    assert len(result["ids"]) == 1

def test_query_returns_nearest(store):
    store.get_or_create_collection("test_collection")
    store.add(collection_name="test_collection", ids=["p1", "p2", "p3"], embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]], metadatas=[{"paper_id": "p1"}, {"paper_id": "p2"}, {"paper_id": "p3"}])
    results = store.query(collection_name="test_collection", query_embeddings=[[1.0, 0.0, 0.0]], n_results=2)
    assert len(results["ids"][0]) == 2
    assert "p1" in results["ids"][0]

def test_upsert_overwrites_existing(store):
    store.get_or_create_collection("test_collection")
    store.add(collection_name="test_collection", ids=["p1"], embeddings=[[0.1, 0.2, 0.3]], metadatas=[{"paper_id": "p1", "version": "old"}])
    store.upsert(collection_name="test_collection", ids=["p1"], embeddings=[[0.4, 0.5, 0.6]], metadatas=[{"paper_id": "p1", "version": "new"}])
    result = store.get("test_collection", ids=["p1"])
    assert result["metadatas"][0]["version"] == "new"

def test_delete_embeddings(store):
    store.get_or_create_collection("test_collection")
    store.add(collection_name="test_collection", ids=["p1", "p2"], embeddings=[[0.1, 0.2], [0.3, 0.4]], metadatas=[{"paper_id": "p1"}, {"paper_id": "p2"}])
    store.delete("test_collection", ids=["p1"])
    result = store.get("test_collection", ids=["p1"])
    assert len(result["ids"]) == 0

def test_count(store):
    store.get_or_create_collection("test_collection")
    store.add(collection_name="test_collection", ids=["p1", "p2", "p3"], embeddings=[[0.1], [0.2], [0.3]], metadatas=[{"paper_id": "p1"}, {"paper_id": "p2"}, {"paper_id": "p3"}])
    assert store.count("test_collection") == 3

def test_list_collections(store):
    store.get_or_create_collection("collection_a")
    store.get_or_create_collection("collection_b")
    names = store.list_collections()
    assert "collection_a" in names
    assert "collection_b" in names
