import os
import sqlite3
import re
import logging
from functools import lru_cache
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import random

from reliability import (
    get_db_pool,
    with_retry,
    with_circuit_breaker,
    default_retry_policy,
    db_circuit_breaker,
    CircuitBreakerOpenError,
)

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get('DATA_DIR', '/data/csv')

DATA_RETENTION_DAYS = int(os.environ.get('DATA_RETENTION_DAYS', '365'))
CONSENT_VERSION = os.environ.get('CONSENT_VERSION', '1.0')

# Pre-compiled regex patterns for PHI stripping (performance optimization)
PHI_PATTERNS = [
    ('ssn', re.compile(r'\b\d{3}-\d{2}-\d{4}\b')),
    ('phone', re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')),
    ('email', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')),
    ('address', re.compile(r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b', re.IGNORECASE)),
    ('dob', re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b')),
    ('medical_record', re.compile(r'\bMRN[-\s]?\d+\b', re.IGNORECASE)),
    ('name', re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b')),
]


def get_db():
    pool = get_db_pool()
    return pool.get_connection()


def init_db():
    pool = get_db_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seniors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                age INTEGER NOT NULL,
                mobility_flag INTEGER NOT NULL,
                digital_engagement INTEGER NOT NULL,
                health_conditions TEXT,
                cluster_id INTEGER,
                confidence_score REAL,
                pain_points TEXT,
                consent_given INTEGER DEFAULT 0,
                consent_version TEXT,
                consent_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                senior_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (senior_id) REFERENCES seniors (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                target_cluster INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS consent_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                senior_id INTEGER NOT NULL,
                consent_version TEXT NOT NULL,
                consent_given INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (senior_id) REFERENCES seniors (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_retention_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                records_deleted INTEGER NOT NULL,
                retention_days INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Add performance indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_seniors_cluster_id ON seniors(cluster_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_seniors_created_at ON seniors(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_seniors_consent_given ON seniors(consent_given)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actions_senior_id ON actions(senior_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actions_created_at ON actions(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_consent_log_senior_id ON consent_log(senior_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_retention_log_created_at ON data_retention_log(created_at)')

        conn.commit()


def strip_phi(data):
    """Strip personally identifiable information from data records."""
    if not data:
        return data

    cleaned = {}
    for key, value in data.items():
        if isinstance(value, str):
            cleaned_value = value
            for pattern_name, pattern in PHI_PATTERNS:
                cleaned_value = pattern.sub(f'[REDACTED_{pattern_name.upper()}]', cleaned_value)
            cleaned[key] = cleaned_value
        else:
            cleaned[key] = value
    return cleaned


def load_sample_data():
    pool = get_db_pool()

    def _check_and_load():
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM seniors')
            if cursor.fetchone()[0] > 0:
                return False

            random.seed(42)
            n_samples = 100
            now = datetime.utcnow().isoformat()

            ages = [max(60, min(95, int(random.gauss(75, 8)))) for _ in range(n_samples)]
            mobility = [1 if random.random() < 0.3 else 0 for _ in range(n_samples)]
            digital = [1 if random.random() < 0.4 else 0 for _ in range(n_samples)]

            conditions = []
            for i in range(n_samples):
                conds = []
                if random.random() < 0.3:
                    conds.append('arthritis')
                if random.random() < 0.2:
                    conds.append('diabetes')
                if random.random() < 0.15:
                    conds.append('hypertension')
                conditions.append(','.join(conds) if conds else 'none')

            # Batch insert seniors
            seniors_data = [
                (ages[i], mobility[i], digital[i], conditions[i], 1, CONSENT_VERSION, now)
                for i in range(n_samples)
            ]
            cursor.executemany(
                'INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions, consent_given, consent_version, consent_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
                seniors_data
            )

            # Batch insert programs
            programs = [
                ('Low-Tech Exercise Class', 'Gentle chair-based exercises for mobility support', 0),
                ('Mobile Health Check-ins', 'Weekly nurse visits for homebound seniors', 1),
                ('Digital Literacy Workshop', 'Basic tablet/phone training for staying connected', 2),
                ('Social Connection Group', 'Weekly meetups to reduce isolation', 3),
                ('Nutrition Counseling', 'Personalized meal planning for chronic conditions', 4),
            ]
            cursor.executemany(
                'INSERT INTO programs (name, description, target_cluster) VALUES (?, ?, ?)',
                programs
            )

            conn.commit()
            return True

    try:
        default_retry_policy.execute(_check_and_load)
    except Exception as e:
        logger.error(f"Failed to load sample data after retries: {e}")
        raise


@app.route('/health')
def health():
    db_status = 'ok'
    try:
        pool = get_db_pool()
        with pool.get_connection() as conn:
            conn.execute('SELECT 1')
    except Exception as e:
        logger.error(f"Health check database error: {e}")
        db_status = 'degraded'

    return jsonify({
        'status': 'ok' if db_status == 'ok' else 'degraded',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/data/refresh', methods=['POST'])
def refresh_data():
    pool = get_db_pool()

    def _refresh():
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM seniors')
            cursor.execute('DELETE FROM actions')
            conn.commit()

    try:
        default_retry_policy.execute(_refresh)
        load_sample_data()
        return jsonify({'status': 'success', 'message': 'Data refreshed'})
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for data refresh")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Data refresh failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/clusters')
def get_clusters():
    pool = get_db_pool()

    def _fetch_clusters():
        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Single optimized query with aggregation at database level
            cursor.execute('''
                SELECT 
                    s.cluster_id,
                    COUNT(*) as senior_count,
                    GROUP_CONCAT(s.id) as senior_ids,
                    GROUP_CONCAT(s.age) as senior_ages,
                    GROUP_CONCAT(s.mobility_flag) as senior_mobility,
                    GROUP_CONCAT(s.digital_engagement) as senior_digital,
                    GROUP_CONCAT(s.health_conditions) as senior_health,
                    GROUP_CONCAT(s.confidence_score) as senior_confidence,
                    GROUP_CONCAT(s.pain_points) as senior_pain_points,
                    p.name as program_name,
                    p.description as program_description
                FROM seniors s
                LEFT JOIN programs p ON s.cluster_id = p.target_cluster
                WHERE s.cluster_id IS NOT NULL
                GROUP BY s.cluster_id
            ''')
            rows = cursor.fetchall()

            result = []
            for row in rows:
                # Parse concatenated senior data
                senior_ids = row['senior_ids'].split(',') if row['senior_ids'] else []
                senior_ages = row['senior_ages'].split(',') if row['senior_ages'] else []
                senior_mobility = row['senior_mobility'].split(',') if row['senior_mobility'] else []
                senior_digital = row['senior_digital'].split(',') if row['senior_digital'] else []
                senior_health = row['senior_health'].split(',') if row['senior_health'] else []
                senior_confidence = row['senior_confidence'].split(',') if row['senior_confidence'] else []
                senior_pain_points = row['senior_pain_points'].split(',') if row['senior_pain_points'] else []

                seniors = []
                pain_points_set = set()
                for i in range(len(senior_ids)):
                    senior = {
                        'id': int(senior_ids[i]),
                        'age': int(senior_ages[i]),
                        'mobility_flag': int(senior_mobility[i]),
                        'digital_engagement': int(senior_digital[i]),
                        'health_conditions': senior_health[i],
                        'confidence_score': float(senior_confidence[i]) if senior_confidence[i] else None,
                        'pain_points': senior_pain_points[i],
                        'cluster_id': row['cluster_id']
                    }
                    seniors.append(senior)
                    if senior['pain_points'] and senior['pain_points'] != 'none':
                        for pp in senior['pain_points'].split(','):
                            pain_points_set.add(pp)

                result.append({
                    'id': row['cluster_id'],
                    'program': row['program_name'],
                    'program_description': row['program_description'],
                    'seniors': seniors,
                    'pain_points': list(pain_points_set),
                    'count': row['senior_count']
                })

            return result

    try:
        result = db_circuit_breaker.call(lambda: default_retry_policy.execute(_fetch_clusters))
        return jsonify(result)
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for get_clusters")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Get clusters failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/clusters/generate', methods=['POST'])
def generate_clusters():
    pool = get_db_pool()

    def _generate():
        with pool.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT id, age, mobility_flag, digital_engagement FROM seniors WHERE cluster_id IS NULL')
            rows = cursor.fetchall()

            if len(rows) < 5:
                raise ValueError('Not enough data for clustering')

            # Batch prepare all updates
            updates = []
            cluster_assignments = []
            for row in rows:
                senior_id, age, mobility, digital = row
                if mobility == 1:
                    cluster_id = 0
                elif digital == 0:
                    cluster_id = 1
                elif age > 80:
                    cluster_id = 2
                elif mobility == 0 and digital == 1:
                    cluster_id = 3
                else:
                    cluster_id = 4

                confidence = 0.9 if cluster_id in [0, 1, 2] else 0.7

                pain_points = []
                if mobility == 1:
                    pain_points.append('mobility_support')
                if digital == 0:
                    pain_points.append('digital_exclusion')
                if age > 80:
                    pain_points.append('advanced_age_support')

                pain_points_str = ','.join(pain_points) if pain_points else 'none'

                updates.append((cluster_id, confidence, pain_points_str, senior_id))
                cluster_assignments.append((senior_id, cluster_id))

            # Execute batch update using executemany
            cursor.executemany(
                'UPDATE seniors SET cluster_id = ?, confidence_score = ?, pain_points = ? WHERE id = ?',
                updates
            )

            conn.commit()

            unique_clusters = len(set(c[1] for c in cluster_assignments))
            return unique_clusters

    try:
        unique_clusters = default_retry_policy.execute(_generate)
        return jsonify({'status': 'success', 'clusters_generated': unique_clusters})
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for generate_clusters")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Generate clusters failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/action', methods=['POST'])
def create_action():
    data = request.get_json()
    if not data or 'senior_id' not in data or 'action_type' not in data:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    pool = get_db_pool()

    def _create():
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO actions (senior_id, action_type, description) VALUES (?, ?, ?)',
                (data['senior_id'], data['action_type'], data.get('description', ''))
            )
            conn.commit()
            return cursor.lastrowid

    try:
        action_id = default_retry_policy.execute(_create)
        return jsonify({'status': 'success', 'action_id': action_id})
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for create_action")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Create action failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/actions/<int:senior_id>')
def get_actions(senior_id):
    pool = get_db_pool()

    def _fetch():
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM actions WHERE senior_id = ? ORDER BY id DESC', (senior_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    try:
        result = default_retry_policy.execute(_fetch)
        return jsonify(result)
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for get_actions")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Get actions failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/action/<int:action_id>/complete', methods=['POST'])
def complete_action(action_id):
    pool = get_db_pool()

    def _complete():
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE actions SET status = ?, completed_at = ? WHERE id = ?',
                ('completed', datetime.utcnow().isoformat(), action_id)
            )
            conn.commit()
            return cursor.rowcount

    try:
        rows_affected = default_retry_policy.execute(_complete)
        if rows_affected == 0:
            return jsonify({'status': 'error', 'message': 'Action not found'}), 404
        return jsonify({'status': 'success'})
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for complete_action")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Complete action failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/consent/<int:senior_id>', methods=['POST'])
def update_consent(senior_id):
    data = request.get_json()
    if not data or 'consent_given' not in data:
        return jsonify({'status': 'error', 'message': 'Missing consent_given field'}), 400

    consent_given = 1 if data['consent_given'] else 0
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')

    pool = get_db_pool()

    def _update():
        with pool.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT id FROM seniors WHERE id = ?', (senior_id,))
            if not cursor.fetchone():
                raise ValueError('Senior not found')

            cursor.execute(
                'UPDATE seniors SET consent_given = ?, consent_version = ?, consent_date = ? WHERE id = ?',
                (consent_given, CONSENT_VERSION, datetime.utcnow().isoformat(), senior_id)
            )

            cursor.execute(
                'INSERT INTO consent_log (senior_id, consent_version, consent_given, ip_address, user_agent) VALUES (?, ?, ?, ?, ?)',
                (senior_id, CONSENT_VERSION, consent_given, ip_address, user_agent)
            )

            conn.commit()

    try:
        default_retry_policy.execute(_update)
        return jsonify({'status': 'success', 'message': 'Consent updated'})
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for update_consent")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    except Exception as e:
        logger.error(f"Update consent failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/consent/<int:senior_id>')
def get_consent(senior_id):
    pool = get_db_pool()

    def _fetch():
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT consent_given, consent_version, consent_date FROM seniors WHERE id = ?', (senior_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError('Senior not found')
            return dict(row)

    try:
        result = default_retry_policy.execute(_fetch)
        return jsonify(result)
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for get_consent")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 404
    except Exception as e:
        logger.error(f"Get consent failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/compliance/retention', methods=['POST'])
def run_retention():
    cutoff_date = datetime.utcnow() - timedelta(days=DATA_RETENTION_DAYS)
    cutoff_str = cutoff_date.isoformat()

    pool = get_db_pool()

    def _retention():
        with pool.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('DELETE FROM actions WHERE created_at < ?', (cutoff_str,))
            actions_deleted = cursor.rowcount

            cursor.execute('DELETE FROM seniors WHERE created_at < ? AND consent_given = 0', (cutoff_str,))
            seniors_deleted = cursor.rowcount

            cursor.execute(
                'INSERT INTO data_retention_log (table_name, records_deleted, retention_days) VALUES (?, ?, ?)',
                ('actions', actions_deleted, DATA_RETENTION_DAYS)
            )
            cursor.execute(
                'INSERT INTO data_retention_log (table_name, records_deleted, retention_days) VALUES (?, ?, ?)',
                ('seniors', seniors_deleted, DATA_RETENTION_DAYS)
            )

            conn.commit()
            return actions_deleted, seniors_deleted

    try:
        actions_deleted, seniors_deleted = default_retry_policy.execute(_retention)
        return jsonify({
            'status': 'success',
            'actions_deleted': actions_deleted,
            'seniors_deleted': seniors_deleted,
            'retention_days': DATA_RETENTION_DAYS
        })
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for run_retention")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Run retention failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/compliance/retention/log')
def get_retention_log():
    pool = get_db_pool()

    def _fetch():
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM data_retention_log ORDER BY created_at DESC LIMIT 50')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    try:
        result = default_retry_policy.execute(_fetch)
        return jsonify(result)
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for get_retention_log")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Get retention log failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/compliance/disclaimer')
def get_disclaimer():
    return jsonify({
        'version': CONSENT_VERSION,
        'data_controller': 'SeniorCare Pulse Community Center',
        'purpose': 'Analytics and program recommendations for senior services',
        'legal_basis': 'Legitimate interest / Consent',
        'retention_days': DATA_RETENTION_DAYS,
        'rights': [
            'Access your data',
            'Rectify inaccurate data',
            'Request deletion (right to be forgotten)',
            'Restrict processing',
            'Data portability',
            'Object to processing',
            'Withdraw consent at any time'
        ],
        'contact': 'privacy@seniorcare-pulse.example.com',
        'last_updated': '2024-01-15'
    }), 200, {'Cache-Control': 'public, max-age=3600'}


@app.route('/data/ingest', methods=['POST'])
def ingest_data():
    data = request.get_json()
    if not data or 'records' not in data:
        return jsonify({'status': 'error', 'message': 'Missing records field'}), 400

    records = data['records']
    if not isinstance(records, list):
        return jsonify({'status': 'error', 'message': 'Records must be a list'}), 400

    pool = get_db_pool()

    def _ingest():
        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Prepare batch insert data
            seniors_data = []
            for record in records:
                cleaned = strip_phi(record)

                age = cleaned.get('age')
                mobility = cleaned.get('mobility_flag')
                digital = cleaned.get('digital_engagement')
                health = cleaned.get('health_conditions', 'none')

                if age is None or mobility is None or digital is None:
                    continue

                seniors_data.append((age, mobility, digital, health, 0, CONSENT_VERSION, None))

            if seniors_data:
                cursor.executemany(
                    'INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions, consent_given, consent_version, consent_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    seniors_data
                )

            conn.commit()
            return len(seniors_data)

    try:
        inserted = default_retry_policy.execute(_ingest)
        return jsonify({'status': 'success', 'records_inserted': inserted})
    except CircuitBreakerOpenError:
        logger.error("Circuit breaker open for ingest_data")
        return jsonify({'status': 'error', 'message': 'Service temporarily unavailable'}), 503
    except Exception as e:
        logger.error(f"Ingest data failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    init_db()
    load_sample_data()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)