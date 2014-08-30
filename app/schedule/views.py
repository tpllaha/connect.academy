import json
import time
from datetime import * #datetime
import pytz
from helpers import *
from dateutil.parser import parse
from dateutil.tz import tzoffset

from django.shortcuts import render, redirect, get_object_or_404, render_to_response
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.views.decorators.http import require_GET, require_POST
from django.core.context_processors import csrf

from app.models import *

'''
################################# ADD GUARDS IF THE USER LEAVES THE START AND THE END BLANK ##############################################################
                                                        IN THE VIEWS BELOW 
'''


#date formatting
date_format = "%Y-%m-%dT%H:%M:%S.%f%z"

@login_required
def view_schedule(request):
    context = {
        'page': 'view_schedule'
    }

    # get the CourseAppointments of the courses the user is registered in
    
    # need to fix this too 
    user = get_object_or_404(jUser, id=request.user.id)
    
    courses_enrolled = user.courses_enrolled.all()

    course_appointments = []

    for course in courses_enrolled:
        course_appointments.append(course.appointments.all())

    # get user's PersonalAppointments
    personal_appointments = user.appointments.all()

    # list of JSON strings
    all_appointments = []

    # course appointments
    for cappointments in course_appointments:
        for appointment in cappointments:
            data = {}
            data['id'] = appointment.id
            data['start'] = format_date(appointment.start.strftime(date_format))
            data['end'] = format_date(appointment.end.strftime(date_format))
            if appointment.course_topic.name:
            	data['title'] = appointment.course_topic.name 
            else:
            	data['title']= appointment.location

            data['body'] = appointment.description
            
            all_appointments.append(data)

    for appointment in personal_appointments:
        data = {}
        data['id'] = appointment.id
        data['start'] = format_date(appointment.start.strftime(date_format))
        data['end'] = format_date(appointment.end.strftime(date_format))
        data['title'] = appointment.location
        data['body'] = appointment.description
        
        all_appointments.append(data)

    context['appointments'] = json.dumps(all_appointments)

    #need the largest id in the Appointment table.
    latest_id = 0
    try:
        latest_id = Appointment.objects.latest('id').id
    except Exception:
        pass

    context['latest_id'] = latest_id

    return render(request, "pages/schedule/view_schedule.html", context)


#both professors and students
@require_POST
def add_personal_appointment(request):
    context = {
        'page':'add_personal_appointment'
    }
    context.update(csrf(request))

    if request.is_ajax():
        user = jUser.objects.filter(username=request.user.username).get()
        description = request.POST['body']
        start_time = request.POST['start']
        end_time = request.POST['end']
        location = request.POST['title']
        
        start = parse(start_time) # from dateutil.parser
        end = parse(end_time)
        appointment = PersonalAppointment(start=start \
                                         ,end=end \
                                         ,location=location \
                                         ,description=description \
                                         ,user=user)
        appointment.save()
    else:
        raise Http404

    return redirect('/') # change this

@require_POST
def edit_personal_appointment(request):
    context = {
        'page':'edit_personal_appointment'
    }
    context.update(csrf(request))
    
    if request.is_ajax():
        id_to_edit = request.POST['id']
        new_description = request.POST['body']
        new_location = request.POST['title']
        new_start_time = request.POST['start']
        new_end_time = request.POST['end']

        start = parse(new_start_time)
        end = parse(new_end_time)
        
        appointment = Appointment.objects.filter(id=id_to_edit).get()
        
        appointment.description = new_description
        appointment.location = new_location
        appointment.start = start
        appointment.end = end
        appointment.save()
    else:
        raise Http404

    return redirect('/') #change this too.


@require_POST
def remove_personal_appointment(request):
    context = {
        'page':'remove_personal_appointment'
    }
    context.update(csrf(request))

    if request.is_ajax():
        id_to_delete = request.POST['id']
        Appointment.objects.filter(id=id_to_delete).delete()
    else:
        raise Http404

    return redirect('/') #change this












#only for professors
@require_POST
def add_course_appointment(request):
    context = {
        'page':'add_course_appointment'
    }

    context.update(csrf(request))

    if request.is_ajax():
        user = jUsers.objecs.filter(username=request.user.username).get()
        if user.is_professor():
            pass
        else:
            raise Http404
    else:
        pass

@require_POST
def remove_course_appointment(request):
	context = {
		'page':'remove_course_appointment'
	}
	pass

'''
    IDEA


        Suppose a user clicks on the schedule screen. 
            The user might be :
                1) Student
                2) Professor
                3) Admin (not relevant)
                4) Alumnus (not relevant)

        If the user is a student, a "add personal appointment" form is rendered.
        If the user is a professor, a screen which enables him to choose between adding
        a personal appointment or a course appointment is rendered.

        TODO(s):    
            * Add AJAX for finding out the type of the user upon the request to add
              appointment (make use of the existing ajax calls)

            * Define the new popup.

            * Decouple the JS from the html file 

            * Change the appointments 
            
'''