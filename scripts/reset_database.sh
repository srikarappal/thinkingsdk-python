#!/bin/bash

# Reset ThinkingSDK Database
# This script drops and recreates all ThinkingSDK tables to reset state

echo "========================================="
echo "ThinkingSDK Database Reset Script"
echo "========================================="

# Check if docker container name is provided as argument, otherwise use default
CONTAINER_NAME=${1:-docuextract-postgres-1}
DB_USER=${2:-thinkingsdk}
DB_NAME=${3:-thinkingsdk}

echo "Container: $CONTAINER_NAME"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo ""

# Confirm before proceeding
read -p "⚠️  WARNING: This will DELETE all data! Continue? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1: Dropping all tables..."
echo "----------------------------------------"

docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME <<EOF
-- Drop tables in correct order (respecting foreign key constraints)
-- Junction and mapping tables first
DROP TABLE IF EXISTS event_exception_group_mapping CASCADE;
DROP TABLE IF EXISTS github_repositories CASCADE;

-- State and tracking tables
DROP TABLE IF EXISTS autofix_state CASCADE;
DROP TABLE IF EXISTS debug_steps CASCADE;
DROP TABLE IF EXISTS llmCoder_messages CASCADE;
DROP TABLE IF EXISTS fix_attempts CASCADE;
DROP TABLE IF EXISTS fix_suggestions CASCADE;
DROP TABLE IF EXISTS github_app_states CASCADE;
DROP TABLE IF EXISTS insights CASCADE;
DROP TABLE IF EXISTS metrics CASCADE;

-- Core data tables
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS exception_groups CASCADE;

-- Auth and session tables
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS web_sessions CASCADE;

-- Base tables
DROP TABLE IF EXISTS organizations CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Show remaining tables (should be empty)
SELECT 'Remaining tables:' as info;
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
EOF

if [ $? -ne 0 ]; then
    echo "❌ Failed to drop tables"
    exit 1
fi

echo ""
echo "✅ Tables dropped successfully"
echo ""
echo "Step 2: Recreating tables..."
echo "----------------------------------------"

# Run Python script to reinitialize database
python3 -c "
import os
import sys
sys.path.insert(0, '/Users/srikar/Downloads/code/thinkingSDK')

from thinking_sdk_server.database_ops import DatabaseOperations

# Get database URL from environment or use default
db_url = os.environ.get('DATABASE_URL', 'postgresql://thinkingsdk:thinkingsdk@localhost:5432/thinkingsdk')

print('Initializing database with URL:', db_url.replace(db_url.split('@')[0].split('//')[1], '***'))

try:
    db = DatabaseOperations(db_url)
    print('✅ Database initialized successfully')

    # Verify tables were created
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(\"\"\"
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    \"\"\")
    tables = cursor.fetchall()

    print('')
    print('Created tables:')
    for table in tables:
        print(f'  - {table[0]}')

    cursor.close()
    conn.close()

except Exception as e:
    print(f'❌ Failed to initialize database: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Failed to recreate tables"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Database reset complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Restart the ThinkingSDK server: uvicorn thinking_sdk_server.server:app --reload"
echo "2. Run test scripts to generate new exception data"
echo "3. Check dashboard at http://localhost:8000/dashboard"
