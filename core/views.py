import os, json, statistics, csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.http import JsonResponse, HttpResponse
from .models import Expense, SavingsGoal, Budget, UserProfile, ChatMessage
from .forms import RegisterForm, LoginForm, ExpenseForm, SavingsGoalForm, AddMoneyForm, BudgetForm
from collections import defaultdict
from datetime import datetime, timedelta, date

def get_gemini_api_key():
    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    if api_key:
        return api_key

    # Fallback for Windows: read the persistent user-level environment variable
    # directly from the registry in case the current terminal session is stale.
    if os.name == 'nt':
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment') as env_key:
                value, _ = winreg.QueryValueEx(env_key, 'GEMINI_API_KEY')
                return str(value).strip()
        except Exception:
            pass

    return ''

# ── Gamification helpers ────────────────────────────────────────────────────

def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile

def update_streak_and_xp(user, xp=10):
    profile = get_or_create_profile(user)
    today = date.today()
    if profile.last_expense_date == today:
        pass
    elif profile.last_expense_date == today - timedelta(days=1):
        profile.current_streak += 1
        profile.longest_streak = max(profile.longest_streak, profile.current_streak)
    else:
        profile.current_streak = 1
    profile.last_expense_date = today
    profile.total_expenses_logged += 1
    profile.add_xp(xp)
    _check_badges(profile)
    profile.save()

def _check_badges(profile):
    total = profile.total_expenses_logged
    streak = profile.current_streak
    xp = profile.xp_points
    if total >= 1:    profile.add_badge('🌱 First Step')
    if total >= 10:   profile.add_badge('📊 Data Driven')
    if total >= 50:   profile.add_badge('💼 Pro Tracker')
    if total >= 100:  profile.add_badge('🏆 Century Club')
    if streak >= 3:   profile.add_badge('🔥 3-Day Streak')
    if streak >= 7:   profile.add_badge('⚡ Week Warrior')
    if streak >= 30:  profile.add_badge('💎 Month Master')
    if xp >= 500:     profile.add_badge('⭐ Level Up')
    if xp >= 2000:    profile.add_badge('🚀 XP Hunter')

# ── AI Categorization ───────────────────────────────────────────────────────

def ai_categorize_expense(title):
    title_lower = title.lower()
    keywords = {
        'Food': ['food','restaurant','cafe','coffee','pizza','burger','lunch','dinner','breakfast',
                 'meal','snack','grocery','vegetables','fruits','milk','swiggy','zomato','dominos',
                 'mcdonalds','kfc','subway','blinkit','instamart','zepto'],
        'Travel': ['uber','ola','taxi','bus','train','flight','petrol','fuel','metro','auto',
                   'rickshaw','cab','parking','toll','rapido','redbus','irctc','makemytrip'],
        'Bills': ['electricity','water','gas','internet','wifi','phone','mobile','recharge',
                  'bill','rent','emi','insurance','subscription','airtel','jio','bsnl','dth'],
        'Shopping': ['amazon','flipkart','myntra','shopping','clothes','shirt','shoes',
                     'electronics','gadget','laptop','watch','bag','meesho','ajio','nykaa'],
        'Health': ['medicine','doctor','hospital','clinic','pharmacy','medical','health',
                   'gym','fitness','yoga','checkup','apollo','practo','1mg','netmeds'],
        'Entertainment': ['movie','cinema','netflix','prime','spotify','game','concert',
                          'party','club','bar','pub','bookmyshow','pvr','inox','disney'],
        'Education': ['book','course','class','tuition','education','school','college',
                      'university','training','workshop','udemy','coursera','byju','unacademy'],
    }
    for category, kws in keywords.items():
        if any(kw in title_lower for kw in kws):
            return category
    return 'Other'

# ── Basic Views ─────────────────────────────────────────────────────────────

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            get_or_create_profile(user)
            messages.success(request, 'Account created! Please log in.')
            return redirect('login')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = RegisterForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(request, username=form.cleaned_data['username'],
                                password=form.cleaned_data['password'])
            if user:
                auth_login(request, user)
                get_or_create_profile(user)
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'core/login.html', {'form': form})

@login_required
def logout_view(request):
    auth_logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('login')

# ── Dashboard ───────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            if expense.category == 'Other':
                expense.category = ai_categorize_expense(expense.title)
                expense.auto_categorized = True
            expense.save()
            update_streak_and_xp(request.user, xp=10)
            if expense.auto_categorized:
                messages.success(request, f'✨ Auto-categorized as {expense.category}!')
            else:
                messages.success(request, 'Expense added!')
            return redirect('dashboard')
    else:
        form = ExpenseForm()

    expenses = Expense.objects.filter(user=request.user)
    total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    category_data = {}
    for exp in expenses:
        category_data[exp.category] = category_data.get(exp.category, 0) + float(exp.amount)

    goals = SavingsGoal.objects.filter(user=request.user)[:3]
    total_saved = sum([float(g.current_amount) for g in goals])
    profile = get_or_create_profile(request.user)

    context = {
        'form': form,
        'expenses': expenses[:10],
        'total': total,
        'expense_count': expenses.count(),
        'category_data': category_data,
        'goals': goals,
        'total_saved': total_saved,
        'daily_summary': generate_daily_summary(request.user),
        'budget_warnings': generate_budget_warnings(request.user),
        'monthly_story': generate_monthly_story(request.user),
        'health_score': calculate_health_score(request.user),
        'profile': profile,
        'badges': profile.get_badges(),
        'chat_messages': ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:20][::-1],
    }
    return render(request, 'core/dashboard.html', context)

# ── Expense Management ───────────────────────────────────────────────────────

@login_required
def delete_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)
    expense.delete()
    messages.success(request, 'Expense deleted!')
    return redirect('dashboard')

# ── Savings Goals ────────────────────────────────────────────────────────────

@login_required
def savings_goals(request):
    if request.method == 'POST' and 'create_goal' in request.POST:
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            profile = get_or_create_profile(request.user)
            profile.add_xp(50)
            profile.add_badge('🎯 Goal Setter')
            profile.save()
            messages.success(request, f'Goal "{goal.name}" created! +50 XP')
            return redirect('savings_goals')
    else:
        form = SavingsGoalForm()

    goals = SavingsGoal.objects.filter(user=request.user)
    return render(request, 'core/savings_goals.html', {
        'form': form, 'goals': goals, 'add_money_form': AddMoneyForm(),
    })

@login_required
def add_money_to_goal(request, goal_id):
    goal = get_object_or_404(SavingsGoal, id=goal_id, user=request.user)
    if request.method == 'POST':
        form = AddMoneyForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            goal.current_amount += amount
            if goal.current_amount >= goal.target_amount:
                goal.completed = True
                profile = get_or_create_profile(request.user)
                profile.add_xp(200)
                profile.add_badge('🏆 Goal Achiever')
                profile.save()
                messages.success(request, f'🎉 Goal "{goal.name}" completed! +200 XP')
            else:
                messages.success(request, f'Added ₹{amount} to "{goal.name}"!')
            goal.save()
    return redirect('savings_goals')

@login_required
def delete_goal(request, goal_id):
    goal = get_object_or_404(SavingsGoal, id=goal_id, user=request.user)
    goal.delete()
    messages.success(request, 'Goal deleted!')
    return redirect('savings_goals')

# ── AI Chat ──────────────────────────────────────────────────────────────────

@login_required
def ai_chat(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not user_message:
        return JsonResponse({'error': 'Empty message'}, status=400)

    # Build financial context
    expenses = Expense.objects.filter(user=request.user).order_by('-date')[:50]
    goals = SavingsGoal.objects.filter(user=request.user)
    budgets = Budget.objects.filter(user=request.user)

    expense_summary = []
    for e in expenses[:20]:
        expense_summary.append(f"- {e.title}: ₹{e.amount} ({e.category}) on {e.date}")

    goal_summary = [f"- {g.name}: ₹{float(g.current_amount):.0f}/₹{float(g.target_amount):.0f}" for g in goals]
    budget_summary = [f"- {b.category}: ₹{float(b.monthly_limit):.0f}/month" for b in budgets]

    total_spent = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    category_data = {}
    for exp in expenses:
        category_data[exp.category] = category_data.get(exp.category, 0) + float(exp.amount)
    cat_breakdown = [f"- {k}: ₹{v:.0f}" for k, v in sorted(category_data.items(), key=lambda x: -x[1])]

    system_prompt = f"""You are FinWise AI, a friendly personal finance assistant for {request.user.username}.
You have access to their real financial data. Be concise, helpful, and specific with numbers.
Always use ₹ (Indian Rupees). Give actionable advice.

USER'S FINANCIAL SNAPSHOT:
Total tracked spending: ₹{float(total_spent):.0f}

Recent expenses:
{chr(10).join(expense_summary) or 'No expenses yet'}

Category breakdown:
{chr(10).join(cat_breakdown) or 'No data'}

Savings goals:
{chr(10).join(goal_summary) or 'No goals set'}

Monthly budgets:
{chr(10).join(budget_summary) or 'No budgets set'}

Answer questions about their finances, give advice, do calculations, and help them make better money decisions.
Keep responses under 150 words unless they ask for detailed analysis."""

    # Call Gemini API
    api_key = get_gemini_api_key()
    if not api_key:
        reply = "⚠️ AI Chat requires a Gemini API key. Set GEMINI_API_KEY in your terminal."
    else:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_prompt
            )
            response = model.generate_content(user_message)
            try:
                reply = (response.text or '').strip()
            except Exception:
                reply = ''

            if not reply:
                reply = (
                    "I couldn't generate a response for that prompt. "
                    "Please rephrase and try again."
                )
        except ModuleNotFoundError as e:
            if e.name == 'google':
                reply = (
                    "Gemini SDK is not installed in this Python environment. "
                    "Run `pip install -r requirements.txt` and restart the server."
                )
            else:
                reply = f"Sorry, I couldn't connect to Gemini. Error: {str(e)[:100]}"
        except Exception as e:
            reply = f"Sorry, I couldn't connect to Gemini. Error: {str(e)[:100]}"

    # Save messages
    ChatMessage.objects.create(user=request.user, role='user', content=user_message)
    ChatMessage.objects.create(user=request.user, role='assistant', content=reply)

    # Award XP for using chat
    profile = get_or_create_profile(request.user)
    profile.add_xp(2)
    profile.save()

    return JsonResponse({'reply': reply})

@login_required
def clear_chat(request):
    ChatMessage.objects.filter(user=request.user).delete()
    return JsonResponse({'success': True})

# ── Receipt Scanner ───────────────────────────────────────────────────────────

@login_required
def scan_receipt(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    image_file = request.FILES.get('receipt')
    if not image_file:
        return JsonResponse({'error': 'No image uploaded'}, status=400)

    # Read image data
    image_data = image_file.read()

    api_key = get_gemini_api_key()
    if not api_key:
        # Return demo data if no API key
        return JsonResponse({
            'success': True,
            'demo': True,
            'title': 'Coffee at Cafe (Demo)',
            'amount': '150',
            'category': 'Food',
            'date': str(date.today()),
            'message': 'Demo mode - Set GEMINI_API_KEY for real receipt scanning'
        })

    try:
        import google.generativeai as genai
        import PIL.Image
        import io

        genai.configure(api_key=api_key)

        # Convert image bytes to PIL Image
        image = PIL.Image.open(io.BytesIO(image_data))

        model = genai.GenerativeModel('gemini-2.5-flash')

        response = model.generate_content([
            image,
            '''Extract expense info from this receipt. Return ONLY a JSON object with these fields:
{
  "title": "short description of what was purchased",
  "amount": "total amount as number string (no currency symbol)",
  "category": "one of: Food, Travel, Bills, Shopping, Health, Entertainment, Education, Other",
  "date": "YYYY-MM-DD format or today if not visible",
  "confidence": "high/medium/low"
}
No other text, just the JSON.'''
        ])

        text = response.text.strip()

        # Clean JSON if wrapped in code blocks
        if '```' in text:
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]

        result = json.loads(text)
        result['success'] = True
        return JsonResponse(result)

    except ModuleNotFoundError as e:
        if e.name == 'google':
            return JsonResponse({
                'error': (
                    "Gemini SDK is missing in this Python environment. "
                    "Run `pip install -r requirements.txt` and restart the server."
                )
            }, status=500)
        return JsonResponse({'error': f'Scan failed: {str(e)[:100]}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Scan failed: {str(e)[:100]}'}, status=500)

@login_required
def upload_statement(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    csv_file = request.FILES.get('statement')
    if not csv_file or not csv_file.name.endswith('.csv'):
        return JsonResponse({'error': 'Please upload a valid CSV file'}, status=400)

    try:
        # Read the CSV
        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.reader(decoded_file)
        rows = list(reader)

        if not rows:
             return JsonResponse({'error': 'CSV is empty'}, status=400)

        # Basic heuristic to find headers
        header_row_idx = 0
        for i, row in enumerate(rows[:20]):
            row_text = ' '.join(row).lower()
            if 'date' in row_text and ('description' in row_text or 'narration' in row_text or 'particulars' in row_text):
                header_row_idx = i
                break
                
        headers = [h.lower() for h in rows[header_row_idx]]
        
        date_idx = -1
        desc_idx = -1
        amount_idx = -1
        debit_idx = -1
        withdrawal_idx = -1

        for i, h in enumerate(headers):
            if 'date' in h: date_idx = i
            elif 'description' in h or 'narration' in h or 'particulars' in h: desc_idx = i
            elif 'amount' in h: amount_idx = i
            elif 'debit' in h: debit_idx = i
            elif 'withdrawal' in h: withdrawal_idx = i

        if date_idx == -1 or desc_idx == -1:
             return JsonResponse({'error': 'Could not detect Date and Description columns.'}, status=400)

        # Decide which column holds the expense amount
        if debit_idx != -1: amt_col = debit_idx
        elif withdrawal_idx != -1: amt_col = withdrawal_idx
        elif amount_idx != -1: amt_col = amount_idx
        else:
             return JsonResponse({'error': 'Could not detect Amount/Debit column.'}, status=400)

        expenses_to_process = []
        for row in rows[header_row_idx+1:]:
            if len(row) <= max(date_idx, desc_idx, amt_col): continue
            
            raw_date = row[date_idx].strip()
            desc = row[desc_idx].strip()
            amt_str = row[amt_col].strip().replace(',', '')
            
            if not raw_date or not desc or not amt_str: continue

            try:
                amt = float(amt_str)
                if amt <= 0: continue # ignore zero or negative
                
                # Parse date roughly
                try:
                    dt = datetime.strptime(raw_date, '%d/%m/%Y').date()
                except:
                    try: dt = datetime.strptime(raw_date, '%d-%m-%Y').date()
                    except:
                        try: dt = datetime.strptime(raw_date, '%Y-%m-%d').date()
                        except: dt = date.today()

                expenses_to_process.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'title': desc[:200],
                    'amount': amt
                })
            except ValueError:
                pass # Unparseable amount
                
        if not expenses_to_process:
             return JsonResponse({'error': 'No valid expenses found in CSV.'}, status=400)

        # Use Gemini to bulk categorize
        api_key = get_gemini_api_key()
        
        # We can do this in batch
        simplified_list = [{'id': i, 'desc': e['title']} for i, e in enumerate(expenses_to_process[:50])] # Limit to 50
        
        prompt = f"""
We have a list of bank transactions. Categorize each one into ONLY ONE of these categories: Food, Travel, Bills, Shopping, Health, Entertainment, Education, Other.
Return ONLY valid JSON format mapping IDs to Categories. Example: {{"0": "Food", "1": "Travel"}}
Transactions:
{json.dumps(simplified_list)}
"""
        categories_map = {}
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(prompt)
                text = response.text.strip()
                if '```' in text:
                    text = text.split('```')[1]
                    if text.startswith('json'): text = text[4:]
                categories_map = json.loads(text.strip())
            except Exception as e:
                print("Gemini Categorization Error:", e)

        # Create objects
        expenses_created = 0
        for i, exp in enumerate(expenses_to_process[:50]):
            cat = categories_map.get(str(i), ai_categorize_expense(exp['title']))
            if cat not in [c[0] for c in Expense.CATEGORIES]: cat = 'Other'
            
            Expense.objects.create(
                user=request.user,
                title=exp['title'],
                amount=exp['amount'],
                category=cat,
                date=exp['date'],
                auto_categorized=True
            )
            expenses_created += 1

        # Reward XP
        if expenses_created > 0:
            profile = get_or_create_profile(request.user)
            profile.add_xp(expenses_created * 5)
            profile.add_badge('💼 Bulk Importer')
            profile.total_expenses_logged += expenses_created
            profile.save()

        return JsonResponse({'success': True, 'count': expenses_created})

    except Exception as e:
        return JsonResponse({'error': f'Upload failed: {str(e)[:100]}'}, status=500)

# ── What-If Simulator ──────────────────────────────────────────────────────────

@login_required
def what_if_simulator(request):
    expenses = Expense.objects.filter(user=request.user)
    goals = SavingsGoal.objects.filter(user=request.user, completed=False)

    month_start = date.today().replace(day=1)
    monthly_expenses = expenses.filter(date__gte=month_start)
    cat_totals = {}
    for exp in monthly_expenses:
        cat_totals[exp.category] = cat_totals.get(exp.category, 0) + float(exp.amount)

    if not cat_totals:
        for exp in expenses:
            cat_totals[exp.category] = cat_totals.get(exp.category, 0) + float(exp.amount)

    goal_list = [
        {
            'id': g.id,
            'name': g.name,
            'emoji': g.emoji,
            'target': float(g.target_amount),
            'current': float(g.current_amount),
            'remaining': float(g.remaining_amount()),
            'monthly': float(g.monthly_contribution),
        }
        for g in goals
    ]

    return render(request, 'core/what_if.html', {
        'cat_totals': json.dumps(cat_totals),
        'goals': json.dumps(goal_list),
        'goals_qs': goals,
    })

# ── PDF Report ─────────────────────────────────────────────────────────────────

@login_required
def generate_pdf_report(request):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from io import BytesIO

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                                leftMargin=20*mm, rightMargin=20*mm)

        # Colors
        CARD_BG = HexColor('#1a1f2e')
        BLUE    = HexColor('#0ea5e9')
        PURPLE  = HexColor('#8b5cf6')
        GREEN   = HexColor('#10b981')
        LIGHT   = HexColor('#e5e7eb')
        GRAY    = HexColor('#6b7280')
        WHITE   = HexColor('#ffffff')

        story = []

        title_style = ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=26, textColor=WHITE, spaceAfter=4)
        sub_style   = ParagraphStyle('sub',   fontName='Helvetica',      fontSize=12, textColor=GRAY,  spaceAfter=20)
        h2_style    = ParagraphStyle('h2',    fontName='Helvetica-Bold', fontSize=16, textColor=BLUE,  spaceAfter=12, spaceBefore=20)
        body_style  = ParagraphStyle('body',  fontName='Helvetica',      fontSize=11, textColor=LIGHT, spaceAfter=6)

        # Data
        user     = request.user
        expenses = Expense.objects.filter(user=user).order_by('-date')
        goals    = SavingsGoal.objects.filter(user=user)
        profile  = get_or_create_profile(user)
        health   = calculate_health_score(user)
        today    = date.today()

        total_spent   = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
        month_start   = today.replace(day=1)
        month_expenses = expenses.filter(date__gte=month_start)
        month_total   = month_expenses.aggregate(Sum('amount'))['amount__sum'] or 0
        total_saved   = sum([float(g.current_amount) for g in goals])

        cat_data = {}
        for e in month_expenses:
            cat_data[e.category] = cat_data.get(e.category, 0) + float(e.amount)

        # Header
        story.append(Paragraph("💰 FinWise", title_style))
        story.append(Paragraph(f"Financial Report · {today.strftime('%B %Y')} · {user.username}", sub_style))
        story.append(HRFlowable(width="100%", thickness=1, color=BLUE))
        story.append(Spacer(1, 10))

        # Summary
        story.append(Paragraph("📊 Monthly Summary", h2_style))
        summary_data = [
            ['Metric', 'Value'],
            ['This Month Spent',       f'₹{float(month_total):,.0f}'],
            ['Total All-Time Spent',   f'₹{float(total_spent):,.0f}'],
            ['Total Saved in Goals',   f'₹{total_saved:,.0f}'],
            ['Active Goals',           str(goals.filter(completed=False).count())],
            ['Financial Health Score', f'{health["score"]}/100 (Grade {health["grade"]})'],
            ['FinWise Level',          f'Level {profile.level} — {profile.level_title()}'],
            ['Current Streak',         f'{profile.current_streak} days 🔥'],
        ]
        t = Table(summary_data, colWidths=[90*mm, 80*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0),  BLUE),
            ('TEXTCOLOR',    (0,0), (-1,0),  WHITE),
            ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 11),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [CARD_BG, HexColor('#232a3a')]),
            ('TEXTCOLOR',    (0,1), (-1,-1), LIGHT),
            ('GRID',         (0,0), (-1,-1), 0.5, HexColor('#2d3748')),
            ('PADDING',      (0,0), (-1,-1), 10),
            ('FONTNAME',     (0,1), (0,-1),  'Helvetica-Bold'),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

        # Category Breakdown
        if cat_data:
            story.append(Paragraph("🛒 Spending by Category (This Month)", h2_style))
            cat_table_data = [['Category', 'Amount', '% of Total']]
            total_cat = sum(cat_data.values()) or 1
            for cat, amt in sorted(cat_data.items(), key=lambda x: -x[1]):
                pct = (amt / total_cat) * 100
                cat_table_data.append([cat, f'₹{amt:,.0f}', f'{pct:.1f}%'])
            ct = Table(cat_table_data, colWidths=[80*mm, 60*mm, 30*mm])
            ct.setStyle(TableStyle([
                ('BACKGROUND',   (0,0), (-1,0),  PURPLE),
                ('TEXTCOLOR',    (0,0), (-1,0),  WHITE),
                ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
                ('FONTSIZE',     (0,0), (-1,-1), 10),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [CARD_BG, HexColor('#232a3a')]),
                ('TEXTCOLOR',    (0,1), (-1,-1), LIGHT),
                ('GRID',         (0,0), (-1,-1), 0.5, HexColor('#2d3748')),
                ('PADDING',      (0,0), (-1,-1), 8),
                ('ALIGN',        (1,0), (-1,-1), 'RIGHT'),
            ]))
            story.append(ct)
            story.append(Spacer(1, 10))

        # Recent Expenses
        story.append(Paragraph("📋 Recent Expenses (Last 15)", h2_style))
        exp_data = [['Date', 'Title', 'Category', 'Amount']]
        for e in expenses[:15]:
            exp_data.append([e.date.strftime('%d %b'), e.title[:35], e.category, f'₹{float(e.amount):,.0f}'])
        et = Table(exp_data, colWidths=[25*mm, 75*mm, 35*mm, 35*mm])
        et.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,0),  HexColor('#1e3a5f')),
            ('TEXTCOLOR',    (0,0), (-1,0),  WHITE),
            ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 9),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [CARD_BG, HexColor('#232a3a')]),
            ('TEXTCOLOR',    (0,1), (-1,-1), LIGHT),
            ('GRID',         (0,0), (-1,-1), 0.3, HexColor('#2d3748')),
            ('PADDING',      (0,0), (-1,-1), 6),
            ('ALIGN',        (3,0), (3,-1),  'RIGHT'),
        ]))
        story.append(et)

        # Savings Goals
        if goals:
            story.append(Paragraph("🎯 Savings Goals Progress", h2_style))
            goal_data = [['Goal', 'Target', 'Saved', 'Progress']]
            for g in goals:
                pct = g.progress_percentage()
                goal_data.append([
                    f'{g.emoji} {g.name}',
                    f'₹{float(g.target_amount):,.0f}',
                    f'₹{float(g.current_amount):,.0f}',
                    f'{pct}% {"✅" if g.completed else "🔄"}'
                ])
            gt = Table(goal_data, colWidths=[65*mm, 35*mm, 35*mm, 35*mm])
            gt.setStyle(TableStyle([
                ('BACKGROUND',   (0,0), (-1,0),  GREEN),
                ('TEXTCOLOR',    (0,0), (-1,0),  WHITE),
                ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
                ('FONTSIZE',     (0,0), (-1,-1), 10),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [CARD_BG, HexColor('#232a3a')]),
                ('TEXTCOLOR',    (0,1), (-1,-1), LIGHT),
                ('GRID',         (0,0), (-1,-1), 0.5, HexColor('#2d3748')),
                ('PADDING',      (0,0), (-1,-1), 8),
            ]))
            story.append(gt)

        # AI Insights
        story.append(Paragraph("💡 AI Financial Insights", h2_style))
        insights = []
        if health.get('factors'):
            insights.append(f"✅ Strengths: {', '.join(health['factors'])}")
        insights.append(f"💡 Tip: {health.get('suggestion', 'Keep tracking!')}")
        if cat_data:
            top_cat = max(cat_data, key=cat_data.get)
            insights.append(f"📊 Highest spend: {top_cat} at ₹{cat_data[top_cat]:,.0f} this month")
        for insight in insights:
            story.append(Paragraph(insight, body_style))

        # Footer
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=GRAY))
        story.append(Spacer(1, 5))
        story.append(Paragraph(
            f"Generated by FinWise AI · {today.strftime('%d %B %Y')} · Confidential",
            ParagraphStyle('footer', fontName='Helvetica', fontSize=9, textColor=GRAY, alignment=1)
        ))

        doc.build(story)
        buffer.seek(0)

        response_http = HttpResponse(buffer, content_type='application/pdf')
        response_http['Content-Disposition'] = f'attachment; filename="finwise-report-{today.strftime("%Y-%m")}.pdf"'

        # Award XP
        profile = get_or_create_profile(request.user)
        profile.add_xp(25)
        profile.add_badge('📄 Report Generator')
        profile.save()

        return response_http

    except ImportError:
        return HttpResponse("ReportLab not installed. Run: pip install reportlab", status=500)
    except Exception as e:
        return HttpResponse(f"PDF generation error: {str(e)}", status=500)

# ── Original AI Endpoints ─────────────────────────────────────────────────────

@login_required
def ai_forecast(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')[:90]
    if len(expenses) < 5:
        return JsonResponse({'success': False, 'message': 'Need at least 5 expenses'})
    category_totals = defaultdict(list)
    for exp in expenses:
        category_totals[exp.category].append(float(exp.amount))
    forecast = {cat: round((sum(amts) / len(expenses)) * 30, 2) for cat, amts in category_totals.items()}
    total_forecast = sum(forecast.values())
    recent = [e for e in expenses if e.date >= (datetime.now().date() - timedelta(days=30))]
    older  = [e for e in expenses if timedelta(days=60) >= (datetime.now().date() - e.date) >= timedelta(days=30)]
    recent_total = sum([float(e.amount) for e in recent])
    older_total  = sum([float(e.amount) for e in older]) or 1
    trend_pct = ((recent_total - older_total) / older_total) * 100
    if trend_pct > 15:   trend = "increasing significantly"
    elif trend_pct > 5:  trend = "slightly increasing"
    elif trend_pct < -15: trend = "decreasing significantly"
    elif trend_pct < -5: trend = "slightly decreasing"
    else:                trend = "stable"
    top_cat = max(forecast.items(), key=lambda x: x[1])
    return JsonResponse({'success': True, 'total_forecast': round(total_forecast, 2),
                         'category_forecast': forecast, 'trend': trend,
                         'trend_percentage': round(trend_pct, 2), 'top_category': top_cat[0]})

@login_required
def ai_anomalies(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')[:60]
    if len(expenses) < 10:
        return JsonResponse({'success': False, 'message': 'Need at least 10 expenses'})
    amounts = [float(e.amount) for e in expenses]
    mean = statistics.mean(amounts)
    try:
        stdev     = statistics.stdev(amounts)
        threshold = mean + (2 * stdev)
        anomalies = []
        for exp in expenses:
            if float(exp.amount) > threshold:
                pct = ((float(exp.amount) - mean) / mean) * 100
                anomalies.append({
                    'title': exp.title, 'amount': float(exp.amount),
                    'category': exp.category, 'date': exp.date.strftime('%b %d'),
                    'description': f'₹{exp.amount} is {pct:.0f}% higher than average'
                })
        return JsonResponse({'success': True, 'anomalies': anomalies[:5], 'total': len(anomalies)})
    except:
        return JsonResponse({'success': False, 'message': 'Not enough data'})

@login_required
def ai_advice(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')[:60]
    if len(expenses) < 5:
        return JsonResponse({'success': False, 'message': 'Need more expenses'})
    advice = []
    cat_totals = defaultdict(float)
    for exp in expenses:
        cat_totals[exp.category] += float(exp.amount)
    total = sum(cat_totals.values())
    if cat_totals:
        top_cat, top_amt = max(cat_totals.items(), key=lambda x: x[1])
        pct = (top_amt / total) * 100
        if pct > 40:
            advice.append({
                'icon': '💰', 'title': f'{top_cat} Spending Alert',
                'description': f'{top_cat} is {pct:.0f}% of spending. Reduce by 15% to save ₹{top_amt*0.15:.0f}/month.',
                'priority': 'high'
            })
    daily_avg = (total / 2) / 30
    advice.append({
        'icon': '📊', 'title': 'Daily Average',
        'description': f'You spend ₹{daily_avg:.0f}/day. Limit to ₹{daily_avg*0.85:.0f} to save ₹{(total/2)*0.15:.0f}/month.',
        'priority': 'medium'
    })
    return JsonResponse({'success': True, 'advice': advice, 'potential_savings': round(total * 0.12, 2)})

# ── Gamification ──────────────────────────────────────────────────────────────

@login_required
def gamification(request):
    profile = get_or_create_profile(request.user)
    badges  = profile.get_badges()
    all_possible_badges = [
        ('🌱 First Step',      'Log your first expense'),
        ('📊 Data Driven',     'Log 10 expenses'),
        ('💼 Pro Tracker',     'Log 50 expenses'),
        ('🏆 Century Club',    'Log 100 expenses'),
        ('🔥 3-Day Streak',    '3 days in a row'),
        ('⚡ Week Warrior',    '7-day streak'),
        ('💎 Month Master',    '30-day streak'),
        ('⭐ Level Up',        'Reach 500 XP'),
        ('🚀 XP Hunter',       'Reach 2000 XP'),
        ('🎯 Goal Setter',     'Create a savings goal'),
        ('🏆 Goal Achiever',   'Complete a savings goal'),
        ('📄 Report Generator','Generate a PDF report'),
    ]
    return render(request, 'core/gamification.html', {
        'profile': profile,
        'badges': badges,
        'all_badges': all_possible_badges,
    })