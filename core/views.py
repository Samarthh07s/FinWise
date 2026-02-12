from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.http import JsonResponse
from .models import Expense, SavingsGoal, Budget
from .forms import RegisterForm, LoginForm, ExpenseForm, SavingsGoalForm, AddMoneyForm
from collections import defaultdict
from datetime import datetime, timedelta, date
import statistics

# AI Auto-Categorization Function
def ai_categorize_expense(title):
    """AI-powered expense categorization based on keywords"""
    title_lower = title.lower()
    
    food_keywords = ['food', 'restaurant', 'cafe', 'coffee', 'pizza', 'burger', 'lunch', 'dinner', 
                     'breakfast', 'meal', 'snack', 'grocery', 'vegetables', 'fruits', 'milk',
                     'swiggy', 'zomato', 'dominos', 'mcdonalds', 'kfc', 'subway']
    
    travel_keywords = ['uber', 'ola', 'taxi', 'bus', 'train', 'flight', 'petrol', 'fuel', 
                       'metro', 'auto', 'rickshaw', 'cab', 'parking', 'toll']
    
    bills_keywords = ['electricity', 'water', 'gas', 'internet', 'wifi', 'phone', 'mobile',
                      'recharge', 'bill', 'rent', 'emi', 'insurance', 'subscription']
    
    shopping_keywords = ['amazon', 'flipkart', 'myntra', 'shopping', 'clothes', 'shirt', 'shoes',
                         'electronics', 'gadget', 'phone', 'laptop', 'watch', 'bag']
    
    health_keywords = ['medicine', 'doctor', 'hospital', 'clinic', 'pharmacy', 'medical',
                       'health', 'gym', 'fitness', 'yoga', 'checkup']
    
    entertainment_keywords = ['movie', 'cinema', 'netflix', 'prime', 'spotify', 'game',
                              'concert', 'party', 'club', 'bar', 'pub', 'entertainment']
    
    education_keywords = ['book', 'course', 'class', 'tuition', 'education', 'school',
                          'college', 'university', 'training', 'workshop', 'seminar']
    
    if any(keyword in title_lower for keyword in food_keywords):
        return 'Food'
    elif any(keyword in title_lower for keyword in travel_keywords):
        return 'Travel'
    elif any(keyword in title_lower for keyword in bills_keywords):
        return 'Bills'
    elif any(keyword in title_lower for keyword in shopping_keywords):
        return 'Shopping'
    elif any(keyword in title_lower for keyword in health_keywords):
        return 'Health'
    elif any(keyword in title_lower for keyword in entertainment_keywords):
        return 'Entertainment'
    elif any(keyword in title_lower for keyword in education_keywords):
        return 'Education'
    else:
        return 'Other'

# Basic Views
def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Account created successfully! Please log in.')
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
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                auth_login(request, user)
                messages.success(request, f'Welcome back, {username}!')
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

# Dashboard with AI Features
@login_required
def dashboard(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            
            # AI Auto-categorization
            if expense.category == 'Other':
                ai_category = ai_categorize_expense(expense.title)
                expense.category = ai_category
                expense.auto_categorized = True
            
            expense.save()
            
            if expense.auto_categorized:
                messages.success(request, f'✨ Expense added and auto-categorized as {expense.category}!')
            else:
                messages.success(request, 'Expense added successfully!')
            
            return redirect('dashboard')
    else:
        form = ExpenseForm()
    
    expenses = Expense.objects.filter(user=request.user)
    total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    
    category_data = {}
    for exp in expenses:
        category_data[exp.category] = category_data.get(exp.category, 0) + float(exp.amount)
    
    goals = SavingsGoal.objects.filter(user=request.user)[:3]
    total_saved = sum([g.current_amount for g in goals])
    
    # AI Features
    daily_summary = generate_daily_summary(request.user)
    budget_warnings = generate_budget_warnings(request.user)
    monthly_story = generate_monthly_story(request.user)
    health_score = calculate_health_score(request.user)
    
    context = {
        'form': form,
        'expenses': expenses[:10],
        'total': total,
        'expense_count': expenses.count(),
        'category_count': len(category_data),
        'category_data': category_data,
        'goals': goals,
        'total_saved': total_saved,
        'daily_summary': daily_summary,
        'budget_warnings': budget_warnings,
        'monthly_story': monthly_story,
        'health_score': health_score,
    }
    return render(request, 'core/dashboard.html', context)

# Expense Management
@login_required
def delete_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)
    expense.delete()
    messages.success(request, 'Expense deleted!')
    return redirect('dashboard')

# Savings Goals
@login_required
def savings_goals(request):
    if request.method == 'POST' and 'create_goal' in request.POST:
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f'Goal "{goal.name}" created!')
            return redirect('savings_goals')
    else:
        form = SavingsGoalForm()
    
    goals = SavingsGoal.objects.filter(user=request.user)
    return render(request, 'core/savings_goals.html', {
        'form': form,
        'goals': goals,
        'add_money_form': AddMoneyForm(),
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
                messages.success(request, f'🎉 Goal "{goal.name}" completed!')
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

# AI Analytics APIs
@login_required
def ai_forecast(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')[:90]
    
    if len(expenses) < 5:
        return JsonResponse({'success': False, 'message': 'Need at least 5 expenses'})
    
    category_totals = defaultdict(list)
    for exp in expenses:
        category_totals[exp.category].append(float(exp.amount))
    
    forecast = {}
    for cat, amounts in category_totals.items():
        forecast[cat] = round((sum(amounts) / len(expenses)) * 30, 2)
    
    total_forecast = sum(forecast.values())
    
    recent = [e for e in expenses if e.date >= (datetime.now().date() - timedelta(days=30))]
    older = [e for e in expenses if timedelta(days=60) >= (datetime.now().date() - e.date) >= timedelta(days=30)]
    
    recent_total = sum([float(e.amount) for e in recent])
    older_total = sum([float(e.amount) for e in older]) or 1
    trend_pct = ((recent_total - older_total) / older_total) * 100
    
    if trend_pct > 15:
        trend = "increasing significantly"
    elif trend_pct > 5:
        trend = "slightly increasing"
    elif trend_pct < -15:
        trend = "decreasing significantly"
    elif trend_pct < -5:
        trend = "slightly decreasing"
    else:
        trend = "stable"
    
    top_cat = max(forecast.items(), key=lambda x: x[1])
    
    return JsonResponse({
        'success': True,
        'total_forecast': round(total_forecast, 2),
        'category_forecast': forecast,
        'trend': trend,
        'trend_percentage': round(trend_pct, 2),
        'top_category': top_cat[0],
    })

@login_required
def ai_anomalies(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')[:60]
    
    if len(expenses) < 10:
        return JsonResponse({'success': False, 'message': 'Need at least 10 expenses'})
    
    amounts = [float(e.amount) for e in expenses]
    mean = statistics.mean(amounts)
    
    try:
        stdev = statistics.stdev(amounts)
        threshold = mean + (2 * stdev)
        anomalies = []
        
        for exp in expenses:
            if float(exp.amount) > threshold:
                pct = ((float(exp.amount) - mean) / mean) * 100
                anomalies.append({
                    'title': exp.title,
                    'amount': float(exp.amount),
                    'category': exp.category,
                    'date': exp.date.strftime('%b %d'),
                    'description': f'₹{exp.amount} is {pct:.0f}% higher than average'
                })
        
        return JsonResponse({
            'success': True,
            'anomalies': anomalies[:5],
            'total': len(anomalies)
        })
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
            savings = top_amt * 0.15
            advice.append({
                'icon': '💰',
                'title': f'{top_cat} Spending Alert',
                'description': f'{top_cat} is {pct:.0f}% of spending. Reduce by 15% to save ₹{savings:.0f}/month.',
                'priority': 'high'
            })
    
    daily_avg = (total / 2) / 30
    advice.append({
        'icon': '📊',
        'title': 'Daily Average',
        'description': f'You spend ₹{daily_avg:.0f}/day. Limit to ₹{daily_avg*0.85:.0f} to save ₹{(total/2)*0.15:.0f}/month.',
        'priority': 'medium'
    })
    
    return JsonResponse({
        'success': True,
        'advice': advice,
        'potential_savings': round(total * 0.12, 2)
    })

# AI Feature Functions
def generate_daily_summary(user):
    """Generate daily AI summary"""
    yesterday = date.today() - timedelta(days=1)
    yesterday_expenses = Expense.objects.filter(user=user, date=yesterday)
    yesterday_total = float(yesterday_expenses.aggregate(Sum('amount'))['amount__sum'] or 0)
    
    thirty_days_ago = date.today() - timedelta(days=30)
    last_month = Expense.objects.filter(user=user, date__gte=thirty_days_ago, date__lt=date.today())
    total_last_month = float(last_month.aggregate(Sum('amount'))['amount__sum'] or 0)
    days_count = max((date.today() - thirty_days_ago).days, 1)
    avg_daily = total_last_month / days_count
    
    if yesterday_total == 0:
        return {
            'icon': '🌟',
            'message': 'No expenses yesterday! Great job staying budget-conscious.',
            'comparison': 'zero_spending'
        }
    elif yesterday_total < avg_daily * 0.7:
        return {
            'icon': '🎉',
            'message': f'Yesterday you spent ₹{yesterday_total:.0f}, much lower than your usual ₹{avg_daily:.0f}. Excellent!',
            'comparison': 'much_lower'
        }
    elif yesterday_total < avg_daily:
        return {
            'icon': '✅',
            'message': f'Yesterday you spent ₹{yesterday_total:.0f}, lower than your usual ₹{avg_daily:.0f}. Doing well!',
            'comparison': 'lower'
        }
    elif yesterday_total > avg_daily * 1.3:
        return {
            'icon': '⚠️',
            'message': f'Yesterday you spent ₹{yesterday_total:.0f}, higher than usual ₹{avg_daily:.0f}. Review expenses.',
            'comparison': 'much_higher'
        }
    else:
        return {
            'icon': '📊',
            'message': f'Yesterday you spent ₹{yesterday_total:.0f}, close to average ₹{avg_daily:.0f}. Consistent!',
            'comparison': 'average'
        }

def generate_budget_warnings(user):
    """Generate soft budget warnings"""
    warnings = []
    budgets = Budget.objects.filter(user=user)
    
    if not budgets.exists():
        return []
    
    today = date.today()
    month_start = today.replace(day=1)
    
    for budget in budgets:
        spent = float(Expense.objects.filter(
            user=user,
            category=budget.category,
            date__gte=month_start,
            date__lte=today
        ).aggregate(Sum('amount'))['amount__sum'] or 0)
        monthly_limit = float(budget.monthly_limit)

        percentage = (spent / monthly_limit) * 100 if monthly_limit > 0 else 0
        
        if 75 <= percentage < 85:
            warnings.append({
                'icon': '💡',
                'category': budget.category,
                'percentage': int(percentage),
                'message': f'Used {int(percentage)}% of {budget.category} budget. Small adjustment helps.',
                'level': 'info'
            })
        elif 85 <= percentage < 95:
            warnings.append({
                'icon': '⚠️',
                'category': budget.category,
                'percentage': int(percentage),
                'message': f'Used {int(percentage)}% of {budget.category} budget. Consider slowing down.',
                'level': 'warning'
            })
        elif percentage >= 95:
            warnings.append({
                'icon': '🔴',
                'category': budget.category,
                'percentage': int(percentage),
                'message': f'Reached {int(percentage)}% of {budget.category} budget. Be extra careful.',
                'level': 'critical'
            })
    
    return warnings

def generate_monthly_story(user):
    """Generate monthly financial story"""
    today = date.today()
    days_in_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    is_month_end = today.day >= days_in_month.day - 4
    
    month_start = today.replace(day=1)
    month_expenses = Expense.objects.filter(user=user, date__gte=month_start, date__lte=today)
    
    if not month_expenses.exists():
        return None
    
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_expenses = Expense.objects.filter(user=user, date__gte=prev_month_start, date__lte=prev_month_end)
    
    curr_month_total = month_expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    prev_month_total = prev_expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    
    curr_cat_totals = {}
    for exp in month_expenses:
        curr_cat_totals[exp.category] = curr_cat_totals.get(exp.category, 0) + float(exp.amount)
    
    prev_cat_totals = {}
    for exp in prev_expenses:
        prev_cat_totals[exp.category] = prev_cat_totals.get(exp.category, 0) + float(exp.amount)
    
    improved = []
    worsened = []
    
    for category in curr_cat_totals:
        curr_amt = curr_cat_totals[category]
        prev_amt = prev_cat_totals.get(category, 0)
        
        if prev_amt > 0:
            change_pct = ((curr_amt - prev_amt) / prev_amt) * 100
            if change_pct < -10:
                improved.append(category)
            elif change_pct > 10:
                worsened.append(category)
    
    goals = SavingsGoal.objects.filter(user=user)
    total_saved = sum([g.current_amount for g in goals])
    
    month_name = today.strftime('%B')
    
    story_parts = []
    
    if total_saved > 0:
        story_parts.append(f'you have saved ₹{total_saved:.0f} in your goals')
    
    if curr_month_total < prev_month_total:
        reduction = prev_month_total - curr_month_total
        story_parts.append(f'reduced spending by ₹{reduction:.0f}')
    
    if improved:
        story_parts.append(f'{", ".join(improved)} spending improved')
    
    if worsened:
        story_parts.append(f'{", ".join(worsened)} costs increased slightly')
    
    if story_parts:
        story = f'In {month_name}, ' + ', while '.join(story_parts) + '.'
    else:
        story = f'In {month_name}, you spent ₹{curr_month_total:.0f}. Keep tracking!'
    
    return {
        'month': month_name,
        'story': story,
        'is_month_end': is_month_end,
        'total_spent': curr_month_total,
        'total_saved': total_saved,
    }

def calculate_health_score(user):
    """Calculate financial health score"""
    score = 0
    factors = []
    suggestions = []
    
    expenses = Expense.objects.filter(user=user)
    goals = SavingsGoal.objects.filter(user=user)
    
    if not expenses.exists():
        return {
            'score': 0,
            'grade': 'N/A',
            'emoji': '📊',
            'message': 'Add expenses to calculate score',
            'factors': [],
            'suggestion': 'Start tracking expenses!'
        }
    
    total_saved = float(sum(g.current_amount for g in goals))
    last_month_expenses = expenses.filter(date__gte=date.today()-timedelta(days=30))
    last_month_total = float(last_month_expenses.aggregate(Sum('amount'))['amount__sum'] or 1)
    savings_base = total_saved + last_month_total

    savings_rate = (total_saved / savings_base) * 100 if total_saved > 0 and savings_base > 0 else 0
    
    if savings_rate >= 20:
        score += 30
        factors.append('Excellent savings')
    elif savings_rate >= 10:
        score += 20
        factors.append('Good savings')
    elif savings_rate > 0:
        score += 10
        factors.append('Some savings')
    else:
        suggestions.append('Start saving! Even ₹100/month helps.')
    
    budgets = Budget.objects.filter(user=user)
    if budgets.exists():
        score += 25
        factors.append('Budgets set')
    else:
        score += 10
        suggestions.append('Set budgets to improve control.')
    
    if len(expenses) >= 7:
        amounts = [float(e.amount) for e in expenses[:30]]
        try:
            std_dev = statistics.stdev(amounts)
            mean_amt = statistics.mean(amounts)
            cv = (std_dev / mean_amt) * 100 if mean_amt > 0 else 100
            
            if cv < 50:
                score += 25
                factors.append('Consistent spending')
            elif cv < 100:
                score += 15
                factors.append('Fair consistency')
            else:
                score += 5
        except:
            score += 10
    
    category_counts = expenses.values('category').annotate(count=Count('id'))
    if len(category_counts) >= 3:
        score += 20
        factors.append('Diversified expenses')
    elif len(category_counts) >= 2:
        score += 10
    
    if score >= 80:
        grade = 'A'
        emoji = '🌟'
    elif score >= 60:
        grade = 'B'
        emoji = '✅'
    elif score >= 40:
        grade = 'C'
        emoji = '📊'
    else:
        grade = 'D'
        emoji = '⚠️'
    
    if not suggestions:
        if savings_rate < 15:
            suggestions.append('Increase savings rate to 15-20%.')
        else:
            suggestions.append('Great job! Keep it up.')
    
    return {
        'score': score,
        'grade': grade,
        'emoji': emoji,
        'message': f'Financial Health: {score}/100',
        'factors': factors,
        'suggestion': suggestions[0] if suggestions else 'Keep going!'
    }
