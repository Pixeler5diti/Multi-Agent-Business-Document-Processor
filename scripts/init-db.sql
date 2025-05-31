-- Initialize the database for the document processor
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the processing_results table if it doesn't exist
CREATE TABLE IF NOT EXISTS processing_results (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    business_intent VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    extracted_data JSONB,
    processing_metadata JSONB,
    actions_taken JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_processing_results_status ON processing_results(status);
CREATE INDEX IF NOT EXISTS idx_processing_results_file_type ON processing_results(file_type);
CREATE INDEX IF NOT EXISTS idx_processing_results_business_intent ON processing_results(business_intent);
CREATE INDEX IF NOT EXISTS idx_processing_results_created_at ON processing_results(created_at);

-- Create trigger to update the updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_processing_results_updated_at
    BEFORE UPDATE ON processing_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();