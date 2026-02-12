from django.contrib import admin
from .models import Expense, SavingsGoal, Budget

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'amount', 'category', 'date', 'auto_categorized']
    list_filter = ['category', 'date', 'auto_categorized']

@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'current_amount', 'target_amount', 'completed']

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'monthly_limit', 'created_at']
    list_filter = ['category']
