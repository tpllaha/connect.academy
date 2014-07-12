from django import forms
from django.template.defaultfilters import filesizeformat

from app.models import *



#The form required for submitting a create/change request to a course's Wiki
class WikiPageForm(forms.Form):
    title = forms.CharField(required=True)
    content = forms.CharField(required=False)
    
    def __init__(self,user,course,modified_on,*args,**kwargs):
        self.user = user
        self.course = course
        self.modified_on = modified_on
        super(WikiPageForm,self).__init__(*args,**kwargs)

    
    def clean(self):
        cleaned_data = super(WikiPageForm,self).clean()
        return cleaned_data
