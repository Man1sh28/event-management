from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, make_response
import os
from datetime import datetime, date, timedelta
import calendar
import json
import csv
from io import StringIO
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import tempfile
import pandas as pd
import io
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-me')

# ─────────────────────────────────────────────
# Supabase client  (replaces get_db_connection)
# ─────────────────────────────────────────────
SUPABASE_URL: str = os.environ['SUPABASE_URL']
SUPABASE_KEY: str = os.environ['SUPABASE_KEY']   # service_role key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─────────────────────────────────────────────
# Auth decorators  (unchanged from original)
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page', 'error')
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ─────────────────────────────────────────────
# Auth routes
# ─────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        result = supabase.table('users').select('*').eq('username', username).execute()
        users = result.data

        if users and check_password_hash(users[0]['password_hash'], password):
            user = users[0]
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')

        existing = supabase.table('users').select('id').eq('username', username).execute()
        if existing.data:
            flash('Username already exists', 'error')
            return render_template('register.html')

        password_hash = generate_password_hash(password)
        count_result = supabase.table('users').select('id', count='exact').execute()
        role = 'super_admin' if count_result.count == 0 else 'student'

        supabase.table('users').insert({
            'username': username,
            'password_hash': password_hash,
            'role': role
        }).execute()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today().isoformat()

    total_events      = supabase.table('events').select('id', count='exact').execute().count
    total_participants = supabase.table('participants').select('id', count='exact').eq('type', 'student').execute().count
    total_duty_personnel = supabase.table('duty_personnel').select('id', count='exact').execute().count
    total_duties      = supabase.table('duties').select('id', count='exact').execute().count

    upcoming_events = (
        supabase.table('events')
        .select('*')
        .gte('event_date', today)
        .order('event_date')
        .limit(5)
        .execute()
        .data
    )

    is_student = session.get('role') == 'student'

    return render_template('dashboard.html',
                           total_events=total_events,
                           total_participants=total_participants,
                           total_duty_personnel=total_duty_personnel,
                           total_duties=total_duties,
                           upcoming_events=upcoming_events,
                           is_student=is_student)


# ─────────────────────────────────────────────
# Calendar
# ─────────────────────────────────────────────
def get_calendar_data(year, month):
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    start_date = date(year, month, 1).isoformat()
    last_day   = calendar.monthrange(year, month)[1]
    end_date   = date(year, month, last_day).isoformat()

    events = (
        supabase.table('events')
        .select('*')
        .gte('event_date', start_date)
        .lte('event_date', end_date)
        .order('event_date')
        .execute()
        .data
    )

    events_by_date = {}
    for event in events:
        d = event['event_date']
        events_by_date.setdefault(d, []).append(event)

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
        'datetime': dt,
    }

@app.route('/calendar')
@login_required
def calendar_view():
    year  = int(request.args.get('year',  datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    return render_template('calendar.html', **get_calendar_data(year, month))

@app.route('/calendar/<int:year>/<int:month>/<int:day>')
@login_required
def day_events(year, month, day):
    selected_date = date(year, month, day).isoformat()

    events_data = (
        supabase.table('events')
        .select('*')
        .eq('event_date', selected_date)
        .order('start_time')
        .execute()
        .data
    )

    events = []
    for e in events_data:
        rows = (
            supabase.table('participant_events')
            .select('participants(name)')
            .eq('event_id', e['id'])
            .execute()
            .data
        )
        e['assigned_participants'] = [r['participants']['name'] for r in rows if r.get('participants')]
        events.append(e)

    return render_template('day_events.html',
                           events=events,
                           selected_date=date(year, month, day),
                           year=year, month=month, day=day)

@app.route('/calendar/add_event', methods=['GET', 'POST'])
@role_required(['admin', 'super_admin'])
def add_calendar_event():
    if request.method == 'POST':
        supabase.table('events').insert({
            'name':                 request.form['name'],
            'type':                 request.form['type'],
            'event_date':           request.form['event_date'],
            'start_time':           request.form['start_time'],
            'end_time':             request.form['end_time'],
            'venue':                request.form['venue'],
            'description':          request.form['description'],
            'host_school':          request.form['host_school'],
            'participating_schools': request.form['participating_schools'],
        }).execute()

        flash('Event added successfully!', 'success')
        year  = int(request.args.get('year',  datetime.now().year))
        month = int(request.args.get('month', datetime.now().month))
        return redirect(url_for('calendar_view', year=year, month=month))

    year  = request.args.get('year',  datetime.now().year)
    month = request.args.get('month', datetime.now().month)
    day   = request.args.get('day',   datetime.now().day)
    prefill_date = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    return render_template('add_calendar_event.html', prefill_date=prefill_date)


# ─────────────────────────────────────────────
# Events CRUD
# ─────────────────────────────────────────────
@app.route('/events')
@login_required
def events():
    filter_type = request.args.get('filter', 'all')
    search      = request.args.get('search', '')
    is_student  = session.get('role') == 'student'
    today       = date.today().isoformat()

    query = supabase.table('events').select('*')

    if is_student:
        # Find participant record linked to this user
        user_result = supabase.table('users').select('username').eq('id', session['user_id']).execute()
        if not user_result.data:
            return render_template('events.html', events=[], filter_type=filter_type,
                                   search=search, is_student=is_student)

        participant_result = (
            supabase.table('participants')
            .select('id')
            .eq('unique_id', f"user_{session['user_id']}")
            .execute()
        )
        if not participant_result.data:
            return render_template('events.html', events=[], filter_type=filter_type,
                                   search=search, is_student=is_student)

        participant_id = participant_result.data[0]['id']
        pe_rows = (
            supabase.table('participant_events')
            .select('event_id')
            .eq('participant_id', participant_id)
            .execute()
            .data
        )
        event_ids = [r['event_id'] for r in pe_rows]
        if not event_ids:
            return render_template('events.html', events=[], filter_type=filter_type,
                                   search=search, is_student=is_student)
        query = query.in_('id', event_ids)

    if filter_type == 'upcoming':
        query = query.gte('event_date', today)
    elif filter_type == 'completed':
        query = query.lt('event_date', today)

    events_data = query.order('event_date').execute().data

    # Apply search filter in Python (Supabase PostgREST supports ilike but not OR easily cross-column)
    if search:
        s = search.lower()
        events_data = [e for e in events_data if
                       s in e.get('name', '').lower() or
                       s in e.get('type', '').lower() or
                       s in e.get('venue', '').lower()]

    events = []
    for e in events_data:
        rows = (
            supabase.table('participant_events')
            .select('participants(name)')
            .eq('event_id', e['id'])
            .execute()
            .data
        )
        e['assigned_participants'] = [r['participants']['name'] for r in rows if r.get('participants')]
        e['is_enrolled'] = True
        events.append(e)

    return render_template('events.html', events=events, filter_type=filter_type,
                           search=search, is_student=is_student)

@app.route('/events/add', methods=['GET', 'POST'])
@role_required(['admin', 'super_admin'])
def add_event():
    if request.method == 'POST':
        supabase.table('events').insert({
            'name':                  request.form['name'],
            'type':                  request.form['type'],
            'event_date':            request.form['event_date'],
            'start_time':            request.form['start_time'],
            'end_time':              request.form['end_time'],
            'venue':                 request.form['venue'],
            'description':           request.form['description'],
            'host_school':           request.form['host_school'],
            'participating_schools': request.form['participating_schools'],
        }).execute()
        flash('Event added successfully!', 'success')
        return redirect(url_for('events'))

    return render_template('add_event.html')

@app.route('/events/<int:id>')
@login_required
def event_detail(id):
    result = supabase.table('events').select('*').eq('id', id).execute()
    if not result.data:
        flash('Event not found', 'error')
        return redirect(url_for('events'))

    event = result.data[0]
    is_student = session.get('role') == 'student'

    if is_student:
        pe = (
            supabase.table('participant_events')
            .select('participant_id')
            .eq('event_id', id)
            .execute()
            .data
        )
        enrolled_ids = [r['participant_id'] for r in pe]
        my_p = (
            supabase.table('participants')
            .select('id')
            .eq('unique_id', f"user_{session['user_id']}")
            .execute()
            .data
        )
        if not my_p or my_p[0]['id'] not in enrolled_ids:
            flash('You are not enrolled in this event', 'error')
            return redirect(url_for('events'))

    participants_rows = (
        supabase.table('participant_events')
        .select('participants(*)')
        .eq('event_id', id)
        .execute()
        .data
    )
    participants = [r['participants'] for r in participants_rows if r.get('participants')]

    duties_rows = (
        supabase.table('duties')
        .select('*, duty_personnel(name, designation)')
        .eq('event_id', id)
        .execute()
        .data
    )
    duties = []
    for d in duties_rows:
        flat = {**d}
        if d.get('duty_personnel'):
            flat['person_name']  = d['duty_personnel']['name']
            flat['designation']  = d['duty_personnel']['designation']
        duties.append(flat)

    announcements_rows = (
        supabase.table('announcements')
        .select('*, users(username)')
        .eq('event_id', id)
        .order('created_at')
        .execute()
        .data
    )
    announcements = []
    for a in announcements_rows:
        flat = {**a}
        flat['author'] = a['users']['username'] if a.get('users') else 'Unknown'
        announcements.append(flat)

    return render_template('event_detail.html',
                           event=event,
                           participants=participants,
                           duties=duties,
                           announcements=announcements,
                           is_student=is_student)

@app.route('/events/<int:id>/edit', methods=['GET', 'POST'])
@role_required(['admin', 'super_admin'])
def edit_event(id):
    if request.method == 'POST':
        supabase.table('events').update({
            'name':                  request.form['name'],
            'type':                  request.form['type'],
            'event_date':            request.form['event_date'],
            'start_time':            request.form['start_time'],
            'end_time':              request.form['end_time'],
            'venue':                 request.form['venue'],
            'description':           request.form['description'],
            'host_school':           request.form['host_school'],
            'participating_schools': request.form['participating_schools'],
        }).eq('id', id).execute()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('events'))

    event = supabase.table('events').select('*').eq('id', id).execute().data[0]
    return render_template('edit_event.html', event=event)

@app.route('/events/<int:id>/delete', methods=['POST'])
@role_required(['admin', 'super_admin'])
def delete_event(id):
    supabase.table('events').delete().eq('id', id).execute()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('events'))


# ─────────────────────────────────────────────
# Participants CRUD
# ─────────────────────────────────────────────
@app.route('/participants')
@login_required
def participants():
    search = request.args.get('search', '')

    query = supabase.table('participants').select('*').eq('type', 'student')
    participants_data = query.execute().data

    if search:
        s = search.lower()
        participants_data = [p for p in participants_data if
                             s in p.get('name', '').lower() or
                             s in p.get('class_dept', '').lower()]

    participants = []
    for p in participants_data:
        rows = (
            supabase.table('participant_events')
            .select('events(name)')
            .eq('participant_id', p['id'])
            .execute()
            .data
        )
        p['assigned_events_list'] = [r['events']['name'] for r in rows if r.get('events')]
        p['events_count'] = len(p['assigned_events_list'])
        participants.append(p)

    return render_template('participants.html', participants=participants, search=search)

@app.route('/participants/add', methods=['GET', 'POST'])
@role_required(['admin', 'super_admin'])
def add_participant():
    if request.method == 'POST':
        unique_id          = request.form['unique_id']
        name               = request.form['name']
        participant_type   = request.form['type']
        school             = request.form['school']
        grade              = request.form.get('grade', '')
        contact            = request.form['contact']
        emergency_contact  = request.form['emergency_contact']
        selected_events    = request.form.getlist('events')
        class_dept         = f"Grade {grade}" if grade else school

        existing = supabase.table('participants').select('id').eq('unique_id', unique_id).execute()
        if existing.data:
            events_list = supabase.table('events').select('id, name, event_date').order('event_date').execute().data
            flash('A participant with this Unique ID already exists!', 'error')
            return render_template('add_participant.html', events=events_list)

        result = supabase.table('participants').insert({
            'unique_id':         unique_id,
            'name':              name,
            'type':              participant_type,
            'class_dept':        class_dept,
            'school':            school,
            'contact':           contact,
            'emergency_contact': emergency_contact,
        }).execute()
        participant_id = result.data[0]['id']

        for event_id in selected_events:
            supabase.table('participant_events').insert({
                'participant_id': participant_id,
                'event_id':       int(event_id),
            }).execute()

        flash('Participant added and assigned to events successfully!', 'success')
        return redirect(url_for('participants'))

    events_list = supabase.table('events').select('id, name, event_date').order('event_date').execute().data
    return render_template('add_participant.html', events=events_list)

@app.route('/participants/<int:id>/edit', methods=['GET', 'POST'])
@role_required(['admin', 'super_admin'])
def edit_participant(id):
    if request.method == 'POST':
        unique_id         = request.form['unique_id']
        name              = request.form['name']
        participant_type  = request.form['type']
        school            = request.form['school']
        grade             = request.form.get('grade', '')
        contact           = request.form['contact']
        emergency_contact = request.form['emergency_contact']
        selected_events   = request.form.getlist('events')
        class_dept        = f"Grade {grade}" if grade else school

        supabase.table('participants').update({
            'unique_id':         unique_id,
            'name':              name,
            'type':              participant_type,
            'class_dept':        class_dept,
            'school':            school,
            'contact':           contact,
            'emergency_contact': emergency_contact,
        }).eq('id', id).execute()

        # Re-assign events
        supabase.table('participant_events').delete().eq('participant_id', id).execute()
        for event_id in selected_events:
            supabase.table('participant_events').insert({
                'participant_id': id,
                'event_id':       int(event_id),
            }).execute()

        flash('Participant updated successfully!', 'success')
        return redirect(url_for('participants'))

    participant   = supabase.table('participants').select('*').eq('id', id).execute().data[0]
    events_list   = supabase.table('events').select('id, name, event_date').order('event_date').execute().data
    assigned_rows = supabase.table('participant_events').select('event_id').eq('participant_id', id).execute().data
    assigned_events = [r['event_id'] for r in assigned_rows]
    return render_template('edit_participant.html', participant=participant,
                           events=events_list, assigned_events=assigned_events)

@app.route('/participants/<int:id>/delete', methods=['POST'])
@role_required(['admin', 'super_admin'])
def delete_participant(id):
    supabase.table('participants').delete().eq('id', id).execute()
    flash('Participant deleted successfully!', 'success')
    return redirect(url_for('participants'))

# Bulk upload
@app.route('/participants/bulk-upload')
@role_required(['admin', 'super_admin'])
def bulk_upload_participants():
    return render_template('bulk_upload_participants.html')

@app.route('/participants/bulk-upload/template')
@role_required(['admin', 'super_admin'])
def download_bulk_upload_template():
    df = pd.DataFrame({
        'unique_id':         ['STU001', 'STU002', 'STU003'],
        'name':              ['John Smith', 'Jane Doe', 'Bob Wilson'],
        'school':            ['School A', 'School B', 'School C'],
        'grade':             ['6', '7', '8'],
        'contact':           ['email@example.com', 'phone@example.com', 'other@example.com'],
        'emergency_contact': ['EC Name 1 - Phone 1', 'EC Name 2 - Phone 2', 'EC Name 3 - Phone 3'],
        'event_ids':         ['1,2', '2,3', '1,3'],
    })
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=participant_template.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/participants/bulk-upload/process', methods=['POST'])
@role_required(['admin', 'super_admin'])
def process_bulk_upload():
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('bulk_upload_participants'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('bulk_upload_participants'))

    if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
        return redirect(url_for('bulk_upload_participants'))

    added_count   = 0
    skipped_count = 0
    error_messages = []

    try:
        df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
        df.columns = df.columns.str.strip().str.lower()

        required_columns = ['unique_id', 'name', 'school']
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            flash(f'Missing required columns: {", ".join(missing)}', 'error')
            return redirect(url_for('bulk_upload_participants'))

        for index, row in df.iterrows():
            try:
                unique_id         = str(row.get('unique_id', '')).strip()
                name              = str(row.get('name', '')).strip()
                school            = str(row.get('school', '')).strip()
                grade             = str(row.get('grade', '')).strip()
                contact           = str(row.get('contact', '')).strip()
                emergency_contact = str(row.get('emergency_contact', '')).strip()
                event_ids_str     = str(row.get('event_ids', '')).strip()

                if not unique_id or not name or not school:
                    skipped_count += 1
                    error_messages.append(f'Row {index + 2}: Missing required fields')
                    continue

                existing = supabase.table('participants').select('id').eq('unique_id', unique_id).execute()
                if existing.data:
                    skipped_count += 1
                    error_messages.append(f'Row {index + 2}: Duplicate unique_id {unique_id}')
                    continue

                class_dept = f"Grade {grade}" if grade else school

                result = supabase.table('participants').insert({
                    'unique_id':         unique_id,
                    'name':              name,
                    'type':              'student',
                    'class_dept':        class_dept,
                    'school':            school,
                    'contact':           contact,
                    'emergency_contact': emergency_contact,
                }).execute()
                participant_id = result.data[0]['id']

                if event_ids_str:
                    event_ids = [eid.strip() for eid in event_ids_str.split(',') if eid.strip().isdigit()]
                    for eid in event_ids:
                        supabase.table('participant_events').insert({
                            'participant_id': participant_id,
                            'event_id':       int(eid),
                        }).execute()

                added_count += 1

            except Exception as e:
                skipped_count += 1
                error_messages.append(f'Row {index + 2}: {str(e)}')

        message = f'Successfully added {added_count} participants.'
        if skipped_count:
            message += f' Skipped {skipped_count} rows.'
        flash(message, 'success' if added_count > 0 else 'warning')

    except Exception as e:
        flash(f'Error processing file: {str(e)}', 'error')

    return redirect(url_for('bulk_upload_participants'))

# Assign participant from user account
@app.route('/events/<int:id>/assign_participant', methods=['POST'])
@role_required(['admin', 'super_admin'])
def assign_participant(id):
    user_id = request.form.get('user_id', type=int)
    if not user_id:
        flash('No student selected', 'error')
        return redirect(url_for('event_detail', id=id))

    event_result = supabase.table('events').select('id').eq('id', id).execute()
    if not event_result.data:
        flash('Event not found', 'error')
        return redirect(url_for('events'))

    user_result = supabase.table('users').select('*').eq('id', user_id).eq('role', 'student').execute()
    if not user_result.data:
        flash('Student user not found', 'error')
        return redirect(url_for('event_detail', id=id))

    user      = user_result.data[0]
    unique_id = f'user_{user["id"]}'

    participant_result = supabase.table('participants').select('id').eq('unique_id', unique_id).execute()
    if participant_result.data:
        participant_id = participant_result.data[0]['id']
    else:
        ins = supabase.table('participants').insert({
            'unique_id':         unique_id,
            'name':              user['username'],
            'type':              'student',
            'class_dept':        'Student',
            'school':            'Main School',
            'contact':           '',
            'emergency_contact': '',
        }).execute()
        participant_id = ins.data[0]['id']

    existing = (
        supabase.table('participant_events')
        .select('participant_id')
        .eq('participant_id', participant_id)
        .eq('event_id', id)
        .execute()
    )
    if existing.data:
        flash(f'{user["username"]} is already assigned to this event', 'warning')
        return redirect(url_for('event_detail', id=id))

    supabase.table('participant_events').insert({
        'participant_id': participant_id,
        'event_id':       id,
    }).execute()

    flash(f'{user["username"]} has been assigned as a participant!', 'success')
    return redirect(url_for('event_detail', id=id))


# ─────────────────────────────────────────────
# Duties CRUD
# ─────────────────────────────────────────────
@app.route('/duties')
@login_required
def duties():
    duties_rows = (
        supabase.table('duties')
        .select('*, events(name, event_date), duty_personnel(name, designation, school)')
        .order('duty_date')
        .execute()
        .data
    )
    duties = []
    for d in duties_rows:
        flat = {**d}
        if d.get('events'):
            flat['event_name'] = d['events']['name']
            flat['event_date'] = d['events']['event_date']
        if d.get('duty_personnel'):
            flat['person_name']  = d['duty_personnel']['name']
            flat['designation']  = d['duty_personnel']['designation']
            flat['school']       = d['duty_personnel']['school']
        duties.append(flat)

    events_list = supabase.table('events').select('id, name, event_date').order('event_date').execute().data
    duty_personnel = supabase.table('duty_personnel').select('id, name, designation').order('name').execute().data

    return render_template('duties.html', duties=duties, events=events_list,
                           duty_personnel=duty_personnel)

def _resolve_duty_person(user_id):
    """Get or create a duty_personnel record from a user id."""
    user = supabase.table('users').select('username, role').eq('id', user_id).execute().data[0]
    existing = supabase.table('duty_personnel').select('id').eq('name', user['username']).execute()
    if existing.data:
        return existing.data[0]['id']
    result = supabase.table('duty_personnel').insert({
        'name':        user['username'],
        'designation': user['role'].capitalize(),
        'school':      'Main School',
    }).execute()
    return result.data[0]['id']

@app.route('/duties/assign', methods=['GET', 'POST'])
@role_required(['admin', 'super_admin'])
def assign_duty():
    if request.method == 'POST':
        time_parts = request.form['time_slot'].split(' - ')
        start_time = time_parts[0].strip()
        end_time   = time_parts[1].strip() if len(time_parts) > 1 else start_time

        duty_person_id = _resolve_duty_person(request.form['user_id'])

        supabase.table('duties').insert({
            'event_id':       int(request.form['event_id']),
            'duty_person_id': duty_person_id,
            'duty_type':      request.form['duty_type'],
            'duty_date':      request.form['duty_date'],
            'start_time':     start_time,
            'end_time':       end_time,
            'location':       request.form['location'],
            'description':    request.form['description'],
            'notes':          request.form['notes'],
        }).execute()

        flash('Duty assigned successfully!', 'success')
        return redirect(url_for('duties'))

    events_list = supabase.table('events').select('id, name, event_date, venue, start_time, end_time').order('event_date').execute().data
    admins      = supabase.table('users').select('id, username, role').in_('role', ['admin', 'super_admin']).execute().data
    return render_template('add_duty.html', events=events_list, admins=admins)

@app.route('/duties/add', methods=['GET', 'POST'])
@role_required(['admin', 'super_admin'])
def add_duty():
    return assign_duty()

@app.route('/duties/<int:id>/edit', methods=['GET', 'POST'])
@role_required(['admin', 'super_admin'])
def edit_duty(id):
    if request.method == 'POST':
        time_parts = request.form['time_slot'].split(' - ')
        start_time = time_parts[0].strip()
        end_time   = time_parts[1].strip() if len(time_parts) > 1 else start_time
        duty_person_id = _resolve_duty_person(request.form['user_id'])

        supabase.table('duties').update({
            'event_id':       int(request.form['event_id']),
            'duty_person_id': duty_person_id,
            'duty_type':      request.form['duty_type'],
            'duty_date':      request.form['duty_date'],
            'start_time':     start_time,
            'end_time':       end_time,
            'location':       request.form['location'],
            'description':    request.form['description'],
            'notes':          request.form['notes'],
        }).eq('id', id).execute()

        flash('Duty updated successfully!', 'success')
        return redirect(url_for('duties'))

    duty        = supabase.table('duties').select('*').eq('id', id).execute().data[0]
    events_list = supabase.table('events').select('id, name, event_date, venue').order('event_date').execute().data
    admins      = supabase.table('users').select('id, username, role').in_('role', ['admin', 'super_admin']).execute().data

    person      = supabase.table('duty_personnel').select('name').eq('id', duty['duty_person_id']).execute().data[0]
    current_user = supabase.table('users').select('id').eq('username', person['name']).execute().data
    current_user_id = current_user[0]['id'] if current_user else None

    return render_template('edit_duty.html', duty=duty, events=events_list,
                           admins=admins, current_user_id=current_user_id)

@app.route('/duties/<int:id>/delete', methods=['POST'])
@role_required(['admin', 'super_admin'])
def delete_duty(id):
    supabase.table('duties').delete().eq('id', id).execute()
    flash('Duty deleted successfully!', 'success')
    return redirect(url_for('duties'))


# ─────────────────────────────────────────────
# Announcements
# ─────────────────────────────────────────────
@app.route('/announcements/add', methods=['POST'])
@role_required(['admin', 'super_admin'])
def add_announcement():
    supabase.table('announcements').insert({
        'title':      request.form.get('title', 'Event Update'),
        'content':    request.form['content'],
        'event_id':   int(request.form['event_id']),
        'created_by': session['user_id'],
    }).execute()
    flash('Message sent successfully!', 'success')
    return redirect(url_for('event_detail', id=request.form['event_id']))

@app.route('/announcements/<int:id>/delete', methods=['POST'])
@role_required(['admin', 'super_admin'])
def delete_announcement(id):
    supabase.table('announcements').delete().eq('id', id).execute()
    flash('Announcement deleted successfully!', 'success')
    return redirect(request.referrer or url_for('dashboard'))


# ─────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────
@app.route('/reports')
@login_required
def reports():
    is_student = session.get('role') == 'student'

    if is_student:
        my_p_result = (
            supabase.table('participants')
            .select('*')
            .eq('unique_id', f"user_{session['user_id']}")
            .execute()
            .data
        )
        my_participant = my_p_result[0] if my_p_result else None

        my_events = []
        my_duties = []
        if my_participant:
            event_rows = (
                supabase.table('participant_events')
                .select('events(*)')
                .eq('participant_id', my_participant['id'])
                .execute()
                .data
            )
            my_events = [r['events'] for r in event_rows if r.get('events')]

            duty_rows = (
                supabase.table('duties')
                .select('*, events(name)')
                .eq('duty_person_id',
                    supabase.table('duty_personnel').select('id').eq('name', session['username']).execute().data[0]['id']
                    if supabase.table('duty_personnel').select('id').eq('name', session['username']).execute().data
                    else -1)
                .order('duty_date', desc=True)
                .execute()
                .data
            )
            for d in duty_rows:
                flat = {**d}
                flat['event_name'] = d['events']['name'] if d.get('events') else ''
                my_duties.append(flat)

        return render_template('reports.html',
                               is_student=is_student,
                               my_participant=my_participant,
                               my_events=my_events,
                               my_duties=my_duties)

    # Admin view — aggregate stats
    total_events       = supabase.table('events').select('id', count='exact').execute().count
    total_participants = supabase.table('participants').select('id', count='exact').execute().count
    total_duties       = supabase.table('duties').select('id', count='exact').execute().count

    # Event types breakdown
    all_events  = supabase.table('events').select('type').execute().data
    type_counts = {}
    for e in all_events:
        type_counts[e['type']] = type_counts.get(e['type'], 0) + 1
    event_types = [{'type': k, 'count': v} for k, v in sorted(type_counts.items(), key=lambda x: -x[1])]

    # Monthly events (last 12 months)
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=365)).isoformat()
    recent_events = (
        supabase.table('events')
        .select('event_date')
        .gte('event_date', cutoff)
        .execute()
        .data
    )
    month_counts = {}
    for e in recent_events:
        ym = e['event_date'][:7]
        month_counts[ym] = month_counts.get(ym, 0) + 1
    monthly_events = [{'month': k, 'count': v} for k, v in sorted(month_counts.items())]

    # Top schools by participants
    all_participants = supabase.table('participants').select('school').execute().data
    school_counts = {}
    for p in all_participants:
        school_counts[p['school']] = school_counts.get(p['school'], 0) + 1
    top_schools = [{'school': k, 'count': v}
                   for k, v in sorted(school_counts.items(), key=lambda x: -x[1])[:10]]

    # Duty type stats
    all_duties = supabase.table('duties').select('duty_type').execute().data
    duty_counts = {}
    for d in all_duties:
        duty_counts[d['duty_type']] = duty_counts.get(d['duty_type'], 0) + 1
    duty_stats = [{'duty_type': k, 'count': v} for k, v in duty_counts.items()]

    return render_template('reports.html',
                           is_student=is_student,
                           total_events=total_events,
                           total_participants=total_participants,
                           total_duties=total_duties,
                           event_types=event_types,
                           monthly_events=monthly_events,
                           top_schools=top_schools,
                           duty_stats=duty_stats)


# ─────────────────────────────────────────────
# Export routes
# ─────────────────────────────────────────────
def _csv_response(rows, headers, key_fn, filename):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(key_fn(row))
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-Type'] = 'text/csv'
    return response

@app.route('/reports/export')
@role_required(['admin', 'super_admin'])
def export_reports():
    events       = supabase.table('events').select('*').order('event_date').execute().data
    participants = supabase.table('participants').select('*').order('name').execute().data
    duties_raw   = (
        supabase.table('duties')
        .select('*, events(name), duty_personnel(name)')
        .order('duty_date')
        .execute()
        .data
    )

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(['Events Report'])
    writer.writerow(['ID', 'Name', 'Type', 'Date', 'Start Time', 'End Time', 'Venue', 'Host School'])
    for e in events:
        writer.writerow([e['id'], e['name'], e['type'], e['event_date'],
                         e['start_time'], e['end_time'], e['venue'], e['host_school']])

    writer.writerow([])
    writer.writerow(['Participants Report'])
    writer.writerow(['ID', 'Unique ID', 'Name', 'Type', 'Class/Dept', 'School', 'Contact'])
    for p in participants:
        writer.writerow([p['id'], p['unique_id'], p['name'], p['type'],
                         p['class_dept'], p['school'], p['contact']])

    writer.writerow([])
    writer.writerow(['Duties Report'])
    writer.writerow(['ID', 'Event Name', 'Person Name', 'Duty Type', 'Date', 'Time', 'Location'])
    for d in duties_raw:
        writer.writerow([d['id'],
                         d['events']['name'] if d.get('events') else '',
                         d['duty_personnel']['name'] if d.get('duty_personnel') else '',
                         d['duty_type'], d['duty_date'],
                         f"{d['start_time']} - {d['end_time']}", d['location']])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=event_reports.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

@app.route('/export/events')
@role_required(['admin', 'super_admin'])
def export_events():
    events = supabase.table('events').select('*').order('event_date').execute().data
    return _csv_response(
        events,
        ['ID', 'Name', 'Type', 'Date', 'Start Time', 'End Time', 'Venue', 'Host School', 'Description'],
        lambda e: [e['id'], e['name'], e['type'], e['event_date'],
                   e['start_time'], e['end_time'], e['venue'], e['host_school'], e['description']],
        'events.csv'
    )

@app.route('/export/participants')
@role_required(['admin', 'super_admin'])
def export_participants():
    participants = supabase.table('participants').select('*').order('name').execute().data
    return _csv_response(
        participants,
        ['ID', 'Unique ID', 'Name', 'Type', 'Class/Dept', 'School', 'Contact'],
        lambda p: [p['id'], p['unique_id'], p['name'], p['type'],
                   p['class_dept'], p['school'], p['contact']],
        'participants.csv'
    )

@app.route('/export/duties')
@role_required(['admin', 'super_admin'])
def export_duties():
    duties = (
        supabase.table('duties')
        .select('*, events(name), duty_personnel(name)')
        .order('duty_date')
        .execute()
        .data
    )
    return _csv_response(
        duties,
        ['ID', 'Event Name', 'Person Name', 'Duty Type', 'Date', 'Start Time', 'End Time', 'Location'],
        lambda d: [d['id'],
                   d['events']['name'] if d.get('events') else '',
                   d['duty_personnel']['name'] if d.get('duty_personnel') else '',
                   d['duty_type'], d['duty_date'], d['start_time'], d['end_time'], d['location']],
        'duties.csv'
    )

@app.route('/export/teachers')
@role_required(['admin', 'super_admin'])
def export_teachers():
    teachers = (
        supabase.table('duty_personnel')
        .select('*')
        .in_('designation', ['Teacher', 'Staff'])
        .order('name')
        .execute()
        .data
    )
    return _csv_response(
        teachers,
        ['ID', 'Name', 'Designation', 'Contact', 'School'],
        lambda t: [t['id'], t['name'], t['designation'], t['contact'], t['school']],
        'teachers.csv'
    )


# ─────────────────────────────────────────────
# User management
# ─────────────────────────────────────────────
@app.route('/manage_users')
@role_required(['super_admin'])
def manage_users():
    users = (
        supabase.table('users')
        .select('id, username, role')
        .neq('role', 'super_admin')
        .execute()
        .data
    )
    return render_template('manage_users.html', users=users)

@app.route('/promote_user/<int:user_id>/<string:role>')
@role_required(['super_admin'])
def promote_user(user_id, role):
    if role not in ['admin', 'student']:
        flash('Invalid role', 'error')
        return redirect(url_for('manage_users'))
    supabase.table('users').update({'role': role}).eq('id', user_id).execute()
    flash(f'User role updated to {role}', 'success')
    return redirect(url_for('manage_users'))

@app.route('/delete_all_data', methods=['POST'])
@role_required(['super_admin'])
def delete_all_data():
    try:
        supabase.table('duties').delete().neq('id', 0).execute()
        supabase.table('duty_personnel').delete().neq('id', 0).execute()
        supabase.table('participant_events').delete().neq('participant_id', 0).execute()
        supabase.table('participants').delete().neq('id', 0).execute()
        supabase.table('announcements').delete().neq('id', 0).execute()
        supabase.table('events').delete().neq('id', 0).execute()
        supabase.table('users').delete().neq('role', 'super_admin').execute()
        return jsonify({'success': True, 'message': 'All data has been deleted successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ─────────────────────────────────────────────
# API endpoints
# ─────────────────────────────────────────────
@app.route('/api/events')
@login_required
def api_events():
    events = supabase.table('events').select('*').order('event_date').execute().data
    return jsonify(events)

@app.route('/api/participants')
@login_required
def api_participants():
    participants = supabase.table('participants').select('*').execute().data
    return jsonify(participants)

@app.route('/api/duties')
@login_required
def api_duties():
    duties = (
        supabase.table('duties')
        .select('*, events(name), duty_personnel(name)')
        .execute()
        .data
    )
    flat = []
    for d in duties:
        row = {**d}
        row['event_name']  = d['events']['name'] if d.get('events') else ''
        row['person_name'] = d['duty_personnel']['name'] if d.get('duty_personnel') else ''
        flat.append(row)
    return jsonify(flat)

@app.route('/api/search_students')
@role_required(['admin', 'super_admin'])
def search_students():
    query    = request.args.get('q', '').strip()
    event_id = request.args.get('event_id', type=int)

    q = supabase.table('users').select('id, username').eq('role', 'student')
    if query:
        q = q.ilike('username', f'%{query}%')
    students = q.order('username').limit(20).execute().data

    results = []
    for s in students:
        already_assigned = False
        if event_id:
            participant = supabase.table('participants').select('id').eq('unique_id', f'user_{s["id"]}').execute().data
            if participant:
                pe = (
                    supabase.table('participant_events')
                    .select('participant_id')
                    .eq('participant_id', participant[0]['id'])
                    .eq('event_id', event_id)
                    .execute()
                    .data
                )
                already_assigned = bool(pe)
        results.append({'id': s['id'], 'username': s['username'], 'already_assigned': already_assigned})

    return jsonify(results)

@app.route('/api/scan-event', methods=['POST'])
@login_required
def scan_event():
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from ai_event import EventExtractor

        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            file.save(tmp_file.name)
            temp_path = tmp_file.name

        try:
            extractor = EventExtractor()
            result    = extractor.extract_event_info(temp_path)
            os.unlink(temp_path)

            if result.get('error'):
                return jsonify({'error': result['error']}), 500

            return jsonify({'success': True, 'event': {
                'name':        result.get('event_name', 'Untitled Event'),
                'venue':       result.get('location', ''),
                'event_date':  result.get('date', ''),
                'start_time':  result.get('time', ''),
                'description': result.get('additional_info', ''),
                'confidence':  result.get('confidence', 'medium'),
            }})
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return jsonify({'error': f'Processing error: {str(e)}'}), 500

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500


# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)