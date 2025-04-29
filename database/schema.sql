-- Initialize the database.
-- Drop any existing tables to start fresh.
DROP TABLE IF EXISTS plans;
DROP TABLE IF EXISTS subject_marks;

-- Create the plans table
CREATE TABLE plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    subjects TEXT NOT NULL, -- Comma-separated list
    learning_goal TEXT,
    difficulty_feedback TEXT, -- User's text feedback
    hours_per_day REAL NOT NULL,
    off_days TEXT, -- Comma-separated list of days (e.g., "Saturday,Sunday")
    class_schedule TEXT, -- User's description of class hours
    generated_guide TEXT, -- The AI-generated learning guide
    generated_schedule TEXT, -- The AI-generated schedule (e.g., JSON or structured text)
    resources TEXT, -- AI-generated links/resources
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create a table to store detailed subject marks
CREATE TABLE subject_marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    subject_name TEXT NOT NULL,
    component_type TEXT NOT NULL, -- e.g., "Theory", "Practical"
    assessment_name TEXT NOT NULL, -- e.g., "FT-I", "FT-II"
    max_marks REAL NOT NULL,
    obtained_marks REAL NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(id)
); 