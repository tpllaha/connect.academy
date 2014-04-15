# Shortcuts
from django.core.context_processors import csrf
from django.shortcuts import render, redirect, get_object_or_404, render_to_response
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.template import RequestContext
from app.helpers import *
import hashlib
import string
import random

# Mimetypes for images
from mimetypes import guess_type

# App Models
from app.models import *
from app.course_info import *
from app.context_processor import *
from app.auth.forms import *
from app.campusnet_login import *

def login_action(request):
    context = {}
    if request.method != 'POST':
        raise Http404

    form = LoginForm(request.POST)
    if not form.is_valid():
        raise Http404
    
    #login_user is the username OR email of the user attempting login.
    login_user = form.cleaned_data['username']
    login_pass = form.cleaned_data['password']
    
    # Using jUserBackend, which also tries to find a match for the email address.
    user=authenticate(username = login_user,password=login_pass)
    if user is not None:
        # Found user
        login(request,user)
        context['user_auth']= user 
        return redirect("/home")
    
    
    if not login_success(login_user, login_pass):
        #user not found neither on our database nor on campusnet
        context['error'] = "The <b>username/email</b> or <b>password</b> is incorrect. Please try again.<br/>"
        context['error'] += "If you don't have an account, you may be able to register below.<br/>"
        
        return render(request, "pages/welcome_page.html", context)
    else:
        # campusnet confirmed
        users = jUser.objects.filter(username=login_user).count()
        if users == 0:
            # Jacobs University user
            jacobs = University.objects.filter(domains__name="jacobs-university.de")[0] 
            user = jUser.objects.create_user(username=login_user, password=login_pass, university=jacobs)
            user.is_active = False # Account inactive until confirmed
            user.save()

    user = authenticate(username=login_user, password=login_pass)
    
    if user is not None:
        login(request, user)
        context['user_auth']=user
        return redirect("home")
        
    else:
        context['error'] = "The <b>username/email</b> or <b>password</b> is incorrect. Please try again.<br/>"
        context['error'] += "If you don't have an account, you may be able to register below.<br/>"
        return render(request, "pages/welcome_page.html", context)
    
    raise Http404


@login_required
def logout_action(request):
    if request.user:
        user = request.user
    logout(request)
    return redirect('/')

# Sends a confirmation e-mail to the user currently logged in (if e-mail is available)
@login_required
def send_confirmation(request):
    context = {
        "page": "send_confirmation",
    }
    context.update(csrf(request))
    context["user_auth"] = user_authenticated(request)
    
    user = request.user
    
    if user.email and len(user.email) > 0:
        # The user already has an e-mail address
            
        send_email_confirmation(user,request.get_host())
        return redirect("/home")
    else:
        # We don't have the user's e-mail address.
        if request.method == "POST" and request.POST["email"]:
            # The e-mail address is posted
            if jUser.objects.filter(email=request.POST["email"]).count() > 0:
                context["error"] = "A user with that <b>e-mail address</b> already exists."
                return render(request, "pages/send_confirmation.html", context)

            form = EmailConfirmationForm(request.POST)
            if not form.is_valid():
                raise Http404

            email = form.cleaned_data["email"]
            emailID, domain = email.split('@')
            universities = University.objects.filter(domains__name=domain)
            if len(universities) < 1: 
                # university not found
                context["error"] = "Sorry, we don't have any <b>university</b> with the domain of your <b>e-mail address</b>. <br/>"
                context["error"] += "Please check if you made any errors or come back soon.<br/>"
                return render(request,"pages/send_confirmation.html", context)
            else:
                # university found
                university = universities[0]
                # We recognize the university
                user = request.user
                user.university = university
                user.email = email
                user.save()
                send_email_confirmation(user,request.get_host())
                return redirect("/home")
        else: 
            # e-mail is not posted
            return render(request, "pages/send_confirmation.html", context)

    raise Http404 # Should never reach this line

# takes the username and the confirmation hash
def validate_user(request,username,confirmation):
    
    user = get_object_or_404(jUser, username = username)

    if not default_token_generator.check_token(user, confirmation):
        raise Http404

    user.is_active = True
    user.save()
  
    return redirect("/")

# If a user receives a confirmation e-mail, but they didn't sign up, they can delete their account by following
# the delete link. This is the view associated with the delete URL.
def delete_user(request,username,confirmation):
    context = {
        "page" : "delete"
    }
    user = get_object_or_404(jUser, username=username)
    if not default_token_generator.check_token(user, confirmation):
        raise Http404

    user.delete()
    context["success"] = "User successfully deleted. <br/>"
    return render(request,"pages/welcome_page.html", context)

def signup_action(request):
    context = context = {
        "page": "signup_action",
    }
    context.update(csrf(request))
    if request.method != 'POST':
        raise Http404

    form = SignupForm(request.POST)
    if not form.is_valid():
        raise Http404

    username = form.cleaned_data["username"]
    password = form.cleaned_data["password"]
    password_confirmation = form.cleaned_data["password_confirmation"]
    email = form.cleaned_data["email"]
    fname = form.cleaned_data["fname"]
    lname = form.cleaned_data["lname"]
    is_instructor = form.cleaned_data["is_instructor"]
    department_id = form.cleaned_data["department"]
    emailID, domain = email.split("@")

    if is_instructor:
        user_type = USER_TYPE_INSTRUCTOR
    else:
        user_type = USER_TYPE_STUDENT
           


    # Check if username or email exists
    users_same_name = jUser.objects.filter(username=username).count()
    users_same_email = jUser.objects.filter(email=email).count()
    error = False # No error
    if users_same_name > 0:
        context["error"] = "Sorry, that <b>username</b> is taken. Please try a different one. <br/>"
        error = True
    if users_same_email > 0:
        if "error" in context:
            context["error"] += "A user with that <b>e-mail address</b> already exists. If you already have an account, you can log in on the panel above.<br/>"
        else:
            context["error"] = "A user with that <b>e-mail address</b> already exists. If you already have an account, you can log in on the panel above.<br/>"

    if "error" in context:
        return render(request, "pages/welcome_page.html",context)

    # Check if we know the domain of the e-mail address
    universities = University.objects.filter(domains__name=domain)
    if len(universities) < 1: # not found
        context["error"] = "Sorry, we don't have a <b>university</b> with the domain of your <b>e-mail address</b>. Please check again soon.<br/>"
        return render(request,"pages/welcome_page.html", context)

    # university found
    university = universities[0]

    
    # create user
    
    if (password_confirmation == password): # passwords match

        user = jUser.objects.create_user(username=username, user_type=user_type ,password=password,email=email,university=university,
            first_name=fname, last_name=lname)
        
        if department_id:
            department = Department.objects.filter(id=department_id)[0]
            if department and len(department.name) > 0:
                department.save()
                user.departments.add(department)
                

        user.is_active = False
    
        #save new user
        user.save()       

        # Authenticate user
        auth_user = authenticate(username=username, password=password)
        if auth_user is not None:
            login(request, auth_user)
            # it needs to be request.user, not auth_user. 
            send_email_confirmation(request.user,request.get_host())
            context["user_auth"] = auth_user
            if 'login' in request.META.get('HTTP_REFERER'):
                return redirect('/')
            return redirect(request.META.get('HTTP_REFERER'))
    else: # passwords don't match
        if "error" in context:
            context["error"] += "Your <b>passwords</b> don't match. Please try again. <br/>"
        else:
            context["error"] = "Your <b>passwords</b> don't match. Please try again. <br/>"
            return render(request,"pages/welcome_page.html",context)
