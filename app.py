from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime, date, timedelta
import calendar
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Database setup
def init_db():
    conn = sqlite3.connect('events.db')
    cursor = conn.cursor()
    
    # Events table - Fixed column names
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            event_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            venue TEXT NOT NULL,
            description TEXT,
            host_school TEXT NOT NULL,
            participating_schools TEXT,
            status TEXT DEFAULT 'upcoming',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Participants table (for teachers/non-students)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('teacher')),
            class_dept TEXT NOT NULL,
            contact TEXT,
            emergency_contact TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
   
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS duties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            participant_id INTEGER,
            volunteer_id INTEGER,
            duty_type TEXT NOT NULL,
            duty_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            location TEXT NOT NULL,
            description TEXT,
            notes TEXT,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
            FOREIGN KEY (participant_id) REFERENCES participants (id) ON DELETE CASCADE,
            FOREIGN KEY (volunteer_id) REFERENCES volunteers (id) ON DELETE CASCADE,
            CHECK ((participant_id IS NOT NULL AND volunteer_id IS NULL) OR 
                   (participant_id IS NULL AND volunteer_id IS NOT NULL))
        )
    ''')
    
    conn.commit()
    conn.close()

# Database helper functions
def get_db_connection():
    conn = sqlite3.connect('events.db')
    conn.row_factory = sqlite3.Row
    return conn

# Calendar helper functions
def get_calendar_data(year, month):
    """Get calendar data for a given month"""
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    # Get events for this month
    conn = get_db_connection()
    start_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    
    events = conn.execute('''
        SELECT * FROM events 
        WHERE event_date >= ? AND event_date <= ?
        ORDER BY event_date, start_time
    ''', (start_date, end_date)).fetchall()
    
    conn.close()
    
    # Group events by date
    events_by_date = {}
    for event in events:
        event_date = event['event_date']
        if event_date not in events_by_date:
            events_by_date[event_date] = []
        events_by_date[event_date].append(event)
    
    from datetime import datetime as dt
    return {
        'calendar': cal,
        'month_name': month_name,
        'year': year,
        'month': month,
        'events_by_date': events_by_date,
        'prev_month': month - 1 if month > 1 else 12,
        'prev_year': year if month > 1 else year - 1,
        'next_month': month + 1 if month < 12 else 1,
        'next_year': year if month < 12 else year + 1,
        'datetime': dt
    }

# Routes
@app.route('/calendar')
def calendar_view():
    """Display calendar view"""
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    calendar_data = get_calendar_data(year, month)
    return render_template('calendar.html', **calendar_data)

@app.route('/calendar/<int:year>/<int:month>/<int:day>')
def day_events(year, month, day):
    """Display events for a specific day"""
    selected_date = date(year, month, day)
    
    conn = get_db_connection()
    events = conn.execute('''
        SELECT * FROM events 
        WHERE event_date = ?
        ORDER BY start_time
    ''', (selected_date,)).fetchall()
    conn.close()
    
    return render_template('day_events.html', 
                         events=events, 
                         selected_date=selected_date,
                         year=year, month=month, day=day)

@app.route('/calendar/add_event', methods=['GET', 'POST'])
def add_calendar_event():
    """Add event from calendar view"""
    if request.method == 'POST':
        name = request.form['name']
        event_type = request.form['type']
        event_date = request.form['event_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        venue = request.form['venue']
        description = request.form['description']
        host_school = request.form['host_school']
        participating_schools = request.form['participating_schools']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO events (name, type, event_date, start_time, end_time, venue,
                              description, host_school, participating_schools)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, event_type, event_date, start_time, end_time, venue,
              description, host_school, participating_schools))
        conn.commit()
        conn.close()
        
        flash('Event added successfully!', 'success')
        
        # Redirect back to calendar or day view
        year = int(request.args.get('year', datetime.now().year))
        month = int(request.args.get('month', datetime.now().month))
        day = int(request.args.get('day', 1))
        
        return redirect(url_for('calendar_view', year=year, month=month))
    
    # Pre-fill date if provided
    year = request.args.get('year', datetime.now().year)
    month = request.args.get('month', datetime.now().month)
    day = request.args.get('day', datetime.now().day)
    prefill_date = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    
    return render_template('add_calendar_event.html', prefill_date=prefill_date)

@app.route('/')
def dashboard():
    conn = get_db_connection()
    
    # Statistics
    total_events = conn.execute('SELECT COUNT(*) as count FROM events').fetchone()['count']
    total_participants = conn.execute('SELECT COUNT(*) as count FROM participants').fetchone()['count']
    total_teachers = conn.execute('SELECT COUNT(*) as count FROM participants WHERE type = "teacher"').fetchone()['count']
    total_duties = conn.execute('SELECT COUNT(*) as count FROM duties').fetchone()['count']

    # Upcoming events
    upcoming_events = conn.execute('''
        SELECT * FROM events 
        WHERE event_date >= DATE('now') 
        ORDER BY event_date ASC 
        LIMIT 5
    ''').fetchall()

    conn.close()
    
    return render_template('dashboard.html', 
                         total_events=total_events,
                         total_participants=total_participants,
                         total_teachers=total_teachers,
                         total_duties=total_duties,
                         upcoming_events=upcoming_events)

@app.route('/events')
def events():
    conn = get_db_connection()
    filter_type = request.args.get('filter', 'all')
    search = request.args.get('search', '')
    
    query = 'SELECT * FROM events WHERE 1=1'
    params = []
    
    if filter_type == 'upcoming':
        query += ' AND event_date >= DATE("now")'
    elif filter_type == 'completed':
        query += ' AND event_date < DATE("now")'
    
    if search:
        query += ' AND (name LIKE ? OR type LIKE ? OR venue LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    query += ' ORDER BY event_date ASC'
    
    events = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('events.html', events=events, filter_type=filter_type, search=search)

@app.route('/events/add', methods=['GET', 'POST'])
def add_event():
    if request.method == 'POST':
        name = request.form['name']
        event_type = request.form['type']
        event_date = request.form['event_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        venue = request.form['venue']
        description = request.form['description']
        host_school = request.form['host_school']
        participating_schools = request.form['participating_schools']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO events (name, type, event_date, start_time, end_time, venue, 
                              description, host_school, participating_schools)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, event_type, event_date, start_time, end_time, venue, 
              description, host_school, participating_schools))
        conn.commit()
        conn.close()
        
        flash('Event added successfully!', 'success')
        return redirect(url_for('events'))
    
    return render_template('add_event.html')

@app.route('/events/<int:id>/edit', methods=['GET', 'POST'])
def edit_event(id):
    conn = get_db_connection()
    event = conn.execute('SELECT * FROM events WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        event_type = request.form['type']
        event_date = request.form['event_date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        venue = request.form['venue']
        description = request.form['description']
        host_school = request.form['host_school']
        participating_schools = request.form['participating_schools']
        
        conn.execute('''
            UPDATE events SET name = ?, type = ?, event_date = ?, start_time = ?, 
                           end_time = ?, venue = ?, description = ?, host_school = ?, 
                           participating_schools = ? WHERE id = ?
        ''', (name, event_type, event_date, start_time, end_time, venue, 
              description, host_school, participating_schools, id))
        conn.commit()
        conn.close()
        
        flash('Event updated successfully!', 'success')
        return redirect(url_for('events'))
    
    conn.close()
    return render_template('edit_event.html', event=event)

@app.route('/events/<int:id>/delete', methods=['POST'])
def delete_event(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM events WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('events'))

@app.route('/participants')
def participants():
    conn = get_db_connection()
    type_filter = request.args.get('type', 'all')
    search = request.args.get('search', '')
    
    query = 'SELECT * FROM participants WHERE 1=1'
    params = []
    
    if type_filter != 'all':
        query += ' AND type = ?'
        params.append(type_filter)
    
    if search:
        query += ' AND (name LIKE ? OR class_dept LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    
    participants = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('participants.html', participants=participants, type_filter=type_filter, search=search)

@app.route('/participants/add', methods=['GET', 'POST'])
def add_participant():
    if request.method == 'POST':
        name = request.form['name']
        participant_type = request.form['type']
        school = request.form['school']
        contact = request.form['contact']
        emergency_contact = request.form['emergency_contact']
        
        # Use school as class_dept since they're equivalent
        class_dept = school
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO participants (name, type, class_dept, contact, emergency_contact)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, participant_type, class_dept, contact, emergency_contact))
        conn.commit()
        conn.close()
        
        flash('Participant added successfully!', 'success')
        return redirect(url_for('participants'))
    
    return render_template('add_participant.html')

@app.route('/participants/<int:id>/edit', methods=['GET', 'POST'])
def edit_participant(id):
    conn = get_db_connection()
    participant = conn.execute('SELECT * FROM participants WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        participant_type = request.form['type']
        school = request.form['school']
        contact = request.form['contact']
        emergency_contact = request.form['emergency_contact']
        
        # Use school as class_dept since they're equivalent
        class_dept = school
        
        conn.execute('''
            UPDATE participants SET name = ?, type = ?, class_dept = ?, 
                           contact = ?, emergency_contact = ? WHERE id = ?
        ''', (name, participant_type, class_dept, contact, emergency_contact, id))
        conn.commit()
        conn.close()
        
        flash('Participant updated successfully!', 'success')
        return redirect(url_for('participants'))
    
    conn.close()
    return render_template('edit_participant.html', participant=participant)

@app.route('/participants/<int:id>/delete', methods=['POST'])
def delete_participant(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM participants WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Participant deleted successfully!', 'success')
    return redirect(url_for('participants'))

# Volunteers routes


@app.route('/duties')
def duties():
    conn = get_db_connection()
    
    duties = conn.execute('''
        SELECT d.*, e.name as event_name, e.event_date as event_date,
               p.name as person_name, 'Participant' as person_type
        FROM duties d
        JOIN events e ON d.event_id = e.id
        JOIN participants p ON d.participant_id = p.id
        ORDER BY e.event_date
    ''').fetchall()
    
    events = conn.execute('SELECT id, name, event_date FROM events ORDER BY event_date').fetchall()
    participants = conn.execute('SELECT id, name, class_dept FROM participants ORDER BY name').fetchall()
    
    conn.close()
    
    return render_template('duties.html', duties=duties, events=events, 
                         participants=participants)

@app.route('/duties/assign', methods=['GET', 'POST'])
def assign_duty():
    if request.method == 'POST':
        event_id = request.form['event_id']
        duty_type = request.form['duty_type']
        duty_date = request.form['duty_date']
        time_slot = request.form['time_slot']
        location = request.form['location']
        description = request.form['description']
        notes = request.form['notes']
        
        # Parse time slot into start and end times
        time_parts = time_slot.split(' - ')
        start_time = time_parts[0].strip()
        end_time = time_parts[1].strip() if len(time_parts) > 1 else start_time
        
        teacher_name = request.form['teacher_name'].strip()
        
        conn = get_db_connection()
        
        # Find or create teacher
        teacher = conn.execute('SELECT id FROM participants WHERE name = ? AND type = "teacher"', 
                             (teacher_name,)).fetchone()
        
        if teacher:
            participant_id = teacher['id']
        else:
            # Create new teacher with minimal info
            cursor = conn.execute('INSERT INTO participants (name, type, class_dept) VALUES (?, "teacher", "")',
                                (teacher_name,))
            participant_id = cursor.lastrowid
        
        conn.execute('''
            INSERT INTO duties (event_id, participant_id, duty_type, 
                              duty_date, start_time, end_time, location, description, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (event_id, participant_id, duty_type, 
              duty_date, start_time, end_time, location, description, notes))
        conn.commit()
        conn.close()
        
        flash('Duty assigned successfully!', 'success')
        return redirect(url_for('duties'))
    
    conn = get_db_connection()
    events = conn.execute('SELECT id, name, event_date, venue FROM events ORDER BY event_date').fetchall()
    conn.close()
    
    return render_template('add_duty.html', events=events)

# Alternative route name for backward compatibility
@app.route('/duties/add', methods=['GET', 'POST'])
def add_duty():
    return assign_duty()

@app.route('/duties/<int:id>/edit', methods=['GET', 'POST'])
def edit_duty(id):
    conn = get_db_connection()
    duty = conn.execute('SELECT * FROM duties WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        event_id = request.form['event_id']
        teacher_name = request.form['teacher_name'].strip()
        duty_type = request.form['duty_type']
        duty_date = request.form['duty_date']
        time_slot = request.form['time_slot']
        location = request.form['location']
        description = request.form['description']
        notes = request.form['notes']
        
        # Parse time slot into start and end times
        time_parts = time_slot.split(' - ')
        start_time = time_parts[0].strip()
        end_time = time_parts[1].strip() if len(time_parts) > 1 else start_time
        
        conn = get_db_connection()
        
        # Find or create teacher
        teacher = conn.execute('SELECT id FROM participants WHERE name = ? AND type = "teacher"', 
                             (teacher_name,)).fetchone()
        
        if teacher:
            participant_id = teacher['id']
        else:
            # Create new teacher with minimal info
            cursor = conn.execute('INSERT INTO participants (name, type, class_dept) VALUES (?, "teacher", "")',
                                (teacher_name,))
            participant_id = cursor.lastrowid
        
        conn.execute('''
            UPDATE duties SET event_id = ?, participant_id = ?, duty_type = ?,
                           duty_date = ?, start_time = ?, end_time = ?, location = ?, 
                           description = ?, notes = ? WHERE id = ?
        ''', (event_id, participant_id, duty_type, duty_date, 
              start_time, end_time, location, description, notes, id))
        conn.commit()
        conn.close()
        
        flash('Duty updated successfully!', 'success')
        return redirect(url_for('duties'))
    
    events = conn.execute('SELECT id, name, event_date, venue FROM events ORDER BY event_date').fetchall()
    conn.close()
    
    return render_template('edit_duty.html', duty=duty, events=events)

@app.route('/duties/<int:id>/delete', methods=['POST'])
def delete_duty(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM duties WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Duty deleted successfully!', 'success')
    return redirect(url_for('duties'))

@app.route('/api/events')
def api_events():
    conn = get_db_connection()
    events = conn.execute('SELECT * FROM events ORDER BY event_date DESC').fetchall()
    conn.close()
    return jsonify([dict(event) for event in events])

@app.route('/api/participants')
def api_participants():
    conn = get_db_connection()
    participants = conn.execute('SELECT * FROM participants ORDER BY name').fetchall()
    conn.close()
    
    return jsonify([dict(participant) for participant in participants])



@app.route('/api/duties')
def api_duties():
    conn = get_db_connection()
    duties = conn.execute('''
        SELECT d.*, e.name as event_name, 
               p.name as person_name,
               'Participant' as person_type
        FROM duties d
        JOIN events e ON d.event_id = e.id
        JOIN participants p ON d.participant_id = p.id
        ORDER BY d.assigned_at DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(duty) for duty in duties])

@app.route('/reports')
def reports():
    conn = get_db_connection()
    
    # Get statistics
    stats = {
        'total_events': conn.execute('SELECT COUNT(*) as count FROM events').fetchone()['count'],
        'total_participants': conn.execute('SELECT COUNT(*) as count FROM participants').fetchone()['count'],
        'total_duties': conn.execute('SELECT COUNT(*) as count FROM duties').fetchone()['count']
    }
    
    # Get events by type for chart
    events_by_type = conn.execute('''
        SELECT type, COUNT(*) as count
        FROM events
        GROUP BY type
    ''').fetchall()
    events_by_type_labels = [row['type'] for row in events_by_type]
    events_by_type_data = [row['count'] for row in events_by_type]
    
    # Get participants by type for chart
    participants_by_type = conn.execute('''
        SELECT type, COUNT(*) as count
        FROM participants
        GROUP BY type
    ''').fetchall()
    participants_by_type_data = [row['count'] for row in participants_by_type]
    
    # Get events timeline for chart
    events_timeline = conn.execute('''
        SELECT event_date, COUNT(*) as count
        FROM events
        WHERE event_date >= date('now', '-30 days')
        GROUP BY event_date
        ORDER BY event_date
    ''').fetchall()
    events_timeline_labels = [row['event_date'] for row in events_timeline]
    events_timeline_data = [row['count'] for row in events_timeline]
    
    # Get top participating schools
    top_schools = []
    
    # Get duty statistics
    duty_stats = conn.execute('''
        SELECT duty_type, COUNT(*) as count
        FROM duties
        GROUP BY duty_type
    ''').fetchall()
    
    conn.close()
    
    return render_template('reports.html', 
                         stats=stats, 
                         top_schools=top_schools,
                         duty_stats=duty_stats,
                         events_by_type_labels=events_by_type_labels,
                         events_by_type_data=events_by_type_data,
                         participants_by_type_data=participants_by_type_data,
                         events_timeline_labels=events_timeline_labels,
                         events_timeline_data=events_timeline_data)

@app.route('/export')
def export_data():
    export_type = request.args.get('type', 'events')
    conn = get_db_connection()
    
    if export_type == 'events':
        data = conn.execute('SELECT * FROM events ORDER BY event_date DESC').fetchall()
    elif export_type == 'participants':
        data = conn.execute('SELECT * FROM participants ORDER BY name').fetchall()
    elif export_type == 'teachers':
        data = conn.execute('SELECT * FROM participants WHERE type = "teacher" ORDER BY class_dept, name').fetchall()
    elif export_type == 'duties':
        data = conn.execute('''
            SELECT d.*, e.name as event_name, 
                   COALESCE(p.name, v.name) as person_name,
                   CASE WHEN d.participant_id IS NOT NULL THEN 'Participant' ELSE 'Volunteer' END as person_type
            FROM duties d
            JOIN events e ON d.event_id = e.id
            LEFT JOIN participants p ON d.participant_id = p.id
            LEFT JOIN volunteers v ON d.volunteer_id = v.id
            ORDER BY d.assigned_at DESC
        ''').fetchall()
    else:
        return jsonify({'error': 'Invalid export type'}), 400
    
    conn.close()
    return jsonify([dict(row) for row in data])

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=8001)