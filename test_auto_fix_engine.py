#!/usr/bin/env python3
"""
Test the ThinkingSDK Autofix Engine with existing database data.
Tests all 5 phases of the autofix pipeline.
"""
import sys
import os
import logging
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thinking_sdk_server.database_ops import DatabaseOperations
from thinking_sdk_server.autofix_orchestrator import AutofixOrchestratorV2
from thinking_sdk_server.autofix_states import AutofixStates, AutofixWoRepoStates

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("autofix_test")

def create_test_user(db, org_id):
    """Create a test user for the organization."""
    import uuid
    
    user_id = str(uuid.uuid4())
    
    # Check if user already exists
    existing = db.query("""
        SELECT * FROM users WHERE email = %s
    """, ('testuser@example.com',))
    
    if existing:
        user = existing[0]
        logger.info(f"Found existing user: {user['email']} ({user['id']})")
        return user
    
    # Create new user
    db.execute("""
        INSERT INTO users (
            id, organization_id, email, username, full_name,
            oauth_provider, oauth_id, role, created_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, NOW()
        )
    """, (
        user_id, org_id, 'testuser@example.com', 'testuser', 'Test User',
        'google', f'google_oauth_{user_id}', 'admin'
    ))
    
    logger.info(f"Created test user: testuser@example.com ({user_id})")
    
    # Fetch and return the created user
    users = db.query("SELECT * FROM users WHERE id = %s", (user_id,))
    return users[0] if users else None

def create_test_organization(db):
    """Create a test organization with autofix enabled."""
    import uuid
    
    org_id = str(uuid.uuid4())
    org_name = 'TestingOrg'
    
    # Check if organization already exists
    existing = db.query("""
        SELECT * FROM organizations WHERE name = %s
    """, (org_name,))
    
    if existing:
        org = existing[0]
        logger.info(f"Found existing organization: {org['name']} ({org['id']})")
        # Enable autofix
        db.execute("""
            UPDATE organizations 
            SET auto_fix_enabled = true,
                github_oauth_status = 'not_connected',  -- No repo scenario
                auto_fix_analysis_mode = 'file_only'
            WHERE id = %s
        """, (org['id'],))
        return org
    
    # Create new organization
    db.execute("""
        INSERT INTO organizations (
            id, name, email, tier, 
            auto_fix_enabled, github_oauth_status, 
            auto_fix_analysis_mode, created_at
        ) VALUES (
            %s, %s, %s, %s, 
            %s, %s, 
            %s, NOW()
        )
    """, (
        org_id, org_name, 'test@example.com', 'pro',
        True, 'not_connected',  # Python comment - No repo scenario
        'file_only'
    ))
    
    logger.info(f"Created new organization: {org_name} ({org_id})")
    
    # Fetch and return the created org
    orgs = db.query("SELECT * FROM organizations WHERE id = %s", (org_id,))
    return orgs[0] if orgs else None

def create_sample_exceptions(db, org_id):
    """Create sample exception events for testing no-repo scenario."""
    import uuid
    from datetime import datetime
    
    # Sample exceptions with different types
    sample_exceptions = [
        {
            'type': 'ValueError',
            'message': "invalid literal for int() with base 10: 'abc'",
            'file': 'data_processor.py',
            'line': 42,
            'func': 'process_user_input',
            'code': "user_age = int(user_input)"
        },
        {
            'type': 'KeyError',
            'message': "'user_id' not found in dictionary",
            'file': 'user_manager.py', 
            'line': 87,
            'func': 'get_user_details',
            'code': "user_id = data['user_id']"
        },
        {
            'type': 'ZeroDivisionError',
            'message': "division by zero",
            'file': 'calculator.py',
            'line': 15,
            'func': 'calculate_average',
            'code': "average = total / count"
        },
        {
            'type': 'AttributeError',
            'message': "'NoneType' object has no attribute 'strip'",
            'file': 'string_utils.py',
            'line': 23,
            'func': 'clean_text',
            'code': "cleaned = text.strip().lower()"
        }
    ]
    
    logger.info(f"Creating {len(sample_exceptions)} sample exceptions...")
    
    for exc_data in sample_exceptions:
        event_id = str(uuid.uuid4())
        
        # Build structured traceback
        traceback = [{
            'file': exc_data['file'],
            'file_path': f"/app/{exc_data['file']}",  # Simulated path
            'line': exc_data['line'],
            'func': exc_data['func'],
            'code': exc_data['code'],
            'locals': {
                'sample_var': 'sample_value'
            }
        }]
        
        # Build event data
        event_data = {
            'exception': {
                'type': exc_data['type'],
                'message': exc_data['message'],
                'value': exc_data['message'],  # Some formats use 'value' instead
                'structured_traceback': traceback
            },
            # No repo info for no-repo scenario
            'repo_name': '',
            'repo_branch': '',
            'file': exc_data['file'],
            'file_path': f"/app/{exc_data['file']}"
        }
        
        # Insert into events table
        db.execute("""
            INSERT INTO events (
                id, organization_id, timestamp, event_type,
                data, created_at
            ) VALUES (
                %s, %s, NOW(), %s,
                %s, NOW()
            )
        """, (
            event_id, org_id, 'exception',
            json.dumps(event_data)
        ))
        
        logger.info(f"  Created: {exc_data['type']} in {exc_data['file']}:{exc_data['line']}")
    
    logger.info(f"Successfully created {len(sample_exceptions)} sample exceptions")
    return len(sample_exceptions)

def get_recent_exceptions(db, org_id, limit=1):
    """Get recent exception events from the database."""
    # Get recent exceptions for this org
    events = db.query("""
        SELECT * FROM events 
        WHERE organization_id = %s 
        AND event_type = 'exception'
        AND created_at > %s::timestamp
        ORDER BY created_at DESC
        LIMIT %s
    """, 
    (org_id, 
    datetime.now() - timedelta(days=7),  # Last 7 days
    limit)
    )

    logger.info(f"Found {len(events)} recent exception events")

    # Show exception details
    for event in events[:5]:  # Show first 5
        data = event['data']
        if isinstance(data, str):
            data = json.loads(data)
        exc_info = data.get('exception', {})
        logger.info(f"  - {exc_info.get('type', 'Unknown')}: {exc_info.get('message', 'No message')[:50]}...")
        logger.info(f"    File: {data.get('file_path', data.get('file', 'Unknown'))}")

    return events

def check_existing_autofix_state(db, org_id):
    """Check if there are any existing autofix states in progress."""
    # Check exception groups and their states
    groups = db.query("""
        SELECT eg.*, afs.state, afs.iteration_count, afs.updated_at
        FROM exception_groups eg
        LEFT JOIN autofix_state afs ON eg.id = afs.exception_group_id
        WHERE eg.organization_id = %s
        ORDER BY eg.created_at DESC
        LIMIT 1
    """, (org_id,))

    if groups:
        logger.info(f"\nFound {len(groups)} existing exception groups:")
        for group in groups:
            state = group['state'] or 'NO_STATE'
            logger.info(f"  - {group['exception_type']}: {group['exception_message'][:50]}...")
            logger.info(f"    State: {state}, Iterations: {group['iteration_count'] or 0}")
            logger.info(f"    Last updated: {group['updated_at'] or 'Never'}")
    else:
        logger.info("No existing exception groups found")

    return groups

def test_autofix():
    # Initialize database
    # Use environment variable or default to Docker PostgreSQL
    database_url = os.getenv('DATABASE_URL', 'postgresql://thinkingsdk:thinkingsdk123@localhost:5432/thinkingsdk')

    logger.info(f"Connecting to database: {database_url}")

    try:
        db = DatabaseOperations(database_url)
        db.init()
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        logger.error("Make sure Docker PostgreSQL is running")
        return

    # Create or get test organization
    org = create_test_organization(db)
    if not org:
        logger.error("Failed to create test organization!")
        db.close()
        return

    # Create test user for the organization
    user = create_test_user(db, org['id'])
    if user:
        logger.info(f"Test user ready: {user['email']} (role: {user['role']})")
    
    # Create sample exceptions for testing no-repo scenario
    num_created = create_sample_exceptions(db, org['id'])
    logger.info(f"\nCreated {num_created} sample exceptions for testing")
    
    # Check for recent exceptions
    exceptions = get_recent_exceptions(db, org['id'], limit=10)

    # Check existing autofix states
    existing_groups = check_existing_autofix_state(db, org['id'])

    # Create orchestrator
    orchestrator = AutofixOrchestratorV2(db)

    logger.info("\n=== STARTING AUTOFIX ORCHESTRATOR ===")
    logger.info(f"Organization: {org['name']} ({org['id']})")
    logger.info(f"Autofix enabled: {org['auto_fix_enabled']}")
    logger.info(f"Recent exceptions: {len(exceptions)}")
    logger.info(f"Existing exception groups: {len(existing_groups)}")

    # Run a single orchestration cycle
    logger.info("\n--- Running Orchestrator (Complete Flow Processing) ---")

    import pdb; pdb.set_trace()
    orchestrator.orchestrate_cycle()

    # Check final state of exception groups
    groups = db.query("""
        SELECT eg.*, afs.state, afs.iteration_count, afs.fix_attempts
        FROM exception_groups eg
        LEFT JOIN autofix_state afs ON eg.id = afs.exception_group_id
        WHERE eg.organization_id = %s
        ORDER BY eg.created_at DESC
        LIMIT 1
    """, (org['id'],))

    if groups:
        logger.info("\nException groups after orchestration:")
        for group in groups[:5]:  # Show top 5
            state = group['state'] or 'NO_STATE'
            logger.info(f"  Group {str(group['id'])[:8]}... - {group['exception_type']} - State: {state} - Iterations: {group['iteration_count'] or 0}")

    # Check stats
    stats = orchestrator.get_stats()
    logger.info(f"\nOrchestrator stats: {json.dumps(stats, indent=2)}")

    # Test incomplete groups handler separately
    logger.info("\n--- Testing Incomplete Groups Handler ---")

    # Simulate some stuck groups by manually updating their timestamps
    db.execute("""
        UPDATE autofix_state
        SET updated_at = NOW() - INTERVAL '35 minutes'
        WHERE state NOT IN (
            'PR_FIX_SUBMITTED', 'PR_MERGED', 'PR_REJECTED', 'COMPLETED',
            'ABANDONED', 'MAX_RETRIES_EXCEEDED', 'VALIDATION_FAILED',
            'completed_no_repo', 'fix_suggestion_ready', 'analysis_failed', 'fix_generation_failed'
        )
        AND exception_group_id IN (
            SELECT id FROM exception_groups WHERE organization_id = %s LIMIT 1
        )
    """, (org['id'],))

    # Run incomplete groups handler
    orchestrator.orchestrate_cycle(mode='incomplete')

    # Check if incomplete groups were processed
    logger.info("\nIncomplete groups handler completed")

    # Final summary
    logger.info("\n=== AUTOFIX TEST COMPLETE ===")

    # Get final state of all exception groups
    final_groups = db.query("""
        SELECT eg.*, afs.state, afs.fix_attempts, afs.iteration_count,
               afs.last_error, afs.pr_url
        FROM exception_groups eg
        LEFT JOIN autofix_state afs ON eg.id = afs.exception_group_id
        WHERE eg.organization_id = %s
        ORDER BY eg.created_at DESC
        LIMIT 1
    """, (org['id'],))

    success_count = 0
    failed_count = 0
    in_progress_count = 0

    logger.info(f"\nFinal state of {len(final_groups)} exception groups:")
    for group in final_groups:
        state = group['state'] or 'NO_STATE'
        logger.info(f"\nException Group: {group['id']}")
        logger.info(f"  Type: {group['exception_type']}")
        logger.info(f"  Message: {group['exception_message'][:100]}...")
        logger.info(f"  Final State: {state}")
        logger.info(f"  Fix Attempts: {group['fix_attempts'] or 0}")
        logger.info(f"  Iterations: {group['iteration_count'] or 0}")

        if group['pr_url']:
            logger.info(f"  PR URL: {group['pr_url']}")
        if group['last_error']:
            logger.info(f"  Last Error: {group['last_error'][:100]}...")

        # Count outcomes for both flows
        if state in [AutofixStates.PR_FIX_SUBMITTED.value, AutofixStates.PR_MERGED.value]:
            success_count += 1
        elif state == AutofixWoRepoStates.FIX_SUGGESTION_READY.value:
            success_count += 1  # No-repo flow success
        elif state in [AutofixStates.FIX_FAILED.value, AutofixStates.VALIDATION_FAILED.value, 
                      AutofixWoRepoStates.ANALYSIS_FAILED.value, AutofixWoRepoStates.FIX_GENERATION_FAILED.value]:
            failed_count += 1
        elif state not in ['NO_STATE', AutofixStates.COMPLETED.value, AutofixWoRepoStates.COMPLETED_NO_REPO.value]:
            in_progress_count += 1

    logger.info(f"\n=== SUMMARY ===")
    logger.info(f"Total exception groups: {len(final_groups)}")
    logger.info(f"Successfully fixed (PR submitted): {success_count}")
    logger.info(f"Failed to fix: {failed_count}")
    logger.info(f"Still in progress: {in_progress_count}")

    # Clean up
    db.close()
    logger.info("\nDatabase connection closed.")

def create_test_exception_groups(db, org_id):
    """Create test exception groups with and without repo information."""
    # Create exception group WITH repo info (repo_name should be a URL)
    db.execute("""
        INSERT INTO exception_groups (
            id, organization_id, exception_group_hash, 
            exception_type, exception_message, 
            repo_name, repo_branch, file_name,
            occurrences, first_seen, last_seen
        ) VALUES (
            gen_random_uuid(), %s, %s,
            'ValueError', 'Test exception with repo info',
            'https://github.com/user/test-repo', 'main', 'src/app.py',
            5, NOW() - INTERVAL '1 hour', NOW()
        ) ON CONFLICT (exception_group_hash) DO NOTHING
    """, (org_id, f"test_with_repo_{org_id}"))

    # Create exception group WITHOUT repo info
    db.execute("""
        INSERT INTO exception_groups (
            id, organization_id, exception_group_hash, 
            exception_type, exception_message, 
            repo_name, repo_branch, file_name,
            occurrences, first_seen, last_seen
        ) VALUES (
            gen_random_uuid(), %s, %s,
            'TypeError', 'Test exception without repo info',
            NULL, NULL, 'unknown_file.py',
            3, NOW() - INTERVAL '30 minutes', NOW()
        ) ON CONFLICT (exception_group_hash) DO NOTHING
    """, (org_id, f"test_without_repo_{org_id}"))

    logger.info("Created test exception groups with and without repo info")

def test_forked_flow():
    """Test the forked flow behavior - repo vs no-repo paths."""
    database_url = os.getenv('DATABASE_URL', 'postgresql://thinkingsdk:thinkingsdk123@localhost:5432/thinkingsdk')

    logger.info("\n=== TESTING FORKED FLOW BEHAVIOR ===")

    try:
        db = DatabaseOperations(database_url)
        db.init()
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return

    # Get the test organization
    org = get_or_create_autofix_org(db)
    if not org:
        logger.error("No organization found to test with!")
        db.close()
        return

    # Create test exception groups with and without repo info
    create_test_exception_groups(db, org['id'])

    # Check exception groups to see flow type distribution
    groups_with_repo = db.query("""
        SELECT eg.*, afs.state 
        FROM exception_groups eg
        LEFT JOIN autofix_state afs ON eg.id = afs.exception_group_id
        WHERE eg.organization_id = %s 
        AND eg.repo_name IS NOT NULL 
        AND eg.repo_branch IS NOT NULL
        LIMIT 1
    """, (org['id'],))

    groups_without_repo = db.query("""
        SELECT eg.*, afs.state 
        FROM exception_groups eg
        LEFT JOIN autofix_state afs ON eg.id = afs.exception_group_id
        WHERE eg.organization_id = %s 
        AND (eg.repo_name IS NULL OR eg.repo_branch IS NULL)
        LIMIT 1
    """, (org['id'],))

    logger.info(f"\nGroups WITH repo info: {len(groups_with_repo)}")
    for g in groups_with_repo:
        logger.info(f"  - {g['exception_type']} | repo: {g['repo_name']} | branch: {g['repo_branch']} | state: {g['state'] or 'NEW'}")

    logger.info(f"\nGroups WITHOUT repo info: {len(groups_without_repo)}")
    for g in groups_without_repo:
        logger.info(f"  - {g['exception_type']} | repo: {g['repo_name']} | branch: {g['repo_branch']} | state: {g['state'] or 'NEW'}")

    # Run orchestrator to see flow branching
    orchestrator = AutofixOrchestratorV2(db)

    logger.info("\n--- Running orchestrator to see flow branching ---")
    import pdb; pdb.set_trace()
    orchestrator.orchestrate_cycle()

    # Check how groups were routed
    repo_flow_groups = db.query("""
        SELECT eg.*, afs.state 
        FROM exception_groups eg
        JOIN autofix_state afs ON eg.id = afs.exception_group_id
        WHERE eg.organization_id = %s 
        AND afs.state IN (%s, %s, %s, %s, %s)
        LIMIT 1
    """, (org['id'], 
    AutofixStates.PR_CREATED.value,
    AutofixStates.CLONING_REPO.value, 
    AutofixStates.SETTING_UP_ENV.value,
    AutofixStates.READY_TO_FIX.value,
    AutofixStates.GENERATING_FIX.value))

    no_repo_flow_groups = db.query("""
        SELECT eg.*, afs.state 
        FROM exception_groups eg
        JOIN autofix_state afs ON eg.id = afs.exception_group_id
        WHERE eg.organization_id = %s 
        AND afs.state IN (%s, %s, %s, %s)
        LIMIT 1
    """, (org['id'],
    AutofixWoRepoStates.ANALYZING_EXCEPTION.value,
    AutofixWoRepoStates.GENERATING_SNIPPET_FIX.value,
    AutofixWoRepoStates.CREATING_SYNTHETIC_TEST.value,
    AutofixWoRepoStates.VALIDATING_FIX_LOGIC.value))

    logger.info(f"\n=== FLOW ROUTING RESULTS ===")
    logger.info(f"Groups in REPO flow: {len(repo_flow_groups)}")
    for g in repo_flow_groups:
        logger.info(f"  - {g['exception_type']} -> {g['state']}")

    logger.info(f"\nGroups in NO-REPO flow: {len(no_repo_flow_groups)}")
    for g in no_repo_flow_groups:
        logger.info(f"  - {g['exception_type']} -> {g['state']}")

    db.close()
    logger.info("\nForked flow test complete.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "forked":
        test_forked_flow()
    else:
        test_autofix()
