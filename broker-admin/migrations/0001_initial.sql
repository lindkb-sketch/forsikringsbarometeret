-- Private operational data ONLY. Never published to GitHub Pages.
CREATE TABLE IF NOT EXISTS folders (
  company TEXT NOT NULL,
  quarter TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (company, quarter)
);
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  company TEXT NOT NULL,
  quarter TEXT NOT NULL,
  house TEXT NOT NULL,
  original_name TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  r2_key TEXT NOT NULL,
  size_bytes INTEGER NOT NULL CHECK (size_bytes BETWEEN 20 AND 10485760),
  status TEXT NOT NULL CHECK (status IN ('queued','processing','analyzed','error','deleted')),
  analysis_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (company,quarter) REFERENCES folders(company,quarter)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_broker_report_hash
  ON reports(company,quarter,sha256);
CREATE INDEX IF NOT EXISTS idx_broker_folder ON reports(company,quarter,created_at);
CREATE TABLE IF NOT EXISTS drafts (
  company TEXT NOT NULL,
  quarter TEXT NOT NULL,
  reaction TEXT NOT NULL,
  drivers TEXT NOT NULL,
  outlook TEXT NOT NULL,
  report_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK (status IN ('draft','reviewed','published','needs_review')),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (company,quarter),
  FOREIGN KEY (company,quarter) REFERENCES folders(company,quarter)
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  company TEXT,
  quarter TEXT,
  report_id TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);
