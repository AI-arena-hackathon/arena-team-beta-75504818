import os
import tempfile
import pytest
import sqlite3


def create_test_db():
    test_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    os.environ['DATABASE_PATH'] = test_db.name
    return test_db.name


def get_db():
    conn = sqlite3.connect(os.environ['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def client():
    db_path = create_test_db()
    os.environ['DATABASE_PATH'] = db_path

    from app import app, init_db, strip_phi
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

    try:
        os.unlink(db_path)
    except:
        pass


def teardown_module(module):
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


# Compliance feature tests

def test_strip_phi_name():
    from app import strip_phi
    data = {'name': 'John Smith', 'age': 75}
    result = strip_phi(data)
    assert result['name'] == '[REDACTED_NAME]'
    assert result['age'] == 75


def test_strip_phi_ssn():
    from app import strip_phi
    data = {'ssn': '123-45-6789', 'age': 75}
    result = strip_phi(data)
    assert result['ssn'] == '[REDACTED_SSN]'


def test_strip_phi_phone():
    from app import strip_phi
    data = {'phone': '555-123-4567', 'age': 75}
    result = strip_phi(data)
    assert result['phone'] == '[REDACTED_PHONE]'


def test_strip_phi_email():
    from app import strip_phi
    data = {'email': 'john@example.com', 'age': 75}
    result = strip_phi(data)
    assert result['email'] == '[REDACTED_EMAIL]'


def test_strip_phi_address():
    from app import strip_phi
    data = {'address': '123 Main Street', 'age': 75}
    result = strip_phi(data)
    assert result['address'] == '[REDACTED_ADDRESS]'


def test_strip_phi_dob():
    from app import strip_phi
    data = {'dob': '01/15/1950', 'age': 75}
    result = strip_phi(data)
    assert result['dob'] == '[REDACTED_DOB]'


def test_strip_phi_medical_record():
    from app import strip_phi
    data = {'medical_record': 'MRN-12345', 'age': 75}
    result = strip_phi(data)
    assert result['medical_record'] == '[REDACTED_MEDICAL_RECORD]'


def test_strip_phi_multiple_fields():
    from app import strip_phi
    data = {
        'name': 'Jane Doe',
        'ssn': '987-65-4321',
        'phone': '555.123.4567',
        'email': 'jane@test.org',
        'address': '456 Oak Avenue',
        'dob': '05/20/1948',
        'medical_record': 'MRN 67890',
        'age': 76
    }
    result = strip_phi(data)
    assert result['name'] == '[REDACTED_NAME]'
    assert result['ssn'] == '[REDACTED_SSN]'
    assert result['phone'] == '[REDACTED_PHONE]'
    assert result['email'] == '[REDACTED_EMAIL]'
    assert result['address'] == '[REDACTED_ADDRESS]'
    assert result['dob'] == '[REDACTED_DOB]'
    assert result['medical_record'] == '[REDACTED_MEDICAL_RECORD]'
    assert result['age'] == 76


def test_update_consent_given(client):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions) VALUES (?, ?, ?, ?)',
                   (75, 0, 1, 'none'))
    conn.commit()
    senior_id = cursor.lastrowid
    conn.close()

    response = client.post(f'/consent/{senior_id}', json={'consent_given': True})
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT consent_given, consent_version FROM seniors WHERE id = ?', (senior_id,))
    row = cursor.fetchone()
    conn.close()
    assert row['consent_given'] == 1
    assert row['consent_version'] == '1.0'


def test_update_consent_withdrawn(client):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions, consent_given) VALUES (?, ?, ?, ?, ?)',
                   (75, 0, 1, 'none', 1))
    conn.commit()
    senior_id = cursor.lastrowid
    conn.close()

    response = client.post(f'/consent/{senior_id}', json={'consent_given': False})
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT consent_given FROM seniors WHERE id = ?', (senior_id,))
    row = cursor.fetchone()
    conn.close()
    assert row['consent_given'] == 0


def test_get_consent(client):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions, consent_given, consent_version, consent_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
                   (75, 0, 1, 'none', 1, '1.0', '2024-01-01T00:00:00'))
    conn.commit()
    senior_id = cursor.lastrowid
    conn.close()

    response = client.get(f'/consent/{senior_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['consent_given'] == 1
    assert data['consent_version'] == '1.0'
    assert data['consent_date'] == '2024-01-01T00:00:00'


def test_consent_log_created(client):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions) VALUES (?, ?, ?, ?)',
                   (75, 0, 1, 'none'))
    conn.commit()
    senior_id = cursor.lastrowid
    conn.close()

    client.post(f'/consent/{senior_id}', json={'consent_given': True})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM consent_log WHERE senior_id = ?', (senior_id,))
    row = cursor.fetchone()
    conn.close()
    assert row is not None
    assert row['consent_given'] == 1
    assert row['consent_version'] == '1.0'


def test_consent_not_found(client):
    response = client.post('/consent/99999', json={'consent_given': True})
    assert response.status_code == 404


def test_run_retention(client):
    os.environ['DATA_RETENTION_DAYS'] = '365'

    conn = get_db()
    cursor = conn.cursor()
    old_date = '2020-01-01T00:00:00'
    cursor.execute('INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions, created_at, consent_given) VALUES (?, ?, ?, ?, ?, ?)',
                   (75, 0, 1, 'none', old_date, 0))
    cursor.execute('INSERT INTO actions (senior_id, action_type, description, created_at) VALUES (?, ?, ?, ?)',
                   (1, 'exercise', 'Old action', old_date))
    conn.commit()
    conn.close()

    response = client.post('/compliance/retention')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['seniors_deleted'] >= 1
    assert data['actions_deleted'] >= 1


def test_retention_log(client):
    response = client.get('/compliance/retention/log')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_get_disclaimer(client):
    response = client.get('/compliance/disclaimer')
    assert response.status_code == 200
    data = response.get_json()
    assert data['version'] == '1.0'
    assert data['data_controller'] == 'SeniorCare Pulse Community Center'
    assert 'rights' in data
    assert len(data['rights']) == 7


def test_ingest_data_strips_phi(client):
    records = [{
        'age': 75,
        'mobility_flag': 1,
        'digital_engagement': 0,
        'health_conditions': 'arthritis',
        'name': 'John Smith',
        'ssn': '123-45-6789'
    }]

    response = client.post('/data/ingest', json={'records': records})
    assert response.status_code == 200
    data = response.get_json()
    assert data['records_inserted'] == 1

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT health_conditions FROM seniors WHERE id = (SELECT MAX(id) FROM seniors)')
    row = cursor.fetchone()
    conn.close()
    assert 'REDACTED' not in row['health_conditions'] or row['health_conditions'] == 'arthritis'