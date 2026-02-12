from django.db import models
from django.contrib.auth.models import User
from datetime import date

class Expense(models.Model):
    CATEGORIES = [
        ('Food', 'Food'),
        ('Travel', 'Travel'),
        ('Bills', 'Bills'),
        ('Shopping', 'Shopping'),
        ('Health', 'Health'),
        ('Entertainment', 'Entertainment'),
        ('Education', 'Education'),
        ('Other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50, choices=CATEGORIES, default='Other')
    date = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)
    auto_categorized = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.title} - ₹{self.amount}"

class Budget(models.Model):
    CATEGORIES = [
        ('Food', 'Food'),
        ('Travel', 'Travel'),
        ('Bills', 'Bills'),
        ('Shopping', 'Shopping'),
        ('Health', 'Health'),
        ('Entertainment', 'Entertainment'),
        ('Education', 'Education'),
        ('Other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=50, choices=CATEGORIES)
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'category']
    
    def __str__(self):
        return f"{self.user.username} - {self.category}: ₹{self.monthly_limit}"

class SavingsGoal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=10, default='🎯')
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    monthly_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    target_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def progress_percentage(self):
        if self.target_amount > 0:
            return min(int((self.current_amount / self.target_amount) * 100), 100)
        return 0
    
    def remaining_amount(self):
        return max(self.target_amount - self.current_amount, 0)
    
    def __str__(self):
        return f"{self.name} - ₹{self.current_amount}/₹{self.target_amount}"
