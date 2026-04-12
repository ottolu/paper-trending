from __future__ import annotations
from typing import Any
import chromadb

class VectorStore:
    def __init__(self, persist_dir: str):
        self._client = chromadb.PersistentClient(path=persist_dir)

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(name=name)

    def add(self, collection_name: str, ids: list[str], embeddings: list[list[float]], metadatas: list[dict[str, Any]] | None = None) -> None:
        collection = self._client.get_collection(collection_name)
        collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def upsert(self, collection_name: str, ids: list[str], embeddings: list[list[float]], metadatas: list[dict[str, Any]] | None = None) -> None:
        collection = self._client.get_collection(collection_name)
        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)

    def get(self, collection_name: str, ids: list[str] | None = None, where: dict | None = None) -> dict:
        collection = self._client.get_collection(collection_name)
        kwargs = {}
        if ids: kwargs["ids"] = ids
        if where: kwargs["where"] = where
        return collection.get(**kwargs)

    def query(self, collection_name: str, query_embeddings: list[list[float]], n_results: int = 10, where: dict | None = None) -> dict:
        collection = self._client.get_collection(collection_name)
        kwargs: dict[str, Any] = {"query_embeddings": query_embeddings, "n_results": n_results}
        if where: kwargs["where"] = where
        return collection.query(**kwargs)

    def delete(self, collection_name: str, ids: list[str]) -> None:
        collection = self._client.get_collection(collection_name)
        collection.delete(ids=ids)

    def count(self, collection_name: str) -> int:
        collection = self._client.get_collection(collection_name)
        return collection.count()

    def list_collections(self) -> list[str]:
        collections = self._client.list_collections()
        return [c.name for c in collections]
