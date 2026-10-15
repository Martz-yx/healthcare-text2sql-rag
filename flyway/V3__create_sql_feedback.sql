CREATE TABLE IF NOT EXISTS sql_feedback (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    sql_query TEXT NOT NULL,
    feedback TEXT NOT NULL CHECK (feedback IN ('positive', 'negative')),
    username TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sql_feedback_created_at ON sql_feedback (created_at DESC);
CREATE INDEX idx_sql_feedback_feedback ON sql_feedback (feedback);
