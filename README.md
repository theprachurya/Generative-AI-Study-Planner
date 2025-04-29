# AI Assisted Study Planner

An intelligent study planning application that leverages Google's Generative AI to create personalized study schedules based on user preferences and academic goals.

## Features

* **Smart Schedule Generation**
  * AI-powered study schedule creation
  * Personalized learning guides
  * Subject-specific resource recommendations
  * Calendar view of study plans
  * Downloadable study plans

* **User Customization**
  * Subject selection and duration
  * Learning goals and preferences
  * Study hours and off-days
  * Class schedule integration
  * Difficulty level perception

* **User Interface**
  * Clean, modern design
  * Dark mode support
  * Responsive layout
  * Interactive calendar view
  * Easy plan management

## Tech Stack

* **Backend:**
  * Python 3.x
  * Flask web framework
  * Google Gemini AI API
  * SQLite database

* **Frontend:**
  * HTML5
  * CSS3
  * JavaScript
  * Jinja2 templating

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone [repository-url]
   cd ai-planner
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory with:
   ```
   FLASK_SECRET_KEY=your_secret_key #Generate a secret key locally
   GEMINI_API_KEY=your_gemini_api_key #Obtain your key from Google AI Studio
   ```

5. **Initialize the database**
   ```bash
   flask init-db
   ```

6. **Run the application**
   ```bash
   flask run
   ```

## Project Structure

```
generative-ai-study-planner/
├── app.py              # Main application file
├── requirements.txt    # Python dependencies
├── database/          # Database files and schema
├── static/           # Static assets (CSS, JS, images)
├── templates/        # HTML templates
└── .env             # Environment variables (create this)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 