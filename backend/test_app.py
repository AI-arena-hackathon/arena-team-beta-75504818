import os
import tempfile
import pytest
import sqlite3

# Use a file-based database for testing to persist across connections
test_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
os.environ['DATABASE_PATH'] = test_db.name

from app import app, init_db, get_db


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

def teardown_module(module):
    try:
        os.unlink(test_db.name)
    except:
        pass


def test_health_endpoint(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'timestamp' in data


def test_clusters_endpoint_empty(client):
    response = client.get('/clusters')
    assert response.status_code == 200
    data = response.get_json()
    assert data == []


def test_generate_clusters_not_enough_data(client):
    response = client.post('/clusters/generate')
    assert response.status_code == 400


def test_create_action_missing_fields(client):
    response = client.post('/action', json={})
    assert response.status_code == 400


def test_create_action_success(client):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions) VALUES (?, ?, ?, ?)',
                   (75, 0, 1, 'none'))
    conn.commit()
    senior_id = cursor.lastrowid
    conn.close()

    response = client.post('/action', json={
        'senior_id': senior_id,
        'action_type': 'exercise',
        'description': 'Join exercise class'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'action_id' in data


def test_get_actions(client):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions) VALUES (?, ?, ?, ?)',
                   (75, 0, 1, 'none'))
    conn.commit()
    senior_id = cursor.lastrowid
    cursor.execute('INSERT INTO actions (senior_id, action_type, description) VALUES (?, ?, ?)',
                   (senior_id, 'exercise', 'Join exercise class'))
    conn.commit()
    conn.close()

    response = client.get(f'/actions/{senior_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['action_type'] == 'exercise'


def test_complete_action(client):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions) VALUES (?, ?, ?, ?)',
                   (75, 0, 1, 'none'))
    conn.commit()
    senior_id = cursor.lastrowid
    cursor.execute('INSERT INTO actions (senior_id, action_type, description) VALUES (?, ?, ?)',
                   (senior_id, 'exercise', 'Join exercise class'))
    conn.commit()
    action_id = cursor.lastrowid
    conn.close()

    response = client.post(f'/action/{action_id}/complete')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM actions WHERE id = ?', (action_id,))
    row = cursor.fetchone()
    conn.close()
    assert row['status'] == 'completed'


def test_refresh_data(client):
    response = client.post('/data/refresh')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'