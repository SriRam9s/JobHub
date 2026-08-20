import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from database import get_db_connection

app = Flask(__name__)

# Secret key is required for sessions and flash messages
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "job_portal_secret_key_2026"
)

bcrypt = Bcrypt(app)


# ================= HOME =================

@app.route("/")
def home():
    return render_template("index.html")


# ================= REGISTER =================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        role = request.form["role"]

        # Check empty fields
        if not name or not email or not password:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("register"))

        # Check passwords
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        # Check password length
        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "error")
            return redirect(url_for("register"))

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Check whether email already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                flash("An account with this email already exists.", "error")
                return redirect(url_for("register"))

            # Hash password
            hashed_password = bcrypt.generate_password_hash(
                password
            ).decode("utf-8")

            # Insert user
            cursor.execute(
                """
                INSERT INTO users (name, email, password, role)
                VALUES (%s, %s, %s, %s)
                """,
                (name, email, hashed_password, role)
            )

            connection.commit()

            flash("Account created successfully! Please login.", "success")

            return redirect(url_for("login"))

        except Exception as e:

            if connection:
                connection.rollback()

            flash(f"Registration failed: {e}", "error")

            return redirect(url_for("register"))

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("register.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id, name, email, password, role
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

            if user and bcrypt.check_password_hash(
                user["password"],
                password
            ):

                # Store user information in session
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                session["user_email"] = user["email"]
                session["user_role"] = user["role"]

                flash("Login successful!", "success")

                if str(user["role"]).lower() == "recruiter":
                    return redirect(url_for("recruiter_dashboard"))

                return redirect(url_for("dashboard"))
            else:

                flash("Invalid email or password.", "error")

                return redirect(url_for("login"))

        except Exception as e:

            flash(f"Login failed: {e}", "error")

            return redirect(url_for("login"))

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("login.html")


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        role=session["user_role"]
    )


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("home"))

# ================= JOB LISTING =================

@app.route("/jobs")
def jobs():

    search = request.args.get("search", "").strip()
    location = request.args.get("location", "").strip()

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                jobs.id,
                jobs.title,
                jobs.description,
                jobs.location,
                jobs.salary,
                jobs.job_type,
                jobs.skills,
                jobs.status,
                jobs.created_at,
                companies.company_name
            FROM jobs
            JOIN companies
                ON jobs.company_id = companies.id
            WHERE jobs.status = 'Active'
        """

        parameters = []

        if search:

            query += """
                AND (
                    jobs.title LIKE %s
                    OR jobs.skills LIKE %s
                )
            """

            search_value = f"%{search}%"

            parameters.extend([
                search_value,
                search_value
            ])

        if location:

            query += """
                AND jobs.location LIKE %s
            """

            parameters.append(
                f"%{location}%"
            )

        query += """
            ORDER BY jobs.created_at DESC
        """

        cursor.execute(
            query,
            parameters
        )

        jobs = cursor.fetchall()

        return render_template(
            "jobs.html",
            jobs=jobs,
            search=search,
            location=location
        )

    except Exception as e:

        return f"Error loading jobs: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= JOB DETAILS =================

@app.route("/job/<int:job_id>")
def job_details(job_id):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                jobs.*,
                companies.company_name,
                companies.description AS company_description,
                companies.location AS company_location,
                companies.website
            FROM jobs
            JOIN companies
                ON jobs.company_id = companies.id
            WHERE jobs.id = %s
        """, (job_id,))

        job = cursor.fetchone()

        if not job:
            return "Job not found", 404

        return render_template(
            "job_details.html",
            job=job
        )

    except Exception as e:

        return f"Error loading job: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= APPLY FOR JOB =================

@app.route("/apply/<int:job_id>", methods=["GET", "POST"])
def apply_job(job_id):

    # User must be logged in
    if "user_id" not in session:
        flash("Please login to apply for a job.", "error")
        return redirect(url_for("login"))

    # Only job seekers can apply
    if session.get("user_role") != "job_seeker":
        flash("Only job seekers can apply for jobs.", "error")
        return redirect(url_for("jobs"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        # Get job information
        cursor.execute("""
            SELECT
                jobs.*,
                companies.company_name
            FROM jobs
            JOIN companies
                ON jobs.company_id = companies.id
            WHERE jobs.id = %s
        """, (job_id,))

        job = cursor.fetchone()

        if not job:
            return "Job not found", 404


        # When user submits application
        if request.method == "POST":

            resume = request.form["resume"]
            cover_letter = request.form["cover_letter"]

            # Check whether already applied
            cursor.execute("""
                SELECT id
                FROM applications
                WHERE job_id = %s
                AND user_id = %s
            """, (
                job_id,
                session["user_id"]
            ))

            existing_application = cursor.fetchone()

            if existing_application:

                flash(
                    "You have already applied for this job.",
                    "error"
                )

                return redirect(
                    url_for(
                        "job_details",
                        job_id=job_id
                    )
                )


            # Insert application
            cursor.execute("""
                INSERT INTO applications
                (
                    job_id,
                    user_id,
                    resume,
                    cover_letter,
                    status
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    'Applied'
                )
            """, (
                job_id,
                session["user_id"],
                resume,
                cover_letter
            ))

            connection.commit()

            flash(
                "Application submitted successfully!",
                "success"
            )

            return redirect(
                url_for(
                    "applications"
                )
            )


        return render_template(
            "applications.html",
            job=job
        )

    except Exception as e:

        if connection:
            connection.rollback()

        return f"Application error: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= MY APPLICATIONS =================

@app.route("/applications")
def applications():

    # Check login
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    # Only job seekers can view their applications
    if session.get("user_role") != "job_seeker":
        flash("Only job seekers can view applications.", "error")
        return redirect(url_for("dashboard"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get applications submitted by the logged-in user
        cursor.execute("""
            SELECT
                applications.id,
                applications.resume,
                applications.cover_letter,
                applications.status,
                applications.applied_at,
                jobs.id AS job_id,
                jobs.title,
                jobs.location,
                jobs.job_type,
                jobs.salary,
                companies.company_name
            FROM applications
            JOIN jobs
                ON applications.job_id = jobs.id
            JOIN companies
                ON jobs.company_id = companies.id
            WHERE applications.user_id = %s
            ORDER BY applications.applied_at DESC
        """, (session["user_id"],))

        applications_list = cursor.fetchall()

        return render_template(
            "my_applications.html",
            applications=applications_list
        )

    except Exception as e:

        return f"Error loading applications: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= CREATE COMPANY =================

@app.route("/create-company", methods=["GET", "POST"])
def create_company():

    # Check login
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    # Only recruiters can create companies
    if session.get("user_role") != "recruiter":
        flash("Only recruiters can create a company profile.", "error")
        return redirect(url_for("dashboard"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check whether recruiter already has a company
        cursor.execute("""
            SELECT id
            FROM companies
            WHERE user_id = %s
        """, (session["user_id"],))

        existing_company = cursor.fetchone()

        if existing_company:
            flash("You already have a company profile.", "error")
            return redirect(url_for("recruiter_dashboard"))

        # Handle form submission
        if request.method == "POST":

            company_name = request.form["company_name"].strip()
            description = request.form["description"].strip()
            location = request.form["location"].strip()
            website = request.form["website"].strip()

            # Validate required fields
            if not company_name or not description or not location:
                flash(
                    "Please fill in all required fields.",
                    "error"
                )
                return redirect(url_for("create_company"))

            # Insert company
            cursor.execute("""
                INSERT INTO companies
                (
                    user_id,
                    company_name,
                    description,
                    location,
                    website
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
            """, (
                session["user_id"],
                company_name,
                description,
                location,
                website
            ))

            connection.commit()

            flash(
                "Company profile created successfully!",
                "success"
            )

            return redirect(
                url_for("recruiter_dashboard")
            )

        return render_template("create_company.html")

    except Exception as e:

        if connection:
            connection.rollback()

        return f"Company creation error: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= RECRUITER DASHBOARD =================

@app.route("/recruiter/dashboard")
def recruiter_dashboard():

    # Check login
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    # Only recruiters allowed
    if session.get("user_role") != "recruiter":
        flash("Access denied. Recruiter account required.", "error")
        return redirect(url_for("dashboard"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        # Get company belonging to recruiter
        cursor.execute("""
            SELECT *
            FROM companies
            WHERE user_id = %s
        """, (session["user_id"],))

        company = cursor.fetchone()

        jobs = []

        if company:

            cursor.execute("""
                SELECT
                    jobs.id,
                    jobs.title,
                    jobs.location,
                    jobs.salary,
                    jobs.job_type,
                    jobs.status,
                    jobs.created_at,

                    (
                        SELECT COUNT(*)
                        FROM applications
                        WHERE applications.job_id = jobs.id
                    ) AS applicant_count

                FROM jobs

                WHERE jobs.company_id = %s

                ORDER BY jobs.created_at DESC
            """, (company["id"],))

            jobs = cursor.fetchall()

        return render_template(
            "recruiter_dashboard.html",
            company=company,
            jobs=jobs
        )

    except Exception as e:

        return f"Recruiter dashboard error: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= POST JOB =================

@app.route("/post-job", methods=["GET", "POST"])
def post_job():

    # Check login
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    # Only recruiters can post jobs
    if session.get("user_role") != "recruiter":
        flash("Only recruiters can post jobs.", "error")
        return redirect(url_for("dashboard"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        # Find recruiter's company
        cursor.execute("""
            SELECT id, company_name
            FROM companies
            WHERE user_id = %s
        """, (session["user_id"],))

        company = cursor.fetchone()

        if not company:
            flash(
                "Please create a company profile first.",
                "error"
            )

            return redirect(
                url_for("recruiter_dashboard")
            )

        # Form submitted
        if request.method == "POST":

            title = request.form["title"].strip()
            description = request.form["description"].strip()
            location = request.form["location"].strip()
            salary = request.form["salary"].strip()
            job_type = request.form["job_type"]
            skills = request.form["skills"].strip()

            # Validate
            if not title or not description or not location or not skills:

                flash(
                    "Please fill in all required fields.",
                    "error"
                )

                return redirect(
                    url_for("post_job")
                )

            # Insert job
            cursor.execute("""
                INSERT INTO jobs
                (
                    company_id,
                    title,
                    description,
                    location,
                    salary,
                    job_type,
                    skills,
                    status
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'Active'
                )
            """, (
                company["id"],
                title,
                description,
                location,
                salary,
                job_type,
                skills
            ))

            connection.commit()

            flash(
                "Job posted successfully!",
                "success"
            )

            return redirect(
                url_for("recruiter_dashboard")
            )

        return render_template(
            "post_job.html",
            company=company
        )

    except Exception as e:

        if connection:
            connection.rollback()

        return f"Error posting job: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= VIEW APPLICANTS =================

@app.route("/recruiter/applicants/<int:job_id>")
def view_applicants(job_id):

    # Check login
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    # Only recruiters
    if session.get("user_role") != "recruiter":
        flash("Only recruiters can view applicants.", "error")
        return redirect(url_for("dashboard"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get recruiter's company
        cursor.execute("""
            SELECT id, company_name
            FROM companies
            WHERE user_id = %s
        """, (session["user_id"],))

        company = cursor.fetchone()

        if not company:
            flash("Company profile not found.", "error")
            return redirect(url_for("recruiter_dashboard"))

        # Make sure this job belongs to recruiter
        cursor.execute("""
            SELECT
                jobs.id,
                jobs.title,
                jobs.location,
                jobs.job_type
            FROM jobs
            WHERE jobs.id = %s
            AND jobs.company_id = %s
        """, (
            job_id,
            company["id"]
        ))

        job = cursor.fetchone()

        if not job:
            flash("Job not found.", "error")
            return redirect(url_for("recruiter_dashboard"))

        # Get applicants
        cursor.execute("""
            SELECT
                applications.id,
                applications.resume,
                applications.cover_letter,
                applications.status,
                applications.applied_at,
                users.name,
                users.email
            FROM applications
            JOIN users
                ON applications.user_id = users.id
            WHERE applications.job_id = %s
            ORDER BY applications.applied_at DESC
        """, (job_id,))

        applicants = cursor.fetchall()

        return render_template(
            "applicants.html",
            job=job,
            applicants=applicants
        )

    except Exception as e:

        return f"Error loading applicants: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= ACCEPT APPLICATION =================

@app.route(
    "/recruiter/application/<int:application_id>/accept",
    methods=["POST"]
)
def accept_application(application_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_role") != "recruiter":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Verify application belongs to recruiter's company
        cursor.execute("""
            SELECT applications.job_id
            FROM applications
            JOIN jobs
                ON applications.job_id = jobs.id
            JOIN companies
                ON jobs.company_id = companies.id
            WHERE applications.id = %s
            AND companies.user_id = %s
        """, (
            application_id,
            session["user_id"]
        ))

        application = cursor.fetchone()

        if not application:
            flash("Application not found.", "error")
            return redirect(
                url_for("recruiter_dashboard")
            )

        cursor.execute("""
            UPDATE applications
            SET status = 'Accepted'
            WHERE id = %s
        """, (application_id,))

        connection.commit()

        flash(
            "Application accepted successfully.",
            "success"
        )

        return redirect(
            url_for(
                "view_applicants",
                job_id=application["job_id"]
            )
        )

    except Exception as e:

        if connection:
            connection.rollback()

        return f"Error accepting application: {e}"

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
# ================= RUN APPLICATION =================

if __name__ == "__main__":
    app.run(debug=True)