import os
import sqlite3
import re
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import random

app = Flask(__name__)
CORS(app)

DATA_DIR = os.environ.get('DATA_DIR', '/data/csv')

DATA_RETENTION_DAYS = int(os.environ.get('DATA_RETENTION_DAYS', '365'))
CONSENT_VERSION = os.environ.get('CONSENT_VERSION', '1.0')


def get_db():
    db_path = os.environ.get('DATABASE_PATH', '/data/seniorcare.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
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

    conn.commit()
    conn.close()


def strip_phi(data):
    """Strip personally identifiable information from data records."""
    if not data:
        return data

    phi_patterns = [
        ('ssn', r'\b\d{3}-\d{2}-\d{4}\b'),
        ('phone', r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
        ('email', r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        ('address', r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b'),
        ('dob', r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
        ('medical_record', r'\bMRN[-\s]?\d+\b'),
        ('name', r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'),
    ]

    cleaned = {}
    for key, value in data.items():
        if isinstance(value, str):
            cleaned_value = value
            for pattern_name, pattern in phi_patterns:
                cleaned_value = re.sub(pattern, f'[REDACTED_{pattern_name.upper()}]', cleaned_value, flags=re.IGNORECASE)
            cleaned[key] = cleaned_value
        else:
            cleaned[key] = value
    return cleaned


def load_sample_data():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM seniors')
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    random.seed(42)
    n_samples = 100

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

    for i in range(n_samples):
        cursor.execute(
            'INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions, consent_given, consent_version, consent_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (ages[i], mobility[i], digital[i], conditions[i], 1, CONSENT_VERSION, datetime.utcnow().isoformat())
        )

    programs = [
        ('Low-Tech Exercise Class', 'Gentle chair-based exercises for mobility support', 0),
        ('Mobile Health Check-ins', 'Weekly nurse visits for homebound seniors', 1),
        ('Digital Literacy Workshop', 'Basic tablet/phone training for staying connected', 2),
        ('Social Connection Group', 'Weekly meetups to reduce isolation', 3),
        ('Nutrition Counseling', 'Personalized meal planning for chronic conditions', 4),
    ]
    for name, desc, cluster in programs:
        cursor.execute(
            'INSERT INTO programs (name, description, target_cluster) VALUES (?, ?, ?)',
            (name, desc, cluster)
        )

    conn.commit()
    conn.close()


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/data/refresh', methods=['POST'])
def refresh_data():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM seniors')
        cursor.execute('DELETE FROM actions')
        conn.commit()
        conn.close()
        load_sample_data()
        return jsonify({'status': 'success', 'message': 'Data refreshed'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/clusters')
def get_clusters():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT s.*, p.name as program_name, p.description as program_description
        FROM seniors s
        LEFT JOIN programs p ON s.cluster_id = p.target_cluster
        WHERE s.cluster_id IS NOT NULL
    ''')
    rows = cursor.fetchall()
    conn.close()

    clusters = {}
    for row in rows:
        cluster_id = row['cluster_id']
        if cluster_id not in clusters:
            clusters[cluster_id] = {
                'id': cluster_id,
                'program': row['program_name'],
                'program_description': row['program_description'],
                'seniors': [],
                'pain_points': set()
            }
        senior = dict(row)
        clusters[cluster_id]['seniors'].append(senior)
        if senior['pain_points']:
            for pp in senior['pain_points'].split(','):
                clusters[cluster_id]['pain_points'].add(pp)

    result = []
    for cluster in clusters.values():
        cluster['pain_points'] = list(cluster['pain_points'])
        cluster['count'] = len(cluster['seniors'])
        result.append(cluster)

    return jsonify(result)


@app.route('/clusters/generate', methods=['POST'])
def generate_clusters():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id, age, mobility_flag, digital_engagement FROM seniors WHERE cluster_id IS NULL')
    rows = cursor.fetchall()

    if len(rows) < 5:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Not enough data for clustering'}), 400

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

        cursor.execute(
            'UPDATE seniors SET cluster_id = ?, confidence_score = ?, pain_points = ? WHERE id = ?',
            (cluster_id, confidence, pain_points_str, senior_id)
        )
        cluster_assignments.append((senior_id, cluster_id))

    conn.commit()

    unique_clusters = len(set(c[1] for c in cluster_assignments))
    conn.close()
    return jsonify({'status': 'success', 'clusters_generated': unique_clusters})


@app.route('/action', methods=['POST'])
def create_action():
    data = request.get_json()
    if not data or 'senior_id' not in data or 'action_type' not in data:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO actions (senior_id, action_type, description) VALUES (?, ?, ?)',
        (data['senior_id'], data['action_type'], data.get('description', ''))
    )
    conn.commit()
    action_id = cursor.lastrowid
    conn.close()

    return jsonify({'status': 'success', 'action_id': action_id})


@app.route('/actions/<int:senior_id>')
def get_actions(senior_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM actions WHERE senior_id = ? ORDER BY id DESC', (senior_id,))
    rows = cursor.fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


@app.route('/action/<int:action_id>/complete', methods=['POST'])
def complete_action(action_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE actions SET status = ?, completed_at = ? WHERE id = ?',
        ('completed', datetime.utcnow().isoformat(), action_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})


@app.route('/consent/<int:senior_id>', methods=['POST'])
def update_consent(senior_id):
    data = request.get_json()
    if not data or 'consent_given' not in data:
        return jsonify({'status': 'error', 'message': 'Missing consent_given field'}), 400

    consent_given = 1 if data['consent_given'] else 0
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM seniors WHERE id = ?', (senior_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'status': 'error', 'message': 'Senior not found'}), 404

    cursor.execute(
        'UPDATE seniors SET consent_given = ?, consent_version = ?, consent_date = ? WHERE id = ?',
        (consent_given, CONSENT_VERSION, datetime.utcnow().isoformat(), senior_id)
    )

    cursor.execute(
        'INSERT INTO consent_log (senior_id, consent_version, consent_given, ip_address, user_agent) VALUES (?, ?, ?, ?, ?)',
        (senior_id, CONSENT_VERSION, consent_given, ip_address, user_agent)
    )

    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'message': 'Consent updated'})


@app.route('/consent/<int:senior_id>')
def get_consent(senior_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT consent_given, consent_version, consent_date FROM seniors WHERE id = ?', (senior_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'status': 'error', 'message': 'Senior not found'}), 404

    return jsonify(dict(row))


@app.route('/compliance/retention', methods=['POST'])
def run_retention():
    cutoff_date = datetime.utcnow() - timedelta(days=DATA_RETENTION_DAYS)
    cutoff_str = cutoff_date.isoformat()

    conn = get_db()
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
    conn.close()

    return jsonify({
        'status': 'success',
        'actions_deleted': actions_deleted,
        'seniors_deleted': seniors_deleted,
        'retention_days': DATA_RETENTION_DAYS
    })


@app.route('/compliance/retention/log')
def get_retention_log():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM data_retention_log ORDER BY created_at DESC LIMIT 50')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


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
    })


@app.route('/data/ingest', methods=['POST'])
def ingest_data():
    data = request.get_json()
    if not data or 'records' not in data:
        return jsonify({'status': 'error', 'message': 'Missing records field'}), 400

    records = data['records']
    if not isinstance(records, list):
        return jsonify({'status': 'error', 'message': 'Records must be a list'}), 400

    conn = get_db()
    cursor = conn.cursor()

    inserted = 0
    for record in records:
        cleaned = strip_phi(record)

        age = cleaned.get('age')
        mobility = cleaned.get('mobility_flag')
        digital = cleaned.get('digital_engagement')
        health = cleaned.get('health_conditions', 'none')

        if age is None or mobility is None or digital is None:
            continue

        cursor.execute(
            'INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions, consent_given, consent_version, consent_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (age, mobility, digital, health, 0, CONSENT_VERSION, None)
        )
        inserted += 1

    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'records_inserted': inserted})


if __name__ == '__main__':
    init_db()
    load_sample_data()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)