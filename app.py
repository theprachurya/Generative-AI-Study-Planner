from flask import Flask, render_template, request, redirect, url_for, g, flash
import sqlite3
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import re
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
load_dotenv()

# Configure logging
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/ai-planner.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'database', 'planner.db')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# Add security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        app.logger.info("Gemini API Key configured successfully.")
    except Exception as e:
        app.logger.error(f"Error configuring Gemini API: {e}")
else:
    app.logger.warning("GEMINI_API_KEY not found in environment variables. AI features will be disabled.")

# Add ProxyFix middleware for proper handling of proxy headers
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# --- Add custom date filter for Jinja2 ---
@app.template_filter('date')
def date_filter(value, format='%Y-%m-%d'):
    if value == 'now':
        return datetime.now().strftime(format)
    if isinstance(value, datetime):
        return value.strftime(format)
    return value

# --- Add context processor to make current datetime available to all templates ---
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# --- Database Helper Functions ---

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')
    with open(schema_path, 'r') as f:
        db.executescript(f.read())

@app.cli.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    # Check if DB exists, delete if it does to ensure clean init
    if os.path.exists(app.config['DATABASE']):
        os.remove(app.config['DATABASE'])
        print('Deleted existing database.')
    # Ensure the database directory exists
    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
    # Initialize DB
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.close()
    # Run init script
    with app.app_context():
        init_db()
    print('Initialized the database.')

app.teardown_appcontext(close_db)

# --- Routes ---

@app.route('/')
def index():
    plans_exist = False
    try:
        db = get_db()
        # Check if there's at least one plan
        count = db.execute('SELECT COUNT(id) FROM plans').fetchone()[0]
        if count > 0:
            plans_exist = True
    except sqlite3.Error as e:
        print(f"Database error checking for plans: {e}")
        flash("Error checking for existing plans.", "danger")

    return render_template('index.html', plans_exist=plans_exist)

def extract_json_from_text(text):
    """Attempt to extract valid JSON from text - handles cases where model might add extra content."""
    
    # First try to parse the entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # If that fails, try to extract JSON object using regex
        json_pattern = r'(\{[\s\S]*\})' # Match {...} including newlines
        matches = re.findall(json_pattern, text)
        
        # Try each match from longest to shortest (assume larger match is more complete)
        matches.sort(key=len, reverse=True)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
                
        # If no valid JSON found, create a structured object with the text
        return {
            "extraction_error": "Could not extract valid JSON",
            "raw_text": text
        }

def generate_fallback_schedule(form_data):
    """Generate a simple fallback schedule when AI fails to provide valid JSON."""
    start_date = datetime.strptime(form_data['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(form_data['end_date'], '%Y-%m-%d')
    hours_per_day = form_data['hours_per_day']
    subjects = form_data['subjects'].split(',')
    off_days_list = form_data.getlist('off_days') if isinstance(form_data.get('off_days'), list) else \
                    form_data.get('off_days', '').split(',') if form_data.get('off_days') else []
    
    # Generate simple schedule
    schedule = {}
    current_date = start_date
    day_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        current_day = day_of_week[current_date.weekday()]
        
        # Check if current day is an off day
        if current_day in off_days_list or 'all' in off_days_list:
            schedule[date_str] = []
        else:
            # Simple distribution of subjects
            schedule[date_str] = []
            subject_index = 0
            study_blocks = []
            
            # Create a simple 2-hour block for each subject, up to hours_per_day
            try:
                hours = int(hours_per_day)
                remaining_hours = hours
                start_hour = 9  # Default start at 9 AM
                
                while remaining_hours > 0 and subject_index < len(subjects):
                    block_hours = min(2, remaining_hours)  # 2-hour blocks or remaining time
                    
                    study_blocks.append({
                        "start_time": f"{start_hour:02d}:00",
                        "end_time": f"{start_hour + block_hours:02d}:00",
                        "subject": subjects[subject_index].strip(),
                        "task": f"Study {subjects[subject_index].strip()}"
                    })
                    
                    start_hour += block_hours
                    remaining_hours -= block_hours
                    subject_index = (subject_index + 1) % len(subjects)
                
                schedule[date_str] = study_blocks
            except (ValueError, TypeError):
                # If hours_per_day is invalid, create a simple default block
                schedule[date_str] = [{
                    "start_time": "09:00",
                    "end_time": "12:00",
                    "subject": subjects[0].strip() if subjects else "Study",
                    "task": "General study session"
                }]
        
        current_date = datetime.fromordinal(current_date.toordinal() + 1)
    
    return schedule

def parse_subject_marks(marks_text):
    """Parse the complex subject marks format into a structured format."""
    if not marks_text:
        return []
    
    marks_data = []
    current_subject = None
    current_component = None
    
    lines = marks_text.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
            
        # New subject
        if not current_subject:
            current_subject = line
            i += 1
            continue
            
        # Component type
        if not current_component:
            current_component = line
            i += 1
            continue
            
        # Assessment and marks
        if '/' in line:
            assessment, max_marks = line.split('/')
            obtained_marks = float(lines[i + 1].strip())
            
            marks_data.append({
                'subject_name': current_subject,
                'component_type': current_component,
                'assessment_name': assessment,
                'max_marks': float(max_marks),
                'obtained_marks': obtained_marks
            })
            
            i += 2
        else:
            i += 1
            
        # Reset for next subject if we've reached the end of current subject's data
        if i >= len(lines) or not lines[i].strip():
            current_subject = None
            current_component = None
            i += 1
            
    return marks_data

def generate_ai_response(prompt):
    """Generate AI response using Gemini API."""
    if not GEMINI_API_KEY:
        return {
            'learning_guide': "AI generation skipped: API key not configured.",
            'schedule': {},
            'resources': "AI generation skipped: API key not configured."
        }
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        print("--- Sending Prompt to Gemini ---")
        response = model.generate_content(prompt)
        print("--- Received Response from Gemini ---")
        
        # Process the response
        try:
            ai_output = extract_json_from_text(response.text)
            
            if "learning_guide" in ai_output and "resources" in ai_output and "schedule" in ai_output:
                return {
                    'learning_guide': ai_output['learning_guide'],
                    'schedule': ai_output['schedule'],
                    'resources': ai_output['resources']
                }
            else:
                print("JSON extraction failed, using fallback schedule")
                return {
                    'learning_guide': "AI guide extraction failed. Please review the schedule for any available guidance.",
                    'schedule': generate_fallback_schedule(request.form),
                    'resources': "AI resources extraction failed. Consider using standard study resources for your subjects."
                }
                
        except Exception as e:
            print(f"Error processing AI response: {e}")
            return {
                'learning_guide': "Error during AI generation (Processing failed).",
                'schedule': generate_fallback_schedule(request.form),
                'resources': "AI generation failed. Consider using standard study resources for your subjects."
            }
            
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return {
            'learning_guide': f"AI generation failed: {e}",
            'schedule': generate_fallback_schedule(request.form),
            'resources': f"AI generation failed. Consider using standard study resources for your subjects."
        }

@app.route('/generate', methods=['GET', 'POST'])
def generate_plan():
    if request.method == 'POST':
        try:
            # Get form data
            title = request.form['title']
            description = request.form['description']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            subjects = request.form['subjects']
            learning_goal = request.form['learning_goal']
            difficulty_feedback = request.form['difficulty_feedback']
            hours_per_day = request.form['hours_per_day']
            off_days = request.form.get('off_days', '')
            class_schedule = request.form.get('class_schedule', '')
            
            # Parse subject marks
            marks_text = request.form.get('subject_marks', '')
            marks_data = parse_subject_marks(marks_text)
            
            # Calculate average marks for each subject
            subject_averages = {}
            for mark in marks_data:
                subject = mark['subject_name']
                if subject not in subject_averages:
                    subject_averages[subject] = {'total_obtained': 0, 'total_max': 0}
                subject_averages[subject]['total_obtained'] += mark['obtained_marks']
                subject_averages[subject]['total_max'] += mark['max_marks']
            
            # Format marks for AI prompt
            marks_summary = []
            for subject, data in subject_averages.items():
                percentage = (data['total_obtained'] / data['total_max']) * 100
                marks_summary.append(f"{subject}: {percentage:.1f}%")
            
            # Sort subjects by performance (lowest first)
            sorted_subjects = sorted(subject_averages.items(), 
                                  key=lambda x: (x[1]['total_obtained'] / x[1]['total_max']))
            
            # Generate AI prompt
            prompt = f"""
            Generate a personalized study plan based on the following details.
            Please provide the output STRICTLY in JSON format with three main keys: "learning_guide", "resources", and "schedule".

            **Plan Details:**
            - Title: {title}
            - Description: {description}
            - Duration: {start_date} to {end_date}
            - Subjects: {subjects}
            - Previous Exam Performance: {', '.join(marks_summary) if marks_summary else 'Not provided'}
            - Subject Performance Ranking (from lowest to highest):
              {', '.join([f"{subject}: {data['total_obtained']/data['total_max']*100:.1f}%" for subject, data in sorted_subjects]) if sorted_subjects else 'Not provided'}
            - Learning Goal: {learning_goal}
            - Subject Confidence/Difficulty: {difficulty_feedback}
            - Target Study Hours Per Day: {hours_per_day}
            - Days Off (No Studying): {off_days if off_days else 'None'}
            - Existing Class/Fixed Schedule: {class_schedule if class_schedule else 'None'}

            **Output Requirements:**

            1.  **learning_guide**: (String) A concise, step-by-step guide outlining a study strategy. Focus on how to approach the subjects based on the provided confidence levels and previous marks. IMPORTANT: Prioritize subjects with lower marks and provide specific improvement strategies for them. Include actionable advice for each subject, with more detailed guidance for subjects with lower performance.

            2.  **resources**: (String) A list of relevant learning resources (like specific websites, concepts to search on YouTube, types of practice problems, or book recommendations if applicable) for the subjects listed. Format this as a simple bulleted list or paragraphs within the string. Prioritize resources that address weaker areas, with more resources suggested for subjects with lower marks.

            3.  **schedule**: (JSON Object) A day-by-day schedule from {start_date} to {end_date}
                - "start_time": (String) Estimated start time (e.g., "09:00").
                - "end_time": (String) Estimated end time (e.g., "11:00").
                - "subject": (String) The subject to study.
                - "task": (String) A specific task or topic for that block (e.g., "Read Chapter 3", "Practice calculus problems", "Review lecture notes").
                IMPORTANT: Allocate more study time to subjects with lower marks. The schedule should reflect this priority by:
                - Assigning more time blocks to subjects with lower performance
                - Scheduling more frequent review sessions for weaker subjects
                - Including more practice problems and revision tasks for subjects with lower marks
                Factor in the `hours_per_day`, `off_days`, and `class_schedule`. Keep tasks focused and aligned with improvement needs.
                Example for one day: "YYYY-MM-DD": [ {{"start_time": "10:00", "end_time": "12:00", "subject": "Math", "task": "Practice integration techniques"}}, {{"start_time": "14:00", "end_time": "15:30", "subject": "Physics", "task": "Review kinematics concepts"}} ]
                If a day is an off_day, the value should be an empty array: "YYYY-MM-DD": []

            **Important:** Your response must be a valid JSON object with ONLY these three keys. Do not include any explanatory text, markdown formatting, or code blocks. Just return the raw JSON object.
            """
            
            # Generate AI response and get JSON output
            ai_response = generate_ai_response(prompt)
            
            # Save to database
            db = get_db()
            cursor = db.cursor()
            
            # Insert plan
            cursor.execute('''
                INSERT INTO plans (title, description, start_date, end_date, subjects, learning_goal, 
                                 difficulty_feedback, hours_per_day, off_days, class_schedule, 
                                 generated_guide, generated_schedule, resources)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, description, start_date, end_date, subjects, learning_goal,
                  difficulty_feedback, hours_per_day, off_days, class_schedule,
                  ai_response['learning_guide'], json.dumps(ai_response['schedule']),
                  ai_response['resources']))
            
            plan_id = cursor.lastrowid
            
            # Insert subject marks
            for mark in marks_data:
                cursor.execute('''
                    INSERT INTO subject_marks (plan_id, subject_name, component_type, 
                                             assessment_name, max_marks, obtained_marks)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (plan_id, mark['subject_name'], mark['component_type'],
                      mark['assessment_name'], mark['max_marks'], mark['obtained_marks']))
            
            db.commit()
            flash("Study plan generated successfully!", "success")
            return redirect(url_for('view_plan', plan_id=plan_id))
            
        except Exception as e:
            print(f"Error generating plan: {e}")
            flash(f"An error occurred while generating the plan: {e}", "danger")
            return render_template('generate.html')
    
    return render_template('generate.html')

@app.route('/plans')
def list_plans():
    db = get_db()
    plans = db.execute('SELECT id, title, start_date, end_date FROM plans ORDER BY id DESC').fetchall()
    return render_template('plans.html', plans=plans)

@app.route('/plan/<int:plan_id>')
def view_plan(plan_id):
    plan = None
    try:
        db = get_db()
        plan = db.execute(
            'SELECT * FROM plans WHERE id = ?', (plan_id,)
        ).fetchone()
    except sqlite3.Error as e:
        print(f"Database error fetching plan {plan_id}: {e}")
        flash(f"Error retrieving plan details: {e}", "danger")

    if plan is None:
        flash("Study plan not found.", "warning")
        return redirect(url_for('list_plans')) # Redirect if plan doesn't exist

    # Process generated_schedule for calendar view
    calendar_data = {}
    schedule_json_string = plan['generated_schedule']
    is_raw_schedule = False # Flag to indicate if schedule is not valid JSON

    if schedule_json_string:
        try:
            calendar_data = json.loads(schedule_json_string)
            if not isinstance(calendar_data, dict):
                 # If it's valid JSON but not a dict (e.g., just a string), treat as raw
                 print(f"Parsed schedule for plan {plan_id} is not a dictionary, treating as raw.")
                 calendar_data = {}
                 is_raw_schedule = True
            # print(f"Successfully parsed schedule JSON for plan {plan_id}")
        except json.JSONDecodeError:
            print(f"Could not parse schedule JSON for plan {plan_id}, treating as raw text.")
            calendar_data = {}
            is_raw_schedule = True # Keep the raw string for display
    else:
        print(f"Schedule data is empty for plan {plan_id}.")

    return render_template('plan.html', plan=plan, calendar_data=calendar_data, schedule_raw=schedule_json_string if is_raw_schedule else None)

@app.route('/fix-schedule/<int:plan_id>', methods=['POST'])
def fix_schedule(plan_id):
    """Attempt to fix invalid JSON in schedule data"""
    try:
        db = get_db()
        plan = db.execute('SELECT generated_schedule FROM plans WHERE id = ?', (plan_id,)).fetchone()
        
        if not plan:
            flash("Plan not found", "danger")
            return redirect(url_for('list_plans'))
            
        raw_schedule = plan['generated_schedule']
        
        # Try to identify and fix common JSON issues using our improved function
        try:
            extracted_json = extract_json_from_text(raw_schedule)
            
            if "schedule" in extracted_json:
                # We found a full JSON object with schedule
                fixed_json = extracted_json["schedule"]
                db.execute(
                    'UPDATE plans SET generated_schedule = ? WHERE id = ?',
                    (json.dumps(fixed_json), plan_id)
                )
                db.commit()
                flash("Successfully extracted and fixed JSON schedule data!", "success")
            elif not "extraction_error" in extracted_json:
                # We found some valid JSON but not with the expected structure
                db.execute(
                    'UPDATE plans SET generated_schedule = ? WHERE id = ?',
                    (json.dumps(extracted_json), plan_id)
                )
                db.commit()
                flash("JSON structure was fixed, but might not have the expected schedule format.", "warning")
            else:
                # Generate a fallback schedule based on plan data
                plan_data = db.execute('SELECT * FROM plans WHERE id = ?', (plan_id,)).fetchone()
                
                # Create a dict to mimic the form data structure
                form_data = {
                    'start_date': plan_data['start_date'],
                    'end_date': plan_data['end_date'],
                    'subjects': plan_data['subjects'],
                    'hours_per_day': plan_data['hours_per_day'],
                    'off_days': plan_data['off_days'].split(',') if plan_data['off_days'] else []
                }
                
                fallback_schedule = generate_fallback_schedule(form_data)
                db.execute(
                    'UPDATE plans SET generated_schedule = ? WHERE id = ?',
                    (json.dumps(fallback_schedule), plan_id)
                )
                db.commit()
                flash("Generated a new schedule based on your plan details.", "success")
                
        except Exception as e:
            flash(f"Could not fix JSON: {e}", "danger")
            
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "danger")
        
    return redirect(url_for('view_plan', plan_id=plan_id))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db = get_db()
    db.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Ensure the database directory exists before running
    db_dir = os.path.dirname(app.config['DATABASE'])
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Created database directory: {db_dir}")

    # Recommend running init-db manually first
    if not os.path.exists(app.config['DATABASE']):
        print("Database file not found. Run 'flask init-db' to initialize.")

    app.run(debug=True)