#!/bin/bash

# Clear ThinkingSDK Data (DELETE rows, keep schema)
# This script deletes all rows from tables while preserving the schema

echo "========================================="
echo "ThinkingSDK Data Clear Script"
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
echo "Step 1: Deleting all rows from tables..."
echo "----------------------------------------"

docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME <<EOF
-- Delete rows in correct order (child tables first to respect foreign keys)
DELETE FROM event_exception_group_mapping;
DELETE FROM llmcoder_messages;
DELETE FROM debug_steps;
DELETE FROM fix_attempts;
DELETE FROM autofix_state;
DELETE FROM exception_groups;
DELETE FROM events;

-- Show row counts to verify deletion
SELECT 'Row counts after deletion:' as info;
SELECT 'events' as table_name, COUNT(*) as row_count FROM events
UNION ALL
SELECT 'exception_groups', COUNT(*) FROM exception_groups
UNION ALL
SELECT 'event_exception_group_mapping', COUNT(*) FROM event_exception_group_mapping
UNION ALL
SELECT 'autofix_state', COUNT(*) FROM autofix_state
UNION ALL
SELECT 'fix_attempts', COUNT(*) FROM fix_attempts
UNION ALL
SELECT 'llmcoder_messages', COUNT(*) FROM llmcoder_messages
ORDER BY table_name;
EOF

if [ $? -ne 0 ]; then
    echo "❌ Failed to delete data"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Data cleared successfully!"
echo "========================================="
echo ""
echo "Tables preserved with schema intact."
echo "All rows deleted from:"
echo "  - events"
echo "  - exception_groups"
echo "  - event_exception_group_mapping"
echo "  - autofix_state"
echo "  - fix_attempts"
echo "  - llmcoder_messages"
echo "  - debug_steps"
echo ""
echo "Next steps:"
echo "1. Run test scripts to generate new exception data"
echo "2. Run orchestrator: python -m thinking_sdk_server.autofix_orchestrator"
echo "3. Check dashboard at http://localhost:8000/dashboard"
