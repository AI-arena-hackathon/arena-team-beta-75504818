import os
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from datetime import datetime
import random

app = Flask(__name__)
CORS(app)

DB_PATH = os.environ.get('DATABASE_PATH', '/data/seniorcare.db')
DATA_DIR = os.environ.get('DATA_DIR', '/data/csv')


def get_db():
    conn = sqlite3.connect(DB_PATH)
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

    conn.commit()
    conn.close()


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
            'INSERT INTO seniors (age, mobility_flag, digital_engagement, health_conditions) VALUES (?, ?, ?, ?)',
            (ages[i], mobility[i], digital[i], conditions[i])
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

    # Simple rule-based clustering (fallback from KNN)
    # Cluster 0: High mobility needs (mobility_flag=1)
    # Cluster 1: Low digital engagement (digital_engagement=0)
    # Cluster 2: Advanced age (age > 80)
    # Cluster 3: Independent, digitally engaged
    # Cluster 4: Mixed needs
    
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
        
        # Calculate confidence based on how well they fit the cluster
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
    
    # Count unique clusters created
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


if __name__ == '__main__':
    init_db()
    load_sample_data()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)