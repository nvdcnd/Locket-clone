from django import forms
from django.contrib.auth.models import User
from .models import Bio

class LoginForm(forms.Form):
    email = forms.CharField(label="Email",widget=forms.EmailInput(attrs={'class':'form-control'}),max_length=1000)
    password = forms.CharField(label="Password",widget=forms.PasswordInput(attrs={'class':'form-control'}))

class UserRegistrationForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    image = forms.ImageField(required=False)
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)

"""
class BioForm(forms.ModelForm):
    user = User.objects.
    class Meta:
"""
