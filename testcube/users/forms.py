from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from testcube.utils import get_domain


class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2',)

    def __init__(self, *args, **kwargs):
        super(UserCreationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'autofocus': True})
        self.fields['email'].widget.attrs.update({'data-text': get_domain()})

        for name in ['username', 'password1', 'password2']:
            self.fields[name].help_text = ''


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['readonly'] = True

        for name in ['username', ]:
            self.fields[name].help_text = ''


class ResetPasswordForm(forms.ModelForm):
    reset_user = forms.CharField(label='Username or Email', max_length=100)
    password1 = forms.CharField(label='New Password', max_length=100, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password Confirm', max_length=100, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['readonly'] = True

        for name in ['username', ]:
            self.fields[name].help_text = 'Your user name will be recorded when reset password for others.'
            self.fields[name].label = 'Operator'
