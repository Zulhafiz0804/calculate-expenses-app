import csv
import io
import os
import calendar
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, render_template, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)

# SQLite is default for easy local setup. PostgreSQL can be used by setting DATABASE_URL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///expenses.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


expense_tags = db.Table(
    "expense_tags",
    db.Column("expense_id", db.Integer, db.ForeignKey("expense.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    tags = db.relationship("Tag", secondary=expense_tags, back_populates="expenses")

    def to_dict(self):
        return {
            "id": self.id,
            "amount": self.amount,
            "category": self.category,
            "description": self.description,
            "date": self.date.isoformat(),
            "tags": [tag.to_dict() for tag in self.tags],
        }


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    color_hex = db.Column(db.String(7), nullable=False)
    expenses = db.relationship("Expense", secondary=expense_tags, back_populates="tags")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "color_hex": self.color_hex}


class BudgetSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monthly_budget = db.Column(db.Float, nullable=False, default=0.0)


class RecurringBill(db.Model):
    __tablename__ = "recurring_bills"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "description": self.description,
            "amount": self.amount,
        }


with app.app_context():
    db.create_all()
    default_tags = [
        ("#Food", "#d7ead9"),
        ("#Bills", "#cbdcf0"),
        ("#Wants", "#f3d4dc"),
    ]
    for name, color_hex in default_tags:
        if not Tag.query.filter_by(name=name).first():
            db.session.add(Tag(name=name, color_hex=color_hex))
    db.session.commit()

    if not BudgetSettings.query.first():
        db.session.add(BudgetSettings(monthly_budget=0.0))
        db.session.commit()

    if not RecurringBill.query.first():
        default_bills = [
            RecurringBill(category="Bills", description="Internet", amount=79.99),
            RecurringBill(category="Loan Commitment", description="Car Loan", amount=310.00),
            RecurringBill(category="Bills", description="Phone Bill", amount=42.50),
            RecurringBill(category="Bills", description="Electricity", amount=68.40),
        ]
        db.session.add_all(default_bills)
        db.session.commit()


@app.route("/")
def index():
    total_amount = float(db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).scalar() or 0)
    recent_expenses = Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).limit(10).all()
    return render_template(
        "index.html",
        recent_expenses=[expense.to_dict() for expense in recent_expenses],
        total_amount=round(total_amount, 2),
    )


@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    rows = (
        db.session.query(Expense, Tag)
        .outerjoin(expense_tags, Expense.id == expense_tags.c.expense_id)
        .outerjoin(Tag, Tag.id == expense_tags.c.tag_id)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .all()
    )
    expenses = {}
    for expense, tag in rows:
        if expense.id not in expenses:
            expenses[expense.id] = expense.to_dict()
            expenses[expense.id]["tags"] = []
        if tag is not None:
            expenses[expense.id]["tags"].append(tag.to_dict())
    return jsonify(list(expenses.values()))


@app.route("/api/tags", methods=["GET", "POST"])
def tags_api():
    if request.method == "GET":
        tags = Tag.query.order_by(Tag.name).all()
        return jsonify([tag.to_dict() for tag in tags])

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    color_hex = str(data.get("color_hex", "")).strip().lower()
    if not name or len(name) > 100 or not color_hex.startswith("#") or len(color_hex) != 7:
        return jsonify({"error": "A tag name and a valid 6-digit hex color are required."}), 400

    try:
        int(color_hex[1:], 16)
    except ValueError:
        return jsonify({"error": "Color must be a valid hex value."}), 400

    if Tag.query.filter(db.func.lower(Tag.name) == name.lower()).first():
        return jsonify({"error": "A tag with that name already exists."}), 409

    tag = Tag(name=name, color_hex=color_hex)
    db.session.add(tag)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not create tag."}), 500
    return jsonify(tag.to_dict()), 201


@app.route("/api/expense/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    db.session.execute(text("DELETE FROM expense_tags WHERE expense_id = :expense_id"), {"expense_id": expense_id})
    result = db.session.execute(
        text("DELETE FROM expense WHERE id = :expense_id"),
        {"expense_id": expense_id},
    )
    db.session.commit()

    if result.rowcount == 0:
        return jsonify({"error": "Expense not found."}), 404

    return jsonify({"success": True, "deleted_id": expense_id})


@app.route("/api/expenses/reset", methods=["DELETE"])
def reset_expenses():
    db.session.execute(text("DELETE FROM expense_tags"))
    db.session.execute(text("DELETE FROM expense"))
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/dashboard-data")
def dashboard_data():
    today = datetime.utcnow().date()
    chart_range = request.args.get("range", "7d")
    if chart_range not in {"7d", "30d", "year"}:
        chart_range = "7d"

    month_key = today.strftime("%Y-%m")
    year_key = today.strftime("%Y")
    dialect = db.engine.dialect.name

    if dialect == "sqlite":
        daily_sql = text(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expense
            WHERE date = :today
            """
        )
        monthly_sql = text(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expense
            WHERE strftime('%Y-%m', date) = :month_key
            """
        )
        yearly_sql = text(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expense
            WHERE strftime('%Y', date) = :year_key
            """
        )
    else:
        daily_sql = text(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expense
            WHERE CAST(date AS DATE) = CURRENT_DATE
            """
        )
        monthly_sql = text(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expense
            WHERE to_char(date, 'YYYY-MM') = :month_key
            """
        )
        yearly_sql = text(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expense
            WHERE EXTRACT(YEAR FROM date) = CAST(:year_key AS INT)
            """
        )

    daily_total = float(db.session.execute(daily_sql, {"today": today.isoformat()}).scalar() or 0)
    monthly_total = float(db.session.execute(monthly_sql, {"month_key": month_key}).scalar() or 0)
    yearly_total = float(db.session.execute(yearly_sql, {"year_key": year_key}).scalar() or 0)

    current_month_start = today.replace(day=1)
    previous_month_end = current_month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    previous_month_total = float(
        db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0))
        .filter(Expense.date >= previous_month_start, Expense.date <= previous_month_end)
        .scalar()
        or 0
    )
    mom_trend = 0.0 if previous_month_total == 0 else ((monthly_total - previous_month_total) / previous_month_total) * 100
    elapsed_days = (today - current_month_start).days + 1
    days_in_current_month = calendar.monthrange(today.year, today.month)[1]
    projected_monthly_spend = (monthly_total / elapsed_days) * days_in_current_month

    budget_settings = BudgetSettings.query.first()
    monthly_budget = float(budget_settings.monthly_budget if budget_settings else 0.0)
    budget_percent = 0.0 if monthly_budget == 0 else (monthly_total / monthly_budget) * 100
    budget_alert = monthly_budget > 0 and budget_percent >= 80.0

    if chart_range == "year":
        start_date = today.replace(month=1, day=1)
        recent_expenses = Expense.query.filter(Expense.date >= start_date, Expense.date <= today).all()
        totals_by_month = {}
        for expense in recent_expenses:
            month_start = expense.date.replace(day=1)
            totals_by_month[month_start] = totals_by_month.get(month_start, 0.0) + float(expense.amount)

        labels = []
        values = []
        current_month = start_date
        while current_month <= today:
            labels.append(current_month.strftime("%b"))
            values.append(round(totals_by_month.get(current_month, 0.0), 2))
            current_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        day_count = 7 if chart_range == "7d" else 30
        start_day = today - timedelta(days=day_count - 1)
        recent_expenses = Expense.query.filter(Expense.date >= start_day, Expense.date <= today).all()
        totals_by_day = {}
        for expense in recent_expenses:
            totals_by_day[expense.date] = totals_by_day.get(expense.date, 0.0) + float(expense.amount)

        labels = []
        values = []
        for day_offset in range(day_count):
            date_in_range = start_day + timedelta(days=day_offset)
            labels.append(date_in_range.strftime("%b %-d") if os.name != "nt" else date_in_range.strftime("%b %#d"))
            values.append(round(totals_by_day.get(date_in_range, 0.0), 2))

    category_totals_by_name = {}
    for expense in recent_expenses:
        expense_tags = expense.tags or []
        if not expense_tags:
            category_totals_by_name["Untagged"] = category_totals_by_name.get("Untagged", 0.0) + float(expense.amount)
        for tag in expense_tags:
            category_totals_by_name[tag.name] = category_totals_by_name.get(tag.name, 0.0) + float(expense.amount)

    category_labels = list(category_totals_by_name)
    category_totals = [round(category_totals_by_name[label], 2) for label in category_labels]

    return jsonify(
        {
            "daily_total": round(daily_total, 2),
            "monthly_total": round(monthly_total, 2),
            "yearly_total": round(yearly_total, 2),
            "mom_trend": round(mom_trend, 2),
            "projected_monthly_spend": round(projected_monthly_spend, 2),
            "monthly_budget": round(monthly_budget, 2),
            "budget_percent": round(budget_percent, 2),
            "budget_alert": budget_alert,
            "chart": {"range": chart_range, "labels": labels, "values": values},
            "category_labels": category_labels,
            "category_totals": category_totals,
        }
    )


@app.route("/api/monthly-budget", methods=["GET", "POST"])
def monthly_budget():
    settings = BudgetSettings.query.first()

    if request.method == "GET":
        return jsonify({"monthly_budget": round(float(settings.monthly_budget if settings else 0.0), 2)})

    data = request.get_json(force=True) or {}
    monthly_budget = float(data.get("monthly_budget", 0) or 0)

    if monthly_budget < 0:
        return jsonify({"error": "Budget must be zero or greater."}), 400

    if settings is None:
        settings = BudgetSettings(monthly_budget=monthly_budget)
    else:
        settings.monthly_budget = monthly_budget

    db.session.add(settings)
    db.session.commit()

    return jsonify({"monthly_budget": round(float(settings.monthly_budget), 2)})


@app.route("/api/export-csv")
def export_csv():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Category", "Description", "Amount"])

    expenses = Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    for expense in expenses:
        writer.writerow([
            expense.date.isoformat(),
            expense.category,
            expense.description,
            f"{expense.amount:.2f}",
        ])

    buffer.seek(0)
    return send_file(
        io.BytesIO(buffer.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="expenses.csv",
    )


@app.route("/api/recurring-bills", methods=["GET"])
def get_recurring_bills():
    return jsonify([bill.to_dict() for bill in RecurringBill.query.order_by(RecurringBill.description).all()])


@app.route("/api/fixed-bills", methods=["POST"])
def create_fixed_bill():
    data = request.get_json(silent=True) or {}
    category = str(data.get("category", "")).strip()
    description = str(data.get("description", "")).strip()

    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        amount = 0

    if not category or not description or amount <= 0:
        return jsonify({"error": "Category, description, and a positive amount are required."}), 400

    bill = RecurringBill(category=category, description=description, amount=amount)
    try:
        db.session.add(bill)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not add fixed bill."}), 500

    return jsonify(bill.to_dict()), 201


@app.route("/api/fixed-bills/<int:bill_id>", methods=["PUT"])
def update_fixed_bill(bill_id):
    bill = db.session.get(RecurringBill, bill_id)
    if bill is None:
        return jsonify({"error": "Fixed bill not found."}), 404

    data = request.get_json(silent=True) or {}
    description = str(data.get("description", bill.description)).strip()
    try:
        amount = float(data.get("amount", bill.amount))
    except (TypeError, ValueError):
        amount = 0

    if not description or amount <= 0:
        return jsonify({"error": "Description and a positive amount are required."}), 400

    bill.description = description
    bill.amount = amount
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not update fixed bill."}), 500

    return jsonify(bill.to_dict())


@app.route("/api/fixed-bills/<int:bill_id>", methods=["DELETE"])
def delete_fixed_bill(bill_id):
    bill = db.session.get(RecurringBill, bill_id)
    if bill is None:
        return jsonify({"error": "Fixed bill not found."}), 404

    try:
        db.session.delete(bill)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not delete fixed bill."}), 500

    return jsonify({"success": True, "deleted_id": bill_id})


@app.route("/api/log-recurring", methods=["POST"])
def log_recurring_bill():
    data = request.get_json(silent=True) or {}
    bill_id = data.get("bill_id")
    bill = db.session.get(RecurringBill, bill_id) if bill_id is not None else None

    if bill is None:
        return jsonify({"error": "Please select a valid recurring bill."}), 400

    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    existing_expense = Expense.query.filter(
        Expense.category == bill.category,
        Expense.description == bill.description,
        Expense.date >= month_start,
        Expense.date < next_month,
    ).first()

    if existing_expense:
        month_name = today.strftime("%B %Y")
        return jsonify({"error": f"{bill.description} already logged for {month_name}."}), 409

    expense = Expense(
        amount=float(bill.amount),
        category=bill.category,
        description=bill.description,
        date=today,
    )
    matching_tag = Tag.query.filter(db.func.lower(Tag.name) == f"#{bill.category}".lower()).first()
    if matching_tag:
        expense.tags.append(matching_tag)

    try:
        db.session.add(expense)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to log recurring bill."}), 500

    return jsonify({"success": True, "message": f"{bill.description} logged!", "expense": expense.to_dict()}), 201


@app.route("/api/expense", methods=["POST"])
@app.route("/api/expenses", methods=["POST"])
def create_expense():
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        amount = 0
    description = str(data.get("description", "")).strip()
    date_value = data.get("date")
    tag_ids = data.get("tag_ids", [])

    if amount <= 0 or not description or not date_value or not isinstance(tag_ids, list) or not tag_ids:
        return jsonify({"error": "Invalid expense data."}), 400

    try:
        expense_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Date must be in YYYY-MM-DD format."}), 400

    try:
        tag_ids = list(dict.fromkeys(int(tag_id) for tag_id in tag_ids))
    except (TypeError, ValueError):
        return jsonify({"error": "tag_ids must contain valid tag IDs."}), 400

    tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
    if len(tags) != len(tag_ids):
        return jsonify({"error": "One or more selected tags do not exist."}), 400

    expense = Expense(
        amount=amount,
        category=tags[0].name,
        description=description,
        date=expense_date,
        tags=tags,
    )
    try:
        db.session.add(expense)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not save expense."}), 500
    return jsonify(expense.to_dict()), 201


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
