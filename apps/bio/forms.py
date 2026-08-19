from django import forms
from django.contrib.auth.models import User
from .models import Bio

class LoginForm(forms.Form):
    email = forms.EmailField(label="Email",widget=forms.EmailInput(attrs={'class':'form-control'}),max_length=1000)
    password = forms.CharField(label="Password",widget=forms.PasswordInput(attrs={'class':'form-control'}))

class UserRegistrationForm(forms.Form):
    email = forms.EmailField(label="Email",widget=forms.EmailInput(attrs={'class':'form-control'}))
    username = forms.CharField(label="Username")
    image = forms.ImageField(label="Avatar")
    password = forms.CharField(label="Password",widget=forms.PasswordInput(attrs={'class':'form-control'}))
    '''
    fields = ['username', 'email', 'image', 'password']
    widgets = {
        'username': forms.CharField(),
        'email': forms.EmailField(),
        'image': forms.ImageField(),
        'password': forms.PasswordInput(attrs={'class':'form-control'}),
    }
    '''

"""
class BioForm(forms.ModelForm):
    user = User.objects.
    class Meta:
"""
