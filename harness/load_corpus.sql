CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS items (id bigserial PRIMARY KEY, embedding vector(768));
TRUNCATE items;
INSERT INTO items (embedding)
SELECT ARRAY(SELECT random()*2-1 FROM generate_series(1,768))::vector
FROM generate_series(1,100000);
CREATE INDEX IF NOT EXISTS items_embedding_hnsw ON items USING hnsw (embedding vector_cosine_ops);
