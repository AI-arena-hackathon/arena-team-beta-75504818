import os
import tempfile
import pytest
import sqlite3
import time
from unittest.mock import patch, MagicMock


def create_test_db():
    test_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    os.environ['DATABASE_PATH'] = test_db.name
    os.environ['DB_POOL_SIZE'] = '2'
    os.environ['DB_TIMEOUT'] = '5.0'
    return test_db.name


def get_db():
    # Use direct connection for tests to avoid pool singleton issues
    conn = sqlite3.connect(os.environ['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    # Enable WAL mode and foreign keys like the pool does
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset the database pool singleton before each test"""
    from reliability import DatabasePool
    DatabasePool._instance = None
    DatabasePool._initialized = False
    yield
    DatabasePool._instance = None
    DatabasePool._initialized = False


@pytest.fixture
def client():
    db_path = create_test_db()
    os.environ['DATABASE_PATH'] = db_path
    os.environ['DB_POOL_SIZE'] = '2'
    os.environ['DB_TIMEOUT'] = '5.0'

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
    assert data['database'] == 'ok'


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


# Reliability tests

def test_retry_policy_retries_on_failure():
    from reliability import RetryPolicy
    
    call_count = [0]
    
    def failing_func():
        call_count[0] += 1
        if call_count[0] < 3:
            raise sqlite3.OperationalError("database is locked")
        return "success"
    
    policy = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)
    result = policy.execute(failing_func)
    assert result == "success"
    assert call_count[0] == 3


def test_retry_policy_exhausts_retries():
    from reliability import RetryPolicy
    
    call_count = [0]
    
    def always_fails():
        call_count[0] += 1
        raise sqlite3.OperationalError("database is locked")
    
    policy = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)
    with pytest.raises(sqlite3.OperationalError):
        policy.execute(always_fails)
    assert call_count[0] == 3


def test_circuit_breaker_opens_after_threshold():
    from reliability import CircuitBreaker, CircuitBreakerOpenError
    
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    
    def failing_func():
        raise ValueError("test error")
    
    # First 3 calls should fail and increment counter
    for _ in range(3):
        with pytest.raises(ValueError):
            breaker.call(failing_func)
    
    # 4th call should raise CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(failing_func)
    
    assert breaker.state == "open"


def test_circuit_breaker_recovers_after_timeout():
    from reliability import CircuitBreaker, CircuitBreakerOpenError
    
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
    
    def failing_func():
        raise ValueError("test error")
    
    def succeeding_func():
        return "success"
    
    # Trigger circuit breaker open
    for _ in range(2):
        with pytest.raises(ValueError):
            breaker.call(failing_func)
    
    assert breaker.state == "open"
    
    # Wait for recovery timeout
    time.sleep(0.1)
    
    # Next call should be half-open and succeed
    result = breaker.call(succeeding_func)
    assert result == "success"
    assert breaker.state == "closed"


def test_database_pool_singleton():
    from reliability import DatabasePool, get_db_pool
    
    pool1 = get_db_pool()
    pool2 = get_db_pool()
    assert pool1 is pool2
    assert isinstance(pool1, DatabasePool)


def test_database_pool_wal_mode():
    from reliability import get_db_pool
    
    pool = get_db_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.upper() == "WAL"


def test_database_pool_foreign_keys():
    from reliability import get_db_pool
    
    pool = get_db_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        fk = cursor.fetchone()[0]
        assert fk == 1


def test_database_pool_busy_timeout():
    from reliability import get_db_pool
    
    pool = get_db_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout")
        timeout = cursor.fetchone()[0]
        assert timeout == 30000


def test_health_check_reports_database_status(client):
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert 'database' in data
    assert data['database'] in ('ok', 'degraded')


def test_circuit_breaker_returns_503_when_open(client):
    from reliability import db_circuit_breaker
    from unittest.mock import patch
    
    # Force circuit breaker open
    db_circuit_breaker.failure_count = 10
    db_circuit_breaker.state = "open"
    db_circuit_breaker.last_failure_time = time.time()
    
    try:
        response = client.get('/clusters')
        # Should return 503 when circuit breaker is open
        assert response.status_code == 503
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'temporarily unavailable' in data['message'].lower()
    finally:
        # Reset circuit breaker
        db_circuit_breaker.reset()