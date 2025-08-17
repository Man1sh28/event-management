# School Event Management System

A comprehensive web-based portal for managing interschool events, tracking participants (students and teachers), and assigning duties. Built with Python Flask, SQLite, HTML, CSS, and JavaScript.

## Features

### 🎯 Core Functionality
- **Event Management**: Create, edit, and track interschool events
- **Participant Tracking**: Manage students and teachers from different schools
- **Duty Assignment**: Assign and track duties for events
- **Dashboard Analytics**: Real-time insights and statistics
- **Comprehensive Reports**: Export data in various formats

### 📊 Dashboard & Analytics
- Real-time statistics display
- Events by type visualization
- Participant distribution charts
- Upcoming events timeline
- Top participating schools ranking

### 🔍 Advanced Features
- **Search & Filter**: Advanced filtering for events, participants, and duties
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Export Functionality**: Export reports as CSV/JSON
- **Data Validation**: Comprehensive form validation
- **User-Friendly Interface**: Intuitive navigation and clean design

## Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, Bootstrap 5
- **Charts**: Chart.js for data visualization
- **Icons**: Font Awesome
- **JavaScript**: Vanilla JS for interactivity

## Installation & Setup

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Quick Start

1. **Clone or download the project** to your local machine

2. **Install dependencies**:
   ```bash
   pip install flask
   ```

3. **Run the application**:
   ```bash
   python3 app.py
   ```

4. **Access the application**:
   - Open your web browser
   - Navigate to `http://localhost:8000`

## Database Structure

The system uses SQLite with the following tables:

### Events Table
- `id`: Primary key
- `name`: Event name
- `type`: Event type (sports, cultural, academic, technical, other)
- `event_date`: Date of the event
- `start_time`, `end_time`: Event duration
- `venue`: Event location
- `host_school`: School hosting the event
- `participating_schools`: Comma-separated list of participating schools (for sport tournaments)
- `description`: Event description

### Participants Table
- `id`: Primary key
- `name`: Participant's full name
- `type`: 'student' or 'teacher'
- `school`: School/institution name
- `grade`: Student's grade (if applicable)
- `designation`: Teacher's designation (if applicable)
- `email`: Contact email
- `phone`: Contact phone number
- `emergency_contact`: Emergency contact information

### Duties Table
- `id`: Primary key
- `event_id`: Foreign key to events
- `participant_id`: Foreign key to participants
- `duty_type`: Type of duty assigned
- `duty_date`: Date of duty
- `start_time`, `end_time`: Duty duration
- `location`: Duty location
- `description`: Duty description
- `notes`: Additional notes
- `status`: 'assigned', 'completed', or 'cancelled'

## Usage Guide

### Managing Events
1. **Add New Event**: Click "Add New Event" from the Events page
2. **Edit Event**: Click the edit button on any event card
3. **Delete Event**: Click the delete button (with confirmation)
4. **Filter Events**: Use the filter dropdown and search box

### Managing Participants
1. **Add Participant**: Click "Add Participant" from the Participants page
2. **Participant Types**: Choose between Student or Teacher
3. **Required Fields**: Name, type, and school are mandatory
4. **Contact Info**: Optional email and phone fields

### Assigning Duties
1. **Create Duty**: Click "Assign Duty" from the Duties page
2. **Select Event**: Choose from available events
3. **Assign Person**: Select participant from dropdown
4. **Set Schedule**: Define date, time, and location
5. **Track Status**: Monitor assigned duties

### Reports & Analytics
1. **View Dashboard**: Access comprehensive statistics
2. **Visual Charts**: Interactive charts for data visualization
3. **Export Data**: Download reports in CSV format
4. **Filter Reports**: Customize reports by date ranges and categories

## Screens Overview

### 1. Dashboard
- **Overview**: Total events, participants, duties, and schools
- **Quick Actions**: Direct links to add events, participants, and duties
- **Upcoming Events**: Timeline of upcoming activities

### 2. Events Management
- **Event List**: Grid view of all events
- **Event Details**: Comprehensive event information
- **Search & Filter**: Find events by type, date, or name

### 3. Participants Management
- **Participant List**: Table view with sorting capabilities
- **Participant Profiles**: Detailed participant information
- **Type Filtering**: Filter by students or teachers

### 4. Duties & Assignments
- **Duty Calendar**: View all assigned duties
- **Assignment Details**: Track duty status and progress
- **Filter Options**: Filter by event, duty type, or person

### 5. Reports & Analytics
- **Visual Charts**: Pie charts, bar charts, and line graphs
- **Statistics**: Real-time metrics and KPIs
- **Export Options**: Download data for further analysis

## API Endpoints

### Events
- `GET /` - Dashboard
- `GET /events` - List all events
- `GET /add_event` - Add event form
- `POST /add_event` - Create new event
- `GET /edit_event/<id>` - Edit event form
- `POST /edit_event/<id>` - Update event
- `POST /delete_event/<id>` - Delete event

### Participants
- `GET /participants` - List all participants
- `GET /add_participant` - Add participant form
- `POST /add_participant` - Create new participant
- `GET /edit_participant/<id>` - Edit participant form
- `POST /edit_participant/<id>` - Update participant
- `POST /delete_participant/<id>` - Delete participant

### Duties
- `GET /duties` - List all duties
- `GET /add_duty` - Assign duty form
- `POST /add_duty` - Create new duty
- `GET /edit_duty/<id>` - Edit duty form
- `POST /edit_duty/<id>` - Update duty
- `POST /delete_duty/<id>` - Delete duty

### Reports
- `GET /reports` - Analytics dashboard
- `GET /export/<type>` - Export data (events, participants, duties)

## File Structure

project-folder/
│── __pycache__/
│   └── app.cpython-313.pyc
│
│── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│
│── templates/
│   ├── add_calendar_event.html
│   ├── add_duty.html
│   ├── add_event.html
│   ├── add_participant.html
│   ├── base.html
│   ├── calendar.html
│   ├── dashboard.html
│   ├── day_events.html
│   ├── duties.html
│   ├── edit_duty.html
│   ├── edit_event.html
│   ├── edit_participant.html
│   ├── events.html
│   ├── participants.html
│   └── reports.html
│
│── app.py
│── events.db
│── index.html
│── README.md
│── Untitled-1.py


## Customization

### Adding New Event Types
Edit the event type dropdown in `templates/add_event.html` and update the validation in `app.py`.

### Modifying Database Schema
Update the table schemas in `init_db.py` and run it to recreate the database.

### Styling Changes
Modify `static/css/style.css` to customize the appearance.

## Troubleshooting

### Common Issues
1. **Port 8001 in use**: Change the port in `app.py`
2. **Database errors**: Delete `school_events.db` and restart the app
3. **Missing dependencies**: Run `pip install flask`
4. **Permission errors**: Ensure proper file permissions

### Performance Tips
- Use production WSGI server (gunicorn, uWSGI) for deployment
- Implement caching for frequently accessed data
- Use database indexing for large datasets

## Support

For questions or issues:
1. Check the browser console for JavaScript errors
2. Review the Flask logs in the terminal
3. Ensure all dependencies are properly installed
4. Verify database connectivity

## License

This project is open-source and available for educational and commercial use.

---

**Happy Event Management!** 🎉

The system is now ready to use. Access it at `http://localhost:8001` in your web browser.