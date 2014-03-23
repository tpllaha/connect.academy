
# Shortcuts
from django.core.context_processors import csrf
from django.shortcuts import render, redirect, get_object_or_404, render_to_response
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
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
from app.forms import *
from app.campusnet_login import *

@login_required
def home(request):
    context = {
        "page": "home",
        'user_auth': user_authenticated(request)
    }
    # Get courses
    courses = Course.objects.all()
    context = dict(context.items() + course_timeline_context(courses).items())
    return render(request, "pages/home.html", context)


@login_required
def course_page(request, slug):
    course = get_object_or_404(Course, slug=slug)
    context = {
        "page": "course",
        'user_auth': user_authenticated(request)
    }
    context = dict(context.items() + course_page_context(request, course).items())

    return render(request, "pages/course.html", context)


@login_required
def vote_course(request):

    context = {}
    if request.method != 'POST':
        raise Http404
    user = get_object_or_404(jUser, id=request.user.id)

    form = VoteCourseForm(request.POST)
    if not form.is_valid():
        raise Http404

    course = form.cleaned_data['course']
    rating_value = form.cleaned_data['rating_value']
    rating_type = form.cleaned_data['rating_type']

    if rating_type != PROFESSOR_R:
        ratings = Rating.objects.filter(user= user, course= course, rating_type= rating_type)
        if len(ratings) == 0:
            rating = Rating(user= user, course= course, rating= rating_value, rating_type= rating_type)
            rating.save()
        else:
            rating = ratings[0]
            rating.rating = rating_value
            rating.save()
    else:
        prof = form.cleaned_data['prof']
        ratings = Professor_Rating.objects.filter(user= user, course= course, rating_type= rating_type, prof=prof)
        if len(ratings) == 0:
            rating = Professor_Rating(user= user, course= course, rating= rating_value, rating_type= rating_type, prof=prof)
            rating.save()
        else:
            rating = ratings[0]
            rating.rating = rating_value
            rating.save()

    return redirect(form.cleaned_data['url'])


@login_required
def get_course_image(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not course.image:
        raise Http404

    content_type = guess_type(course.image.name)
    return HttpResponse(course.image, mimetype=content_type)


@login_required
def submit_comment(request):
    if request.method != 'POST':
        raise Http404

    form = SubmitCommentForm(request.POST)
    if not form.is_valid():
        raise Http404

    course = form.cleaned_data['course']

    comment_text = form.cleaned_data['comment']
    comment = Comment(course= course, comment= comment_text)
    comment.save()

    return redirect(form.cleaned_data['url'])


@login_required
def all_comments(request):
    context = {
        'page': 'all_comments',
        'user_auth': user_authenticated(request)
    }
    context['comments'] = Comment.objects.all()

    return render(request, 'pages/comments.html', context)


##### User authentication here on

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
            jacobs = University.objects.filter(domain="jacobs-university.de")[0] 
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
    seed = ''.join(random.choice(string.lowercase) for x in range(30))
    confirmation_hash = hashlib.sha224(seed).hexdigest()
    
    if request.user.email and len(request.user.email) > 0:
        # The user already has an e-mail address
        request.user.confirmation_hash = confirmation_hash
        request.user.save()
        confirmation_link = request.get_host() + "/confirmation/" + confirmation_hash
        send_email_confirmation(request.user,confirmation_link)
        return redirect("/home")
    else:
        # We don't have the user's e-mail address.
        if request.method == "POST" and request.POST["email"]:
            # The e-mail address is posted
            form = EmailConfirmationForm(request.POST)
            if not form.is_valid():
                raise Http404

            email = form.cleaned_data["email"]
            emailID, domain = email.split('@')
            universities = University.objects.filter(domain=domain)
            if len(universities) < 1: 
                # university not found
                context["error"] = "Sorry, we don't have any <b>university</b> with the domain of your <b>e-mail address</b>. <br/>"
                context["error"] += "Please check if you made any errors or come back soon.<br/>"
                return render(request,"pages/send_confirmation.html", context)
            else:
                # university found
                university = universities[0]
                # We recognize the university
                request.user.university = university
                request.user.email = email
                request.user.confirmation_hash = confirmation_hash
                request.user.save()
                confirmation_link = request.get_host() + "/confirmation/" + confirmation_hash
                send_email_confirmation(request.user,confirmation_link)
                return redirect("/home")
        else: 
            # e-mail is not posted
            return render(request, "pages/send_confirmation.html", context)

    raise Http404 # Should never reach this line

def validate_user(request,confirmation):


    user = get_object_or_404(jUser, confirmation_hash = confirmation)

    user.is_active = True
    user.confirmation_hash = ""  # don't need it anymore.
    user.save()
  
    return redirect("/")

# If a user receives a confirmation e-mail, but they didn't sign up, they can delete their account by following
# the delete link. This is the view associated with the delete URL.
def delete_user(request,confirmation):
    context = {
        "page" : "delete"
    }
    user = get_object_or_404(jUser, confirmation_hash = confirmation)
    user.delete()
    context["error"] = "User successfully deleted. <br/>" # using error for now, should probably change this.
    return render(request,"pages/welcome_page.html", context)

def welcome(request):
    context = {
        "page": "welcome",
    }
    if user_authenticated(request):
        context['user_auth'] = request.user
        return redirect('/home')

    return render(request,"pages/welcome_page.html",context)

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
    emailID, domain = email.split("@")

    # Check if username or email exists
    users_same_name = jUser.objects.filter(username=username).count()
    users_same_email = jUser.objects.filter(email=email).count()
    error = False # No error
    if users_same_name > 0:
        context["error"] = "Sorry, that <b>username</b> is taken. Please try a different one. <br/>"
        error = True
    if users_same_email > 0:
        if "error" in context:
            context["error"]+= "A user with that <b>e-mail address</b> already exists. If you already have an account, you can log in on the panel above.<br/>"
        else:
            context["error"] = "A user with that <b>e-mail address</b> already exists. If you already have an account, you can log in on the panel above.<br/>"

    if "error" in context:
        return render(request, "pages/welcome_page.html",context)

    # Check if we know the domain of the e-mail address
    universities = University.objects.filter(domain=domain)
    if len(universities) < 1: # not found
        context["error"] = "Sorry, we don't have a <b>university</b> with the domain of your <b>e-mail address</b>. Please check again soon.<br/>"
        return render(request,"pages/welcome_page.html", context)

    # university found
    university = universities[0]

    
    # create user
    seed = ''.join(random.choice(string.lowercase) for x in range(30))
    confirmation_hash = hashlib.sha224(seed).hexdigest()
    if (password_confirmation == password): # passwords match
        user = jUser.objects.create_user(username=username, password=password,email=email,university=university,
            first_name=fname, last_name=lname, confirmation_hash = confirmation_hash)
        user.is_active = False
        
        #### Send confirmation e-mail
        confirmation = request.get_host() + "/confirmation/" + confirmation_hash
        send_email_confirmation(user,confirmation)
        # Then save the user
        user.save()

        # Authenticate user
        auth_user = authenticate(username=username, password=password)
        if auth_user is not None:
            login(request, auth_user)
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
