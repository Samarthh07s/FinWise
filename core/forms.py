from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Expense, SavingsGoal, Budget

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'amount', 'category', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ['name', 'emoji', 'target_amount', 'monthly_contribution', 'target_date']
        widgets = {
            'target_date': forms.DateInput(attrs={'type': 'date'}),
        }

class AddMoneyForm(forms.Form):
    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'monthly_limit']
