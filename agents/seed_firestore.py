"""Seed Firestore with initial pipeline data for dashboard monitoring."""
import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

cred = credentials.Certificate('firebase/serviceAccountKey.json')
project_id = os.getenv('FIREBASE_PROJECT_ID', 'timi-children-stories')
firebase_admin.initialize_app(cred, {
    'projectId': project_id,
})
db = firestore.client()

AGENT_ROLES = [
    ('scriptwriter', 'Scriptwriter', '#FF6B6B', 'idle', 'Waiting for next task'),
    ('storyboard', 'Storyboard Artist', '#4ECDC4', 'idle', 'Waiting for next task'),
    ('voice', 'Voice Actor', '#FFD93D', 'idle', 'Waiting for next task'),
    ('composer', 'Composer', '#A29BFE', 'idle', 'Waiting for next task'),
    ('animator', 'Animator', '#00D2FF', 'idle', 'Waiting for next task'),
    ('editor', 'Video Editor', '#F39C12', 'idle', 'Waiting for next task'),
    ('thumbnail', 'Thumbnail Creator', '#E056FD', 'idle', 'Waiting for next task'),
    ('metadata', 'Metadata Writer', '#22A6B3', 'idle', 'Waiting for next task'),
    ('publisher', 'Publisher', '#7ED6DF', 'idle', 'Waiting for next task'),
    ('quality_scorer', 'Quality Scorer', '#10B981', 'idle', 'Waiting for next task'),
    ('trend_discovery', 'Trend Scout', '#F97316', 'idle', 'Scanning for trending topics'),
    ('repurposer', 'Content Repurposer', '#06B6D4', 'idle', 'Waiting for videos to repurpose'),
    ('scheduler', 'Scheduler AI', '#06D6A0', 'idle', 'Planning daily content schedule'),
]

print('Seeding agent_status...')
for agent_id, name, color, status, action in AGENT_ROLES:
    db.collection('agent_status').document(agent_id).set({
        'agent_id': agent_id,
        'status': status,
        'current_action': action,
        'enabled': True,
        'last_updated': datetime.now(timezone.utc),
        'error_message': '',
    })
    print(f'  {name}: {status}')

print('Seeding system/pipeline...')
db.collection('system').document('pipeline').set({
    'running': False,
    'current_video': '',
    'paused_by_user': False,
    'last_updated': datetime.now(timezone.utc),
})

print('Seeding settings/general...')
db.collection('settings').document('general').set({
    'shortsPerDay': 2,
    'longPerDay': 1,
    'category': 'Self-Learning',
    'enableMultiLang': True,
    'enableSubtitles': True,
    'enableReviewGate': True,
    'autoApproveThreshold': 80,
    'last_updated': datetime.now(timezone.utc),
}, merge=True)

print('Seeding activity_logs (welcome)...')
db.collection('activity_logs').add({
    'agent_id': 'system',
    'message': 'Dashboard initialized. Agents ready for pipeline execution.',
    'level': 'info',
    'timestamp': datetime.now(timezone.utc),
})

print('\nFirestore seeded successfully! Dashboard should now show real-time pipeline monitoring.')
